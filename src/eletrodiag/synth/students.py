"""Gerador de sessões SINTÉTICAS de estudantes (telemetria do app) para alimentar o pipeline.

ATENÇÃO: os números produzidos por este gerador vêm de comportamentos ASSUMIDOS (ver
docs/assumptions.md) e não de estudantes reais. Servem para validar a arquitetura de dados, o
motor de diagnóstico e o BI. Ao colocar o app em produção, a camada bronze `app_events` passa a
receber eventos reais com o mesmo esquema e nada além da fonte muda.

Projeto pareado: cada cenário de defeito é executado nos TRÊS modos (guiado, medição aleatória,
componente a componente), com o mesmo circuito defeituoso, isolando o efeito do método.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np

from ..diagnose import Diagnoser
from ..pipeline import config as C
from ..pipeline.parsing import BR_TZ
from ..sim.circuits import get_circuit, simulate

MEDIAN_S = {"V": 35.0, "I": 80.0, "component": 110.0}  # tempo mediano por passo (premissa)
P_GROSS_ERROR = {"iniciante": 0.06, "intermediario": 0.03}
P_DETECT = {"iniciante": 0.85, "intermediario": 0.92}  # componente defeituoso é reconhecido no teste
P_FALSE_POS = {"iniciante": 0.06, "intermediario": 0.03}  # componente bom condenado por engano
P_GIVEUP, P_NO_FINISH = 0.015, 0.01


def _h(*parts, n=12) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:n]


def _duration(rng, kind: str) -> float:
    return round(float(MEDIAN_S[kind] * np.exp(rng.normal(0, 0.4))), 1)


def _fmt_reading(v: float, kind: str, rng) -> tuple[str, str | None]:
    """Como o estudante digitaria a leitura: casas decimais do display, vírgula, unidade variável."""
    comma = rng.random() < 0.4
    if kind == "V":
        res = 0.01 if abs(v) >= 2 else 0.001
        r = round(v / res) * res
        dec = 2 if res == 0.01 else 3
        u = rng.random()
        if abs(v) < 1 and u < 0.15:
            txt, unit = f"{r * 1000:.0f}", "mV"
        else:
            txt = f"{r:.{dec}f}"
            unit = "V" if u < 0.7 else (None if u < 0.85 else "v")
            if u >= 0.85 and u < 0.95:
                txt, unit = txt + " V", None
    else:
        if abs(v) >= 1:
            txt, unit = f"{v:.2f}", "A"
        else:
            ma = v * 1000
            res = 0.01 if abs(ma) < 20 else (0.1 if abs(ma) < 200 else 1.0)
            r = round(ma / res) * res
            dec = 2 if res == 0.01 else (1 if res == 0.1 else 0)
            u = rng.random()
            if abs(v) < 1e-3 and u < 0.25:
                txt, unit = f"{v * 1e6:.0f}", "uA"
            else:
                txt = f"{r:.{dec}f}"
                unit = "mA" if u < 0.8 else (None if u < 0.9 else str(rng.choice(["MA", "ma"])))
    if comma:
        txt = txt.replace(".", ",")
    return txt, unit


def _ts_str(dt: datetime, rng) -> str:
    u = rng.random()
    if u < 0.70:
        return dt.astimezone(BR_TZ).isoformat(timespec="seconds")
    if u < 0.90:
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return dt.astimezone(BR_TZ).strftime("%d/%m/%Y %H:%M:%S")


def _read_with_noise(true_v: float, kind: str, rng) -> float:
    sd = max(0.003 * abs(true_v), 0.003) if kind == "V" else max(0.005 * abs(true_v), 2e-5)
    return true_v + rng.normal(0, sd)


def _gross_error(v: float, others: list[float], rng) -> float:
    u = rng.random()
    if u < 0.4:
        return -v  # ponteiras invertidas
    if u < 0.7:
        return v * 10.0  # erro de escala/ponto decimal
    return float(rng.choice(others)) if others else v * 0.1  # mediu no ponto errado


def generate(dictionary: dict, seed: int = C.SEED, n_scenarios: int = C.N_SCENARIOS,
             n_learners: int = C.N_LEARNERS, start: str = C.SESSIONS_START, days: int = C.SESSIONS_DAYS):
    rng = np.random.default_rng(seed + 1)
    mm = dictionary["meter_model"]
    learners = [{"id": _h("learner", i, seed), "level": "iniciante" if rng.random() < 0.65 else "intermediario",
                 "device": "mobile" if rng.random() < 0.75 else "desktop"} for i in range(n_learners)]
    t_start = datetime.fromisoformat(start).replace(tzinfo=BR_TZ)
    hour_w = np.array([1, 2, 3, 3, 3, 2, 2, 2, 3, 4, 5, 5, 4, 3, 2], dtype=float)  # 8h..22h
    hour_w /= hour_w.sum()
    by_week: dict[str, list[dict]] = {}
    truth: list[dict] = []

    for cdict in dictionary["circuits"]:
        circuit = get_circuit(cdict["id"])
        dg = Diagnoser(cdict, mm)
        for sc in range(n_scenarios):
            fi = int(rng.choice(len(dg.fault_ids), p=dg.prior))
            fid = dg.fault_ids[fi]
            comp_id, fmode = fid.split(":")
            for _ in range(20):
                values, sol = simulate(circuit, (comp_id, fmode), rng)
                if sol.converged:
                    break
            scenario_id = f"{cdict['id']}-{sc:04d}"
            for mode in C.MODES:
                learner = learners[int(rng.integers(len(learners)))]
                t0 = t_start + timedelta(days=int(rng.integers(days)), hours=8 + int(rng.choice(15, p=hour_w)),
                                         minutes=int(rng.integers(60)), seconds=int(rng.integers(60)))
                sid = "s-" + _h(scenario_id, mode, seed, n=14)
                evs, finish = _run_session(dg, circuit, values, comp_id, mode, learner, rng)
                records = _emit(sid, cdict["id"], mode, learner, t0, evs, finish, rng)
                iso = t0.isocalendar()
                by_week.setdefault(f"{iso.year}-W{iso.week:02d}", []).extend(records)
                truth.append({"session_id": sid, "scenario_id": scenario_id, "circuit_id": cdict["id"],
                              "true_fault": fid, "synthetic": True})
    return by_week, truth


# ----------------------------------------------------------------------------- políticas
def _run_session(dg: Diagnoser, circuit, values: dict, true_comp: str, mode: str, learner: dict, rng):
    level = learner["level"]
    steps: list[dict] = []
    outcome = replaced = stop_reason = None
    if mode == "componente_a_componente":
        order = [c.id for c in circuit.comps]
        rng.shuffle(order)
        found, abandoned = None, False
        for _pass in range(2):
            for cid in order:
                p = P_DETECT[level] if cid == true_comp else P_FALSE_POS[level]
                verdict = "defeituoso" if rng.random() < p else "ok"
                steps.append({"type": "component_tested", "component_id": cid, "verdict": verdict,
                              "duration_s": _duration(rng, "component")})
                if verdict == "defeituoso":
                    found = cid
                    break
                if rng.random() < P_GIVEUP / 3:
                    abandoned = True
                    break
            if found or abandoned:
                break
        replaced = found
        stop_reason = "componente_encontrado" if found else ("abandono" if abandoned else "sem_mais_componentes")
    else:
        taken: dict[str, float] = {}
        guided = mode == "guiado"
        remaining = list(dg.obs_ids)
        true_vals = {o: values[o] for o in dg.obs_ids}
        for step in range(1, len(dg.obs_ids) + 1):
            if guided:
                post = dg.posterior(taken) if taken else dg.prior
                oid = dg.rank_next(post, set(taken))[0]["observable_id"]
            else:
                oid = str(rng.choice([o for o in remaining if o not in taken]))
            kind = dg.obs_kind[dg.obs_ids.index(oid)]
            v = _read_with_noise(true_vals[oid], kind, rng)
            if rng.random() < P_GROSS_ERROR[level]:
                v = _gross_error(v, [true_vals[o] for o in dg.obs_ids if o != oid], rng)
            raw, unit = _fmt_reading(v, kind, rng)
            taken[oid] = _entered_value(raw, unit, kind)
            post = dg.posterior(taken)
            cp = dg.component_posterior(post)
            top = max(cp, key=cp.get)
            tf = max((i for i, c in enumerate(dg.comp_of) if c == top), key=lambda i: post[i])
            steps.append({"type": "measurement_taken", "observable_id": oid, "raw_value": raw, "unit_raw": unit,
                          "duration_s": _duration(rng, kind), "diag": {
                              "top_component": top, "top_fault": dg.fault_ids[tf], "top_prob": round(cp[top], 4)}})
            if step >= C.MIN_MEASUREMENTS and cp[top] >= C.CONFIDENCE_STOP:
                replaced, stop_reason = top, "confianca"
                break
            if step >= 3 and rng.random() < P_GIVEUP:
                stop_reason = "abandono"
                break
        else:
            replaced, stop_reason = top, "sem_mais_medicoes"
        if stop_reason == "abandono":
            replaced = None
    if stop_reason == "abandono" or replaced is None:
        outcome, replaced = "desistiu", None
    else:
        outcome = "reparado" if replaced == true_comp else "troca_errada"
    no_finish = rng.random() < P_NO_FINISH
    return steps, None if no_finish else {"outcome": outcome, "replaced_component": replaced,
                                           "stop_reason": stop_reason}


def _entered_value(raw: str, unit: str | None, kind: str) -> float:
    """Valor que o app usa na hora (mesma regra de parsing da silver, mas sem rejeitar)."""
    from ..pipeline.parsing import parse_measurement
    val, _, why = parse_measurement(raw, unit, kind)
    if val is None:  # o app valida o campo na digitação; aqui nunca ocorre
        raise ValueError(f"leitura inválida gerada: {raw!r} {unit!r} ({why})")
    return val


def _emit(sid, circuit_id, mode, learner, t0, steps, finish, rng) -> list[dict]:
    ver = "0.1.0" if rng.random() < 0.85 else "0.1.1"
    base = {"session_id": sid, "learner_id": learner["id"], "app_version": ver}
    out: list[dict] = []
    t = t0

    def add(etype, payload, when):
        out.append({"event_id": _h(sid, len(out), n=16), "event_type": etype, "ts": _ts_str(when, rng),
                    **base, "payload": payload})

    add("session_started", {"circuit_id": circuit_id, "mode": mode, "level": learner["level"],
                            "device": learner["device"]}, t)
    for i, st in enumerate(steps, 1):
        t = t + timedelta(seconds=st["duration_s"])
        if st["type"] == "measurement_taken":
            add("measurement_taken", {"step": i, "observable_id": st["observable_id"], "raw_value": st["raw_value"],
                                      "unit_raw": st["unit_raw"], "duration_s": st["duration_s"]}, t)
            add("diagnosis_shown", {"step": i, **st["diag"]}, t + timedelta(seconds=1))
        else:
            add("component_tested", {"step": i, "component_id": st["component_id"], "verdict": st["verdict"],
                                     "duration_s": st["duration_s"]}, t)
    if finish:
        add("session_finished", {**finish, "n_steps": len(steps)}, t + timedelta(seconds=30))
    return out

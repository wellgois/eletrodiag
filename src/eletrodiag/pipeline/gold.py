"""Camada GOLD: modelo dimensional pronto para BI + dicionário de falhas que alimenta o app.

Duas etapas, porque o app precisa do dicionário ANTES de gerar telemetria:
  1) build_dictionary  : silver.sim_runs  -> fct_fault_signature, fct_fault_pair_separability, dictionary.json
  2) build_analytics   : silver.sessions/... -> fct_session, fct_session_step, agg_* (KPIs de eficiência)
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..diagnose import DEFAULT_METER_MODEL, Diagnoser
from . import config as C
from . import silver
from .quality import DQ

SEPARABLE = 3.0  # distância de Bhattacharyya total mínima p/ considerar duas hipóteses distinguíveis


def _write(df: pd.DataFrame, name: str) -> None:
    C.GOLD.mkdir(parents=True, exist_ok=True)
    df.to_parquet(C.GOLD / f"{name}.parquet", index=False)


def read(name: str) -> pd.DataFrame:
    return pd.read_parquet(C.GOLD / f"{name}.parquet")


# ============================================================================ etapa 1: dicionário
def build_dictionary(run_id: str, dq: DQ) -> dict:
    sims = silver.read("sim_runs")
    g = sims.groupby(["circuit_id", "fault_id", "observable_id"])["value"]
    sig = g.agg(mean="mean", std="std", min="min", max="max", n="size").reset_index()
    q = g.quantile([0.05, 0.95]).unstack().reset_index().rename(columns={0.05: "p05", 0.95: "p95"})
    sig = sig.merge(q, on=["circuit_id", "fault_id", "observable_id"])
    sig["std"] = sig["std"].fillna(0.0)
    dq.check("gold", "fct_fault_signature", "enough_samples_per_signature", len(sig), int((sig.n < C.MIN_SIGNATURE_SAMPLES).sum()))
    dq.check("gold", "fct_fault_signature", "no_null_stats", len(sig), int(sig[["mean", "std"]].isna().any(axis=1).sum()))
    _write(sig, "fct_fault_signature")

    for name in ("dim_circuit", "dim_component", "dim_observable", "dim_fault"):
        _write(silver.read(name), name)

    dictionary = _dictionary_json(sig)
    out = C.GOLD / "app"
    out.mkdir(parents=True, exist_ok=True)
    (out / "dictionary.json").write_text(json.dumps(dictionary, ensure_ascii=False, separators=(",", ":")))

    sep = _separability(dictionary)
    dq.check("gold", "fct_fault_pair_separability", "has_pairs", 1, int(len(sep) == 0))
    _write(sep, "fct_fault_pair_separability")
    return dictionary


def _dictionary_json(sig: pd.DataFrame) -> dict:
    circ, comp, obs, flt = (silver.read(n) for n in ("dim_circuit", "dim_component", "dim_observable", "dim_fault"))
    stats = {(r.circuit_id, r.fault_id, r.observable_id): [r.mean, r.std] for r in sig.itertuples()}
    circuits = []
    for c in circ.itertuples():
        obs_c = obs[obs.circuit_id == c.circuit_id]
        faults = []
        for f in flt[flt.circuit_id == c.circuit_id].itertuples():
            faults.append({
                "id": f.fault_id, "component": f.component_id, "mode": f.mode, "prior": f.prior,
                "descricao": f.descricao, "teste_confirmacao": f.teste_confirmacao, "acao": f.acao,
                "signature": {o: [round(stats[(c.circuit_id, f.fault_id, o)][0], 9),
                                  round(stats[(c.circuit_id, f.fault_id, o)][1], 9)] for o in obs_c.observable_id},
            })
        circuits.append({
            "id": c.circuit_id, "nome": c.nome, "descricao": c.descricao, "nivel": c.nivel, "svg": c.svg,
            "hazard": c.hazard, "nota": c.nota,
            "components": [{"id": x.component_id, "kind": x.kind, "nominal": x.nominal, "funcao": x.funcao}
                           for x in comp[comp.circuit_id == c.circuit_id].itertuples()],
            "observables": [{"id": x.observable_id, "kind": x.kind, "ref": x.ref, "label": x.label,
                             "onde": x.onde, "unit": x.unit, "cost": x.cost} for x in obs_c.itertuples()],
            "baseline": {o: [round(v, 9) for v in stats[(c.circuit_id, "OK", o)]] for o in obs_c.observable_id},
            "faults": faults,
        })
    body = {"meter_model": DEFAULT_METER_MODEL, "confidence_stop": C.CONFIDENCE_STOP,
            "min_measurements": C.MIN_MEASUREMENTS, "circuits": circuits}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    return {"version": digest, "generated_at": datetime.now(timezone.utc).isoformat(),
            "sim_version": C.SIM_VERSION, **body}


def _separability(dictionary: dict) -> pd.DataFrame:
    rows = []
    for c in dictionary["circuits"]:
        dg = Diagnoser(c, dictionary["meter_model"])
        d_v, d_all = dg.separability(("V",)), dg.separability(("V", "I"))
        n = len(dg.faults)
        for i in range(n):
            for j in range(i + 1, n):
                same = dg.comp_of[i] == dg.comp_of[j]
                if same:
                    cls = "mesmo_componente"
                elif d_v[i, j] >= SEPARABLE:
                    cls = "distinguivel_por_tensao"
                elif d_all[i, j] >= SEPARABLE:
                    cls = "requer_corrente"
                else:
                    cls = "indistinguivel_eletricamente"
                rows.append({"circuit_id": c["id"], "fault_a": dg.fault_ids[i], "fault_b": dg.fault_ids[j],
                             "component_a": dg.comp_of[i], "component_b": dg.comp_of[j],
                             "dist_voltage": float(d_v[i, j]), "dist_all": float(d_all[i, j]), "class": cls})
    return pd.DataFrame(rows)


# ============================================================================ etapa 2: analítico
def _dim_date(dates: pd.Series) -> pd.DataFrame:
    rng = pd.date_range(dates.min(), dates.max(), freq="D")
    return pd.DataFrame({
        "date_id": rng.strftime("%Y%m%d").astype(int), "date": rng.date, "year": rng.year, "month": rng.month,
        "day": rng.day, "iso_week": rng.isocalendar().week.astype(int).values,
        "weekday": rng.day_name().str.lower(), "is_weekend": rng.dayofweek >= 5})


def build_analytics(run_id: str, dq: DQ) -> None:
    dictionary = json.loads((C.GOLD / "app" / "dictionary.json").read_text())
    dgs = {c["id"]: Diagnoser(c, dictionary["meter_model"]) for c in dictionary["circuits"]}

    sess = silver.read("sessions")
    meas = silver.read("measurements")
    truth = silver.read("scenario_truth") if (C.SILVER / "scenario_truth.parquet").exists() else None

    # ------------------------------------------------------------ replay do posterior
    step_rows = []
    truth_comp = {}
    if truth is not None:
        truth_comp = dict(zip(truth.session_id, truth.true_fault.str.split(":").str[0]))
    for sid, grp in meas.sort_values(["session_id", "step"]).groupby("session_id"):
        circuit_id = grp.circuit_id.iloc[0]
        dg = dgs[circuit_id]
        taken: dict[str, float] = {}
        for r in grp.itertuples():
            taken[r.observable_id] = r.value_si
            post = dg.posterior(taken)
            cp = dg.component_posterior(post)
            top = max(cp, key=cp.get)
            tc = truth_comp.get(sid)
            step_rows.append({"session_id": sid, "circuit_id": circuit_id, "step": r.step,
                              "observable_id": r.observable_id, "value_si": r.value_si,
                              "top_component": top, "top_prob": cp[top],
                              "true_component": tc, "p_true_component": cp.get(tc) if tc else np.nan,
                              "top_is_true": (top == tc) if tc else None})
    steps = pd.DataFrame(step_rows)
    _write(steps, "fct_session_step")

    # ------------------------------------------------------------ fato de sessão
    s = sess.copy()
    s["date_id"] = s.started_at.dt.strftime("%Y%m%d").astype(int)
    s["is_completed"] = s.status == "completed"
    s["duration_min"] = s.duration_s / 60.0
    if truth is not None:
        s = s.merge(truth[["session_id", "scenario_id", "true_fault"]], on="session_id", how="left")
        s["true_component"] = s.true_fault.str.split(":").str[0]
        s["replaced_is_correct"] = np.where(s.replaced_component.notna() & s.true_component.notna(),
                                           s.replaced_component == s.true_component, None)
    else:
        s["scenario_id"], s["true_fault"], s["true_component"], s["replaced_is_correct"] = None, None, None, None
    s["replaced_is_correct"] = s["replaced_is_correct"].astype("boolean")
    last = steps.sort_values("step").groupby("session_id").tail(1)[["session_id", "top_prob"]] if len(steps) \
        else pd.DataFrame(columns=["session_id", "top_prob"])
    s = s.merge(last.rename(columns={"top_prob": "final_top_prob"}), on="session_id", how="left")
    s["success"] = s.outcome == "reparado"
    dq.check("gold", "fct_session", "unique_session", len(s), int(s.session_id.duplicated().sum()))
    dq.check("gold", "fct_session", "completed_has_outcome", int(s.is_completed.sum()),
             int((s.is_completed & s.outcome.isna()).sum()))
    _write(s, "fct_session")

    # ------------------------------------------------------------ dimensões auxiliares
    _write(pd.DataFrame({"mode": list(C.MODES), "mode_label": [C.MODE_LABEL[m] for m in C.MODES],
                         "usa_app": [True, True, False]}), "dim_mode")
    _write(pd.DataFrame({"level": ["iniciante", "intermediario"]}), "dim_level")
    _write(_dim_date(s.started_at.dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None).dt.normalize()),
           "dim_date")

    # ------------------------------------------------------------ agregações
    kpi = _kpi(s)
    _write(kpi, "agg_kpi_circuit_mode")
    _write(_kpi(s.assign(circuit_id="(todos)")), "agg_kpi_overall_mode")
    _write(_convergence(steps), "agg_convergence")
    _write(_confusion(s), "agg_confusion")
    _write(_observable_usage(meas, s), "agg_observable_usage")
    _write(_daily(s), "agg_daily_usage")

    # ------------------------------------------------------------ qualidade dos dados (BI de saúde do pipeline)
    dq.check("gold", "agg_kpi_circuit_mode", "all_modes_present_per_circuit", len(kpi),
             int(kpi.groupby("circuit_id")["mode"].nunique().ne(len(C.MODES)).sum()))


def _kpi(s: pd.DataFrame) -> pd.DataFrame:
    done = s[s.is_completed]
    g = done.groupby(["circuit_id", "mode"])
    k = g.agg(n_sessions=("session_id", "size"),
              success_rate=("success", "mean"),
              wrong_replacement_rate=("outcome", lambda x: (x == "troca_errada").mean()),
              giveup_rate=("outcome", lambda x: (x == "desistiu").mean()),
              avg_steps=("n_steps", "mean"), median_steps=("n_steps", "median"),
              p90_steps=("n_steps", lambda x: x.quantile(0.9)),
              avg_duration_min=("duration_min", "mean")).reset_index()
    base = k[k["mode"] == "componente_a_componente"].set_index("circuit_id")
    k["steps_reduction_vs_baseline_pct"] = [
        100.0 * (1 - r.avg_steps / base.loc[r.circuit_id, "avg_steps"]) if r.circuit_id in base.index else np.nan
        for r in k.itertuples()]
    k["time_reduction_vs_baseline_pct"] = [
        100.0 * (1 - r.avg_duration_min / base.loc[r.circuit_id, "avg_duration_min"])
        if r.circuit_id in base.index else np.nan for r in k.itertuples()]
    return k


def _convergence(steps: pd.DataFrame) -> pd.DataFrame:
    if steps.empty:
        return pd.DataFrame()
    sess = silver.read("sessions")[["session_id", "mode"]]
    st = steps.merge(sess, on="session_id")
    st = st[st.true_component.notna()]
    return st.groupby(["circuit_id", "mode", "step"]).agg(
        n_sessions=("session_id", "size"), top1_correct_rate=("top_is_true", lambda x: float(np.mean(x.astype(float)))),
        mean_top_prob=("top_prob", "mean"), mean_p_true_component=("p_true_component", "mean")).reset_index()


def _confusion(s: pd.DataFrame) -> pd.DataFrame:
    d = s[s.is_completed & s.true_component.notna() & s.replaced_component.notna()]
    return d.groupby(["circuit_id", "mode", "true_component", "replaced_component"]).size() \
        .rename("n_sessions").reset_index()


def _observable_usage(meas: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    m = meas.merge(s[["session_id", "mode"]], on="session_id")
    return m.groupby(["circuit_id", "mode", "observable_id"]).agg(
        n_measurements=("step", "size"), avg_step_position=("step", "mean"),
        first_choice_rate=("step", lambda x: float((x == 1).mean()))).reset_index()


def _daily(s: pd.DataFrame) -> pd.DataFrame:
    d = s[s.is_completed].copy()
    d["date"] = d.started_at.dt.tz_convert("America/Sao_Paulo").dt.date
    return d.groupby(["date", "mode"]).agg(n_sessions=("session_id", "size"), avg_steps=("n_steps", "mean"),
                                           success_rate=("success", "mean")).reset_index()


def export_app_assets() -> None:
    """Copia o dicionário para a pasta do app (o app é estático e lê um único JSON)."""
    shutil.copy(C.GOLD / "app" / "dictionary.json", C.REPO / "app" / "dictionary.json")

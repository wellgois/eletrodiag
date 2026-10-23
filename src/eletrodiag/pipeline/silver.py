"""Camada SILVER: dado limpo, tipado, deduplicado e validado (esquema estável, em Parquet).

Princípios:
  * linhas inválidas NÃO somem: vão para `silver/_quarantine/<dataset>/` com o motivo;
  * toda regra aplicada gera um registro de qualidade (ver `quality.py`);
  * a camada é reconstruível a partir da bronze (full-refresh idempotente).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .parsing import parse_measurement, parse_ts
from .quality import DQ, quarantine

EVENT_TYPES = {"session_started", "measurement_taken", "component_tested", "diagnosis_shown",
               "session_finished"}
REQUIRED = ("event_id", "event_type", "ts", "session_id")


def _batches(source: str) -> list[tuple[str, Path]]:
    out = []
    for d in sorted((C.BRONZE / source).glob("ingest_date=*/batch_id=*")):
        out.append((d.name.split("=", 1)[1], d))
    return sorted(out)


def _write(df: pd.DataFrame, name: str, partition: list[str] | None = None) -> None:
    path = C.SILVER / name
    if path.is_dir():
        shutil.rmtree(path)
    path.with_suffix(".parquet").unlink(missing_ok=True)
    if partition:
        path.mkdir(parents=True)
        df.to_parquet(path, partition_cols=partition, index=False)
    else:
        df.to_parquet(path.with_suffix(".parquet"), index=False)


def read(name: str) -> pd.DataFrame:
    path = C.SILVER / name
    if path.is_dir():
        df = pd.read_parquet(path)
        if "circuit_id" in df.columns:  # coluna de partição volta como categórica
            df["circuit_id"] = df["circuit_id"].astype(str)
        return df
    return pd.read_parquet(path.with_suffix(".parquet"))


# ----------------------------------------------------------------------------- dimensões
def build_dims(run_id: str, dq: DQ) -> None:
    batches = _batches("catalog")
    if not batches:
        raise RuntimeError("Nenhum lote de catálogo na bronze; execute a ingestão primeiro.")
    cats = json.loads((batches[-1][1] / "circuits.json").read_text())  # lote mais recente vale
    circ, comp, obs, flt = [], [], [], []
    for c in cats:
        cid = c["circuit_id"]
        circ.append({"circuit_id": cid, "nome": c["nome"], "descricao": c["descricao"], "nivel": c["nivel"],
                     "n_components": len(c["components"]), "n_observables": len(c["observables"]),
                     "n_faults": len(c["faults"]), "hazard": c.get("hazard", ""), "nota": c.get("nota", ""),
                     "svg": c["svg"]})
        comp += [{"circuit_id": cid, "component_id": x["id"], "kind": x["kind"], "nominal": x["nominal"],
                  "funcao": x["funcao"]} for x in c["components"]]
        obs += [{"circuit_id": cid, "observable_id": x["id"], "kind": x["kind"], "ref": x["ref"],
                 "label": x["label"], "onde": x["onde"], "unit": x["unit"], "cost": x["cost"]}
                for x in c["observables"]]
        flt += [{"circuit_id": cid, "fault_id": x["fault_id"], "component_id": x["component_id"],
                 "mode": x["mode"], "prior": x["prior"], "descricao": x["descricao"],
                 "teste_confirmacao": x["teste_confirmacao"], "acao": x["acao"]} for x in c["faults"]]
    d_circ, d_comp, d_obs, d_flt = map(pd.DataFrame, (circ, comp, obs, flt))
    for df, name, key in ((d_circ, "dim_circuit", ["circuit_id"]),
                          (d_comp, "dim_component", ["circuit_id", "component_id"]),
                          (d_obs, "dim_observable", ["circuit_id", "observable_id"]),
                          (d_flt, "dim_fault", ["circuit_id", "fault_id"])):
        dq.check("silver", name, "primary_key_unique", len(df), int(df.duplicated(key).sum()))
        _write(df, name)
    known = set(zip(d_comp.circuit_id, d_comp.component_id))
    bad = sum((a, b) not in known for a, b in zip(d_flt.circuit_id, d_flt.component_id))
    dq.check("silver", "dim_fault", "component_exists", len(d_flt), bad)
    psum = d_flt.groupby("circuit_id")["prior"].sum()
    dq.check("silver", "dim_fault", "prior_sums_to_one", len(psum), int((abs(psum - 1) > 1e-6).sum()))


# ----------------------------------------------------------------------------- simulações
def build_sim_runs(run_id: str, dq: DQ) -> pd.DataFrame:
    rows, rejected, total_runs = [], [], 0
    for batch_id, d in _batches("sim_runs"):
        for f in sorted(d.glob("circuit=*.jsonl")):
            for ln_no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                rec = json.loads(line)
                total_runs += 1
                if not rec["converged"]:
                    rejected.append({"dataset": "sim_runs", "reason": "not_converged", "batch_id": batch_id,
                                     "line_no": ln_no, "raw": rec["run_id"]})
                    continue
                for oid, val in rec["observables"].items():
                    rows.append((rec["run_id"], rec["circuit_id"], rec["fault_id"], rec["component_id"],
                                 rec["mode"], rec["mc_idx"], oid, val, batch_id))
    df = pd.DataFrame(rows, columns=["run_id", "circuit_id", "fault_id", "component_id", "fault_mode",
                                     "mc_idx", "observable_id", "value", "_batch_id"])
    dq.check("silver", "sim_runs", "converged", total_runs, len(rejected))
    df["unit"] = np.where(df.observable_id.str.startswith("V("), "V", "A")
    finite = np.isfinite(df["value"])
    lo = np.where(df.unit == "V", -1.0, -1.0)
    hi = np.where(df.unit == "V", 600.0, 1000.0)  # inclui os blocos de alta tensão e corrente do inversor
    in_range = (df["value"] >= lo) & (df["value"] <= hi)
    for rule, ok in (("value_is_finite", finite), ("value_in_physical_range", in_range & finite)):
        dq.check("silver", "sim_runs", rule, len(df), int((~ok).sum()))
    bad = df[~(finite & in_range)]
    if len(bad):
        quarantine("sim_runs", bad.assign(reason="out_of_range").astype({"value": float}), run_id)
    df = df[finite & in_range]
    dup = df.duplicated(["run_id", "observable_id"], keep="last")
    dq.check("silver", "sim_runs", "unique_run_observable", len(df), int(dup.sum()), "warn",
             "reprocessamentos: mantém o lote mais recente")
    df = df[~dup].drop(columns="_batch_id")
    if rejected:
        quarantine("sim_runs_runs", pd.DataFrame(rejected), run_id)
    # cobertura: toda falha do catálogo precisa ter simulações
    flt = read("dim_fault")
    have = set(zip(df.circuit_id, df.fault_id))
    missing = sum((c, f) not in have for c, f in zip(flt.circuit_id, flt.fault_id))
    dq.check("silver", "sim_runs", "every_fault_simulated", len(flt), missing)
    _write(df.reset_index(drop=True), "sim_runs", partition=["circuit_id"])
    return df


# ----------------------------------------------------------------------------- eventos do app
def build_events(run_id: str, dq: DQ) -> None:
    obs = read("dim_observable")
    comp = read("dim_component")
    obs_kind = {(r.circuit_id, r.observable_id): r.kind for r in obs.itertuples()}
    comps = set(zip(comp.circuit_id, comp.component_id))
    rejected: list[dict] = []

    def reject(reason, batch_id, line_no, raw):
        rejected.append({"dataset": "app_events", "reason": reason, "batch_id": batch_id, "line_no": line_no,
                         "raw": raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)})

    events, total = [], 0
    for batch_id, d in _batches("app_events"):
        for f in sorted(d.glob("events-*.jsonl")):
            for ln_no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                total += 1
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    reject("malformed_json", batch_id, ln_no, line)
                    continue
                if any(not rec.get(k) for k in REQUIRED):
                    reject("missing_required_field", batch_id, ln_no, rec)
                    continue
                if rec["event_type"] not in EVENT_TYPES:
                    reject("unknown_event_type", batch_id, ln_no, rec)
                    continue
                ts = parse_ts(rec["ts"])
                if ts is None:
                    reject("bad_timestamp", batch_id, ln_no, rec)
                    continue
                events.append({**rec, "ts_utc": ts, "batch_id": batch_id, "line_no": ln_no})
    n_parse_fail = len(rejected)
    dq.check("silver", "app_events", "json_parseable_and_required_fields", total, n_parse_fail, "warn",
             "linhas rejeitadas vão para a quarentena")

    ev = pd.DataFrame(events)
    dup = ev.duplicated("event_id", keep="first")
    dq.check("silver", "app_events", "unique_event_id", len(ev), int(dup.sum()), "warn",
             "duplicatas de reenvio do app removidas")
    ev = ev[~dup].copy()

    started = ev[ev.event_type == "session_started"]
    started = started[~started.duplicated("session_id", keep="first")]
    sess_ids = set(started.session_id)
    orphan = ~ev.session_id.isin(sess_ids)
    dq.check("silver", "app_events", "session_has_start_event", len(ev), int(orphan.sum()), "warn")
    for r in ev[orphan].itertuples():
        reject("orphan_event", r.batch_id, r.line_no, r.event_id)
    ev = ev[~orphan]

    sess = pd.DataFrame({
        "session_id": started.session_id.values,
        "learner_id": started.learner_id.values,
        "circuit_id": [p["circuit_id"] for p in started.payload],
        "mode": [p["mode"] for p in started.payload],
        "level": [p.get("level") for p in started.payload],
        "device": [p.get("device") for p in started.payload],
        "app_version": started.app_version.values,
        "started_at": pd.to_datetime(started.ts_utc.to_list(), utc=True),
    })
    circ_of = dict(zip(sess.session_id, sess.circuit_id))
    bad_mode = ~sess["mode"].isin(C.MODES)
    dq.check("silver", "sessions", "mode_is_valid", len(sess), int(bad_mode.sum()))
    sess = sess[~bad_mode]

    # --- medições
    m = ev[ev.event_type == "measurement_taken"]
    mrows, mrej = [], 0
    for r in m.itertuples():
        p = r.payload
        cid = circ_of[r.session_id]
        oid = p.get("observable_id")
        if oid is None:
            reject("null_observable", r.batch_id, r.line_no, r.event_id)
            mrej += 1
            continue
        if (cid, oid) not in obs_kind:
            reject("unknown_observable", r.batch_id, r.line_no, r.event_id)
            mrej += 1
            continue
        val, unit, why = parse_measurement(p.get("raw_value"), p.get("unit_raw"), obs_kind[(cid, oid)])
        if why:
            reject(why, r.batch_id, r.line_no, r.event_id)
            mrej += 1
            continue
        mrows.append({"event_id": r.event_id, "session_id": r.session_id, "circuit_id": cid,
                      "step": int(p["step"]), "observable_id": oid, "raw_value": str(p.get("raw_value")),
                      "unit_raw": p.get("unit_raw"), "value_si": val, "unit_si": unit,
                      "duration_s": p.get("duration_s"), "ts": r.ts_utc})
    meas = pd.DataFrame(mrows)
    dq.check("silver", "measurements", "valid_observable_and_parseable_value", len(m), mrej, "warn",
             "medições rejeitadas vão para a quarentena")
    if len(meas):
        d2 = meas.duplicated(["session_id", "step"], keep="first")
        dq.check("silver", "measurements", "unique_session_step", len(meas), int(d2.sum()), "warn")
        meas = meas[~d2]

    # --- testes de componente (método atual)
    t = ev[ev.event_type == "component_tested"]
    trows, trej = [], 0
    for r in t.itertuples():
        p = r.payload
        cid = circ_of[r.session_id]
        if (cid, p.get("component_id")) not in comps or p.get("verdict") not in ("defeituoso", "ok"):
            reject("invalid_component_test", r.batch_id, r.line_no, r.event_id)
            trej += 1
            continue
        trows.append({"event_id": r.event_id, "session_id": r.session_id, "circuit_id": cid,
                      "step": int(p["step"]), "component_id": p["component_id"], "verdict": p["verdict"],
                      "duration_s": p.get("duration_s"), "ts": r.ts_utc})
    tests = pd.DataFrame(trows)
    dq.check("silver", "component_tests", "valid_component_and_verdict", len(t), trej, "warn")

    # --- diagnósticos exibidos
    dg = ev[ev.event_type == "diagnosis_shown"]
    diag = pd.DataFrame([{
        "event_id": r.event_id, "session_id": r.session_id, "step": int(r.payload["step"]),
        "top_component": r.payload["top_component"], "top_fault": r.payload["top_fault"],
        "top_prob": float(r.payload["top_prob"]), "ts": r.ts_utc} for r in dg.itertuples()])
    if len(diag):
        bad_p = ~diag.top_prob.between(0, 1)
        dq.check("silver", "diagnosis_events", "probability_in_0_1", len(diag), int(bad_p.sum()))
        diag = diag[~bad_p]

    # --- desfecho e consolidação de sessões
    fin = ev[ev.event_type == "session_finished"]
    fin = fin[~fin.duplicated("session_id", keep="first")]
    fin_df = pd.DataFrame({
        "session_id": fin.session_id.values,
        "finished_at": pd.to_datetime(fin.ts_utc.to_list(), utc=True),
        "outcome": [p.get("outcome") for p in fin.payload],
        "replaced_component": [p.get("replaced_component") for p in fin.payload],
        "stop_reason": [p.get("stop_reason") for p in fin.payload],
    })
    sess = sess.merge(fin_df, on="session_id", how="left")
    sess["status"] = np.where(sess.finished_at.notna(), "completed", "incomplete")
    dq.check("silver", "sessions", "session_completed", len(sess), int((sess.status == "incomplete").sum()),
             "warn", "sessões sem evento de término")
    cm = meas.groupby("session_id").agg(n_measurements=("step", "size"), dm=("duration_s", "sum")) \
        if len(meas) else pd.DataFrame(columns=["n_measurements", "dm"])
    ct = tests.groupby("session_id").agg(n_component_tests=("step", "size"), dt=("duration_s", "sum")) \
        if len(tests) else pd.DataFrame(columns=["n_component_tests", "dt"])
    sess = sess.merge(cm, left_on="session_id", right_index=True, how="left") \
        .merge(ct, left_on="session_id", right_index=True, how="left")
    for col in ("n_measurements", "n_component_tests", "dm", "dt"):
        sess[col] = sess[col].fillna(0)
    sess["n_steps"] = (sess.n_measurements + sess.n_component_tests).astype("int64")
    sess["duration_s"] = sess.dm + sess.dt
    sess = sess.drop(columns=["dm", "dt"]).astype({"n_measurements": "int64", "n_component_tests": "int64"})
    bad_out = sess.outcome.notna() & ~sess.outcome.isin(["reparado", "troca_errada", "desistiu"])
    dq.check("silver", "sessions", "outcome_is_valid", len(sess), int(bad_out.sum()))
    dq.check("silver", "sessions", "has_steps_when_completed",
             int((sess.status == "completed").sum()),
             int(((sess.status == "completed") & (sess.n_steps == 0) & (sess.outcome != "desistiu")).sum()),
             "warn")

    if rejected:
        quarantine("app_events", pd.DataFrame(rejected), run_id)
    _write(sess.reset_index(drop=True), "sessions")
    _write(meas.reset_index(drop=True), "measurements")
    _write(tests.reset_index(drop=True), "component_tests")
    _write(diag.reset_index(drop=True), "diagnosis_events")

    # --- gabarito dos cenários sintéticos
    truth = []
    for _, d in _batches("scenario_truth"):
        for f in d.glob("truth.jsonl"):
            truth += [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    if truth:
        tdf = pd.DataFrame(truth).drop_duplicates("session_id", keep="last")
        dq.check("silver", "scenario_truth", "session_known", len(tdf), int((~tdf.session_id.isin(sess.session_id)).sum()),
                 "warn")
        _write(tdf.reset_index(drop=True), "scenario_truth")

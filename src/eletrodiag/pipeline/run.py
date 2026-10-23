"""Orquestrador do pipeline medalhão.

Uso:
    python -m eletrodiag.pipeline.run --fresh            # tudo, do zero
    python -m eletrodiag.pipeline.run --steps silver_events gold_analytics warehouse

Ordem (DAG linear): ver docs/architecture.md.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
import traceback
from datetime import datetime, timezone

from . import bronze, config as C, gold, silver, warehouse
from .quality import DQ


def _synth_events(ctx):
    from ..synth.students import generate
    dictionary = json.loads((C.GOLD / "app" / "dictionary.json").read_text())
    by_week, truth = generate(dictionary, seed=ctx["seed"], n_scenarios=ctx["scenarios"])
    bronze.ingest_app_events(by_week, seed=ctx["seed"])
    bronze.ingest_scenario_truth(truth)
    return {"weeks": len(by_week), "sessions": len(truth), "events": sum(len(v) for v in by_week.values())}


def _dashboard(ctx):
    from ..bi.dashboard import build
    return build()


def _app(ctx):
    from ..app_build import build
    gold.export_app_assets()
    return build()


STEPS = {
    "bronze_catalog": lambda ctx, dq: bronze.ingest_catalog() and {},
    "bronze_sim": lambda ctx, dq: bronze.ingest_sim_runs(n_mc=ctx["n_mc"], seed=ctx["seed"]) and {},
    "silver_dims": lambda ctx, dq: silver.build_dims(ctx["run_id"], dq),
    "silver_sim": lambda ctx, dq: {"rows": len(silver.build_sim_runs(ctx["run_id"], dq))},
    "gold_dictionary": lambda ctx, dq: {"version": gold.build_dictionary(ctx["run_id"], dq)["version"]},
    "synth_events": lambda ctx, dq: _synth_events(ctx),
    "silver_events": lambda ctx, dq: silver.build_events(ctx["run_id"], dq),
    "gold_analytics": lambda ctx, dq: gold.build_analytics(ctx["run_id"], dq),
    "warehouse": lambda ctx, dq: warehouse.publish(),
    "app": lambda ctx, dq: _app(ctx),
    "dashboard": lambda ctx, dq: _dashboard(ctx),
}


def _log_run(entry: dict) -> None:
    C.META.mkdir(parents=True, exist_ok=True)
    with (C.META / "runs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="*", default=list(STEPS), choices=list(STEPS))
    ap.add_argument("--fresh", action="store_true", help="apaga data/ antes de rodar")
    ap.add_argument("--n-mc", type=int, default=C.N_MC)
    ap.add_argument("--scenarios", type=int, default=C.N_SCENARIOS)
    ap.add_argument("--seed", type=int, default=C.SEED)
    a = ap.parse_args(argv)

    if a.fresh and C.DATA.exists():
        shutil.rmtree(C.DATA)
    C.ensure_dirs()
    run_id = datetime.now(timezone.utc).strftime("run%Y%m%dT%H%M%S")
    ctx = {"run_id": run_id, "n_mc": a.n_mc, "scenarios": a.scenarios, "seed": a.seed}
    dq = DQ(run_id)
    for step in a.steps:
        t0 = time.time()
        started = datetime.now(timezone.utc).isoformat()
        try:
            details = STEPS[step](ctx, dq) or {}
            status = "ok"
        except Exception:
            _log_run({"run_id": run_id, "step": step, "status": "failed", "started_at": started,
                      "ended_at": datetime.now(timezone.utc).isoformat(), "error": traceback.format_exc()})
            dq.save()
            raise
        dt = time.time() - t0
        dq.save()  # grava as regras desta etapa já (o warehouse lê o log)
        _log_run({"run_id": run_id, "step": step, "status": status, "started_at": started,
                  "ended_at": datetime.now(timezone.utc).isoformat(), "seconds": round(dt, 2),
                  "details": details if isinstance(details, dict) else {}})
        print(f"[{step:16s}] ok  {dt:6.1f}s  {details if isinstance(details, dict) and details else ''}")
    failed = [r for r in dq.results if not r.passed and r.severity == "error"]
    warn = [r for r in dq.results if not r.passed and r.severity == "warn"]
    print(f"\nQualidade de dados: {len(dq.results)} regras | {len(failed)} erros | {len(warn)} avisos")
    for r in failed + warn:
        print(f"  [{r.severity}] {r.layer}.{r.dataset}.{r.rule}: {r.failed}/{r.checked}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

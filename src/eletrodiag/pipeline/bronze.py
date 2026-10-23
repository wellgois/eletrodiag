"""Camada BRONZE: dado bruto, imutável, particionado por data e lote, com manifesto.

Regras da camada:
  * nada é corrigido ou descartado aqui (o que chegou, fica);
  * cada lote grava um `_manifest.json` (contagem de linhas e SHA-256) para rastreabilidade;
  * a escrita é append-only: reprocessar gera um novo lote, nunca sobrescreve um antigo.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from ..sim.circuits import all_circuits, simulate
from . import config as C


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_batch_id(prefix: str = "b") -> str:
    return f"{prefix}{_now():%Y%m%dT%H%M%S}{int(time.time() * 1000) % 1000:03d}"


def _batch_dir(source: str, batch_id: str, ingest_date: str | None = None) -> Path:
    ingest_date = ingest_date or f"{_now():%Y-%m-%d}"
    d = C.BRONZE / source / f"ingest_date={ingest_date}" / f"batch_id={batch_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _write_manifest(d: Path, source: str, batch_id: str, files: list[Path], rows: int, extra=None) -> None:
    manifest = {
        "source": source, "batch_id": batch_id, "ingested_at": _now().isoformat(),
        "schema_version": C.SCHEMA_VERSION, "rows": rows,
        "files": [{"name": f.name, "sha256": _sha256(f)} for f in files],
    }
    manifest.update(extra or {})
    (d / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


# ----------------------------------------------------------------------------- catálogo
def ingest_catalog(batch_id: str | None = None) -> Path:
    """Catálogo de circuitos, componentes, observáveis e falhas (fonte: biblioteca curada)."""
    batch_id = batch_id or new_batch_id("cat")
    d = _batch_dir("catalog", batch_id)
    f = d / "circuits.json"
    f.write_text(json.dumps([c.catalog() for c in all_circuits()], ensure_ascii=False, indent=1))
    _write_manifest(d, "catalog", batch_id, [f], len(all_circuits()))
    return d


# ----------------------------------------------------------------------------- simulações
def ingest_sim_runs(n_mc: int = C.N_MC, seed: int = C.SEED, batch_id: str | None = None) -> Path:
    """Executa o Monte Carlo de cada falha e grava uma linha JSON por simulação (semi-estruturado)."""
    batch_id = batch_id or new_batch_id("sim")
    d = _batch_dir("sim_runs", batch_id)
    files, rows = [], 0
    for ci, circuit in enumerate(all_circuits()):
        out = d / f"circuit={circuit.id}.jsonl"
        hyps = [None] + circuit.faults()
        with out.open("w", encoding="utf-8") as fh:
            for fi, fault in enumerate(hyps):
                rng = np.random.default_rng([seed, ci, fi])
                fid = "OK" if fault is None else f"{fault[0]}:{fault[1]}"
                for k in range(n_mc):
                    values, sol = simulate(circuit, fault, rng)
                    rec = {
                        "run_id": f"{circuit.id}|{fid}|{k}", "circuit_id": circuit.id, "fault_id": fid,
                        "component_id": None if fault is None else fault[0],
                        "mode": None if fault is None else fault[1], "mc_idx": k,
                        "converged": bool(sol.converged), "iterations": int(sol.iterations),
                        "observables": {o: float(v) for o, v in values.items()},
                        "solver": C.SIM_VERSION, "simulated_at": _now().isoformat(),
                    }
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    rows += 1
        files.append(out)
    _write_manifest(d, "sim_runs", batch_id, files, rows, {"n_mc": n_mc, "seed": seed})
    return d


# ----------------------------------------------------------------------------- eventos do app
def ingest_app_events(records_by_week: dict[str, list[dict]], batch_prefix: str = "evt", dirty: bool = True,
                      seed: int = C.SEED) -> list[Path]:
    """Grava eventos do app como JSON Lines, um lote por semana ISO.

    Com `dirty=True` injeta imperfeições realistas de ingestão (duplicatas, linhas truncadas,
    observável nulo e ordem parcialmente embaralhada) para exercitar a camada silver.
    """
    rnd = random.Random(seed)
    dirs = []
    for week, recs in sorted(records_by_week.items()):
        lines = _to_lines(recs, rnd, dirty)
        batch_id = f"{batch_prefix}-{week}"
        d = _batch_dir("app_events", batch_id, ingest_date=week_ingest_date(week))
        f = d / "events-0000.jsonl"
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _write_manifest(d, "app_events", batch_id, [f], len(lines), {"dirty_injected": dirty})
        dirs.append(d)
    return dirs


def week_ingest_date(week: str) -> str:
    """Os eventos de uma semana ISO ('2026-W37') chegam em lote na segunda-feira seguinte."""
    year, w = week.split("-W")
    return f"{datetime.fromisocalendar(int(year), int(w), 1) + timedelta(days=7):%Y-%m-%d}"


def _to_lines(recs: list[dict], rnd: random.Random, dirty: bool) -> list[str]:
    out: list[str] = []
    for rec in recs:
        rec = dict(rec)
        if dirty and rec.get("event_type") == "measurement_taken" and rnd.random() < 0.004:
            rec["payload"] = {**rec["payload"], "observable_id": None}
        ln = json.dumps(rec, ensure_ascii=False)
        if dirty and rnd.random() < 0.004:  # linha truncada (JSON inválido)
            out.append(ln[: max(10, len(ln) // 2)])
            continue
        out.append(ln)
        if dirty and rnd.random() < 0.015:  # reenvio do app: duplicata exata
            out.append(ln)
    if dirty:  # chegada parcialmente fora de ordem
        for _ in range(len(out) // 50):
            i = rnd.randrange(len(out))
            j = min(len(out) - 1, i + rnd.randrange(1, 30))
            out[i], out[j] = out[j], out[i]
    return out


def ingest_scenario_truth(records: list[dict], batch_id: str | None = None) -> Path:
    """Gabarito dos cenários sintéticos (só existe em dados simulados; em produção vem do desfecho)."""
    batch_id = batch_id or new_batch_id("truth")
    d = _batch_dir("scenario_truth", batch_id)
    f = d / "truth.jsonl"
    f.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    _write_manifest(d, "scenario_truth", batch_id, [f], len(records), {"synthetic": True})
    return d

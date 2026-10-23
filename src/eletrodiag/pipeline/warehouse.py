"""Publica a camada gold em formatos consumíveis por BI: DuckDB, SQLite, CSV e Parquet.

* DuckDB  : `data/warehouse/eletrodiag.duckdb`  (consultas analíticas rápidas)
* SQLite  : `data/warehouse/eletrodiag.sqlite`  (suporte amplo em ferramentas de BI)
* CSV     : `data/gold/csv/*.csv`               (importação direta em Power BI/Excel/Sheets)
* Parquet : `data/gold/*.parquet`               (formato nativo da camada gold)
"""
from __future__ import annotations

import json
import sqlite3

import duckdb
import pandas as pd

from . import config as C

VIEWS_SQL = C.REPO / "bi" / "views.sql"


def _meta_tables() -> dict[str, pd.DataFrame]:
    out = {}
    for name, fname in (("fct_dq_result", "dq_results.jsonl"), ("fct_pipeline_run", "runs.jsonl")):
        p = C.META / fname
        rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
        df = pd.DataFrame(rows)
        for col in df.columns:  # colunas aninhadas (dict/list) viram JSON texto
            if len(df) and df[col].map(lambda v: isinstance(v, (dict, list))).any():
                df[col] = df[col].map(lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
        out[name] = df
    return out


def _gold_tables() -> dict[str, pd.DataFrame]:
    tables = {p.stem: pd.read_parquet(p) for p in sorted(C.GOLD.glob("*.parquet"))}
    tables.update({k: v for k, v in _meta_tables().items() if len(v)})
    return tables


def _split_views() -> list[str]:
    out = []
    for chunk in VIEWS_SQL.read_text().split(";"):
        lines = [ln for ln in chunk.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            out.append(stmt)
    return out


def _sqlite_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if isinstance(df[col].dtype, pd.DatetimeTZDtype) or str(df[col].dtype).startswith("datetime64"):
            df[col] = df[col].astype(str)
        elif df[col].dtype == object and len(df[col].dropna()) and hasattr(df[col].dropna().iloc[0], "isoformat"):
            df[col] = df[col].astype(str)
    return df


def publish() -> dict:
    C.WAREHOUSE.mkdir(parents=True, exist_ok=True)
    tables = _gold_tables()
    views = _split_views()
    report = {"tables": {k: len(v) for k, v in tables.items()}, "views": len(views)}

    csv_dir = C.GOLD / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        if name == "dim_circuit":  # o SVG é grande e inútil em CSV de BI
            df = df.drop(columns=["svg"])
        df.to_csv(csv_dir / f"{name}.csv", index=False, encoding="utf-8")

    # DuckDB
    db = C.WAREHOUSE / "eletrodiag.duckdb"
    db.unlink(missing_ok=True)
    con = duckdb.connect(str(db))
    for name, df in tables.items():
        con.register("_df", df)
        con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM _df')
        con.unregister("_df")
    for v in views:
        con.execute(v)
    con.close()

    # SQLite
    sq = C.WAREHOUSE / "eletrodiag.sqlite"
    sq.unlink(missing_ok=True)
    conn = sqlite3.connect(sq)
    for name, df in tables.items():
        _sqlite_frame(df).to_sql(name, conn, index=False)
    for v in views:
        conn.execute(v)
    conn.commit()
    conn.close()
    return report

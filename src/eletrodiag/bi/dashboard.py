"""Gera o painel de BI estático (bi/dashboard/index.html) a partir da camada gold.

O painel é um exemplo de consumo. Em produção, as mesmas tabelas/views alimentam Power BI,
Metabase, Superset etc. (ver docs/bi_guide.md).
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from eletrodiag.pipeline import config as C

HERE = C.REPO / "bi" / "dashboard"


def build() -> dict:
    g = lambda n: pd.read_parquet(C.GOLD / f"{n}.parquet")  # noqa: E731
    circuits = g("dim_circuit")[["circuit_id", "nome"]].rename(columns={"circuit_id": "id"})
    sep = g("fct_fault_pair_separability")
    sep = sep[sep["class"] != "mesmo_componente"]
    dq = pd.DataFrame([json.loads(x) for x in (C.META / "dq_results.jsonl").read_text().splitlines()])
    dq = dq.sort_values("logged_at").groupby(["layer", "dataset", "rule"], as_index=False).tail(1)
    dictionary = json.loads((C.GOLD / "app" / "dictionary.json").read_text())
    data = {
        "meta": {"sessions": int(len(g("fct_session"))), "dictionary_version": dictionary["version"],
                 "generated": datetime.now().strftime("%d/%m/%Y")},
        "circuits": circuits.to_dict("records"),
        "kpi": g("agg_kpi_circuit_mode").to_dict("records"),
        "kpi_all": g("agg_kpi_overall_mode").to_dict("records"),
        "conv": g("agg_convergence").to_dict("records"),
        "sep_summary": sep.groupby(["circuit_id", "class"]).size().rename("pairs").reset_index().to_dict("records"),
        "ambiguous": sep[sep["class"].isin(["requer_corrente", "indistinguivel_eletricamente"])]
        [["circuit_id", "fault_a", "fault_b", "dist_voltage", "dist_all", "class"]].to_dict("records"),
        "dq": dq[["layer", "dataset", "rule", "severity", "checked", "failed"]].to_dict("records"),
    }
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    page = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, default=float))
    head, content = page.split("<!--BODY-->")
    standalone = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
                  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                  f"{head}</head>\n<body>{content}</body>\n</html>\n")
    (HERE / "index.html").write_text(standalone, encoding="utf-8")
    (HERE / "build").mkdir(exist_ok=True)
    (HERE / "build" / "painel-artifact.html").write_text(head + content, encoding="utf-8")
    return {"bytes": len(standalone)}


if __name__ == "__main__":
    print(build())

"""Registro de verificações de qualidade de dados e quarentena de linhas rejeitadas."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import pandas as pd

from . import config as C


@dataclass
class RuleResult:
    run_id: str
    layer: str
    dataset: str
    rule: str
    severity: str  # error | warn | info
    checked: int
    failed: int
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.failed == 0


class DQ:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.results: list[RuleResult] = []
        self._saved = 0

    def check(self, layer, dataset, rule, checked, failed, severity="error", detail=""):
        self.results.append(RuleResult(self.run_id, layer, dataset, rule, severity, int(checked),
                                       int(failed), detail))

    def save(self) -> None:
        """Acrescenta ao log as regras ainda não gravadas (pode ser chamado a cada etapa)."""
        C.META.mkdir(parents=True, exist_ok=True)
        path = C.META / "dq_results.jsonl"
        stamp = datetime.now(timezone.utc).isoformat()
        with path.open("a", encoding="utf-8") as fh:
            for r in self.results[self._saved:]:
                fh.write(json.dumps({**asdict(r), "logged_at": stamp}, ensure_ascii=False) + "\n")
        self._saved = len(self.results)


def quarantine(dataset: str, rows: pd.DataFrame, run_id: str) -> None:
    """Grava linhas rejeitadas (com o motivo) para auditoria, sem perder o dado de origem."""
    if rows is None or rows.empty:
        return
    d = C.QUARANTINE / dataset
    d.mkdir(parents=True, exist_ok=True)
    rows.assign(_run_id=run_id).to_parquet(d / f"{run_id}.parquet", index=False)

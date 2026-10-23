"""Configuração central: caminhos, sementes e versões de esquema."""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("ELETRODIAG_DATA", REPO / "data"))

BRONZE = DATA / "bronze"
SILVER = DATA / "silver"
GOLD = DATA / "gold"
WAREHOUSE = DATA / "warehouse"
META = DATA / "_meta"
QUARANTINE = SILVER / "_quarantine"

SEED = 20261022
N_MC = 150  # amostras Monte Carlo por falha
MIN_SIGNATURE_SAMPLES = 30  # mínimo estatístico de amostras por assinatura (regra de qualidade da gold)
N_SCENARIOS = 300  # cenários de defeito por circuito na geração sintética de sessões
N_LEARNERS = 120
SESSIONS_START = "2026-09-01"
SESSIONS_DAYS = 50

SCHEMA_VERSION = "1.0"
SIM_VERSION = "eletrodiag-mna-0.1"
APP_VERSION = "0.1.0"

# Limiar de decisão e mínimo de medições do app (também usado na geração sintética)
CONFIDENCE_STOP = 0.80
MIN_MEASUREMENTS = 2

MODES = ("guiado", "medicao_aleatoria", "componente_a_componente")
MODE_LABEL = {
    "guiado": "Guiado pelo app (próxima medição sugerida)",
    "medicao_aleatoria": "Ranking do app, medições em ordem aleatória",
    "componente_a_componente": "Componente a componente (método atual do estudante)",
}


def ensure_dirs() -> None:
    for p in (BRONZE, SILVER, GOLD, WAREHOUSE, META, QUARANTINE):
        p.mkdir(parents=True, exist_ok=True)

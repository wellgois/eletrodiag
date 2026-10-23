"""Funções de parsing/normalização usadas na camada silver (puras e testáveis)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BR_TZ = ZoneInfo("America/Sao_Paulo")

# unidade normalizada -> (grandeza, fator para SI)
_UNITS = {
    "v": ("V", 1.0), "mv": ("V", 1e-3), "kv": ("V", 1e3), "uv": ("V", 1e-6), "µv": ("V", 1e-6),
    "a": ("A", 1.0), "ma": ("A", 1e-3), "ua": ("A", 1e-6), "µa": ("A", 1e-6), "μa": ("A", 1e-6),
}
_NUM = re.compile(r"^\s*([+\-−]?\s*\d+(?:[.,]\d+)?)\s*([A-Za-zµμ]*)\s*$")
DEFAULT_UNIT = {"V": "V", "I": "mA"}  # unidade padrão exibida pelo app para cada tipo de medição


def parse_ts(value) -> datetime | None:
    """Converte timestamps heterogêneos para UTC.

    Aceita ISO-8601 (com 'Z' ou offset) e 'dd/mm/aaaa HH:MM:SS' (assumido horário de Brasília).
    """
    if value is None:
        return None
    s = str(value).strip()
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        return datetime.strptime(s, "%d/%m/%Y %H:%M:%S").replace(tzinfo=BR_TZ).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_measurement(raw_value, unit_raw, obs_kind: str) -> tuple[float | None, str | None, str | None]:
    """Converte a leitura digitada para unidade SI.

    Devolve (valor_SI, unidade_SI, motivo_de_rejeição). Aceita vírgula decimal, unidade no texto
    ('473 mV') ou no campo à parte, caixa mista ('MA') e o sinal de menos tipográfico.
    """
    if raw_value is None:
        return None, None, "unparsable_value"
    m = _NUM.match(str(raw_value))
    if not m:
        return None, None, "unparsable_value"
    num = m.group(1).replace(" ", "").replace("−", "-").replace(",", ".")
    unit_txt = m.group(2) or (unit_raw or "") or DEFAULT_UNIT[obs_kind]
    unit_key = unit_txt.strip().lower()
    if unit_key not in _UNITS:
        return None, None, "unknown_unit"
    quantity, factor = _UNITS[unit_key]
    expected = "V" if obs_kind == "V" else "A"
    if quantity != expected:
        return None, None, "unit_mismatch"
    return float(num) * factor, quantity, None

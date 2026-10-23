import pytest

from eletrodiag.pipeline.parsing import parse_measurement, parse_ts


@pytest.mark.parametrize("raw,unit,kind,expected", [
    ("4,73", "V", "V", 4.73),
    ("4.73 V", None, "V", 4.73),
    ("473", "mV", "V", 0.473),
    ("473 mv", None, "V", 0.473),
    ("9,4", "mA", "I", 0.0094),
    ("9,4", None, "I", 0.0094),        # unidade padrão de corrente = mA
    ("2,30", "A", "I", 2.30),
    ("120", "uA", "I", 120e-6),
    ("12", "MA", "I", 0.012),
    ("−0,52", "V", "V", -0.52),         # sinal de menos tipográfico
])
def test_leituras_validas(raw, unit, kind, expected):
    value, _, why = parse_measurement(raw, unit, kind)
    assert why is None and value == pytest.approx(expected)


@pytest.mark.parametrize("raw,unit,kind,reason", [
    ("abc", "V", "V", "unparsable_value"),
    (None, "V", "V", "unparsable_value"),
    ("5", "mA", "V", "unit_mismatch"),
    ("5", "V", "I", "unit_mismatch"),
    ("5", "ohm", "V", "unknown_unit"),
])
def test_leituras_invalidas(raw, unit, kind, reason):
    assert parse_measurement(raw, unit, kind)[2] == reason


def test_timestamps_heterogeneos():
    a = parse_ts("2026-09-01T10:00:00-03:00")
    b = parse_ts("2026-09-01T13:00:00Z")
    c = parse_ts("01/09/2026 10:00:00")  # horário de Brasília
    assert a == b == c
    assert parse_ts("ontem") is None and parse_ts(None) is None

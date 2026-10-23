import numpy as np
import pytest

from eletrodiag.sim.circuits import all_circuits, get_circuit, inject, simulate
from eletrodiag.sim.solver import GND, El, solve_dc


def test_divisor_de_tensao():
    els = [El("V", "V1", ("VCC", GND), {"V": 10}), El("R", "R1", ("VCC", "M"), {"R": 10e3}),
           El("R", "R2", ("M", GND), {"R": 10e3})]
    s = solve_dc(els)
    assert s.converged and s.v["M"] == pytest.approx(5.0, rel=1e-6)


def test_led_com_resistor():
    els = [El("V", "V1", ("VCC", GND), {"V": 5}), El("R", "R1", ("VCC", "A"), {"R": 330}),
           El("D", "D1", ("A", GND), {"Is": 1e-18, "n": 2.0})]
    s = solve_dc(els)
    assert 1.8 < s.v["A"] < 2.0
    assert s.currents["R1"] == pytest.approx((5 - s.v["A"]) / 330, rel=1e-6)


def test_polarizacao_bjt_lei_de_kirchhoff():
    c = get_circuit("emissor_comum")
    rng = np.random.default_rng(0)
    values, sol = simulate(c, None, rng)
    assert sol.converged
    assert 1.5 < values["V(B)"] < 2.5          # divisor de base
    assert 0.55 < values["V(B)"] - values["V(E)"] < 0.8  # Vbe de silício
    assert 0 < values["V(E)"] < values["V(C)"] < values["V(VCC)"]


def test_zener_regula():
    c = get_circuit("zener_shunt")
    values, _ = simulate(c, None, np.random.default_rng(1))
    assert 4.5 < values["V(Z)"] < 5.7


@pytest.mark.parametrize("circuit", all_circuits(), ids=lambda c: c.id)
def test_todas_as_falhas_convergem(circuit):
    rng = np.random.default_rng(7)
    for fault in [None] + circuit.faults():
        for _ in range(5):
            _, sol = simulate(circuit, fault, rng)
            assert sol.converged, (circuit.id, fault)


def test_resistor_aberto_zera_corrente():
    c = get_circuit("led_resistor")
    values, _ = simulate(c, ("R1", "open"), np.random.default_rng(3))
    assert abs(values["I(R1)"]) < 1e-6


def test_curto_no_led_aumenta_corrente_e_zera_tensao():
    c = get_circuit("led_resistor")
    values, _ = simulate(c, ("D1", "short"), np.random.default_rng(3))
    assert values["V(A)"] < 0.05 and values["I(R1)"] > 0.012


def test_inject_nao_altera_original():
    c = get_circuit("bjt_chave_led")
    base = c.nominal_elements()
    inject(base, "Q1", "open_b")
    assert next(e for e in base if e.name == "Q1").nodes == ("C", "B", GND)


# --------------------------------------------------------------------------- MOSFET, regulador, inversor
MOS = {"Kp": 36.0, "Vth": 3.0, "lam": 0.01}


def test_mosfet_ligado_vira_resistencia_pequena():
    els = [El("V", "V1", ("VB", GND), {"V": 12}), El("R", "RL", ("VB", "D"), {"R": 5}),
           El("V", "VG", ("G", GND), {"V": 10}), El("M", "M1", ("D", "G", GND), MOS)]
    s = solve_dc(els)
    rds = 1.0 / (MOS["Kp"] * (10 - MOS["Vth"]))  # triodo com Vds pequeno
    assert s.converged and s.v["D"] == pytest.approx(12 * rds / (5 + rds), rel=0.05)
    assert s.currents["M1.d"] == pytest.approx(12 / (5 + rds), rel=0.01)


def test_mosfet_cortado_nao_conduz():
    els = [El("V", "V1", ("VB", GND), {"V": 12}), El("R", "RL", ("VB", "D"), {"R": 5}),
           El("V", "VG", ("G", GND), {"V": 0}), El("M", "M1", ("D", "G", GND), MOS)]
    s = solve_dc(els)
    assert s.converged and s.v["D"] > 11.99 and abs(s.currents["M1.d"]) < 1e-6


def test_mosfet_diodo_de_corpo_conduz_ao_contrario():
    els = [El("V", "V1", ("VB", GND), {"V": 12}), El("R", "RL", ("VB", "D"), {"R": 100}),
           El("V", "VD", ("D", GND), {"V": -5}), El("M", "M1", ("D", "G", GND), MOS), El("R", "Rg", ("G", GND), {"R": 1e4})]
    s = solve_dc(els)
    assert s.converged and s.currents["M1.d"] < -0.01  # corrente entra pela fonte (diodo de corpo)


def test_regulador_regula_e_cai_com_pouca_entrada():
    def run(vin):
        els = [El("V", "V1", ("VI", GND), {"V": vin}), El("U", "U1", ("VI", "VO"), {"Vset": 15.0}),
               El("R", "RL", ("VO", GND), {"R": 150})]
        return solve_dc(els)

    ok = run(24)
    assert ok.converged and ok.v["VO"] == pytest.approx(15.0, abs=0.1)
    baixa = run(12)  # sem folga (dropout de 2 V): saída acompanha a entrada menos o dropout
    assert baixa.converged and baixa.v["VO"] == pytest.approx(10.0, abs=0.3)
    assert ok.currents["U1.in"] == pytest.approx(ok.currents["U1.out"] + 4e-3, rel=0.02)


def test_regulador_sem_entrada_nao_gera_saida():
    els = [El("V", "V1", ("VI", GND), {"V": 0.0}), El("U", "U1", ("VI", "VO"), {"Vset": 15.0}),
           El("R", "RL", ("VO", GND), {"R": 150})]
    s = solve_dc(els)
    assert s.converged and abs(s.v["VO"]) < 0.05


def _med(circuit, fault, n=12, seed=11):
    rng = np.random.default_rng(seed)
    runs = [simulate(circuit, fault, rng)[0] for _ in range(n)]
    return {k: float(np.mean([r[k] for r in runs])) for k in runs[0]}


def test_inversor_entrada_nominal_e_fusivel_aberto():
    c = get_circuit("inv_entrada")
    ok, f1 = _med(c, None), _med(c, ("F1", "open"))
    assert 22.5 < ok["V(BUS)"] < 23.9 and 14 < ok["V(G)"] < 16 and ok["V(LG)"] < 0.2
    assert 8 < ok["I(F1)"] < 11 and abs(f1["I(F1)"]) < 1e-6
    assert f1["I(F4)"] > 1.25 * ok["I(F4)"]  # os fusíveis vizinhos assumem a corrente


def test_inversor_protecao_de_polaridade_aberta_deixa_carga_sem_terra():
    c = get_circuit("inv_entrada")
    m = _med(c, ("Q1", "open_d"))
    assert m["V(LG)"] > 20 and abs(m["I(F1)"]) < 0.01


def test_inversor_fontes_auxiliares():
    c = get_circuit("inv_fontes_aux")
    ok = _med(c, None)
    assert 14.5 < ok["V(V15)"] < 15.6 and 4.8 < ok["V(V5)"] < 5.2
    assert _med(c, ("U1", "dead"))["V(V15)"] < 0.5
    assert _med(c, ("D1", "open"))["V(V15)"] < 0.1
    assert _med(c, ("U2", "short_io"))["V(V5)"] > 14


def test_inversor_primario_mosfet_em_curto_e_porta_aberta():
    c = get_circuit("inv_primario")
    ok = _med(c, None)
    assert 25 < ok["I(F1)"] < 33 and ok["V(DA)"] < 0.1 and ok["V(GB)"] < 0.01
    assert _med(c, ("M1", "open_g"))["I(F1)"] < 0.01 and _med(c, ("Rg1", "open"))["V(GA)"] < 0.1
    m2 = _med(c, ("M2", "short_ds"))
    assert m2["V(DB)"] < ok["V(DB)"] * 0.2  # o dreno de M2 fica preso no terra


def test_inversor_barramento_alta_tensao():
    c = get_circuit("inv_barramento_hv")
    ok = _med(c, None)
    assert 340 < ok["V(HV)"] < 375 and 2.0 < ok["V(SMP)"] < 2.8
    assert _med(c, ("D1", "open"))["V(HV)"] < 1
    assert _med(c, ("C1", "short"))["V(HV)"] < 5
    assert _med(c, ("Ra", "open"))["V(SMP)"] < 0.1


def test_inversor_ponte_h_estados():
    c = get_circuit("inv_ponte_h")
    ok = _med(c, None)
    assert ok["V(OA)"] > 330 and ok["V(OB)"] < 10 and 4 < ok["I(RL)"] < 8
    assert _med(c, ("Vb1", "zero"))["V(OA)"] < 1  # sem acionador do lado alto, Q1 não liga
    assert _med(c, ("Q2", "short_ds"))["V(OB)"] > 250  # curto de perna: OB sobe ao barramento
    assert _med(c, ("Q4", "open_d"))["I(RL)"] < 0.01


def test_blocos_de_alta_tensao_avisam_o_perigo():
    for cid in ("inv_barramento_hv", "inv_ponte_h"):
        assert "ALTA TENSÃO" in get_circuit(cid).hazard
    assert all(c.hazard == "" for c in all_circuits() if c.nivel != "avancado")


def test_catalogo_do_inversor_tem_falhas_com_texto():
    for cid in ("inv_entrada", "inv_fontes_aux", "inv_primario", "inv_barramento_hv", "inv_ponte_h"):
        cat = get_circuit(cid).catalog()
        assert cat["nivel"] == "avancado" and cat["faults"]
        assert all(f["descricao"] and f["teste_confirmacao"] and f["acao"] for f in cat["faults"])

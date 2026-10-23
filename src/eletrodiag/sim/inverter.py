"""Blocos de um inversor CC-CA senoidal (topologia típica de alta frequência).

IMPORTANTE: são instantâneos em corrente contínua de um semiciclo de operação. Eles representam a
polarização de cada bloco (tensões e correntes médias), não o chaveamento. O esquema do inversor
real do projeto (SOECOPO 15000W) ainda não foi levantado; os valores abaixo seguem a topologia de
referência descrita em docs/inverter_blocks.md e devem ser trocados pelos medidos na placa real.

Blocos: entrada e proteção, fontes auxiliares, primário push-pull, barramento de alta tensão e
ponte H de saída.
"""
from __future__ import annotations

from . import schematics
from .circuits import (COST_V, Circuit, Comp, Obs, _obs_i, _obs_v, _r, _vs, _zd)
from .solver import GND, El

# MOSFET de baixa tensão (vários em paralelo, ~1 mΩ) e de alta tensão (FDP18N50 ou IRF840, ~0,25 Ω)
MOS_LV = {"Kp": 144.0, "Vth": 3.0, "lam": 0.01, "Is_body": 1e-9}
MOS_HV = {"Kp": 0.35, "Vth": 3.5, "lam": 0.005, "Is_body": 1e-11}
RINT_BAT = 0.02  # resistência interna de uma bateria de chumbo (Ω)
V_BAT = 24.0
V_HV = 360.0
HAZ_LV = ("Corrente muito alta: use sempre a bateria desconectada para medir resistência e diodo; para "
          "medir tensão energizada, use fonte limitada em corrente. Nunca ligue a bateria direto sem os fusíveis.")
HAZ_AUX = ("Alimentado pela bateria do inversor: para medir resistência e diodo, desconecte a bateria; para medir "
           "tensão, use fonte limitada em corrente.")
HAZ_HV = ("PERIGO: barramento de ALTA TENSÃO (cerca de 360 V CC) com capacitores que guardam carga. Descarregue "
          "e confirme 0 V antes de tocar. Medição energizada só com ponta de prova CAT III/IV e acompanhamento de "
          "pessoa experiente.")


def _fuse(name, a, b, r=0.0015):
    return [El("R", name, (a, b), {"R": r})]


def _wind(name, a, b, r=0.02):
    return [El("R", name, (a, b), {"R": r})]


def _cap(name, a, b):
    """Capacitor em CC é um circuito aberto (resistência altíssima); as falhas são curto e fuga."""
    return [El("R", name, (a, b), {"R": 1e10})]


def _dio(name, a, k, is_=1e-10, n=1.8):
    return [El("D", name, (a, k), {"Is": is_, "n": n})]


def _mos(name, d, g, s, p):
    return [El("M", name, (d, g, s), dict(p))]


def _reg(name, i, o, vset):
    return [El("U", name, (i, o), {"Vset": vset, "Vdo": 2.0, "rout": 0.2, "iq": 4e-3})]


def _hv(node, label):
    return _obs_v(node, label, " ATENÇÃO: tensão perigosa, use ponta de prova adequada.")


def _obs_dreno(el, label):
    onde = (f"Multímetro em série, escala de 10 A/20 A: com a placa SEM energia, abra o ramo de {label}, intercale o "
            f"instrumento e energize com limitação de corrente (fonte de bancada ou lâmpada em série).")
    return Obs(f"I({el}.d)", "I", f"{el}.d", f"corrente de dreno de {label}", onde, "A", 2.5)


# --------------------------------------------------------------------------- 1. entrada e proteção
def _entrada() -> Circuit:
    def build():
        e = _vs("V1", "BAT", V_BAT, rint=RINT_BAT)
        for i in range(1, 5):
            e += _fuse(f"F{i}", "BAT", "BUS")
        return (e + _r("Rg", "BUS", "G", 10000) + _zd("DZ1", GND, "G", 15.0)
                + _mos("Q1", "LG", "G", GND, MOS_LV) + _r("RL", "BUS", "LG", 0.6) + _cap("C1", "BUS", "LG"))

    comps = [Comp("V1", "V", "24 V (bateria)", "alimentação do inversor")]
    comps += [Comp(f"F{i}", "FUSE", "40 A automotivo", "fusível de entrada em paralelo") for i in range(1, 5)]
    comps += [
        Comp("Rg", "R", "10 kΩ", "polariza a porta da proteção de polaridade"),
        Comp("DZ1", "ZD", "Zener 15 V", "limita a tensão da porta"),
        Comp("Q1", "M", "MOSFET de potência (~1 mΩ)", "proteção contra inversão de polaridade"),
        Comp("RL", "R", "0,6 Ω", "carga equivalente do resto do inversor (~40 A)"),
        Comp("C1", "C", "capacitores de entrada", "filtro de entrada (aberto em CC)"),
    ]
    nl = {"BAT": "BAT (positivo da bateria)", "BUS": "BUS (depois dos fusíveis)", "G": "G (porta de Q1)",
          "LG": "LG (terra da carga, no dreno de Q1)"}
    obs = [_obs_v("BAT", nl["BAT"]), _obs_v("BUS", nl["BUS"]), _obs_v("G", nl["G"]), _obs_v("LG", nl["LG"]),
           _obs_i("F1", "F1", "escala de 10 A/20 A"), _obs_i("F4", "F4", "escala de 10 A/20 A")]
    return Circuit("inv_entrada", "Inversor: entrada, fusíveis e proteção de polaridade",
                   "Bateria de 24 V, quatro fusíveis em paralelo, MOSFET de proteção contra inversão de polaridade e a "
                   "carga do inversor. É onde aparecem os fusíveis queimados.",
                   "avancado", comps, build, obs, nl, schematics.inv_entrada(), HAZ_LV,
                   "Instantâneo em CC. A queda de tensão nos fusíveis é de milivolts: um fusível aberto aparece pela "
                   "corrente dos vizinhos ou, melhor, pelo teste de continuidade com a placa desligada.")


# --------------------------------------------------------------------------- 2. fontes auxiliares
def _fontes_aux() -> Circuit:
    def build():
        return (_vs("V1", "BAT", V_BAT, rint=RINT_BAT) + _dio("D1", "BAT", "VIN", 5e-9, 1.9)
                + _r("Rpd", "VIN", GND, 10e3)  # fuga/descarga do capacitor de entrada (não é um componente testável)
                + _reg("U1", "VIN", "V15", 15.0) + _r("R15", "V15", GND, 150)
                + _reg("U2", "V15", "V5", 5.0) + _r("R5", "V5", GND, 100))

    comps = [
        Comp("V1", "V", "24 V (bateria)", "alimentação"),
        Comp("D1", "DIO", "1N4007 ou similar", "proteção contra polaridade da fonte auxiliar"),
        Comp("U1", "U", "7815", "gera +15 V (drivers de porta)"),
        Comp("R15", "R", "150 Ω", "carga equivalente de +15 V (~100 mA)"),
        Comp("U2", "U", "7805", "gera +5 V (controlador)"),
        Comp("R5", "R", "100 Ω", "carga equivalente de +5 V (~50 mA)"),
    ]
    nl = {"VIN": "VIN (depois de D1)", "V15": "V15 (+15 V)", "V5": "V5 (+5 V)"}
    obs = [_obs_v("VIN", nl["VIN"]), _obs_v("V15", nl["V15"]), _obs_v("V5", nl["V5"]),
           _obs_i("D1", "D1"), _obs_i("R15", "R15"), _obs_i("R5", "R5")]
    return Circuit("inv_fontes_aux", "Inversor: fontes auxiliares de 15 V e 5 V",
                   "Reguladores 7815 e 7805 em cascata que alimentam os drivers de porta e o controlador (EG8010 ou "
                   "similar). Sem elas o inversor liga o display mas não gera saída.",
                   "avancado", comps, build, obs, nl, schematics.inv_fontes_aux(), HAZ_AUX,
                   "Instantâneo em CC. Em modelos de 12 V as fontes auxiliares costumam ser diferentes (o 7815 não "
                   "regula com 12 V de entrada); troque pelo circuito real da placa.")


# --------------------------------------------------------------------------- 3. primário push-pull
def _primario() -> Circuit:
    def build():
        return (_vs("V1", "BAT", V_BAT, rint=RINT_BAT) + _fuse("F1", "BAT", "BUS", 0.0004)
                + _r("RR", "BUS", "CT", 0.8) + _wind("T1a", "CT", "DA") + _wind("T1b", "CT", "DB")
                + _mos("M1", "DA", "GA", GND, MOS_LV) + _mos("M2", "DB", "GB", GND, MOS_LV)
                + _vs("V2", "DRA", 15.0) + _r("Rg1", "DRA", "GA", 22) + _r("Rgs1", "GA", GND, 10000)
                + _r("Rg2", "GB", GND, 22) + _r("Rgs2", "GB", GND, 10000))

    comps = [
        Comp("V1", "V", "24 V (bateria)", "alimentação"),
        Comp("F1", "FUSE", "4 × 40 A em paralelo", "fusíveis de entrada (equivalente)"),
        Comp("RR", "R", "0,8 Ω", "carga refletida do secundário (~30 A)"),
        Comp("T1a", "W", "meio primário A", "enrolamento do transformador"),
        Comp("T1b", "W", "meio primário B", "enrolamento do transformador"),
        Comp("M1", "M", "MOSFETs de potência em paralelo", "chave do semiciclo A (ligada neste estado)"),
        Comp("M2", "M", "MOSFETs de potência em paralelo", "chave do semiciclo B (cortada neste estado)"),
        Comp("V2", "V", "15 V", "nível alto do acionador de M1 (SG3525)"),
        Comp("Rg1", "R", "22 Ω", "resistor de porta de M1"),
        Comp("Rgs1", "R", "10 kΩ", "descarga porta-fonte de M1"),
        Comp("Rg2", "R", "22 Ω", "resistor de porta de M2 (nível baixo)"),
        Comp("Rgs2", "R", "10 kΩ", "descarga porta-fonte de M2"),
    ]
    nl = {"BUS": "BUS (depois do fusível)", "CT": "CT (derivação central do primário)", "DA": "DA (dreno de M1)",
          "DB": "DB (dreno de M2)", "GA": "GA (porta de M1)", "GB": "GB (porta de M2)"}
    obs = [_obs_v("BUS", nl["BUS"]), _obs_v("CT", nl["CT"]), _obs_v("DA", nl["DA"]), _obs_v("DB", nl["DB"]),
           _obs_v("GA", nl["GA"]), _obs_v("GB", nl["GB"]), _obs_i("F1", "F1", "escala de 20 A"),
           _obs_dreno("M1", "M1")]
    return Circuit("inv_primario", "Inversor: primário push-pull (estágio de MOSFETs)",
                   "Meio ciclo do conversor elevador: M1 conduz pela metade A do primário, M2 está cortado. É aqui que "
                   "MOSFETs em curto queimam os fusíveis.",
                   "avancado", comps, build, obs, nl, schematics.inv_primario(), HAZ_LV,
                   "Instantâneo em CC de um semiciclo; o modelo não representa o chaveamento nem o enrolamento "
                   "acoplado. Por isso um MOSFET em curto no lado desligado só aparece parcialmente: o teste de diodo "
                   "com a placa desligada é o complemento necessário.")


# --------------------------------------------------------------------------- 4. barramento HV
def _barramento() -> Circuit:
    def build():
        return (_vs("V1", "SEC", V_HV, rint=2.0) + _dio("D1", "SEC", "HV", 1e-10, 1.8) + _cap("C1", "HV", GND)
                + _r("RL", "HV", GND, 3600) + _r("Ra", "HV", "SMP", 1.5e6) + _r("Rb", "SMP", GND, 10000))

    comps = [
        Comp("V1", "V", "360 V (secundário retificado)", "tensão contínua equivalente do secundário"),
        Comp("D1", "DIO", "HER308 (diodo rápido)", "retificador de alta tensão"),
        Comp("C1", "C", "100 µF / 450 V", "capacitor do barramento"),
        Comp("RL", "R", "3,6 kΩ", "carga equivalente do barramento (~100 mA)"),
        Comp("Ra", "R", "1,5 MΩ", "divisor de realimentação (superior)"),
        Comp("Rb", "R", "10 kΩ", "divisor de realimentação (inferior)"),
    ]
    nl = {"SEC": "SEC (saída do secundário)", "HV": "HV (barramento CC)", "SMP": "SMP (amostra de realimentação)"}
    obs = [_hv("SEC", nl["SEC"]), _hv("HV", nl["HV"]), _obs_v("SMP", nl["SMP"]),
           _obs_i("D1", "D1", "escala de mA"), _obs_i("RL", "RL", "escala de mA")]
    return Circuit("inv_barramento_hv", "Inversor: barramento de alta tensão",
                   "Retificador, capacitor do barramento e divisor que realimenta o controle (TL431 ou optoacoplador). "
                   "O barramento fica em torno de 360 V CC.",
                   "avancado", comps, build, obs, nl, schematics.inv_barramento(), HAZ_HV,
                   "Para versões de 110 V o barramento é menor; confirme pela tensão do capacitor da sua placa. A "
                   "amostra SMP (~2,4 V) é medida com segurança, mas o resto do circuito é energizado em alta tensão.")


# --------------------------------------------------------------------------- 5. ponte H
def _ponte_h() -> Circuit:
    def build():
        e = _vs("V1", "HV", V_HV, rint=1.0)
        e += _mos("Q1", "HV", "G1", "OA", MOS_HV) + _mos("Q2", "HV", "G2", "OB", MOS_HV)
        e += _mos("Q3", "OA", "G3", "SH", MOS_HV) + _mos("Q4", "OB", "G4", "SH", MOS_HV)
        e += [El("V", "Vb1", ("BA", "OA"), {"V": 15.0})]  # alimentação flutuante (bootstrap) do lado alto
        e += _r("Rg1", "BA", "G1", 10) + _r("Rgs1", "G1", "OA", 10000)
        e += _r("Rg2", "G2", "OB", 10) + _r("Rg3", "G3", "SH", 10)
        e += _vs("Vd4", "DR4", 15.0) + _r("Rg4", "DR4", "G4", 10) + _r("Rgs4", "G4", "SH", 10000)
        return e + _r("RL", "OA", "OB", 60) + _r("Rsh", "SH", GND, 0.01)

    comps = [
        Comp("V1", "V", "360 V (barramento)", "alimentação da ponte"),
        Comp("Vb1", "V", "15 V flutuante", "alimenta o acionador do lado alto (bootstrap)"),
        Comp("Vd4", "V", "15 V", "acionador do lado baixo"),
        Comp("Q1", "M", "FDP18N50 ou IRF840", "lado alto A (ligado neste estado)"),
        Comp("Q2", "M", "FDP18N50 ou IRF840", "lado alto B (cortado)"),
        Comp("Q3", "M", "FDP18N50 ou IRF840", "lado baixo A (cortado)"),
        Comp("Q4", "M", "FDP18N50 ou IRF840", "lado baixo B (ligado neste estado)"),
        Comp("Rg1", "R", "10 Ω", "resistor de porta de Q1"),
        Comp("Rg2", "R", "10 Ω", "resistor de porta de Q2"),
        Comp("Rg3", "R", "10 Ω", "resistor de porta de Q3"),
        Comp("Rg4", "R", "10 Ω", "resistor de porta de Q4"),
        Comp("Rgs1", "R", "10 kΩ", "descarga porta-fonte de Q1"),
        Comp("Rgs4", "R", "10 kΩ", "descarga porta-fonte de Q4"),
        Comp("RL", "R", "60 Ω", "carga equivalente (filtro LC e saída)"),
        Comp("Rsh", "R", "10 mΩ", "shunt de medição de corrente"),
    ]
    nl = {"HV": "HV (barramento CC)", "OA": "OA (saída A da ponte)", "OB": "OB (saída B da ponte)",
          "SH": "SH (fontes dos MOSFETs de baixo, topo do shunt)", "G1": "G1 (porta de Q1)", "G4": "G4 (porta de Q4)"}
    obs = [_hv("HV", nl["HV"]), _hv("OA", nl["OA"]), _hv("OB", nl["OB"]), _obs_v("SH", nl["SH"]),
           _hv("G1", nl["G1"]), _obs_v("G4", nl["G4"]), _obs_i("RL", "RL", "escala de 10 A")]
    return Circuit("inv_ponte_h", "Inversor: ponte H de saída",
                   "Quatro MOSFETs de alta tensão em ponte, com shunt de corrente. Neste estado a corrente vai por "
                   "Q1, a carga e Q4.",
                   "avancado", comps, build, obs, nl, schematics.inv_ponte_h(), HAZ_HV,
                   "Instantâneo em CC de um semiciclo; não representa o SPWM nem o tempo morto. A medição de G1 e OA "
                   "acontece em alta tensão em relação ao terra.")


def inverter_circuits() -> list[Circuit]:
    return [_entrada(), _fontes_aux(), _primario(), _barramento(), _ponte_h()]

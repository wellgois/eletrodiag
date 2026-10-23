"""Biblioteca de circuitos curados, modelo de falhas e variação Monte Carlo.

Cada circuito é descrito por componentes, nós, observáveis (o que o estudante pode medir)
e textos didáticos. O catálogo completo é exportado como JSON para a camada bronze.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .solver import GND, El, solve_dc
from . import schematics

RINT = 1.0  # resistência interna da fonte (Ω): fontes reais têm limite de corrente
LED_P = {"Is": 1e-18, "n": 2.0}
BJT_P = {"Is": 1e-14, "bf": 200.0, "br": 2.0}
COST_V, COST_I = 1.0, 2.5  # custo relativo de uma medição (corrente exige abrir o ramo)

MODES = {
    "R": ["open", "short", "high", "low"],
    "LED": ["open", "short"],
    "ZD": ["open", "short", "vz_low"],
    "Q": ["open_b", "open_c", "open_e", "short_ce", "short_be", "short_cb", "beta_low"],
    "V": ["sag", "zero"],
    "DIO": ["open", "short"],
    "FUSE": ["open", "resist"],
    "W": ["open"],
    "C": ["short", "leaky"],
    "U": ["dead", "short_io", "vout_low"],
    "M": ["open_d", "open_s", "open_g", "short_ds", "short_gs", "short_dg", "rds_high"],
}
# Pesos a priori (hipótese de trabalho: aberto é o defeito mais comum). Devem ser substituídos
# por frequências reais coletadas em campo (ver docs/assumptions.md).
PRIOR_W = {
    "open": 3.0, "short": 1.5, "high": 1.0, "low": 1.0, "vz_low": 1.0,
    "open_b": 1.0, "open_c": 1.0, "open_e": 1.0, "short_ce": 1.5, "short_be": 1.0,
    "short_cb": 1.0, "beta_low": 1.0, "sag": 1.0, "zero": 1.0,
    # blocos do inversor (palpites informados: MOSFET em curto é a falha mais relatada em reparos)
    "resist": 1.0, "leaky": 1.0, "dead": 1.5, "short_io": 1.0, "vout_low": 1.0,
    "open_d": 1.0, "open_s": 1.0, "open_g": 1.0, "short_ds": 3.0, "short_gs": 1.0, "short_dg": 0.5,
    "rds_high": 0.5,
}

KIND_NAME = {"R": "Resistor", "LED": "LED", "ZD": "Diodo zener", "Q": "Transistor NPN", "V": "Fonte",
             "DIO": "Diodo retificador", "FUSE": "Fusível", "W": "Enrolamento", "C": "Capacitor",
             "U": "Regulador linear", "M": "MOSFET canal N"}

DESC = {
    ("R", "open"): "{c} aberto (não conduz): o ramo fica sem corrente.",
    ("R", "short"): "{c} em curto (~0 Ω): o ramo conduz corrente excessiva.",
    ("R", "high"): "{c} com valor muito acima do nominal ({n}): corrente do ramo reduzida.",
    ("R", "low"): "{c} com valor muito abaixo do nominal ({n}): corrente do ramo aumentada.",
    ("LED", "open"): "{c} aberto: nenhuma corrente passa pelo componente.",
    ("LED", "short"): "{c} em curto: tensão sobre o componente ~0 V; a corrente só é limitada pelo resto do circuito.",
    ("ZD", "open"): "{c} aberto: sem regulação, a tensão sobe até o valor do divisor/carga.",
    ("ZD", "short"): "{c} em curto: o nó fica preso em ~0 V.",
    ("ZD", "vz_low"): "{c} com tensão zener bem abaixo do nominal (componente degradado).",
    ("Q", "open_b"): "Base de {c} desconectada: o transistor não liga.",
    ("Q", "open_c"): "Coletor de {c} aberto: não há corrente de coletor.",
    ("Q", "open_e"): "Emissor de {c} aberto: não há corrente de emissor.",
    ("Q", "short_ce"): "Coletor e emissor de {c} em curto: o transistor vira um fio entre C e E.",
    ("Q", "short_be"): "Base e emissor de {c} em curto: transistor sempre cortado.",
    ("Q", "short_cb"): "Coletor e base de {c} em curto: o transistor opera como diodo.",
    ("Q", "beta_low"): "Ganho (hFE) de {c} muito baixo: transistor degradado, satura mal ou amplifica pouco.",
    ("V", "sag"): "{c} afundando (~50% da tensão nominal): fonte fraca, sobrecarregada ou bateria descarregada.",
    ("V", "zero"): "{c} sem tensão: sem alimentação (fusível, cabo, chave ou regulador de entrada).",
    ("DIO", "open"): "{c} aberto: bloqueia a corrente nos dois sentidos, o ramo fica sem alimentação.",
    ("DIO", "short"): "{c} em curto: conduz nos dois sentidos, sem retificação nem proteção.",
    ("FUSE", "open"): "{c} aberto (queimado): o ramo perde a corrente que ele conduzia.",
    ("FUSE", "resist"): "{c} com contato resistivo (oxidado ou mal soldado): queda de tensão e aquecimento.",
    ("W", "open"): "{c} aberto: o enrolamento do transformador não conduz.",
    ("C", "short"): "{c} em curto: o barramento é puxado para o terra e a fonte entra em sobrecorrente.",
    ("C", "leaky"): "{c} com fuga alta (centenas de ohms): carrega o barramento e aquece.",
    ("U", "dead"): "{c} sem saída: o regulador não entrega tensão (queimado ou protegido).",
    ("U", "short_io"): "{c} com entrada e saída em curto: a tensão de entrada passa direto para as cargas.",
    ("U", "vout_low"): "{c} com saída bem abaixo do nominal (regulador degradado).",
    ("M", "open_d"): "Dreno de {c} desconectado: o MOSFET não conduz corrente de dreno.",
    ("M", "open_s"): "Fonte de {c} desconectada: não há caminho de corrente pelo MOSFET.",
    ("M", "open_g"): "Porta de {c} desconectada (flutuando): o MOSFET não liga.",
    ("M", "short_ds"): "Dreno e fonte de {c} em curto: o MOSFET vira um fio, sempre conduzindo (falha mais comum em inversores).",
    ("M", "short_gs"): "Porta e fonte de {c} em curto: o MOSFET nunca liga e o driver é sobrecarregado.",
    ("M", "short_dg"): "Dreno e porta de {c} em curto: a tensão do dreno aparece na porta e pode destruir o driver.",
    ("M", "rds_high"): "{c} degradado: resistência de condução muito alta, queda de tensão e aquecimento.",
}
TEST = {
    "R": "Com o circuito desligado, meça {c} fora do circuito (um terminal levantado) em Ω e compare com {n}.",
    "LED": "Use o teste de diodo do multímetro: deve conduzir em um sentido e bloquear no outro. "
           "Sem condução = aberto; condução nos dois sentidos = curto.",
    "ZD": "Teste de diodo: ~0,6-0,7 V no sentido direto e bloqueio no reverso. Para o valor Vz, "
          "alimente por um resistor e meça a tensão sobre o zener.",
    "Q": "Teste de diodo nas junções base-emissor e base-coletor (NPN: ponta vermelha na base): ~0,6-0,7 V; "
         "invertendo, sem condução. Coletor-emissor não deve conduzir nos dois sentidos.",
    "V": "Meça a saída da fonte sem carga e verifique fusível, cabo, chave e conectores.",
    "DIO": "Teste de diodo (com a placa sem energia e capacitores descarregados): ~0,5-0,9 V no sentido direto e "
           "bloqueio no reverso. Conduz nos dois sentidos = curto; não conduz = aberto.",
    "FUSE": "Sem energia, meça a continuidade de {c} (retire um terminal se houver fusíveis em paralelo): "
            "deve ser quase 0 Ω. Aberto = queimado.",
    "W": "Sem energia, meça a resistência do enrolamento {c}: deve ser de poucos miliohms. Infinita = aberto.",
    "C": "Sem energia e com o capacitor descarregado, meça a resistência: deve subir lentamente e passar de "
         "centenas de kΩ. Poucos ohms = curto ou fuga.",
    "U": "Com o circuito desligado, meça a resistência entre os pinos (entrada, saída e GND) sem carga: não deve "
         "haver curto. Depois alimente e compare a saída com o valor nominal.",
    "M": "Sem energia e com os capacitores descarregados, use o teste de diodo: dreno-fonte conduz só no sentido do "
         "diodo de corpo (~0,5 V) e porta-fonte não conduz. Curto dreno-fonte nos dois sentidos = MOSFET queimado. "
         "Se houver MOSFETs em paralelo, solte uma perna de cada um para achar qual é.",
}
ACTION = {"V": "Verificar a alimentação ({c})", "default": "Substituir {c}",
          "FUSE": "Antes de trocar {c}, ache o que causou a sobrecorrente (MOSFET em curto é a causa mais comum)"}


@dataclass
class Comp:
    id: str
    kind: str  # R, LED, ZD, Q, V, DIO, FUSE, W, C, U, M
    nominal: str
    funcao: str


@dataclass
class Obs:
    id: str
    kind: str  # 'V' (tensão de nó) ou 'I' (corrente em elemento)
    ref: str  # nó (V) ou elemento (I)
    label: str
    onde: str
    unit: str
    cost: float


# --------------------------------------------------------------------------- construtores
def _vs(name, node, volts, rint=RINT):
    return [
        El("V", name, (f"{name}#int", GND), {"V": volts}),
        El("R", f"{name}.rint", (f"{name}#int", node), {"R": rint}),
    ]


def _r(name, a, b, ohms):
    return [El("R", name, (a, b), {"R": ohms})]


def _led(name, a, k):
    return [El("D", name, (a, k), dict(LED_P))]


def _zd(name, a, k, vz):
    return [El("D", name, (a, k), {"Is": 1e-14, "n": 1.0, "vz": vz})]


def _npn(name, c, b, e):
    return [El("Q", name, (c, b, e), dict(BJT_P))]


def _obs_v(node, label, onde_extra=""):
    onde = f"Ponta vermelha em {label}; ponta preta no GND (terra)." + onde_extra
    return Obs(f"V({node})", "V", node, label, onde, "V", COST_V)


def _obs_i(el, label, escala="escala de mA"):
    onde = (f"Multímetro em série, {escala}: abra o ramo de {label}, intercale o instrumento "
            f"(vermelha no lado da fonte) e meça a corrente por {label}.")
    return Obs(f"I({el})", "I", el, f"corrente em {label}", onde, "A", COST_I)


class Circuit:
    def __init__(self, id, nome, descricao, nivel, comps, builder, observables, node_labels, svg,
                 hazard="", nota=""):
        self.id, self.nome, self.descricao, self.nivel = id, nome, descricao, nivel
        self.hazard, self.nota = hazard, nota  # aviso de segurança e limites do modelo (texto)
        self.comps, self._builder, self.observables = comps, builder, observables
        self.node_labels, self.svg = node_labels, svg

    def nominal_elements(self) -> list[El]:
        return self._builder()

    def faults(self) -> list[tuple[str, str]]:
        return [(c.id, m) for c in self.comps for m in MODES[c.kind]]

    def comp(self, cid) -> Comp:
        return next(c for c in self.comps if c.id == cid)

    def priors(self) -> dict:
        w = {f"{c}:{m}": PRIOR_W[m] for c, m in self.faults()}
        s = sum(w.values())
        return {k: v / s for k, v in w.items()}

    def catalog(self) -> dict:
        pri = self.priors()
        faults = []
        for cid, mode in self.faults():
            c = self.comp(cid)
            fid = f"{cid}:{mode}"
            faults.append({
                "fault_id": fid, "component_id": cid, "mode": mode, "prior": pri[fid],
                "descricao": DESC[(c.kind, mode)].format(c=cid, n=c.nominal),
                "teste_confirmacao": TEST[c.kind].format(c=cid, n=c.nominal),
                "acao": (ACTION.get(c.kind) or ACTION["default"]).format(c=cid),
            })
        return {
            "circuit_id": self.id, "nome": self.nome, "descricao": self.descricao, "nivel": self.nivel,
            "components": [c.__dict__ for c in self.comps],
            "observables": [o.__dict__ for o in self.observables],
            "node_labels": self.node_labels, "svg": self.svg, "faults": faults,
            "hazard": self.hazard, "nota": self.nota,
        }


# --------------------------------------------------------------------------- definições
def _led_resistor() -> Circuit:
    def build():
        return _vs("V1", "VCC", 5.0) + _r("R1", "VCC", "A", 330) + _led("D1", "A", GND)

    comps = [
        Comp("V1", "V", "5 V", "alimentação"),
        Comp("R1", "R", "330 Ω", "limita a corrente do LED"),
        Comp("D1", "LED", "LED vermelho", "indicador luminoso"),
    ]
    nl = {"VCC": "VCC (+5 V)", "A": "A (entre R1 e o LED)"}
    obs = [_obs_v("VCC", nl["VCC"]), _obs_v("A", nl["A"]), _obs_i("R1", "R1")]
    return Circuit("led_resistor", "LED com resistor limitador",
                   "O circuito mais básico: fonte de 5 V, resistor de 330 Ω e LED vermelho.",
                   "iniciante", comps, build, obs, nl, schematics.led_resistor())


def _zener_shunt() -> Circuit:
    def build():
        return (_vs("V1", "VCC", 12.0) + _r("Rs", "VCC", "Z", 470) + _zd("DZ1", GND, "Z", 5.1)
                + _r("RL", "Z", GND, 1000))

    comps = [
        Comp("V1", "V", "12 V", "alimentação"),
        Comp("Rs", "R", "470 Ω", "resistor série do regulador"),
        Comp("DZ1", "ZD", "Zener 5,1 V", "referência de tensão"),
        Comp("RL", "R", "1 kΩ", "carga"),
    ]
    nl = {"VCC": "VCC (+12 V)", "Z": "Z (saída regulada)"}
    obs = [_obs_v("VCC", nl["VCC"]), _obs_v("Z", nl["Z"]), _obs_i("Rs", "Rs"), _obs_i("RL", "RL")]
    return Circuit("zener_shunt", "Regulador zener (shunt)",
                   "Regulador paralelo: resistor série, zener de 5,1 V e carga de 1 kΩ.",
                   "iniciante", comps, build, obs, nl, schematics.zener_shunt())


def _bjt_chave() -> Circuit:
    def build():
        return (_vs("V1", "VCC", 9.0) + _vs("V2", "VIN", 5.0) + _r("Rb", "VIN", "B", 4700)
                + _r("Rc", "VCC", "N1", 470) + _led("D1", "N1", "C") + _npn("Q1", "C", "B", GND))

    comps = [
        Comp("V1", "V", "9 V", "alimentação da carga"),
        Comp("V2", "V", "5 V", "sinal de comando"),
        Comp("Rb", "R", "4,7 kΩ", "limita a corrente de base"),
        Comp("Rc", "R", "470 Ω", "limita a corrente do LED"),
        Comp("D1", "LED", "LED vermelho", "carga"),
        Comp("Q1", "Q", "NPN (BC548)", "chave"),
    ]
    nl = {"VCC": "VCC (+9 V)", "VIN": "VIN (comando +5 V)", "B": "B (base de Q1)",
          "N1": "N1 (entre Rc e o LED)", "C": "C (coletor de Q1)"}
    obs = [_obs_v("VCC", nl["VCC"]), _obs_v("VIN", nl["VIN"]), _obs_v("B", nl["B"]),
           _obs_v("N1", nl["N1"]), _obs_v("C", nl["C"]), _obs_i("Rc", "Rc")]
    return Circuit("bjt_chave_led", "Transistor como chave (aciona LED)",
                   "Um sinal de 5 V na base liga o transistor, que acende o LED alimentado por 9 V.",
                   "intermediario", comps, build, obs, nl, schematics.bjt_chave())


def _emissor_comum() -> Circuit:
    def build():
        return (_vs("V1", "VCC", 12.0) + _r("R1", "VCC", "B", 47000) + _r("R2", "B", GND, 10000)
                + _r("RC", "VCC", "C", 2200) + _r("RE", "E", GND, 1000) + _npn("Q1", "C", "B", "E"))

    comps = [
        Comp("V1", "V", "12 V", "alimentação"),
        Comp("R1", "R", "47 kΩ", "divisor de polarização (superior)"),
        Comp("R2", "R", "10 kΩ", "divisor de polarização (inferior)"),
        Comp("RC", "R", "2,2 kΩ", "carga de coletor"),
        Comp("RE", "R", "1 kΩ", "estabilização de emissor"),
        Comp("Q1", "Q", "NPN (BC548)", "amplificador"),
    ]
    nl = {"VCC": "VCC (+12 V)", "B": "B (base)", "E": "E (emissor)", "C": "C (coletor)"}
    obs = [_obs_v("VCC", nl["VCC"]), _obs_v("B", nl["B"]), _obs_v("E", nl["E"]),
           _obs_v("C", nl["C"]), _obs_i("RC", "RC")]
    return Circuit("emissor_comum", "Emissor comum (polarização CC)",
                   "Etapa amplificadora com divisor de base e resistor de emissor: ponto de operação em CC.",
                   "intermediario", comps, build, obs, nl, schematics.emissor_comum())


def _reg_serie() -> Circuit:
    def build():
        return (_vs("V1", "VCC", 12.0) + _r("Rz", "VCC", "Z", 1000) + _zd("DZ1", GND, "Z", 6.8)
                + _npn("Q1", "VCC", "Z", "OUT") + _r("RL", "OUT", GND, 220))

    comps = [
        Comp("V1", "V", "12 V", "alimentação"),
        Comp("Rz", "R", "1 kΩ", "polariza o zener e a base"),
        Comp("DZ1", "ZD", "Zener 6,8 V", "referência de tensão"),
        Comp("Q1", "Q", "NPN (BC548)", "transistor de passagem"),
        Comp("RL", "R", "220 Ω", "carga"),
    ]
    nl = {"VCC": "VCC (+12 V)", "Z": "Z (base de Q1 / zener)", "OUT": "OUT (saída regulada)"}
    obs = [_obs_v("VCC", nl["VCC"]), _obs_v("Z", nl["Z"]), _obs_v("OUT", nl["OUT"]),
           _obs_i("Rz", "Rz"), _obs_i("RL", "RL")]
    return Circuit("reg_serie_zener", "Regulador série com zener e transistor",
                   "Seguidor de emissor com referência zener de 6,8 V: saída próxima de 6,1 V.",
                   "intermediario", comps, build, obs, nl, schematics.reg_serie())


def basic_circuits() -> list[Circuit]:
    return [_led_resistor(), _zener_shunt(), _bjt_chave(), _emissor_comum(), _reg_serie()]


def all_circuits() -> list[Circuit]:
    from . import inverter  # importação tardia: inverter.py usa os helpers deste módulo

    return basic_circuits() + inverter.inverter_circuits()


def get_circuit(cid: str) -> Circuit:
    return next(c for c in all_circuits() if c.id == cid)


# --------------------------------------------------------------------------- variação e falhas
def vary(elements: list[El], rng: np.random.Generator) -> list[El]:
    """Aplica tolerâncias de componentes (Monte Carlo)."""
    out = []
    for e in elements:
        e = e.copy()
        if e.kind == "R" and not e.name.endswith(".rint"):
            e.p["R"] *= rng.uniform(0.95, 1.05)
        elif e.kind == "V":
            e.p["V"] *= rng.uniform(0.98, 1.02)
        elif e.kind == "D":
            e.p["Is"] *= math.exp(rng.normal(0, 0.8))
            if "vz" in e.p:
                e.p["vz"] *= rng.uniform(0.95, 1.05)
        elif e.kind == "Q":
            e.p["bf"] *= math.exp(rng.normal(0, 0.25))
            e.p["Is"] *= math.exp(rng.normal(0, 0.5))
        elif e.kind == "M":
            e.p["Kp"] *= math.exp(rng.normal(0, 0.12))
            e.p["Vth"] += rng.normal(0, 0.12)
        elif e.kind == "U":
            e.p["Vset"] *= rng.uniform(0.96, 1.04)
        out.append(e)
    return out


def inject(elements: list[El], comp_id: str, mode: str) -> list[El]:
    """Injeta uma falha no componente indicado (aberto, curto, deriva etc.)."""
    els = [e.copy() for e in elements]
    target = next(e for e in els if e.name == comp_id)
    extra: list[El] = []
    if target.kind == "R":
        if mode == "resist":  # contato resistivo (fusível oxidado)
            target.p["R"] = max(target.p["R"] * 40.0, 0.06)
        elif mode == "leaky":  # capacitor com fuga
            target.p["R"] = 200.0
        else:
            target.p["R"] = {"open": 1e9, "short": 0.01}.get(mode) or target.p["R"] * {"high": 3.0, "low": 1 / 3}[mode]
    elif target.kind == "V":
        target.p["V"] *= 0.5 if mode == "sag" else 0.0
    elif target.kind == "D":
        a, k = target.nodes
        if mode == "open":
            target.nodes = (f"{comp_id}#a", k)
        elif mode == "short":
            extra.append(El("R", f"{comp_id}.short", (a, k), {"R": 0.01}))
        elif mode == "vz_low":
            target.p["vz"] *= 0.6
    elif target.kind == "Q":
        c, b, e = target.nodes
        if mode in ("open_b", "open_c", "open_e"):
            pin = {"open_b": 1, "open_c": 0, "open_e": 2}[mode]
            nodes = list(target.nodes)
            nodes[pin] = f"{comp_id}#{mode[-1]}"
            target.nodes = tuple(nodes)
            # pino flutuante: fuga de 1 GΩ para o terra mantém o sistema bem condicionado
            extra.append(El("R", f"{comp_id}.fl", (nodes[pin], GND), {"R": 1e9}))
        elif mode == "short_ce":
            extra.append(El("R", f"{comp_id}.s", (c, e), {"R": 0.01}))
        elif mode == "short_be":
            extra.append(El("R", f"{comp_id}.s", (b, e), {"R": 0.01}))
        elif mode == "short_cb":
            extra.append(El("R", f"{comp_id}.s", (c, b), {"R": 0.01}))
        elif mode == "beta_low":
            target.p["bf"] = 8.0
    elif target.kind == "M":
        d, g, sn = target.nodes
        if mode in ("open_d", "open_g", "open_s"):
            pin = {"open_d": 0, "open_g": 1, "open_s": 2}[mode]
            nodes = list(target.nodes)
            nodes[pin] = f"{comp_id}#{mode[-1]}"
            target.nodes = tuple(nodes)
            extra.append(El("R", f"{comp_id}.fl", (nodes[pin], GND), {"R": 1e9}))
        elif mode == "short_ds":
            extra.append(El("R", f"{comp_id}.s", (d, sn), {"R": 0.001}))
        elif mode == "short_gs":
            extra.append(El("R", f"{comp_id}.s", (g, sn), {"R": 0.01}))
        elif mode == "short_dg":
            extra.append(El("R", f"{comp_id}.s", (d, g), {"R": 0.01}))
        elif mode == "rds_high":
            target.p["Kp"] /= 25.0
    elif target.kind == "U":
        i, o = target.nodes
        if mode == "dead":
            target.p["Vset"] = 0.0
        elif mode == "short_io":
            extra.append(El("R", f"{comp_id}.s", (i, o), {"R": 0.01}))
        elif mode == "vout_low":
            target.p["Vset"] *= 0.6
    return els + extra


def measure_all(circuit: Circuit, elements: list[El]):
    """Resolve o circuito e devolve (valores por observável em V/A, solução)."""
    sol = solve_dc(elements)
    values = {}
    if sol.converged:
        for o in circuit.observables:
            values[o.id] = sol.v[o.ref] if o.kind == "V" else sol.currents[o.ref]
    return values, sol


METER_R = 10e6  # impedância de entrada do multímetro (10 MΩ) nos nós de medição


def simulate(circuit: Circuit, fault: tuple[str, str] | None, rng: np.random.Generator):
    els = vary(circuit.nominal_elements(), rng)
    if fault is not None:
        els = inject(els, *fault)
    # O multímetro carrega os nós de tensão; isso evita leituras irreais em nós quase flutuantes.
    for o in circuit.observables:
        if o.kind == "V":
            els.append(El("R", f"M.{o.ref}", (o.ref, GND), {"R": METER_R}))
    return measure_all(circuit, els)

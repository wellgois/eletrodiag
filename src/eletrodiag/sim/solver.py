"""Solver DC não linear (Análise Nodal Modificada + Newton-Raphson).

Suporta: resistor (R), fonte de tensão com resistência interna (V), diodo/LED/zener (D),
transistor bipolar NPN no modelo Ebers-Moll (Q), MOSFET de canal N com diodo de corpo (M) e
regulador linear de três terminais, em modelo comportamental (U).

Foi escrito para ser pequeno, legível e sem dependências além do NumPy: o objetivo do
projeto é gerar assinaturas de falha, não substituir um SPICE completo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

VT = 0.025852  # tensão térmica a ~300 K
GMIN = 1e-12  # condutância mínima de cada nó para o terra (evita matriz singular)
GND = "GND"
STEP_LIMIT = 1.0  # passo máximo de tensão por iteração de Newton (amortecimento)


@dataclass
class El:
    """Elemento de circuito.

    kind: 'R', 'V', 'D' (diodo/LED/zener), 'Q' (NPN), 'M' (MOSFET N) ou 'U' (regulador linear).
    nodes: R/V/D -> (a, b); V -> (+, -); D -> (anodo, catodo); Q -> (coletor, base, emissor);
           M -> (dreno, porta, fonte); U -> (entrada, saída); o terceiro pino do regulador é o GND.
    p: parâmetros do modelo (ver funções _diode, _bjt, _mosfet e _regulator).
    """

    kind: str
    name: str
    nodes: tuple
    p: dict = field(default_factory=dict)

    def copy(self) -> "El":
        return El(self.kind, self.name, tuple(self.nodes), dict(self.p))


@dataclass
class Solution:
    v: dict  # tensão por nó (GND = 0)
    currents: dict  # corrente por elemento (R: a->b, D: anodo->catodo)
    converged: bool
    iterations: int


def _exp(x: float) -> tuple[float, float]:
    """exp(x) com extensão linear acima de 40 para evitar overflow; devolve (f, df/dx)."""
    if x > 40.0:
        e40 = math.exp(40.0)
        return e40 * (1.0 + (x - 40.0)), e40
    e = math.exp(x)
    return e, e


def _diode(v: float, p: dict) -> tuple[float, float]:
    """Corrente (anodo->catodo) e condutância dinâmica de um diodo/LED/zener."""
    is_, n = p["Is"], p["n"]
    f, df = _exp(v / (n * VT))
    i = is_ * (f - 1.0)
    g = is_ * df / (n * VT)
    vz = p.get("vz")
    if vz is not None:  # ruptura reversa (zener): vz é a tensão reversa na corrente de teste
        nz = p.get("nz", 1.5)
        itest = p.get("itest", 5e-3)
        fz, dfz = _exp((-v - vz) / (nz * VT))
        i -= itest * fz
        g += itest * dfz / (nz * VT)
    return i + GMIN * v, g + GMIN


def _bjt(vb: float, vc: float, ve: float, p: dict):
    """Ebers-Moll NPN. Devolve correntes que ENTRAM em (c, b, e) e a matriz de condutâncias 3x3."""
    is_, bf, br = p["Is"], p["bf"], p["br"]
    vbe, vbc = vb - ve, vb - vc
    ef, def_ = _exp(vbe / VT)
    er, der = _exp(vbc / VT)
    i_f, i_r = is_ * (ef - 1.0), is_ * (er - 1.0)
    gf, gr = is_ * def_ / VT, is_ * der / VT
    ic = i_f - i_r - i_r / br
    ib = i_f / bf + i_r / br
    ie = -(ic + ib)
    # derivadas em relação a vbe e vbc
    dic_dvbe, dic_dvbc = gf, -gr - gr / br
    dib_dvbe, dib_dvbc = gf / bf, gr / br
    # derivadas em relação às tensões de terminal (Vc, Vb, Ve)
    gic = np.array([-dic_dvbc, dic_dvbe + dic_dvbc, -dic_dvbe])
    gib = np.array([-dib_dvbc, dib_dvbe + dib_dvbc, -dib_dvbe])
    gie = -(gic + gib)
    return np.array([ic, ib, ie]), np.vstack([gic, gib, gie])


def _softplus(x: float, k: float) -> tuple[float, float]:
    """Máximo suave de x e 0 com escala k; devolve (valor, derivada). Evita descontinuidade no corte."""
    z = x / k
    if z > 40.0:
        return x, 1.0
    if z < -40.0:
        return 0.0, 0.0
    e = math.exp(z)
    return k * math.log1p(e), e / (1.0 + e)


def _mos_channel(vgs: float, vds: float, p: dict) -> tuple[float, float, float]:
    """Canal NMOS (lei quadrática com sublimiar suave), vds >= 0. Devolve (id, gm, gds)."""
    kp, vth, lam = p["Kp"], p["Vth"], p.get("lam", 0.01)
    veff, dveff = _softplus(vgs - vth, 0.08)
    clm = 1.0 + lam * vds
    if vds < veff:  # região de triodo
        core = veff * vds - 0.5 * vds * vds
        return kp * core * clm, kp * vds * dveff * clm, kp * (veff - vds) * clm + kp * core * lam
    core = 0.5 * veff * veff  # saturação
    return kp * core * clm, kp * veff * dveff * clm, kp * core * lam


def _mosfet(vd: float, vg: float, vs: float, p: dict):
    """MOSFET N com diodo de corpo (fonte -> dreno). Devolve a corrente que entra no dreno e as
    derivadas em relação a (Vd, Vg, Vs)."""
    vds = vd - vs
    if vds >= 0.0:
        i, gm, gds = _mos_channel(vg - vs, vds, p)
        d_vd, d_vg, d_vs = gds, gm, -(gm + gds)
    else:  # conduz ao contrário: troca os papéis de dreno e fonte
        i, gm, gds = _mos_channel(vg - vd, -vds, p)
        i = -i
        d_vd, d_vg, d_vs = gm + gds, -gm, -gds
    ib, gb = _diode(vs - vd, {"Is": p.get("Is_body", 1e-11), "n": p.get("n_body", 1.2)})
    return i - ib, np.array([d_vd + gb, d_vg, d_vs - gb])


def _regulator(vin: float, vout: float, p: dict):
    """Regulador linear comportamental (78xx): alvo = min(Vset, Vin - Vdo), saída com resistência
    finita e sem drenar corrente da carga. A corrente quiescente some quando a entrada cai a zero.
    Devolve (corrente que sai da entrada, suas derivadas em (Vin, Vout), corrente injetada na saída,
    suas derivadas em (Vin, Vout))."""
    vset, vdo = p["Vset"], p.get("Vdo", 2.0)
    g, iq, eps = 1.0 / p.get("rout", 0.2), p.get("iq", 4e-3), 0.01

    def target(v):
        b = v - vdo
        t = 0.5 * (vset + b - math.sqrt((vset - b) ** 2 + 0.01))  # mínimo suave
        return 0.5 * (t + math.sqrt(t * t + 0.01))  # nunca abaixo de zero

    t = target(vin)
    dt = (target(vin + 1e-6) - target(vin - 1e-6)) / 2e-6
    x = t - vout
    r = math.sqrt(x * x + eps * eps)
    i0 = g * 0.5 * (x + r)  # corrente que o regulador tentaria injetar na saída
    d = g * 0.5 * (1.0 + x / r)
    th = math.tanh((vin - 1.0) / 0.3)  # o regulador só "acorda" com ~1 V na entrada
    av, d_av = 0.5 * (1.0 + th), (1.0 - th * th) / 0.6  # sem tensão na entrada não há corrente alguma
    i_out = av * i0
    g_out = np.array([av * d * dt + d_av * i0, -av * d])
    iq_eff, d_iq = iq * av, iq * d_av
    gl = 1e-6  # fuga de entrada: mantém a entrada flutuante perto de 0 V (em vez de ir a valores negativos)
    return i_out + iq_eff + gl * vin, g_out + np.array([d_iq + gl, 0.0]), i_out, g_out


def solve_dc(elements: list[El], max_iter: int = 400) -> Solution:
    nodes = sorted({n for e in elements for n in e.nodes if n != GND})
    idx = {n: i for i, n in enumerate(nodes)}
    vsrc = [e for e in elements if e.kind == "V"]
    n_nodes, n_v = len(nodes), len(vsrc)
    size = n_nodes + n_v

    def ix(n):
        return idx[n] if n != GND else None

    # Parte linear (R e V) montada uma única vez; a parte não linear é re-estampada a cada iteração.
    a_lin = np.zeros((size, size))
    b_lin = np.zeros(size)
    for i in range(n_nodes):
        a_lin[i, i] += GMIN
    for e in elements:
        if e.kind == "R":
            g = 1.0 / e.p["R"]
            a, b = ix(e.nodes[0]), ix(e.nodes[1])
            if a is not None:
                a_lin[a, a] += g
            if b is not None:
                a_lin[b, b] += g
            if a is not None and b is not None:
                a_lin[a, b] -= g
                a_lin[b, a] -= g
    v_index = {}
    for j, e in enumerate(vsrc):
        k = n_nodes + j
        v_index[e.name] = k
        p_, n_ = ix(e.nodes[0]), ix(e.nodes[1])
        if p_ is not None:
            a_lin[p_, k] += 1.0
            a_lin[k, p_] += 1.0
        if n_ is not None:
            a_lin[n_, k] -= 1.0
            a_lin[k, n_] -= 1.0

    nonlin = [e for e in elements if e.kind in ("D", "Q", "M", "U")]
    v_max = max((abs(e.p["V"]) for e in vsrc), default=0.0)
    step_limit = max(STEP_LIMIT, v_max / 30.0)  # circuitos de alta tensão precisam de passos maiores

    def volt(x, n):
        return 0.0 if n == GND else x[idx[n]]

    def attempt(scale: float, x0: np.ndarray):
        b_base = b_lin.copy()
        for e in vsrc:
            b_base[v_index[e.name]] = e.p["V"] * scale
        x = x0.copy()
        for it in range(1, max_iter + 1):
            a = a_lin.copy()
            b = b_base.copy()
            for e in nonlin:
                if e.kind == "D":
                    na, nk = ix(e.nodes[0]), ix(e.nodes[1])
                    v = volt(x, e.nodes[0]) - volt(x, e.nodes[1])
                    i, g = _diode(v, e.p)
                    ieq = i - g * v
                    if na is not None:
                        a[na, na] += g
                        b[na] -= ieq
                    if nk is not None:
                        a[nk, nk] += g
                        b[nk] += ieq
                    if na is not None and nk is not None:
                        a[na, nk] -= g
                        a[nk, na] -= g
                elif e.kind == "M":
                    tn = e.nodes  # (d, g, s)
                    vd, vg, vs = (volt(x, n) for n in tn)
                    i_d, g_d = _mosfet(vd, vg, vs, e.p)
                    v_t = np.array([vd, vg, vs])
                    ieq = i_d - g_d @ v_t
                    for sign, row in ((1.0, 0), (-1.0, 2)):  # corrente entra no dreno e sai pela fonte
                        rr = ix(tn[row])
                        if rr is None:
                            continue
                        b[rr] -= sign * ieq
                        for c in range(3):
                            cc = ix(tn[c])
                            if cc is not None:
                                a[rr, cc] += sign * g_d[c]
                elif e.kind == "U":
                    tn = e.nodes  # (entrada, saída)
                    vi, vo = (volt(x, n) for n in tn)
                    i_in, g_in, i_o, g_o = _regulator(vi, vo, e.p)
                    v2 = np.array([vi, vo])
                    # corrente sai do nó de entrada (inclui Iq) e entra no nó de saída (sem Iq)
                    for sign, row, i_row, g_row in ((1.0, 0, i_in, g_in), (-1.0, 1, i_o, g_o)):
                        rr = ix(tn[row])
                        if rr is None:
                            continue
                        b[rr] -= sign * (i_row - g_row @ v2)
                        for c in range(2):
                            cc = ix(tn[c])
                            if cc is not None:
                                a[rr, cc] += sign * g_row[c]
                else:  # Q
                    tn = e.nodes  # (c, b, e)
                    vc, vb, ve = (volt(x, n) for n in tn)
                    i_t, g_t = _bjt(vb, vc, ve, e.p)
                    v_t = np.array([vc, vb, ve])
                    ieq = i_t - g_t @ v_t
                    for r in range(3):
                        rr = ix(tn[r])
                        if rr is None:
                            continue
                        b[rr] -= ieq[r]
                        for c in range(3):
                            cc = ix(tn[c])
                            if cc is not None:
                                a[rr, cc] += g_t[r, c]
            try:
                xn = np.linalg.solve(a, b)
            except np.linalg.LinAlgError:
                return None, it
            dx = xn - x
            if n_nodes:
                m = np.max(np.abs(dx[:n_nodes]))
                if m > step_limit:
                    dx *= step_limit / m
            x = x + dx
            tol = 1e-6 * np.maximum(np.abs(x), 1e-3) + np.concatenate(
                [np.full(n_nodes, 1e-9), np.full(n_v, 1e-12)]
            )
            if np.all(np.abs(dx) < tol) and (not nonlin or it > 1):
                return x, it
        return None, max_iter

    x0 = np.zeros(size)
    x, iters = attempt(1.0, x0)
    if x is None:  # continuação por fonte (source stepping)
        x = x0
        ok = True
        for s in np.linspace(0.1, 1.0, 10):
            x_try, it = attempt(float(s), x)
            iters += it
            if x_try is None:
                ok = False
                break
            x = x_try
        if not ok:
            return Solution({n: float("nan") for n in nodes}, {}, False, iters)

    v = {n: float(x[idx[n]]) for n in nodes}
    v[GND] = 0.0
    cur: dict = {}
    for e in elements:
        if e.kind == "R":
            cur[e.name] = (v.get(e.nodes[0], 0.0) - v.get(e.nodes[1], 0.0)) / e.p["R"]
        elif e.kind == "D":
            cur[e.name] = _diode(v.get(e.nodes[0], 0.0) - v.get(e.nodes[1], 0.0), e.p)[0]
        elif e.kind == "Q":
            vc, vb, ve = (v.get(n, 0.0) for n in e.nodes)
            i_t, _ = _bjt(vb, vc, ve, e.p)
            cur[e.name + ".c"], cur[e.name + ".b"] = float(i_t[0]), float(i_t[1])
        elif e.kind == "M":
            vd, vg, vs = (v.get(n, 0.0) for n in e.nodes)
            cur[e.name + ".d"] = float(_mosfet(vd, vg, vs, e.p)[0])
        elif e.kind == "U":
            vi, vo = (v.get(n, 0.0) for n in e.nodes)
            i_in, _, i_out, _ = _regulator(vi, vo, e.p)
            cur[e.name + ".in"], cur[e.name + ".out"] = float(i_in), float(i_out)
        elif e.kind == "V":
            cur[e.name] = float(x[v_index[e.name]])
    return Solution(v, cur, True, iters)

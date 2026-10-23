"""Esquemas em SVG gerados por código (sem dependências).

Os pontos de medição são marcados com `<g class="nd" data-node="X">`, para o app destacar
o nó que o estudante deve medir. Cores vêm de `currentColor`/classes CSS (tema claro e escuro).
"""
from __future__ import annotations

W, H = 300, 270


class _Draw:
    def __init__(self, w=W, h=H):
        self.p: list[str] = []
        self.w, self.h = w, h

    def path(self, pts, close=False):
        d = "M" + " L".join(f"{x:g},{y:g}" for x, y in pts) + (" Z" if close else "")
        self.p.append(f'<path class="w" d="{d}"/>')

    def text(self, x, y, s, cls="cl", anchor="start"):
        self.p.append(f'<text class="{cls}" x="{x:g}" y="{y:g}" text-anchor="{anchor}">{s}</text>')

    def gnd(self, x, y):
        self.path([(x, y), (x, y + 5)])
        for i, w in enumerate((9, 6, 3)):
            self.path([(x - w, y + 5 + 4 * i), (x + w, y + 5 + 4 * i)])

    def res_v(self, x, y1, y2, label, left=False):
        m = (y1 + y2) / 2
        z = [(x, y1), (x, m - 15), (x + 6, m - 10), (x - 6, m - 5), (x + 6, m), (x - 6, m + 5),
             (x + 6, m + 10), (x, m + 15), (x, y2)]
        self.path(z)
        if left:
            self.text(x - 12, m + 4, label, anchor="end")
        else:
            self.text(x + 12, m + 4, label)

    def res_h(self, x1, x2, y, label):
        m = (x1 + x2) / 2
        z = [(x1, y), (m - 15, y), (m - 10, y - 6), (m - 5, y + 6), (m, y - 6), (m + 5, y + 6),
             (m + 10, y - 6), (m + 15, y), (x2, y)]
        self.path(z)
        self.text(m, y - 12, label, anchor="middle")

    def diode_v(self, x, y1, y2, label, cathode_top=False, led=False, zener=False):
        m = (y1 + y2) / 2
        if not cathode_top:
            self.path([(x - 9, m - 8), (x + 9, m - 8), (x, m + 6)], close=True)
            bar = m + 6
            self.path([(x, y1), (x, m - 8)])
            self.path([(x, m + 6), (x, y2)])
        else:
            self.path([(x - 9, m + 8), (x + 9, m + 8), (x, m - 6)], close=True)
            bar = m - 6
            self.path([(x, y1), (x, m - 6)])
            self.path([(x, m + 8), (x, y2)])
        self.path([(x - 9, bar), (x + 9, bar)])
        if zener:
            self.path([(x - 9, bar), (x - 12, bar + 3)])
            self.path([(x + 9, bar), (x + 12, bar - 3)])
        if led:
            self.path([(x + 13, m - 4), (x + 21, m - 12)])
            self.path([(x + 18, m + 2), (x + 26, m - 6)])
        self.text(x + (30 if led else 14), m + 4, label)

    def vsrc(self, x, y1, y2, label):
        m = (y1 + y2) / 2
        self.path([(x, y1), (x, m - 14)])
        self.path([(x, m + 14), (x, y2)])
        self.p.append(f'<circle class="w" cx="{x:g}" cy="{m:g}" r="14"/>')
        self.text(x, m - 3, "+", anchor="middle")
        self.text(x, m + 11, "−", anchor="middle")
        self.text(x + 20, m + 4, label)

    def npn(self, x, y, label):
        """Centro (x, y). Terminais: base (x-24, y), coletor (x+18, y-40), emissor (x+18, y+40)."""
        self.path([(x, y - 14), (x, y + 14)])
        self.path([(x - 24, y), (x, y)])
        self.path([(x, y - 6), (x + 18, y - 20), (x + 18, y - 40)])
        self.path([(x, y + 6), (x + 18, y + 20), (x + 18, y + 40)])
        self.path([(x + 10, y + 12), (x + 18, y + 20), (x + 8, y + 21)])  # seta do emissor
        self.p.append(f'<circle class="w" cx="{x + 6:g}" cy="{y:g}" r="22"/>')
        self.text(x + 28, y + 4, label)

    # ---- símbolos usados nos blocos do inversor
    def fuse_h(self, x1, x2, y, label=""):
        m = (x1 + x2) / 2
        self.path([(x1, y), (m - 14, y)])
        self.path([(m - 14, y - 5), (m + 14, y - 5), (m + 14, y + 5), (m - 14, y + 5)], close=True)
        self.path([(m - 14, y), (m + 14, y)])
        self.path([(m + 14, y), (x2, y)])
        if label:
            self.text(m, y - 9, label, anchor="middle")

    def diode_h(self, x1, x2, y, label=""):
        m = (x1 + x2) / 2
        self.path([(x1, y), (m - 8, y)])
        self.path([(m - 8, y - 9), (m - 8, y + 9), (m + 6, y)], close=True)
        self.path([(m + 6, y - 9), (m + 6, y + 9)])
        self.path([(m + 6, y), (x2, y)])
        if label:
            self.text(m, y - 14, label, anchor="middle")

    def cap_v(self, x, y1, y2, label=""):
        m = (y1 + y2) / 2
        self.path([(x, y1), (x, m - 3)])
        self.path([(x - 10, m - 3), (x + 10, m - 3)])
        self.path([(x - 10, m + 3), (x + 10, m + 3)])
        self.path([(x, m + 3), (x, y2)])
        if label:
            self.text(x + 14, m + 4, label)

    def coil_v(self, x, y1, y2, label="", left=False):
        n = 4
        h = (y2 - y1 - 10) / n
        r = h / 2
        d = f"M{x:g},{y1:g} L{x:g},{y1 + 5:g}"
        for i in range(n):
            d += f" A{r:g},{r:g} 0 0 {0 if left else 1} {x:g},{y1 + 5 + h * (i + 1):g}"
        d += f" L{x:g},{y2:g}"
        self.p.append(f'<path class="w" d="{d}" fill="none"/>')
        if label:
            if left:
                self.text(x - r - 8, (y1 + y2) / 2 + 4, label, anchor="end")
            else:
                self.text(x + r + 8, (y1 + y2) / 2 + 4, label)

    def nmos(self, x, y, label=""):
        """Centro (x, y). Terminais: porta (x-26, y), dreno (x+14, y-34), fonte (x+14, y+34)."""
        self.path([(x - 26, y), (x - 12, y)])
        self.path([(x - 12, y - 12), (x - 12, y + 12)])
        for a, b in ((-14, -7), (-3, 3), (7, 14)):
            self.path([(x - 7, y + a), (x - 7, y + b)])
        self.path([(x - 7, y - 11), (x + 14, y - 11), (x + 14, y - 34)])
        self.path([(x - 7, y + 11), (x + 14, y + 11), (x + 14, y + 34)])
        self.path([(x - 7, y), (x + 14, y), (x + 14, y + 11)])
        self.path([(x - 3, y - 3), (x - 7, y), (x - 3, y + 3)], close=True)
        if label:
            self.text(x + 20, y + 4, label)

    def box(self, x, y, w, h, label, sub=""):
        self.path([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True)
        self.text(x + w / 2, y + h / 2 + (0 if sub else 4), label, anchor="middle")
        if sub:
            self.text(x + w / 2, y + h / 2 + 12, sub, anchor="middle")

    def term(self, x, y, label, anchor="end"):
        self.p.append(f'<circle class="w" cx="{x:g}" cy="{y:g}" r="3"/>')
        self.text(x + (-7 if anchor == "end" else 7), y + 4, label, anchor=anchor)

    def node(self, x, y, name, dx=8, dy=-8):
        self.p.append(
            f'<g class="nd" data-node="{name}"><circle cx="{x:g}" cy="{y:g}" r="4.5"/>'
            f'<text class="nl" x="{x + dx:g}" y="{y + dy:g}">{name}</text></g>'
        )

    def svg(self, dy=0) -> str:
        body = "".join(self.p)
        if dy:  # margem superior para rótulos que passam do topo do desenho
            body = f'<g transform="translate(0,{dy:g})">{body}</g>'
        return (f'<svg class="sch" viewBox="0 0 {self.w:g} {self.h + dy:g}" xmlns="http://www.w3.org/2000/svg" '
                f'role="img">' + body + "</svg>")


def led_resistor() -> str:
    d = _Draw()
    d.vsrc(50, 40, 130, "V1 5 V")
    d.path([(50, 40), (50, 30), (150, 30)])
    d.node(100, 30, "VCC", -10, -10)
    d.res_v(150, 30, 100, "R1 330 Ω")
    d.path([(150, 100), (150, 120)])
    d.node(150, 110, "A", 10, 4)
    d.diode_v(150, 120, 190, "D1", led=True)
    d.path([(50, 130), (50, 190)])
    d.gnd(50, 190)
    d.gnd(150, 190)
    return d.svg()


def zener_shunt() -> str:
    d = _Draw()
    d.vsrc(40, 40, 130, "V1 12 V")
    d.path([(40, 40), (40, 30), (60, 30)])
    d.node(70, 30, "VCC", -2, -10)
    d.path([(60, 30), (90, 30)])
    d.res_h(90, 160, 30, "Rs 470 Ω")
    d.path([(160, 30), (255, 30)])
    d.node(195, 30, "Z", 8, -10)
    d.path([(195, 30), (195, 70)])
    d.diode_v(195, 70, 150, "DZ1 5,1 V", cathode_top=True, zener=True)
    d.path([(255, 30), (255, 70)])
    d.res_v(255, 70, 150, "RL 1 kΩ")
    d.path([(40, 130), (40, 150)])
    d.gnd(40, 150)
    d.gnd(195, 150)
    d.gnd(255, 150)
    d.text(195, 172, "", "cl")
    return d.svg()


def bjt_chave() -> str:
    d = _Draw()
    d.vsrc(35, 25, 105, "V1 9 V")
    d.path([(35, 25), (35, 15), (200, 15)])
    d.node(90, 15, "VCC", 0, -9)
    d.res_v(200, 15, 70, "Rc 470 Ω")
    d.path([(200, 70), (200, 80)])
    d.node(200, 80, "N1", 8, 4)
    d.diode_v(200, 80, 140, "D1", led=True)
    d.path([(200, 140), (200, 150)])
    d.node(200, 150, "C", 10, 4)
    d.npn(182, 190, "Q1")
    d.gnd(200, 238)
    d.path([(158, 190), (130, 190)])
    d.node(144, 190, "B", 0, -10)
    d.res_h(70, 130, 190, "Rb 4,7 kΩ")
    d.path([(50, 190), (70, 190)])
    d.node(50, 190, "VIN", -8, -10)
    d.vsrc(35, 190, 245, "")
    d.path([(35, 190), (50, 190)])
    d.text(15, 262, "V2 5 V")
    d.path([(35, 105), (35, 115)])
    d.gnd(35, 115)
    d.gnd(35, 247)
    return d.svg()


def emissor_comum() -> str:
    d = _Draw()
    d.vsrc(30, 25, 115, "V1 12 V")
    d.path([(30, 25), (30, 15), (188, 15)])
    d.node(70, 15, "VCC", 0, -9)
    d.res_v(110, 15, 95, "R1 47 kΩ")
    d.path([(110, 95), (110, 130)])
    d.node(110, 130, "B", -14, -6)
    d.res_v(110, 130, 215, "R2 10 kΩ")
    d.gnd(110, 215)
    d.path([(110, 130), (146, 130)])
    d.npn(170, 130, "Q1")
    d.path([(188, 15), (188, 50)])
    d.res_v(188, 50, 90, "RC 2,2 kΩ")
    d.path([(188, 90), (188, 90)])
    d.node(188, 92, "C", 10, 4)
    d.node(188, 182, "E", 10, 4)
    d.res_v(188, 182, 245, "RE 1 kΩ")
    d.gnd(188, 245)
    d.path([(30, 115), (30, 125)])
    d.gnd(30, 125)
    return d.svg()


def reg_serie() -> str:
    d = _Draw()
    d.vsrc(30, 25, 115, "V1 12 V")
    d.path([(30, 25), (30, 15), (188, 15)])
    d.node(70, 15, "VCC", 0, -9)
    d.res_v(110, 15, 85, "Rz 1 kΩ")
    d.path([(110, 85), (110, 100)])
    d.node(110, 100, "Z", -14, -6)
    d.diode_v(110, 100, 180, "DZ1 6,8 V", cathode_top=True, zener=True)
    d.gnd(110, 180)
    d.path([(110, 100), (146, 100)])
    d.npn(170, 100, "Q1")
    d.path([(188, 60), (188, 15)])
    d.path([(188, 140), (188, 150)])
    d.node(188, 150, "OUT", 8, -8)
    d.path([(188, 150), (240, 150)])
    d.res_v(240, 150, 220, "RL 220 Ω")
    d.gnd(240, 220)
    d.path([(30, 115), (30, 125)])
    d.gnd(30, 125)
    return d.svg()


# --------------------------------------------------------------------------- blocos do inversor
def inv_entrada() -> str:
    d = _Draw(340, 250)
    d.vsrc(30, 40, 130, "V1")
    d.path([(30, 40), (30, 24), (60, 24)])
    d.path([(60, 24), (60, 104)])
    d.node(60, 104, "BAT", -10, 18)
    for i, y in enumerate((24, 48, 72, 96)):
        d.fuse_h(60, 120, y, f"F{i + 1}")
    d.path([(120, 24), (120, 96)])
    d.path([(120, 60), (290, 60)])
    d.node(150, 60, "BUS", 0, -10)
    d.res_v(175, 60, 105, "Rg")
    d.node(175, 115, "G", 8, -6)
    d.path([(175, 105), (175, 115)])
    d.diode_v(175, 115, 175, "DZ1", cathode_top=True, zener=True)
    d.gnd(175, 175)
    d.path([(175, 115), (140, 115), (140, 169), (200, 169)])
    d.cap_v(225, 60, 108, "C1")
    d.res_v(280, 60, 108, "RL")
    d.path([(225, 108), (225, 135), (280, 135)])
    d.path([(280, 108), (280, 135)])
    d.node(252, 135, "LG", 0, -10)
    d.nmos(226, 169, "Q1")
    d.path([(225, 135), (240, 135)])
    d.gnd(240, 203)
    d.path([(30, 130), (30, 190)])
    d.gnd(30, 190)
    d.text(30, 232, "Q1 protege contra inversão de polaridade", "cl")
    return d.svg()


def inv_fontes_aux() -> str:
    d = _Draw(400, 170)
    d.vsrc(30, 40, 120, "V1")
    d.path([(30, 40), (30, 30), (60, 30)])
    d.diode_h(60, 120, 30, "D1")
    d.node(135, 30, "VIN", -16, -10)
    d.path([(120, 30), (150, 30)])
    d.box(150, 14, 60, 32, "U1", "7815")
    d.path([(180, 46), (180, 60)])
    d.gnd(180, 60)
    d.path([(210, 30), (250, 30)])
    d.node(228, 30, "V15", -4, -10)
    d.res_v(228, 30, 100, "R15")
    d.gnd(228, 100)
    d.box(250, 14, 60, 32, "U2", "7805")
    d.path([(280, 46), (280, 60)])
    d.gnd(280, 60)
    d.path([(310, 30), (350, 30)])
    d.node(335, 30, "V5", -4, -10)
    d.res_v(350, 30, 100, "R5")
    d.gnd(350, 100)
    d.path([(30, 120), (30, 140)])
    d.gnd(30, 140)
    return d.svg()


def inv_primario() -> str:
    d = _Draw(400, 270)
    d.vsrc(30, 20, 90, "V1")
    d.path([(30, 20), (30, 12), (60, 12)])
    d.fuse_h(60, 120, 12, "F1")
    d.path([(120, 12), (170, 12)])
    d.node(135, 12, "BUS", 0, -9)
    d.res_h(170, 230, 12, "RR")
    d.path([(230, 12), (260, 12)])
    d.node(255, 12, "CT", 0, -10)
    d.path([(260, 12), (260, 40)])
    d.path([(190, 40), (330, 40)])
    d.coil_v(190, 40, 100, "T1a", left=True)
    d.coil_v(330, 40, 100, "T1b")
    d.path([(190, 100), (190, 112)])
    d.path([(330, 100), (330, 112)])
    d.node(190, 106, "DA", 10, 4)
    d.node(330, 106, "DB", -26, 4)
    d.nmos(176, 146, "M1")
    d.nmos(316, 146, "M2")
    d.gnd(190, 180)
    d.gnd(330, 180)
    d.path([(190, 180), (330, 180)])
    # comando de M1
    d.path([(150, 146), (136, 146)])
    d.node(143, 146, "GA", 0, -9)
    d.res_h(66, 136, 146, "Rg1")
    d.res_v(110, 150, 210, "Rgs1", left=True)
    d.path([(110, 146), (110, 150)])
    d.gnd(110, 210)
    d.vsrc(30, 146, 216, "V2")
    d.path([(30, 146), (66, 146)])
    d.gnd(30, 216)
    # comando de M2 (nível baixo)
    d.path([(290, 146), (270, 146)])
    d.node(277, 146, "GB", 0, -9)
    d.res_v(270, 150, 210, "Rg2", left=True)
    d.gnd(270, 210)
    d.path([(30, 90), (30, 100)])
    d.gnd(30, 100)
    d.text(30, 250, "Semiciclo: M1 conduz, M2 cortado", "cl")
    return d.svg(dy=18)


def inv_barramento() -> str:
    d = _Draw(380, 220)
    d.vsrc(30, 40, 120, "V1")
    d.path([(30, 40), (30, 30), (70, 30)])
    d.node(50, 30, "SEC", 0, -10)
    d.diode_h(70, 130, 30, "D1")
    d.path([(130, 30), (320, 30)])
    d.node(150, 30, "HV", 0, -10)
    d.cap_v(185, 30, 100, "C1")
    d.gnd(185, 100)
    d.res_v(240, 30, 100, "RL")
    d.gnd(240, 100)
    d.res_v(300, 30, 84, "Ra")
    d.path([(300, 84), (300, 108)])
    d.node(300, 96, "SMP", 10, 4)
    d.res_v(300, 108, 168, "Rb")
    d.gnd(300, 168)
    d.path([(30, 120), (30, 140)])
    d.gnd(30, 140)
    d.text(30, 205, "SEC: tensão CC equivalente do secundário", "cl")
    return d.svg(dy=10)


def inv_ponte_h() -> str:
    d = _Draw(500, 250)
    d.path([(204, 20), (440, 20)])
    d.node(290, 20, "HV", 0, -9)
    d.vsrc(440, 20, 110, "V1")
    d.path([(440, 110), (440, 130)])
    d.gnd(440, 130)
    d.nmos(190, 54, "Q1")
    d.nmos(370, 54, "Q2")
    d.nmos(190, 122, "Q3")
    d.nmos(370, 122, "Q4")
    d.path([(204, 88), (384, 88)])
    d.node(204, 88, "OA", -30, -6)
    d.node(384, 88, "OB", 8, -6)
    d.res_h(230, 320, 88, "RL")
    d.path([(204, 156), (384, 156)])
    d.node(250, 156, "SH", 10, -6)
    d.res_v(250, 156, 206, "Rsh")
    d.gnd(250, 206)
    # porta de Q1 (acionador flutuante Vb1, referido a OA)
    d.path([(164, 54), (157, 54)])
    d.node(157, 54, "G1", -4, -9)
    d.res_h(80, 150, 54, "Rg1")
    d.path([(150, 54), (157, 54)])
    d.res_v(157, 58, 88, "Rgs1", left=True)
    d.path([(157, 54), (157, 58)])
    d.path([(157, 88), (204, 88)])
    d.vsrc(50, 54, 96, "")
    d.text(50, 114, "Vb1", anchor="middle")
    d.path([(50, 54), (80, 54)])
    d.path([(50, 96), (204, 96)])
    # porta de Q2 (cortado: ligada à fonte)
    d.path([(344, 54), (336, 54)])
    d.res_v(336, 58, 88, "Rg2", left=True)
    d.path([(336, 54), (336, 58)])
    d.path([(336, 88), (384, 88)])
    # porta de Q3 (cortado)
    d.path([(164, 122), (150, 122)])
    d.res_v(150, 126, 156, "Rg3", left=True)
    d.path([(150, 122), (150, 126)])
    d.path([(150, 156), (204, 156)])
    # porta de Q4 (acionador de lado baixo)
    d.path([(344, 122), (336, 122)])
    d.node(336, 122, "G4", -2, -9)
    d.res_h(262, 322, 122, "Rg4")
    d.path([(322, 122), (336, 122)])
    d.res_v(328, 126, 156, "Rgs4", left=True)
    d.path([(328, 122), (328, 126)])
    d.term(254, 122, "Vd4")
    d.text(30, 238, "Semiciclo: Q1 e Q4 conduzem, Q2 e Q3 cortados", "cl")
    return d.svg()

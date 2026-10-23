"""Análise de sensibilidade: o resultado do piloto sintético depende das premissas?

Reexecuta o gerador de sessões com premissas alternativas (em memória, sem gravar dados) e
compara guiado x método atual. Serve para dizer onde a conclusão é robusta e onde ela depende
do que foi assumido. Saída: docs/sensitivity.md.

    python -m eletrodiag.synth.sensitivity
"""
from __future__ import annotations

import json
import re
from contextlib import contextmanager

import numpy as np
import pandas as pd

from ..pipeline import config as C
from . import students as S

SCENARIOS = {
    "Base (premissas do pipeline)": {},
    "Método atual perfeito (acha o defeito sempre, sem falso positivo)": {"detect": 1.0, "false_pos": 0.0},
    "Teste de componente rápido (45 s em vez de 110 s)": {"component_s": 45.0},
    "Erros de leitura dobrados (ponteira invertida, escala, ponto errado)": {"err_x": 2.0},
    "Pior caso para o app (os três acima juntos)": {"detect": 1.0, "false_pos": 0.0, "component_s": 45.0, "err_x": 2.0},
}


@contextmanager
def _patched(detect=None, false_pos=None, component_s=None, err_x=None):
    saved = (dict(S.P_DETECT), dict(S.P_FALSE_POS), dict(S.MEDIAN_S), dict(S.P_GROSS_ERROR))
    try:
        if detect is not None:
            S.P_DETECT.update({k: detect for k in S.P_DETECT})
        if false_pos is not None:
            S.P_FALSE_POS.update({k: false_pos for k in S.P_FALSE_POS})
        if component_s is not None:
            S.MEDIAN_S["component"] = component_s
        if err_x is not None:
            S.P_GROSS_ERROR.update({k: v * err_x for k, v in S.P_GROSS_ERROR.items()})
        yield
    finally:
        S.P_DETECT.update(saved[0]); S.P_FALSE_POS.update(saved[1])
        S.MEDIAN_S.update(saved[2]); S.P_GROSS_ERROR.update(saved[3])


def _summarize(by_week: dict) -> pd.DataFrame:
    rows = {}
    for recs in by_week.values():
        for r in recs:
            sid, p = r["session_id"], r["payload"]
            d = rows.setdefault(sid, {"steps": 0, "sec": 0.0, "mode": None, "outcome": None})
            if r["event_type"] == "session_started":
                d["mode"] = p["mode"]
            elif r["event_type"] in ("measurement_taken", "component_tested"):
                d["steps"] += 1
                d["sec"] += p["duration_s"]
            elif r["event_type"] == "session_finished":
                d["outcome"] = p["outcome"]
    df = pd.DataFrame(rows.values()).dropna(subset=["outcome"])
    return df.groupby("mode").agg(sessoes=("steps", "size"), sucesso=("outcome", lambda x: (x == "reparado").mean()),
                                  passos=("steps", "mean"), minutos=("sec", lambda x: x.mean() / 60)).reset_index()


def run(n_scenarios: int = 120) -> str:
    dictionary = json.loads((C.GOLD / "app" / "dictionary.json").read_text())
    lines = ["# Análise de sensibilidade", "",
             "Dados **sintéticos**. Cada linha refaz a simulação com premissas diferentes "
             f"({n_scenarios} cenários por circuito, {len(dictionary['circuits'])} circuitos, 3 métodos, mesma semente). "
             "\"Δ\" é guiado menos método atual.", "",
             "| Premissa | Sucesso guiado | Sucesso atual | Δ sucesso | Passos guiado | Passos atual | Δ passos | Min guiado | Min atual |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, kw in SCENARIOS.items():
        with _patched(**kw):
            by_week, _ = S.generate(dictionary, seed=C.SEED, n_scenarios=n_scenarios)
        t = _summarize(by_week).set_index("mode")
        g, b = t.loc["guiado"], t.loc["componente_a_componente"]
        row = (f"| {name} | {g.sucesso:.0%} | {b.sucesso:.0%} | {100 * (g.sucesso - b.sucesso):+.1f} p.p. | "
               f"{g.passos:.2f} | {b.passos:.2f} | {g.passos - b.passos:+.2f} | {g.minutos:.1f} | {b.minutos:.1f} |")
        lines.append(re.sub(r"(\d)\.(\d)", r"\1,\2", row))
    lines += ["", "## Leitura", "",
              "- Os circuitos básicos têm de 3 a 6 componentes: o método atual já acaba em poucos testes e o ganho em **passos** "
              "é pequeno. Nos blocos do inversor (até 15 componentes) o método atual precisa de mais testes e o ganho em passos "
              "e em tempo é maior, mas a taxa de sucesso do app cai nos blocos em que muitas falhas não se separam com o "
              "circuito energizado (primário e ponte H): ali o teste de componente com a placa desligada faz falta.",
              "- O ganho em **tempo** vem sobretudo da premissa de que testar um componente (desligar, levantar um terminal, medir) "
              "custa bem mais que uma medição de tensão no circuito ligado. Se essa premissa estiver errada, o ganho encolhe.",
              "- O ganho em **sucesso** depende da taxa de acerto assumida para o método atual. Se o método atual acerta sempre, "
              "o app fica ABAIXO em sucesso: ele tem um teto, porque alguns pares de defeitos não se separam só com o multímetro "
              "(ver `v_ambiguidade`). Nesse caso o app só compensa se os passos e o tempo caírem de verdade.",
              "- A simulação do app para na decisão e não modela o teste de confirmação que ele recomenda. "
              "Um estudante que confirma antes de trocar recupera parte desse teto.",
              "- Estes números orientam o desenho do piloto real. Eles não substituem medir estudantes de verdade."]
    out = "\n".join(lines) + "\n"
    (C.REPO / "docs" / "sensitivity.md").write_text(out, encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run())

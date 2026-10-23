"""Motor de diagnóstico (referência em Python; o app usa o espelho em JavaScript `app/diagnose.js`).

Modelo:
  * Hipóteses = falhas simples catalogadas (uma falha por vez).
  * Verossimilhança gaussiana por medição, com desvio = Monte Carlo (tolerâncias) + erro do multímetro,
    misturada com uma componente uniforme (outlier) para tolerar leituras erradas do estudante.
  * Próxima medição = maximiza a separação esperada entre hipóteses de componentes diferentes,
    ponderada pelo posterior, dividida pelo custo da medição (coeficiente de Bhattacharyya).
"""
from __future__ import annotations

import math

import numpy as np

SQRT_2PI = math.sqrt(2.0 * math.pi)

DEFAULT_METER_MODEL = {
    "V": {"rel": 0.01, "abs": 0.02},     # multímetro + erro de leitura de tensão
    "I": {"rel": 0.02, "abs": 5e-5},     # corrente: resolução/ruído de ~50 µA
    "outlier_eps": 0.03,                 # probabilidade a priori de leitura errada
    "uniform_density": {"V": 1 / 24.0, "I": 1 / 2.0},
}


class Diagnoser:
    def __init__(self, circuit: dict, meter_model: dict | None = None):
        self.mm = meter_model or DEFAULT_METER_MODEL
        self.circuit = circuit
        self.obs = circuit["observables"]
        self.obs_ids = [o["id"] for o in self.obs]
        self.obs_kind = [o["kind"] for o in self.obs]
        self.obs_cost = np.array([o["cost"] for o in self.obs])
        self.faults = circuit["faults"]
        self.fault_ids = [f["id"] for f in self.faults]
        self.comp_of = [f["component"] for f in self.faults]
        self.components = sorted(set(self.comp_of), key=self.comp_of.index)
        pri = np.array([f["prior"] for f in self.faults], dtype=float)
        self.prior = pri / pri.sum()
        nf, no = len(self.faults), len(self.obs)
        self.mean = np.zeros((nf, no))
        std = np.zeros((nf, no))
        for i, f in enumerate(self.faults):
            for j, oid in enumerate(self.obs_ids):
                m, s = f["signature"][oid]
                self.mean[i, j], std[i, j] = m, s
        rel = np.array([self.mm[k]["rel"] for k in self.obs_kind])
        ab = np.array([self.mm[k]["abs"] for k in self.obs_kind])
        self.sigma = np.sqrt(std**2 + np.maximum(rel * np.abs(self.mean), ab) ** 2)
        # densidade da componente uniforme (outlier): a faixa cresce com o maior valor esperado do observável,
        # para que circuitos de centenas de volts ou dezenas de ampères não sejam tratados como os de 12 V
        base = np.array([1.0 / self.mm["uniform_density"][k] for k in self.obs_kind])
        self.uni = 1.0 / np.maximum(base, 1.5 * np.max(np.abs(self.mean), axis=0))
        self._comp_mask = np.array(
            [[self.comp_of[i] != self.comp_of[j] for j in range(nf)] for i in range(nf)], dtype=float
        )
        self._bc: dict[int, np.ndarray] = {}

    # ------------------------------------------------------------------ posterior
    def posterior(self, measurements: dict[str, float]) -> np.ndarray:
        logp = np.log(self.prior)
        eps = self.mm["outlier_eps"]
        for oid, x in measurements.items():
            j = self.obs_ids.index(oid)
            s = self.sigma[:, j]
            g = np.exp(-0.5 * ((x - self.mean[:, j]) / s) ** 2) / (s * SQRT_2PI)
            logp = logp + np.log((1 - eps) * g + eps * self.uni[j])
        logp -= logp.max()
        p = np.exp(logp)
        return p / p.sum()

    def component_posterior(self, post: np.ndarray) -> dict[str, float]:
        out = {c: 0.0 for c in self.components}
        for p, c in zip(post, self.comp_of):
            out[c] += float(p)
        return out

    # ------------------------------------------------------------------ próxima medição
    def _bc_matrix(self, j: int) -> np.ndarray:
        if j not in self._bc:
            m, s = self.mean[:, j], self.sigma[:, j]
            s2 = s[:, None] ** 2 + s[None, :] ** 2
            self._bc[j] = np.sqrt(2.0 * s[:, None] * s[None, :] / s2) * np.exp(
                -((m[:, None] - m[None, :]) ** 2) / (4.0 * s2)
            )
        return self._bc[j]

    def rank_next(self, post: np.ndarray, measured: set[str]) -> list[dict]:
        w = np.outer(post, post) * self._comp_mask
        out = []
        for j, oid in enumerate(self.obs_ids):
            if oid in measured:
                continue
            score = 0.5 * float(np.sum(w * (1.0 - self._bc_matrix(j))))
            out.append({"observable_id": oid, "score": score, "cost": float(self.obs_cost[j]),
                        "ratio": score / float(self.obs_cost[j])})
        out.sort(key=lambda r: -r["ratio"])
        return out

    # ------------------------------------------------------------------ separabilidade
    def separability(self, kinds: tuple[str, ...] = ("V", "I")) -> np.ndarray:
        """Distância de Bhattacharyya total (soma de -ln BC) entre cada par de hipóteses."""
        nf = len(self.faults)
        d = np.zeros((nf, nf))
        for j, k in enumerate(self.obs_kind):
            if k in kinds:
                d += -np.log(np.clip(self._bc_matrix(j), 1e-300, 1.0))
        return d

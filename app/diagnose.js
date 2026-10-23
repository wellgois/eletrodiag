/* Motor de diagnóstico do EletroDiag (espelho de src/eletrodiag/diagnose.py).
 * Mantenha os dois arquivos equivalentes: tests/test_js_parity.py compara os resultados.
 * Funciona no navegador (global EletroDiag) e no Node (module.exports). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.EletroDiag = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const SQRT_2PI = Math.sqrt(2 * Math.PI);

  class Diagnoser {
    constructor(circuit, meterModel) {
      this.mm = meterModel;
      this.circuit = circuit;
      this.obs = circuit.observables;
      this.obsIds = this.obs.map((o) => o.id);
      this.obsKind = this.obs.map((o) => o.kind);
      this.obsCost = this.obs.map((o) => o.cost);
      this.faults = circuit.faults;
      this.faultIds = this.faults.map((f) => f.id);
      this.compOf = this.faults.map((f) => f.component);
      this.components = [...new Set(this.compOf)];
      const sum = this.faults.reduce((a, f) => a + f.prior, 0);
      this.prior = this.faults.map((f) => f.prior / sum);
      const nf = this.faults.length;
      const no = this.obs.length;
      this.mean = [];
      this.sigma = [];
      for (let i = 0; i < nf; i++) {
        this.mean.push([]);
        this.sigma.push([]);
        for (let j = 0; j < no; j++) {
          const [m, s] = this.faults[i].signature[this.obsIds[j]];
          const k = this.mm[this.obsKind[j]];
          const meter = Math.max(k.rel * Math.abs(m), k.abs);
          this.mean[i].push(m);
          this.sigma[i].push(Math.sqrt(s * s + meter * meter));
        }
      }
      // densidade da componente uniforme (outlier): a faixa cresce com o maior valor esperado do observável
      this.uni = this.obsKind.map((k, j) => {
        const base = 1 / this.mm.uniform_density[k];
        const big = 1.5 * Math.max(...this.mean.map((row) => Math.abs(row[j])));
        return 1 / Math.max(base, big);
      });
      this._bc = {};
    }

    posterior(meas) {
      const eps = this.mm.outlier_eps;
      let logp = this.prior.map(Math.log);
      for (const [oid, x] of Object.entries(meas)) {
        const j = this.obsIds.indexOf(oid);
        const uni = this.uni[j];
        for (let i = 0; i < logp.length; i++) {
          const s = this.sigma[i][j];
          const z = (x - this.mean[i][j]) / s;
          const g = Math.exp(-0.5 * z * z) / (s * SQRT_2PI);
          logp[i] += Math.log((1 - eps) * g + eps * uni);
        }
      }
      const mx = Math.max(...logp);
      const p = logp.map((v) => Math.exp(v - mx));
      const tot = p.reduce((a, b) => a + b, 0);
      return p.map((v) => v / tot);
    }

    componentPosterior(post) {
      const out = {};
      for (const c of this.components) out[c] = 0;
      post.forEach((p, i) => (out[this.compOf[i]] += p));
      return out;
    }

    _bcMatrix(j) {
      if (!this._bc[j]) {
        const nf = this.faults.length;
        const m = [];
        for (let a = 0; a < nf; a++) {
          const row = [];
          for (let b = 0; b < nf; b++) {
            const sa = this.sigma[a][j], sb = this.sigma[b][j];
            const s2 = sa * sa + sb * sb;
            const d = this.mean[a][j] - this.mean[b][j];
            row.push(Math.sqrt((2 * sa * sb) / s2) * Math.exp(-(d * d) / (4 * s2)));
          }
          m.push(row);
        }
        this._bc[j] = m;
      }
      return this._bc[j];
    }

    rankNext(post, measured) {
      const nf = post.length;
      const out = [];
      this.obsIds.forEach((oid, j) => {
        if (measured.has(oid)) return;
        const bc = this._bcMatrix(j);
        let score = 0;
        for (let a = 0; a < nf; a++)
          for (let b = a + 1; b < nf; b++)
            if (this.compOf[a] !== this.compOf[b]) score += post[a] * post[b] * (1 - bc[a][b]);
        out.push({ observable_id: oid, score, cost: this.obsCost[j], ratio: score / this.obsCost[j] });
      });
      out.sort((a, b) => b.ratio - a.ratio);
      return out;
    }

    /* falha mais provável dentro de um componente */
    topFaultOf(post, comp) {
      let best = -1;
      this.faults.forEach((f, i) => {
        if (f.component === comp && (best < 0 || post[i] > post[best])) best = i;
      });
      return this.faults[best];
    }

    /* desvio (em sigmas) de uma leitura em relação à hipótese i */
    zScore(i, oid, x) {
      const j = this.obsIds.indexOf(oid);
      return Math.abs(x - this.mean[i][j]) / this.sigma[i][j];
    }
  }

  const UNITS = {
    v: ["V", 1], mv: ["V", 1e-3], kv: ["V", 1e3], uv: ["V", 1e-6], "µv": ["V", 1e-6],
    a: ["A", 1], ma: ["A", 1e-3], ua: ["A", 1e-6], "µa": ["A", 1e-6], "μa": ["A", 1e-6],
  };
  const NUM = /^\s*([+\-−]?\s*\d+(?:[.,]\d+)?)\s*([A-Za-zµμ]*)\s*$/;
  const DEFAULT_UNIT = { V: "V", I: "mA" };

  /* mesma regra de src/eletrodiag/pipeline/parsing.py */
  function parseMeasurement(raw, unitRaw, kind) {
    if (raw === null || raw === undefined) return { error: "unparsable_value" };
    const m = NUM.exec(String(raw));
    if (!m) return { error: "unparsable_value" };
    const num = m[1].replace(/\s/g, "").replace("−", "-").replace(",", ".");
    const unit = (m[2] || unitRaw || DEFAULT_UNIT[kind]).trim().toLowerCase();
    if (!(unit in UNITS)) return { error: "unknown_unit" };
    const [q, f] = UNITS[unit];
    if (q !== (kind === "V" ? "V" : "A")) return { error: "unit_mismatch" };
    return { value: parseFloat(num) * f, unit: q };
  }

  return { Diagnoser, parseMeasurement };
});

"""O motor JS (app) e o Python precisam dar o mesmo resultado."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from eletrodiag.diagnose import Diagnoser

JS = Path(__file__).resolve().parents[1] / "app" / "diagnose.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")


def test_posterior_e_ranking_iguais(pipeline_run):
    d = json.loads((pipeline_run["data"] / "gold" / "app" / "dictionary.json").read_text())
    rng = np.random.default_rng(5)
    cases = []
    for c in d["circuits"]:
        for f in rng.choice(c["faults"], 3, replace=False):
            ids = [o["id"] for o in c["observables"]]
            take = list(rng.choice(ids, size=min(3, len(ids)), replace=False))
            cases.append({"circuit": c["id"], "meas": {o: float(f["signature"][o][0] * rng.uniform(0.97, 1.03)) for o in take}})
    # o dicionário é grande (esquemas SVG): vai por arquivo, não pela linha de comando
    data_file = pipeline_run["data"] / "_parity_input.json"
    data_file.write_text(json.dumps({"d": d, "cases": cases}))
    script = f"""
      const {{Diagnoser}} = require({json.dumps(str(JS))});
      const {{d, cases}} = JSON.parse(require("fs").readFileSync({json.dumps(str(data_file))}, "utf8"));
      const out = cases.map(k => {{ const c = d.circuits.find(x => x.id === k.circuit);
        const dg = new Diagnoser(c, d.meter_model); const post = dg.posterior(k.meas);
        const r = dg.rankNext(post, new Set(Object.keys(k.meas)));
        return {{post, rank: r.map(x => [x.observable_id, x.ratio])}}; }});
      console.log(JSON.stringify(out));"""
    js = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    for k, j in zip(cases, js):
        c = next(x for x in d["circuits"] if x["id"] == k["circuit"])
        dg = Diagnoser(c, d["meter_model"])
        post = dg.posterior(k["meas"])
        assert np.allclose(post, j["post"], atol=1e-9)
        py = [(r["observable_id"], r["ratio"]) for r in dg.rank_next(post, set(k["meas"]))]
        assert [a for a, _ in py] == [a for a, _ in j["rank"]]
        assert np.allclose([b for _, b in py], [b for _, b in j["rank"]], atol=1e-9)

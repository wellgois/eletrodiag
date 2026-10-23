import json

import numpy as np

from eletrodiag.diagnose import Diagnoser


def _dict(pipeline_run):
    return json.loads((pipeline_run["data"] / "gold" / "app" / "dictionary.json").read_text())


def test_posterior_soma_um_e_encontra_falha(pipeline_run):
    d = _dict(pipeline_run)
    for c in d["circuits"]:
        dg = Diagnoser(c, d["meter_model"])
        sep = dg.separability()
        for i, f in enumerate(c["faults"]):
            meas = {o: f["signature"][o][0] for o in dg.obs_ids}  # leituras ideais, sem ruído
            post = dg.posterior(meas)
            assert post.sum() == np.float64(1.0) or abs(post.sum() - 1) < 1e-9
            # o componente verdadeiro tem de estar entre os 2 mais prováveis, a menos que a falha seja
            # eletricamente indistinguível (distância de Bhattacharyya < 3) de outra de componente diferente
            cp = dg.component_posterior(post)
            ranked = sorted(cp, key=cp.get, reverse=True)[:2]
            ambiguous = any(sep[i, j] < 3.0 for j in range(len(c["faults"])) if dg.comp_of[j] != f["component"])
            assert f["component"] in ranked or ambiguous, (c["id"], f["id"], ranked)


def test_circuitos_basicos_nao_tem_falha_ambigua_no_ranking(pipeline_run):
    """Nos circuitos pequenos toda falha tem de ser achada sem desculpa de ambiguidade."""
    d = _dict(pipeline_run)
    for c in d["circuits"]:
        if c["nivel"] == "avancado":
            continue
        dg = Diagnoser(c, d["meter_model"])
        for f in c["faults"]:
            cp = dg.component_posterior(dg.posterior({o: f["signature"][o][0] for o in dg.obs_ids}))
            assert f["component"] in sorted(cp, key=cp.get, reverse=True)[:2], (c["id"], f["id"])


def test_proxima_medicao_nao_repete_e_prefere_informativa(pipeline_run):
    d = _dict(pipeline_run)
    c = next(x for x in d["circuits"] if x["id"] == "bjt_chave_led")
    dg = Diagnoser(c, d["meter_model"])
    r = dg.rank_next(dg.prior, {"V(B)"})
    assert "V(B)" not in [x["observable_id"] for x in r]
    assert r[0]["ratio"] >= r[-1]["ratio"]


def test_leitura_errada_isolada_nao_derruba_a_hipotese(pipeline_run):
    d = _dict(pipeline_run)
    c = next(x for x in d["circuits"] if x["id"] == "emissor_comum")
    dg = Diagnoser(c, d["meter_model"])
    f = next(f for f in c["faults"] if f["id"] == "RE:open")
    meas = {o: f["signature"][o][0] for o in dg.obs_ids}
    meas["V(C)"] = -meas["V(C)"] - 3.0  # ponteiras invertidas / ponto errado
    cp = dg.component_posterior(dg.posterior(meas))
    assert max(cp, key=cp.get) == "RE"

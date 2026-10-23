import json

import duckdb
import pandas as pd


def test_pipeline_sem_erros_de_qualidade(pipeline_run):
    assert pipeline_run["code"] == 0


def test_estrutura_medalhao(pipeline_run):
    d = pipeline_run["data"]
    for p in ("bronze/catalog", "bronze/sim_runs", "bronze/app_events", "bronze/scenario_truth",
              "silver/sessions.parquet", "silver/measurements.parquet", "silver/sim_runs",
              "gold/fct_session.parquet", "gold/fct_fault_signature.parquet",
              "gold/app/dictionary.json", "warehouse/eletrodiag.duckdb", "warehouse/eletrodiag.sqlite"):
        assert (d / p).exists(), p
    manifests = list((d / "bronze").rglob("_manifest.json"))
    assert manifests and all(json.loads(m.read_text())["files"] for m in manifests)


def test_bronze_guarda_o_dado_sujo_e_silver_limpa(pipeline_run):
    d = pipeline_run["data"]
    raw = sum(len(f.read_text().splitlines()) for f in (d / "bronze" / "app_events").rglob("events-*.jsonl"))
    silver = pd.read_parquet(d / "silver" / "sessions.parquet")
    quarantined = pd.concat([pd.read_parquet(f) for f in (d / "silver" / "_quarantine" / "app_events").glob("*.parquet")])
    assert raw > 0 and len(silver) > 0
    assert silver.session_id.is_unique
    assert {"malformed_json"} <= set(quarantined.reason)


def test_silver_sem_duplicatas_e_unidades_em_si(pipeline_run):
    d = pipeline_run["data"]
    m = pd.read_parquet(d / "silver" / "measurements.parquet")
    assert not m.duplicated(["session_id", "step"]).any()
    assert set(m.unit_si) <= {"V", "A"} and m.value_si.notna().all()


def test_silver_e_idempotente(pipeline_run):
    from eletrodiag.pipeline.run import main
    d = pipeline_run["data"]
    before = len(pd.read_parquet(d / "silver" / "sessions.parquet"))
    main(["--steps", "silver_events", "gold_analytics"])
    assert len(pd.read_parquet(d / "silver" / "sessions.parquet")) == before


def test_gold_modelo_dimensional_consistente(pipeline_run):
    d = pipeline_run["data"] / "gold"
    s = pd.read_parquet(d / "fct_session.parquet")
    circuits = set(pd.read_parquet(d / "dim_circuit.parquet").circuit_id)
    assert set(s.circuit_id) <= circuits
    assert set(s["mode"]) == {"guiado", "medicao_aleatoria", "componente_a_componente"}
    kpi = pd.read_parquet(d / "agg_kpi_circuit_mode.parquet")
    assert kpi.success_rate.between(0, 1).all()


def test_views_de_bi_consultaveis(pipeline_run):
    con = duckdb.connect(str(pipeline_run["data"] / "warehouse" / "eletrodiag.duckdb"), read_only=True)
    for v in ("v_kpi_circuito", "v_kpi_geral", "v_convergencia", "v_matriz_confusao", "v_ambiguidade",
              "v_resumo_ambiguidade", "v_desempenho_por_componente", "v_uso_diario", "v_assinaturas",
              "v_qualidade_dados"):
        assert con.execute(f"select count(*) from {v}").fetchone()[0] > 0, v

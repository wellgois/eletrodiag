"""Gera docs/data_dictionary.md a partir dos esquemas REAIS dos Parquets (documentação como código).

Falha se alguma coluna não tiver descrição: assim a documentação nunca fica para trás do dado.

    python -m eletrodiag.docs.gen_dictionary
"""
from __future__ import annotations

import pandas as pd

from ..pipeline import config as C

COL = {
    "circuit_id": "Identificador do circuito (ex.: `emissor_comum`).",
    "nome": "Nome didático do circuito.", "descricao": "Descrição em texto (circuito ou falha, conforme a tabela).",
    "nivel": "Nível do circuito: `iniciante`, `intermediario` ou `avancado`.",
    "hazard": "Aviso de segurança do circuito (vazio quando não há perigo especial).",
    "nota": "Limites do modelo do circuito (o que a simulação não representa).",
    "n_components": "Quantidade de componentes.", "n_observables": "Quantidade de pontos medíveis.",
    "n_faults": "Quantidade de falhas catalogadas.", "svg": "Esquema do circuito em SVG (não exportado para CSV).",
    "component_id": "Identificador do componente (ex.: `R1`, `Q1`).",
    "kind": "Tipo: componente (`R`, `LED`, `ZD`, `Q`, `V`) ou observável (`V` tensão, `I` corrente).",
    "nominal": "Valor/modelo nominal do componente.", "funcao": "Função do componente no circuito.",
    "observable_id": "Ponto de medição, ex.: `V(B)` (tensão no nó B) ou `I(R1)` (corrente em R1).",
    "ref": "Nó (tensão) ou elemento (corrente) a que o observável se refere.",
    "label": "Rótulo legível do ponto de medição.", "onde": "Instrução de como medir.",
    "unit": "Unidade SI do observável (`V` ou `A`).", "cost": "Custo relativo da medição (tensão = 1; corrente = 2,5).",
    "fault_id": "Identificador da falha: `componente:modo` (ex.: `R1:open`) ou `OK` (circuito saudável).",
    "mode": "Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`.",
    "prior": "Probabilidade a priori da falha (pesos de trabalho, soma 1 por circuito).",
    "teste_confirmacao": "Teste para confirmar a falha com o circuito desligado.", "acao": "Ação recomendada.",
    "mean": "Média do observável sob a falha (Monte Carlo).", "std": "Desvio-padrão (efeito das tolerâncias).",
    "min": "Mínimo observado.", "max": "Máximo observado.", "n": "Número de amostras Monte Carlo.",
    "p05": "Percentil 5.", "p95": "Percentil 95.",
    "fault_a": "Primeira falha do par.", "fault_b": "Segunda falha do par.",
    "component_a": "Componente da primeira falha.", "component_b": "Componente da segunda falha.",
    "dist_voltage": "Distância de Bhattacharyya total usando só tensões (maior = mais separável).",
    "dist_all": "Distância de Bhattacharyya total usando tensões e correntes.",
    "class": "`distinguivel_por_tensao`, `requer_corrente`, `indistinguivel_eletricamente` ou `mesmo_componente` (limiar 3,0).",
    "session_id": "Identificador da sessão de diagnóstico.", "learner_id": "Pseudônimo do estudante (hash; sem dado pessoal).",
    "level": "Nível do estudante: `iniciante` ou `intermediario`.", "device": "`mobile` ou `desktop`.",
    "app_version": "Versão do app que emitiu os eventos.",
    "started_at": "Início da sessão (UTC).", "finished_at": "Fim da sessão (UTC); nulo se não houve evento de término.",
    "outcome": "Desfecho informado: `reparado`, `troca_errada` ou `desistiu`.",
    "replaced_component": "Componente que o estudante trocou.",
    "stop_reason": "Motivo da parada: `confianca`, `sem_mais_medicoes`, `componente_encontrado`, `sem_mais_componentes`, `abandono`, `manual`.",
    "status": "`completed` (tem evento de término) ou `incomplete`.",
    "n_measurements": "Medições na sessão.", "n_component_tests": "Testes de componente na sessão.",
    "n_steps": "Passos totais (medições + testes de componente).", "duration_s": "Duração em segundos.",
    "date_id": "Chave de data AAAAMMDD (fuso de Brasília).", "is_completed": "Verdadeiro se a sessão foi concluída.",
    "duration_min": "Duração em minutos.", "scenario_id": "Cenário de defeito (mesmo defeito nos 3 métodos; só em dados sintéticos).",
    "true_fault": "Falha real (gabarito; só em dados sintéticos).", "true_component": "Componente realmente defeituoso (gabarito).",
    "replaced_is_correct": "Componente trocado == componente defeituoso (nulo sem gabarito).",
    "final_top_prob": "Probabilidade do suspeito principal na última medição.",
    "success": "Verdadeiro se o desfecho foi `reparado`.",
    "step": "Número do passo dentro da sessão (1, 2, ...).", "value_si": "Leitura em unidade SI (V ou A).",
    "top_component": "Suspeito principal após o passo.", "top_prob": "Probabilidade do suspeito principal.",
    "top_fault": "Falha mais provável dentro do suspeito principal.",
    "p_true_component": "Probabilidade atribuída ao componente realmente defeituoso.",
    "top_is_true": "O suspeito principal é o componente defeituoso.",
    "n_sessions": "Quantidade de sessões.", "success_rate": "Fração de sessões concluídas com desfecho `reparado`.",
    "wrong_replacement_rate": "Fração com `troca_errada`.", "giveup_rate": "Fração com `desistiu`.",
    "avg_steps": "Média de passos.", "median_steps": "Mediana de passos.", "p90_steps": "Percentil 90 de passos.",
    "avg_duration_min": "Duração média em minutos.",
    "steps_reduction_vs_baseline_pct": "Redução % de passos contra o método atual (mesmo circuito).",
    "time_reduction_vs_baseline_pct": "Redução % de tempo contra o método atual (mesmo circuito).",
    "top1_correct_rate": "Fração de sessões em que o suspeito nº 1 é o correto naquele passo.",
    "mean_top_prob": "Confiança média no suspeito principal.", "mean_p_true_component": "Probabilidade média do componente correto.",
    "true_component_": "", "n_measurements_": "",
    "avg_step_position": "Posição média (passo) em que o ponto foi medido.",
    "first_choice_rate": "Fração das vezes em que foi a primeira medição.",
    "date": "Data (dia).", "year": "Ano.", "month": "Mês.", "day": "Dia do mês.", "iso_week": "Semana ISO.",
    "weekday": "Dia da semana.", "is_weekend": "Fim de semana.", "mode_label": "Rótulo do método.",
    "usa_app": "O método usa o app.",
    "event_id": "Identificador único do evento.", "raw_value": "Leitura como foi digitada.", "unit_raw": "Unidade como foi informada.",
    "unit_si": "Unidade SI normalizada.", "ts": "Instante do evento (UTC).", "component_id_": "",
    "verdict": "Resultado do teste de componente: `defeituoso` ou `ok`.",
    "synthetic": "Marca dado sintético.",
    "run_id": "Identificador da execução do pipeline (ou da simulação, em sim_runs).",
    "fault_mode": "Modo da falha injetada.", "mc_idx": "Índice da amostra Monte Carlo.", "value": "Valor simulado do observável (SI).",
    "layer": "Camada (`silver`, `gold`).", "dataset": "Conjunto de dados verificado.", "rule": "Nome da regra de qualidade.",
    "severity": "`error`, `warn` ou `info`.", "checked": "Registros verificados.", "failed": "Registros que falharam.",
    "detail": "Observação da regra.", "logged_at": "Instante do registro (UTC).",
    "step_": "", "started_at_": "", "ended_at": "Fim da etapa (UTC).", "seconds": "Duração da etapa em segundos.",
    "details": "Detalhes da etapa (JSON).", "error": "Traceback, se a etapa falhou.",
}
COL["step"] = "Número do passo na sessão (1, 2, ...) ou etapa do pipeline (fct_pipeline_run)."

TABLES = {
    "silver": [
        ("dim_circuit", "1 linha por circuito", "bronze/catalog"),
        ("dim_component", "1 linha por componente", "bronze/catalog"),
        ("dim_observable", "1 linha por ponto de medição", "bronze/catalog"),
        ("dim_fault", "1 linha por falha catalogada", "bronze/catalog"),
        ("sim_runs", "1 linha por simulação × observável (particionada por circuito)", "bronze/sim_runs"),
        ("sessions", "1 linha por sessão de diagnóstico", "bronze/app_events"),
        ("measurements", "1 linha por medição registrada", "bronze/app_events"),
        ("component_tests", "1 linha por teste de componente (método atual)", "bronze/app_events"),
        ("diagnosis_events", "1 linha por diagnóstico exibido pelo app", "bronze/app_events"),
        ("scenario_truth", "1 linha por sessão sintética (gabarito)", "bronze/scenario_truth"),
    ],
    "gold": [
        ("dim_circuit", "1 linha por circuito", "silver.dim_circuit"),
        ("dim_component", "1 linha por componente", "silver.dim_component"),
        ("dim_observable", "1 linha por ponto de medição", "silver.dim_observable"),
        ("dim_fault", "1 linha por falha", "silver.dim_fault"),
        ("dim_mode", "1 linha por método", "constante do pipeline"),
        ("dim_level", "1 linha por nível", "constante do pipeline"),
        ("dim_date", "1 linha por dia", "silver.sessions"),
        ("fct_fault_signature", "circuito × falha × observável", "silver.sim_runs"),
        ("fct_fault_pair_separability", "circuito × par de falhas", "dictionary.json"),
        ("fct_session", "1 linha por sessão", "silver.sessions + scenario_truth"),
        ("fct_session_step", "1 linha por medição, com o posterior reexecutado", "silver.measurements + dicionário"),
        ("agg_kpi_circuit_mode", "circuito × método", "fct_session"),
        ("agg_kpi_overall_mode", "método (todos os circuitos)", "fct_session"),
        ("agg_convergence", "circuito × método × passo", "fct_session_step"),
        ("agg_confusion", "circuito × método × componente real × componente trocado", "fct_session"),
        ("agg_observable_usage", "circuito × método × ponto de medição", "silver.measurements"),
        ("agg_daily_usage", "dia × método", "fct_session"),
    ],
}
META = {
    "fct_dq_result": ("1 linha por regra de qualidade executada", "_meta/dq_results.jsonl",
                      ["run_id", "layer", "dataset", "rule", "severity", "checked", "failed", "detail", "logged_at"]),
    "fct_pipeline_run": ("1 linha por etapa executada", "_meta/runs.jsonl",
                         ["run_id", "step", "status", "started_at", "ended_at", "seconds", "details", "error"]),
}


def _table_md(name, grain, src, df: pd.DataFrame) -> str:
    out = [f"### `{name}`", "", f"**Granularidade:** {grain}. **Origem:** {src}. **Linhas (execução de exemplo):** {len(df):,}.".replace(",", "."), "",
           "| Coluna | Tipo | Descrição |", "|---|---|---|"]
    for col, dt in df.dtypes.items():
        desc = COL.get(col)
        if not desc:
            raise KeyError(f"coluna sem descrição: {name}.{col}")
        out.append(f"| `{col}` | {dt} | {desc} |")
    return "\n".join(out) + "\n"


def build() -> str:
    parts = ["# Dicionário de dados", "",
             "Gerado automaticamente por `python -m eletrodiag.docs.gen_dictionary` a partir dos Parquets reais. "
             "Não edite à mão: altere as descrições em `src/eletrodiag/docs/gen_dictionary.py`.", "",
             "A camada **bronze** guarda o dado como chegou (JSON Lines); seu contrato está em [event_contract.md](event_contract.md).", ""]
    from ..pipeline import silver
    parts.append("## Silver\n")
    for name, grain, src in TABLES["silver"]:
        parts.append(_table_md(name, grain, src, silver.read(name)))
    parts.append("## Gold\n")
    for name, grain, src in TABLES["gold"]:
        parts.append(_table_md(name, grain, src, pd.read_parquet(C.GOLD / f"{name}.parquet")))
    parts.append("## Metadados do pipeline (publicados também no warehouse)\n")
    import json
    for name, (grain, src, cols) in META.items():
        fn = C.META / ("dq_results.jsonl" if name == "fct_dq_result" else "runs.jsonl")
        rows = [json.loads(x) for x in fn.read_text().splitlines() if x.strip()]
        df = pd.DataFrame(rows).reindex(columns=cols)  # "error" só existe se alguma etapa falhou
        parts.append(_table_md(name, grain, src, df))
    return "\n".join(parts)


if __name__ == "__main__":
    out = C.REPO / "docs" / "data_dictionary.md"
    out.write_text(build(), encoding="utf-8")
    print(f"escrito {out}")

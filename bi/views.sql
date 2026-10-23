-- Views de consumo para BI (SQL padrão: funciona em DuckDB e SQLite).
-- Conecte a ferramenta de BI nestas views. Elas escondem os joins do modelo dimensional.

CREATE VIEW v_kpi_circuito AS
SELECT k.circuit_id,
       c.nome            AS circuito,
       c.nivel           AS nivel_circuito,
       k.mode            AS modo,
       m.mode_label      AS metodo,
       k.n_sessions      AS sessoes,
       k.success_rate    AS taxa_sucesso,
       k.wrong_replacement_rate AS taxa_troca_errada,
       k.giveup_rate     AS taxa_desistencia,
       k.avg_steps       AS passos_medios,
       k.median_steps    AS passos_mediana,
       k.p90_steps       AS passos_p90,
       k.avg_duration_min AS duracao_media_min,
       k.steps_reduction_vs_baseline_pct AS reducao_passos_pct,
       k.time_reduction_vs_baseline_pct  AS reducao_tempo_pct
FROM agg_kpi_circuit_mode k
JOIN dim_circuit c ON c.circuit_id = k.circuit_id
JOIN dim_mode m    ON m.mode = k.mode;

CREATE VIEW v_kpi_geral AS
SELECT k.mode AS modo, m.mode_label AS metodo, k.n_sessions AS sessoes,
       k.success_rate AS taxa_sucesso, k.wrong_replacement_rate AS taxa_troca_errada,
       k.giveup_rate AS taxa_desistencia, k.avg_steps AS passos_medios,
       k.median_steps AS passos_mediana, k.p90_steps AS passos_p90,
       k.avg_duration_min AS duracao_media_min
FROM agg_kpi_overall_mode k
JOIN dim_mode m ON m.mode = k.mode;

CREATE VIEW v_convergencia AS
SELECT a.circuit_id, c.nome AS circuito, a.mode AS modo, a.step AS passo,
       a.n_sessions AS sessoes, a.top1_correct_rate AS acerto_top1,
       a.mean_top_prob AS confianca_media, a.mean_p_true_component AS prob_media_componente_real
FROM agg_convergence a
JOIN dim_circuit c ON c.circuit_id = a.circuit_id;

CREATE VIEW v_matriz_confusao AS
SELECT x.circuit_id, c.nome AS circuito, x.mode AS modo,
       x.true_component AS componente_real, x.replaced_component AS componente_trocado,
       x.n_sessions AS sessoes,
       CASE WHEN x.true_component = x.replaced_component THEN 1 ELSE 0 END AS acerto
FROM agg_confusion x
JOIN dim_circuit c ON c.circuit_id = x.circuit_id;

CREATE VIEW v_ambiguidade AS
SELECT p.circuit_id, c.nome AS circuito, p.fault_a AS falha_a, p.fault_b AS falha_b,
       p.component_a AS componente_a, p.component_b AS componente_b,
       p.dist_voltage AS distancia_tensao, p.dist_all AS distancia_total,
       p."class" AS classe
FROM fct_fault_pair_separability p
JOIN dim_circuit c ON c.circuit_id = p.circuit_id
WHERE p."class" IN ('requer_corrente', 'indistinguivel_eletricamente');

CREATE VIEW v_resumo_ambiguidade AS
SELECT circuit_id, "class" AS classe, COUNT(*) AS pares
FROM fct_fault_pair_separability
WHERE "class" <> 'mesmo_componente'
GROUP BY circuit_id, "class";

CREATE VIEW v_desempenho_por_componente AS
SELECT s.circuit_id, c.nome AS circuito, s.true_component AS componente_defeituoso, s.mode AS modo,
       COUNT(*) AS sessoes,
       AVG(CASE WHEN s.success THEN 1.0 ELSE 0.0 END) AS taxa_sucesso,
       AVG(s.n_steps) AS passos_medios
FROM fct_session s
JOIN dim_circuit c ON c.circuit_id = s.circuit_id
WHERE s.is_completed AND s.true_component IS NOT NULL
GROUP BY s.circuit_id, c.nome, s.true_component, s.mode;

CREATE VIEW v_uso_diario AS
SELECT d."date" AS data, d.mode AS modo, d.n_sessions AS sessoes, d.avg_steps AS passos_medios,
       d.success_rate AS taxa_sucesso
FROM agg_daily_usage d;

CREATE VIEW v_assinaturas AS
SELECT f.circuit_id, f.fault_id AS falha, df.component_id AS componente, df.mode AS modo_falha,
       f.observable_id AS observavel, f.mean AS media, f.std AS desvio, f.p05, f.p95, f.n AS amostras
FROM fct_fault_signature f
LEFT JOIN dim_fault df ON df.circuit_id = f.circuit_id AND df.fault_id = f.fault_id;

CREATE VIEW v_qualidade_dados AS
SELECT r.layer AS camada, r.dataset, r.rule AS regra, r.severity AS severidade, r.checked AS verificados,
       r.failed AS falhas,
       CASE WHEN r.checked = 0 THEN 0.0 ELSE 1.0 * r.failed / r.checked END AS taxa_falha,
       r.logged_at
FROM fct_dq_result r
WHERE r.logged_at = (SELECT MAX(x.logged_at) FROM fct_dq_result x
                     WHERE x.layer = r.layer AND x.dataset = r.dataset AND x.rule = r.rule);

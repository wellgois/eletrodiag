# Qualidade de dados

O pipeline tem um motor simples de regras (`pipeline/quality.py`). Cada regra registra quantas linhas verificou e quantas falharam, com uma severidade.

## Severidades

| Severidade | Significado | Efeito |
|---|---|---|
| `error` | Contrato quebrado. Algo está errado no código ou na entrada | O pipeline falha (`exit code` diferente de zero) |
| `warn` | Sujeira esperada em dados de campo (duplicata, JSON truncado, sessão sem fim) | O pipeline segue; a linha é corrigida ou vai para a quarentena |
| `info` | Informativa | Só registrada |

## Onde ficam os resultados

- `data/_meta/dq_results.jsonl`: uma linha por regra e por execução.
- Warehouse: tabela `fct_dq_result` e view `v_qualidade_dados`.
- Painel: bloco "Qualidade dos dados".

## Regras

Todas rodam a cada execução. Estado na execução de demonstração: **0 `error`**; as `warn` apontam a sujeira que o gerador injeta de propósito.

| Camada | Conjunto | Regra | Sev. | O que verifica |
|---|---|---|---|---|
| silver | dim_* | `primary_key_unique` | error | Chave primária única em circuito, componente, observável e falha |
| silver | dim_fault | `component_exists` | error | Todo defeito aponta para um componente existente |
| silver | dim_fault | `prior_sums_to_one` | error | A probabilidade a priori soma 1 em cada circuito |
| silver | sim_runs | `converged` | error | Todas as simulações convergiram (as que não, vão à quarentena) |
| silver | sim_runs | `value_is_finite` | error | Nenhum NaN ou infinito |
| silver | sim_runs | `value_in_physical_range` | error | Tensão entre -1 e 600 V e corrente entre -1 e 1000 A (faixa que cobre os blocos de alta tensão do inversor) |
| silver | sim_runs | `unique_run_observable` | warn | Sem repetição por reprocessamento (mantém o lote mais recente) |
| silver | sim_runs | `every_fault_simulated` | error | Todo defeito do catálogo tem simulações |
| silver | app_events | `json_parseable_and_required_fields` | warn | Linha é JSON e tem os campos do envelope |
| silver | app_events | `unique_event_id` | warn | Sem evento duplicado |
| silver | app_events | `session_has_start_event` | warn | Toda sessão tem `session_started` |
| silver | sessions | `mode_is_valid` | error | Método é um dos três conhecidos |
| silver | sessions | `session_completed` | warn | Sessão tem `session_finished` |
| silver | sessions | `outcome_is_valid` | error | Resultado é `reparado`, `troca_errada` ou `desistiu` |
| silver | sessions | `has_steps_when_completed` | warn | Sessão concluída tem ao menos um passo |
| silver | measurements | `valid_observable_and_parseable_value` | warn | Observável conhecido e valor legível |
| silver | measurements | `unique_session_step` | warn | Um passo por sessão e número |
| silver | component_tests | `valid_component_and_verdict` | warn | Componente existe e veredito é válido |
| silver | diagnosis_events | `probability_in_0_1` | error | Probabilidades entre 0 e 1 |
| silver | scenario_truth | `session_known` | warn | O gabarito pertence a uma sessão conhecida |
| gold | fct_fault_signature | `enough_samples_per_signature` | error | Pelo menos 30 amostras por assinatura |
| gold | fct_fault_signature | `no_null_stats` | error | Média e desvio sem nulos |
| gold | fct_fault_pair_separability | `has_pairs` | error | A tabela não está vazia |
| gold | fct_session | `unique_session` | error | Uma linha por sessão |
| gold | fct_session | `completed_has_outcome` | error | Sessão concluída tem resultado |
| gold | agg_kpi_circuit_mode | `all_modes_present_per_circuit` | error | Cada circuito tem os três métodos |

## Quarentena

Linhas rejeitadas não somem. Vão para `data/silver/_quarantine/<conjunto>/<run_id>.parquet` com:

| Coluna | Conteúdo |
|---|---|
| `reason` | Motivo da rejeição (ex.: `invalid_json`, `unparseable_value`, `not_converged`, `out_of_range`) |
| `batch_id` | Lote bronze de origem |
| `line_no` | Linha no arquivo de origem |
| `raw` | Dado original |

Com isso dá para auditar, corrigir a origem e reprocessar.

## Sujeira injetada no gerador

Para que as regras tenham o que pegar, o gerador de eventos injeta: eventos duplicados, JSON truncado, medições sem valor, linhas fora de ordem, vírgula decimal, unidades misturadas (`V`, `mV`, `mA`, `µA`) e formatos de data diferentes. A proporção é pequena e fixa (semente `20261022`).

## Como acrescentar uma regra

1. Chame `dq.check(camada, conjunto, nome, verificadas, falhas, severidade, detalhe)` no ponto do código onde o dado está disponível.
2. Se a regra descartar linhas, mande-as para `quarantine(...)` com um `reason`.
3. Documente a regra na tabela acima.
4. Acrescente um teste em `tests/test_pipeline.py`.

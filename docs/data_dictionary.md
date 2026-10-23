# Dicionário de dados

Gerado automaticamente por `python -m eletrodiag.docs.gen_dictionary` a partir dos Parquets reais. Não edite à mão: altere as descrições em `src/eletrodiag/docs/gen_dictionary.py`.

A camada **bronze** guarda o dado como chegou (JSON Lines); seu contrato está em [event_contract.md](event_contract.md).

## Silver

### `dim_circuit`

**Granularidade:** 1 linha por circuito. **Origem:** bronze/catalog. **Linhas (execução de exemplo):** 10.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `nome` | str | Nome didático do circuito. |
| `descricao` | str | Descrição em texto (circuito ou falha, conforme a tabela). |
| `nivel` | str | Nível do circuito: `iniciante`, `intermediario` ou `avancado`. |
| `n_components` | int64 | Quantidade de componentes. |
| `n_observables` | int64 | Quantidade de pontos medíveis. |
| `n_faults` | int64 | Quantidade de falhas catalogadas. |
| `hazard` | str | Aviso de segurança do circuito (vazio quando não há perigo especial). |
| `nota` | str | Limites do modelo do circuito (o que a simulação não representa). |
| `svg` | str | Esquema do circuito em SVG (não exportado para CSV). |

### `dim_component`

**Granularidade:** 1 linha por componente. **Origem:** bronze/catalog. **Linhas (execução de exemplo):** 73.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `component_id` | str | Identificador do componente (ex.: `R1`, `Q1`). |
| `kind` | str | Tipo: componente (`R`, `LED`, `ZD`, `Q`, `V`) ou observável (`V` tensão, `I` corrente). |
| `nominal` | str | Valor/modelo nominal do componente. |
| `funcao` | str | Função do componente no circuito. |

### `dim_observable`

**Granularidade:** 1 linha por ponto de medição. **Origem:** bronze/catalog. **Linhas (execução de exemplo):** 55.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `observable_id` | str | Ponto de medição, ex.: `V(B)` (tensão no nó B) ou `I(R1)` (corrente em R1). |
| `kind` | str | Tipo: componente (`R`, `LED`, `ZD`, `Q`, `V`) ou observável (`V` tensão, `I` corrente). |
| `ref` | str | Nó (tensão) ou elemento (corrente) a que o observável se refere. |
| `label` | str | Rótulo legível do ponto de medição. |
| `onde` | str | Instrução de como medir. |
| `unit` | str | Unidade SI do observável (`V` ou `A`). |
| `cost` | float64 | Custo relativo da medição (tensão = 1; corrente = 2,5). |

### `dim_fault`

**Granularidade:** 1 linha por falha catalogada. **Origem:** bronze/catalog. **Linhas (execução de exemplo):** 261.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `fault_id` | str | Identificador da falha: `componente:modo` (ex.: `R1:open`) ou `OK` (circuito saudável). |
| `component_id` | str | Identificador do componente (ex.: `R1`, `Q1`). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `prior` | float64 | Probabilidade a priori da falha (pesos de trabalho, soma 1 por circuito). |
| `descricao` | str | Descrição em texto (circuito ou falha, conforme a tabela). |
| `teste_confirmacao` | str | Teste para confirmar a falha com o circuito desligado. |
| `acao` | str | Ação recomendada. |

### `sim_runs`

**Granularidade:** 1 linha por simulação × observável (particionada por circuito). **Origem:** bronze/sim_runs. **Linhas (execução de exemplo):** 248.700.

| Coluna | Tipo | Descrição |
|---|---|---|
| `run_id` | str | Identificador da execução do pipeline (ou da simulação, em sim_runs). |
| `fault_id` | str | Identificador da falha: `componente:modo` (ex.: `R1:open`) ou `OK` (circuito saudável). |
| `component_id` | str | Identificador do componente (ex.: `R1`, `Q1`). |
| `fault_mode` | str | Modo da falha injetada. |
| `mc_idx` | int64 | Índice da amostra Monte Carlo. |
| `observable_id` | str | Ponto de medição, ex.: `V(B)` (tensão no nó B) ou `I(R1)` (corrente em R1). |
| `value` | float64 | Valor simulado do observável (SI). |
| `unit` | str | Unidade SI do observável (`V` ou `A`). |
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |

### `sessions`

**Granularidade:** 1 linha por sessão de diagnóstico. **Origem:** bronze/app_events. **Linhas (execução de exemplo):** 8.963.

| Coluna | Tipo | Descrição |
|---|---|---|
| `session_id` | str | Identificador da sessão de diagnóstico. |
| `learner_id` | str | Pseudônimo do estudante (hash; sem dado pessoal). |
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `level` | str | Nível do estudante: `iniciante` ou `intermediario`. |
| `device` | str | `mobile` ou `desktop`. |
| `app_version` | str | Versão do app que emitiu os eventos. |
| `started_at` | datetime64[us, UTC] | Início da sessão (UTC). |
| `finished_at` | datetime64[us, UTC] | Fim da sessão (UTC); nulo se não houve evento de término. |
| `outcome` | str | Desfecho informado: `reparado`, `troca_errada` ou `desistiu`. |
| `replaced_component` | str | Componente que o estudante trocou. |
| `stop_reason` | str | Motivo da parada: `confianca`, `sem_mais_medicoes`, `componente_encontrado`, `sem_mais_componentes`, `abandono`, `manual`. |
| `status` | str | `completed` (tem evento de término) ou `incomplete`. |
| `n_measurements` | int64 | Medições na sessão. |
| `n_component_tests` | int64 | Testes de componente na sessão. |
| `n_steps` | int64 | Passos totais (medições + testes de componente). |
| `duration_s` | float64 | Duração em segundos. |

### `measurements`

**Granularidade:** 1 linha por medição registrada. **Origem:** bronze/app_events. **Linhas (execução de exemplo):** 21.244.

| Coluna | Tipo | Descrição |
|---|---|---|
| `event_id` | str | Identificador único do evento. |
| `session_id` | str | Identificador da sessão de diagnóstico. |
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `step` | int64 | Número do passo na sessão (1, 2, ...) ou etapa do pipeline (fct_pipeline_run). |
| `observable_id` | str | Ponto de medição, ex.: `V(B)` (tensão no nó B) ou `I(R1)` (corrente em R1). |
| `raw_value` | str | Leitura como foi digitada. |
| `unit_raw` | str | Unidade como foi informada. |
| `value_si` | float64 | Leitura em unidade SI (V ou A). |
| `unit_si` | str | Unidade SI normalizada. |
| `duration_s` | float64 | Duração em segundos. |
| `ts` | datetime64[us, UTC] | Instante do evento (UTC). |

### `component_tests`

**Granularidade:** 1 linha por teste de componente (método atual). **Origem:** bronze/app_events. **Linhas (execução de exemplo):** 12.795.

| Coluna | Tipo | Descrição |
|---|---|---|
| `event_id` | str | Identificador único do evento. |
| `session_id` | str | Identificador da sessão de diagnóstico. |
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `step` | int64 | Número do passo na sessão (1, 2, ...) ou etapa do pipeline (fct_pipeline_run). |
| `component_id` | str | Identificador do componente (ex.: `R1`, `Q1`). |
| `verdict` | str | Resultado do teste de componente: `defeituoso` ou `ok`. |
| `duration_s` | float64 | Duração em segundos. |
| `ts` | datetime64[us, UTC] | Instante do evento (UTC). |

### `diagnosis_events`

**Granularidade:** 1 linha por diagnóstico exibido pelo app. **Origem:** bronze/app_events. **Linhas (execução de exemplo):** 21.347.

| Coluna | Tipo | Descrição |
|---|---|---|
| `event_id` | str | Identificador único do evento. |
| `session_id` | str | Identificador da sessão de diagnóstico. |
| `step` | int64 | Número do passo na sessão (1, 2, ...) ou etapa do pipeline (fct_pipeline_run). |
| `top_component` | str | Suspeito principal após o passo. |
| `top_fault` | str | Falha mais provável dentro do suspeito principal. |
| `top_prob` | float64 | Probabilidade do suspeito principal. |
| `ts` | datetime64[us, UTC] | Instante do evento (UTC). |

### `scenario_truth`

**Granularidade:** 1 linha por sessão sintética (gabarito). **Origem:** bronze/scenario_truth. **Linhas (execução de exemplo):** 9.000.

| Coluna | Tipo | Descrição |
|---|---|---|
| `session_id` | str | Identificador da sessão de diagnóstico. |
| `scenario_id` | str | Cenário de defeito (mesmo defeito nos 3 métodos; só em dados sintéticos). |
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `true_fault` | str | Falha real (gabarito; só em dados sintéticos). |
| `synthetic` | bool | Marca dado sintético. |

## Gold

### `dim_circuit`

**Granularidade:** 1 linha por circuito. **Origem:** silver.dim_circuit. **Linhas (execução de exemplo):** 10.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `nome` | str | Nome didático do circuito. |
| `descricao` | str | Descrição em texto (circuito ou falha, conforme a tabela). |
| `nivel` | str | Nível do circuito: `iniciante`, `intermediario` ou `avancado`. |
| `n_components` | int64 | Quantidade de componentes. |
| `n_observables` | int64 | Quantidade de pontos medíveis. |
| `n_faults` | int64 | Quantidade de falhas catalogadas. |
| `hazard` | str | Aviso de segurança do circuito (vazio quando não há perigo especial). |
| `nota` | str | Limites do modelo do circuito (o que a simulação não representa). |
| `svg` | str | Esquema do circuito em SVG (não exportado para CSV). |

### `dim_component`

**Granularidade:** 1 linha por componente. **Origem:** silver.dim_component. **Linhas (execução de exemplo):** 73.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `component_id` | str | Identificador do componente (ex.: `R1`, `Q1`). |
| `kind` | str | Tipo: componente (`R`, `LED`, `ZD`, `Q`, `V`) ou observável (`V` tensão, `I` corrente). |
| `nominal` | str | Valor/modelo nominal do componente. |
| `funcao` | str | Função do componente no circuito. |

### `dim_observable`

**Granularidade:** 1 linha por ponto de medição. **Origem:** silver.dim_observable. **Linhas (execução de exemplo):** 55.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `observable_id` | str | Ponto de medição, ex.: `V(B)` (tensão no nó B) ou `I(R1)` (corrente em R1). |
| `kind` | str | Tipo: componente (`R`, `LED`, `ZD`, `Q`, `V`) ou observável (`V` tensão, `I` corrente). |
| `ref` | str | Nó (tensão) ou elemento (corrente) a que o observável se refere. |
| `label` | str | Rótulo legível do ponto de medição. |
| `onde` | str | Instrução de como medir. |
| `unit` | str | Unidade SI do observável (`V` ou `A`). |
| `cost` | float64 | Custo relativo da medição (tensão = 1; corrente = 2,5). |

### `dim_fault`

**Granularidade:** 1 linha por falha. **Origem:** silver.dim_fault. **Linhas (execução de exemplo):** 261.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `fault_id` | str | Identificador da falha: `componente:modo` (ex.: `R1:open`) ou `OK` (circuito saudável). |
| `component_id` | str | Identificador do componente (ex.: `R1`, `Q1`). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `prior` | float64 | Probabilidade a priori da falha (pesos de trabalho, soma 1 por circuito). |
| `descricao` | str | Descrição em texto (circuito ou falha, conforme a tabela). |
| `teste_confirmacao` | str | Teste para confirmar a falha com o circuito desligado. |
| `acao` | str | Ação recomendada. |

### `dim_mode`

**Granularidade:** 1 linha por método. **Origem:** constante do pipeline. **Linhas (execução de exemplo):** 3.

| Coluna | Tipo | Descrição |
|---|---|---|
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `mode_label` | str | Rótulo do método. |
| `usa_app` | bool | O método usa o app. |

### `dim_level`

**Granularidade:** 1 linha por nível. **Origem:** constante do pipeline. **Linhas (execução de exemplo):** 2.

| Coluna | Tipo | Descrição |
|---|---|---|
| `level` | str | Nível do estudante: `iniciante` ou `intermediario`. |

### `dim_date`

**Granularidade:** 1 linha por dia. **Origem:** silver.sessions. **Linhas (execução de exemplo):** 50.

| Coluna | Tipo | Descrição |
|---|---|---|
| `date_id` | int64 | Chave de data AAAAMMDD (fuso de Brasília). |
| `date` | object | Data (dia). |
| `year` | int32 | Ano. |
| `month` | int32 | Mês. |
| `day` | int32 | Dia do mês. |
| `iso_week` | int64 | Semana ISO. |
| `weekday` | str | Dia da semana. |
| `is_weekend` | bool | Fim de semana. |

### `fct_fault_signature`

**Granularidade:** circuito × falha × observável. **Origem:** silver.sim_runs. **Linhas (execução de exemplo):** 1.658.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `fault_id` | str | Identificador da falha: `componente:modo` (ex.: `R1:open`) ou `OK` (circuito saudável). |
| `observable_id` | str | Ponto de medição, ex.: `V(B)` (tensão no nó B) ou `I(R1)` (corrente em R1). |
| `mean` | float64 | Média do observável sob a falha (Monte Carlo). |
| `std` | float64 | Desvio-padrão (efeito das tolerâncias). |
| `min` | float64 | Mínimo observado. |
| `max` | float64 | Máximo observado. |
| `n` | int64 | Número de amostras Monte Carlo. |
| `p05` | float64 | Percentil 5. |
| `p95` | float64 | Percentil 95. |

### `fct_fault_pair_separability`

**Granularidade:** circuito × par de falhas. **Origem:** dictionary.json. **Linhas (execução de exemplo):** 4.553.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `fault_a` | str | Primeira falha do par. |
| `fault_b` | str | Segunda falha do par. |
| `component_a` | str | Componente da primeira falha. |
| `component_b` | str | Componente da segunda falha. |
| `dist_voltage` | float64 | Distância de Bhattacharyya total usando só tensões (maior = mais separável). |
| `dist_all` | float64 | Distância de Bhattacharyya total usando tensões e correntes. |
| `class` | str | `distinguivel_por_tensao`, `requer_corrente`, `indistinguivel_eletricamente` ou `mesmo_componente` (limiar 3,0). |

### `fct_session`

**Granularidade:** 1 linha por sessão. **Origem:** silver.sessions + scenario_truth. **Linhas (execução de exemplo):** 8.963.

| Coluna | Tipo | Descrição |
|---|---|---|
| `session_id` | str | Identificador da sessão de diagnóstico. |
| `learner_id` | str | Pseudônimo do estudante (hash; sem dado pessoal). |
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `level` | str | Nível do estudante: `iniciante` ou `intermediario`. |
| `device` | str | `mobile` ou `desktop`. |
| `app_version` | str | Versão do app que emitiu os eventos. |
| `started_at` | datetime64[us, UTC] | Início da sessão (UTC). |
| `finished_at` | datetime64[us, UTC] | Fim da sessão (UTC); nulo se não houve evento de término. |
| `outcome` | str | Desfecho informado: `reparado`, `troca_errada` ou `desistiu`. |
| `replaced_component` | str | Componente que o estudante trocou. |
| `stop_reason` | str | Motivo da parada: `confianca`, `sem_mais_medicoes`, `componente_encontrado`, `sem_mais_componentes`, `abandono`, `manual`. |
| `status` | str | `completed` (tem evento de término) ou `incomplete`. |
| `n_measurements` | int64 | Medições na sessão. |
| `n_component_tests` | int64 | Testes de componente na sessão. |
| `n_steps` | int64 | Passos totais (medições + testes de componente). |
| `duration_s` | float64 | Duração em segundos. |
| `date_id` | int64 | Chave de data AAAAMMDD (fuso de Brasília). |
| `is_completed` | bool | Verdadeiro se a sessão foi concluída. |
| `duration_min` | float64 | Duração em minutos. |
| `scenario_id` | str | Cenário de defeito (mesmo defeito nos 3 métodos; só em dados sintéticos). |
| `true_fault` | str | Falha real (gabarito; só em dados sintéticos). |
| `true_component` | str | Componente realmente defeituoso (gabarito). |
| `replaced_is_correct` | boolean | Componente trocado == componente defeituoso (nulo sem gabarito). |
| `final_top_prob` | float64 | Probabilidade do suspeito principal na última medição. |
| `success` | bool | Verdadeiro se o desfecho foi `reparado`. |

### `fct_session_step`

**Granularidade:** 1 linha por medição. com o posterior reexecutado. **Origem:** silver.measurements + dicionário. **Linhas (execução de exemplo):** 21.244.

| Coluna | Tipo | Descrição |
|---|---|---|
| `session_id` | str | Identificador da sessão de diagnóstico. |
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `step` | int64 | Número do passo na sessão (1, 2, ...) ou etapa do pipeline (fct_pipeline_run). |
| `observable_id` | str | Ponto de medição, ex.: `V(B)` (tensão no nó B) ou `I(R1)` (corrente em R1). |
| `value_si` | float64 | Leitura em unidade SI (V ou A). |
| `top_component` | str | Suspeito principal após o passo. |
| `top_prob` | float64 | Probabilidade do suspeito principal. |
| `true_component` | str | Componente realmente defeituoso (gabarito). |
| `p_true_component` | float64 | Probabilidade atribuída ao componente realmente defeituoso. |
| `top_is_true` | bool | O suspeito principal é o componente defeituoso. |

### `agg_kpi_circuit_mode`

**Granularidade:** circuito × método. **Origem:** fct_session. **Linhas (execução de exemplo):** 30.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `n_sessions` | int64 | Quantidade de sessões. |
| `success_rate` | float64 | Fração de sessões concluídas com desfecho `reparado`. |
| `wrong_replacement_rate` | float64 | Fração com `troca_errada`. |
| `giveup_rate` | float64 | Fração com `desistiu`. |
| `avg_steps` | float64 | Média de passos. |
| `median_steps` | float64 | Mediana de passos. |
| `p90_steps` | float64 | Percentil 90 de passos. |
| `avg_duration_min` | float64 | Duração média em minutos. |
| `steps_reduction_vs_baseline_pct` | float64 | Redução % de passos contra o método atual (mesmo circuito). |
| `time_reduction_vs_baseline_pct` | float64 | Redução % de tempo contra o método atual (mesmo circuito). |

### `agg_kpi_overall_mode`

**Granularidade:** método (todos os circuitos). **Origem:** fct_session. **Linhas (execução de exemplo):** 3.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `n_sessions` | int64 | Quantidade de sessões. |
| `success_rate` | float64 | Fração de sessões concluídas com desfecho `reparado`. |
| `wrong_replacement_rate` | float64 | Fração com `troca_errada`. |
| `giveup_rate` | float64 | Fração com `desistiu`. |
| `avg_steps` | float64 | Média de passos. |
| `median_steps` | float64 | Mediana de passos. |
| `p90_steps` | float64 | Percentil 90 de passos. |
| `avg_duration_min` | float64 | Duração média em minutos. |
| `steps_reduction_vs_baseline_pct` | float64 | Redução % de passos contra o método atual (mesmo circuito). |
| `time_reduction_vs_baseline_pct` | float64 | Redução % de tempo contra o método atual (mesmo circuito). |

### `agg_convergence`

**Granularidade:** circuito × método × passo. **Origem:** fct_session_step. **Linhas (execução de exemplo):** 110.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `step` | int64 | Número do passo na sessão (1, 2, ...) ou etapa do pipeline (fct_pipeline_run). |
| `n_sessions` | int64 | Quantidade de sessões. |
| `top1_correct_rate` | float64 | Fração de sessões em que o suspeito nº 1 é o correto naquele passo. |
| `mean_top_prob` | float64 | Confiança média no suspeito principal. |
| `mean_p_true_component` | float64 | Probabilidade média do componente correto. |

### `agg_confusion`

**Granularidade:** circuito × método × componente real × componente trocado. **Origem:** fct_session. **Linhas (execução de exemplo):** 699.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `true_component` | str | Componente realmente defeituoso (gabarito). |
| `replaced_component` | str | Componente que o estudante trocou. |
| `n_sessions` | int64 | Quantidade de sessões. |

### `agg_observable_usage`

**Granularidade:** circuito × método × ponto de medição. **Origem:** silver.measurements. **Linhas (execução de exemplo):** 110.

| Coluna | Tipo | Descrição |
|---|---|---|
| `circuit_id` | str | Identificador do circuito (ex.: `emissor_comum`). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `observable_id` | str | Ponto de medição, ex.: `V(B)` (tensão no nó B) ou `I(R1)` (corrente em R1). |
| `n_measurements` | int64 | Medições na sessão. |
| `avg_step_position` | float64 | Posição média (passo) em que o ponto foi medido. |
| `first_choice_rate` | float64 | Fração das vezes em que foi a primeira medição. |

### `agg_daily_usage`

**Granularidade:** dia × método. **Origem:** fct_session. **Linhas (execução de exemplo):** 150.

| Coluna | Tipo | Descrição |
|---|---|---|
| `date` | object | Data (dia). |
| `mode` | str | Modo da falha (dim_fault) ou método do estudante (tabelas de sessão): `guiado`, `medicao_aleatoria`, `componente_a_componente`. |
| `n_sessions` | int64 | Quantidade de sessões. |
| `avg_steps` | float64 | Média de passos. |
| `success_rate` | float64 | Fração de sessões concluídas com desfecho `reparado`. |

## Metadados do pipeline (publicados também no warehouse)

### `fct_dq_result`

**Granularidade:** 1 linha por regra de qualidade executada. **Origem:** _meta/dq_results.jsonl. **Linhas (execução de exemplo):** 47.

| Coluna | Tipo | Descrição |
|---|---|---|
| `run_id` | str | Identificador da execução do pipeline (ou da simulação, em sim_runs). |
| `layer` | str | Camada (`silver`, `gold`). |
| `dataset` | str | Conjunto de dados verificado. |
| `rule` | str | Nome da regra de qualidade. |
| `severity` | str | `error`, `warn` ou `info`. |
| `checked` | int64 | Registros verificados. |
| `failed` | int64 | Registros que falharam. |
| `detail` | str | Observação da regra. |
| `logged_at` | str | Instante do registro (UTC). |

### `fct_pipeline_run`

**Granularidade:** 1 linha por etapa executada. **Origem:** _meta/runs.jsonl. **Linhas (execução de exemplo):** 21.

| Coluna | Tipo | Descrição |
|---|---|---|
| `run_id` | str | Identificador da execução do pipeline (ou da simulação, em sim_runs). |
| `step` | str | Número do passo na sessão (1, 2, ...) ou etapa do pipeline (fct_pipeline_run). |
| `status` | str | `completed` (tem evento de término) ou `incomplete`. |
| `started_at` | str | Início da sessão (UTC). |
| `ended_at` | str | Fim da etapa (UTC). |
| `seconds` | float64 | Duração da etapa em segundos. |
| `details` | object | Detalhes da etapa (JSON). |
| `error` | float64 | Traceback, se a etapa falhou. |

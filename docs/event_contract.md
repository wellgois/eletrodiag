# Contrato de eventos do app

Este é o contrato entre o aplicativo (produtor) e a camada bronze (consumidor). Versão do esquema: `1.0`.

## Envelope

Todo evento é um objeto JSON com os mesmos campos de topo:

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `event_id` | string | sim | Identificador único do evento (UUID ou hash). Usado para deduplicar. |
| `event_type` | string | sim | Um dos cinco tipos abaixo. |
| `ts` | string | sim | Instante do evento, preferencialmente ISO 8601 com fuso. A silver converte tudo para UTC: ISO 8601 sem fuso é lido como UTC; o formato `dd/mm/aaaa HH:MM:SS` é lido como horário de Brasília. |
| `session_id` | string | sim | Identifica a sessão de diagnóstico. |
| `learner_id` | string | sim | Pseudônimo aleatório do estudante. Não contém nome nem e-mail. |
| `app_version` | string | sim | Versão do app que emitiu o evento. |
| `payload` | objeto | sim | Campos específicos do tipo. |

## Tipos de evento

### `session_started`

| Campo do payload | Tipo | Descrição |
|---|---|---|
| `circuit_id` | string | Circuito escolhido (ex.: `emissor_comum`). |
| `mode` | string | `guiado`, `medicao_aleatoria` ou `componente_a_componente`. |
| `level` | string | Nível autodeclarado do estudante: `iniciante`, `intermediario` ou `avancado`. |
| `device` | string | Tipo de dispositivo (ex.: `mobile`, `desktop`). |

### `measurement_taken`

| Campo do payload | Tipo | Descrição |
|---|---|---|
| `step` | inteiro | Ordem do passo na sessão, a partir de 1. |
| `observable_id` | string | O que foi medido (ex.: `V(base)`, `I(R1)`). |
| `raw_value` | string ou número | Valor como digitado. Pode ter vírgula decimal. |
| `unit_raw` | string | Unidade como escolhida (`V`, `mV`, `A`, `mA`, `µA`). |
| `duration_s` | número | Segundos desde o passo anterior. |

### `diagnosis_shown`

Posterior calculado pelo app depois da medição. Emitido logo após cada `measurement_taken`.

| Campo do payload | Tipo | Descrição |
|---|---|---|
| `step` | inteiro | Passo a que se refere. |
| `top_component` | string | Componente mais provável. |
| `top_fault` | string | Modo de falha mais provável dentro desse componente. |
| `top_prob` | número 0–1 | Probabilidade acumulada do componente mais provável. |

### `component_tested`

> **Hoje só o gerador sintético emite este evento.** O app v0.1 só emite `mode = guiado` e não registra testes de componente. O tipo existe no contrato para o piloto comparativo (estudantes no método atual) e para versões futuras do app.

| Campo do payload | Tipo | Descrição |
|---|---|---|
| `step` | inteiro | Ordem do passo. |
| `component_id` | string | Componente testado fora do circuito. |
| `verdict` | string | `ok` ou `defeituoso`. |
| `duration_s` | número | Segundos desde o passo anterior. |

### `session_finished`

| Campo do payload | Tipo | Descrição |
|---|---|---|
| `outcome` | string | `reparado` (trocou o componente certo), `troca_errada` ou `desistiu`. |
| `replaced_component` | string ou nulo | Componente que o estudante decidiu trocar. |
| `stop_reason` | string | Por que parou (`confianca`, `manual`, `abandono`, `componente_encontrado`, `sem_mais_medicoes`, `sem_mais_componentes`). |
| `n_steps` | inteiro | Total de passos. |

Uma sessão sem `session_finished` é tratada como `incomplete` na silver (regra `session_completed`, severidade `warn`).

## Como o app entrega os eventos

1. O app guarda os eventos da sessão em memória e tem o botão **Copiar eventos** (uma linha JSON por evento), que o estudante ou o instrutor salva como `.jsonl`.
2. Se `window.ELETRODIAG_INGEST_URL` estiver definida, cada evento também é enviado por `POST` (JSON) para essa URL. Falhas de rede são ignoradas: o app não pode travar por causa da telemetria. Essa URL é um ponto de extensão: **o repositório não inclui o serviço receptor**.
3. O arquivo (ou os eventos recebidos) deve entrar na bronze como um novo lote. **Ainda não há comando de linha para importar um `.jsonl` real**: hoje só o gerador sintético grava em `bronze/app_events/` (função `ingest_app_events`). Esse comando é o primeiro item do [roadmap](roadmap.md).

## Regras de leitura (silver)

- Linha que não é JSON válido, ou sem os campos obrigatórios: vai para a quarentena (`json_parseable_and_required_fields`).
- `event_id` repetido: mantém um só (`unique_event_id`).
- Evento de sessão sem `session_started`: sinalizado (`session_without_start_event`, mostrada como `session_has_start_event`).
- Valores com vírgula decimal e unidades mistas são convertidos para volts e ampères.
- Medição ilegível ou observável desconhecido: quarentena (`valid_observable_and_parseable_value`).

## Evolução do esquema

- Campos novos opcionais no payload não quebram nada: a silver ignora o que não conhece.
- Remover ou renomear campo obrigatório exige subir `SCHEMA_VERSION` e tratar as duas versões na silver.
- A bronze guarda a versão do esquema no `_manifest.json` de cada lote.

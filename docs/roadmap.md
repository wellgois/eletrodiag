# Roteiro

Ordem sugerida. Cada fase termina com algo verificável.

## Fase 1: concluída

Pacote de demonstração de ponta a ponta.

- Simulador DC com 5 circuitos básicos e modelo de defeitos.
- Motor de diagnóstico bayesiano e escolha da próxima medição.
- App estático com modo de treinamento.
- Pipeline medalhão (bronze, silver, gold), regras de qualidade, warehouse e views de BI.
- Painel HTML e documentação.

## Fase 1c: blocos de inversor (concluída)

- Modelos novos no solver: MOSFET canal N com diodo de corpo e regulador linear 78xx; fusível, enrolamento e capacitor como resistências.
- Cinco circuitos novos de um inversor CC-CA: entrada e proteção, fontes auxiliares, primário push-pull, barramento de alta tensão e ponte H.
- Aviso de segurança (`hazard`) e limites do modelo (`nota`) por circuito, mostrados no app.
- Detalhes e limites em [inverter_blocks.md](inverter_blocks.md).

Próximos passos desta frente, em ordem:

1. **Observáveis de teste a frio:** resistência, continuidade e diodo com a placa desligada. Sem eles, a ponte H e o primário têm centenas de pares de defeitos indistinguíveis.
2. **Levantar o esquema real** do inversor de teste (fotos e continuidade) e trocar os valores de referência pelos medidos.
3. **Blocos de TV:** fonte chaveada (ponte retificadora, capacitor principal, MOSFET de chaveamento, optoacoplador, TL431, retificadores secundários) e backlight (fitas de LED e driver). Faltam os modelos de ponte, NTC, optoacoplador, TL431 e controlador PWM.
4. **Modelo de comparador e amplificador operacional** (proteção de bateria e realimentação).

## Fase 1b: fechar pontas soltas (curto prazo)

| Item | Por quê |
|---|---|
| Comando `python -m eletrodiag.pipeline.ingest_events arquivo.jsonl` | Hoje só o gerador sintético grava eventos na bronze. Sem isso, dado real não entra |
| Receptor mínimo para `ELETRODIAG_INGEST_URL` | O app já envia eventos por POST, mas não há quem receba |
| Registrar `component_tested` no app | Permite comparar os métodos com estudantes reais |
| Comparar o simulador com ngspice | Validação externa dos números de tensão e corrente |
| Conferir app e painel em navegadores reais (celular e desktop) | Só foram testados por script |
| Testar as conexões do [guia de BI](bi_guide.md) | Foram escritas a partir da documentação das ferramentas |

## Fase 2: piloto com estudantes reais

Objetivo: trocar as premissas por medidas.

1. Recrutar um grupo de estudantes e um instrutor.
2. Definir 10 a 20 defeitos em placas ou protoboards conhecidos.
3. Metade resolve com o app, metade com o método atual, alternando os grupos (desenho cruzado).
4. Registrar tempo, passos e resultado pelo contrato de eventos.
5. Substituir as premissas de `assumptions.md` pelos valores medidos e reexecutar a análise de sensibilidade.

Critério de sucesso a definir antes: redução de tempo e aumento de acerto com intervalo de confiança.

## Fase 3: mais circuitos e defeitos

- Mais circuitos (osciladores com 555, amplificadores com amp-op, fontes lineares).
- Análise AC e transiente para circuitos que precisem.
- Defeitos múltiplos.
- Entrada de circuito por esquema (netlist), com validação.
- Leitura de foto do multímetro ou da placa (visão computacional), como opcional.

## Fase 4: engenharia de dados em escala

Só se o volume pedir.

| Necessidade | Opção |
|---|---|
| Agendamento e reexecução | Airflow ou Dagster, com uma tarefa por etapa atual |
| Transformações em SQL e testes declarativos | dbt sobre DuckDB ou um warehouse em nuvem |
| Tabelas transacionais no lake | Delta Lake ou Apache Iceberg no lugar do Parquet puro |
| Ingestão contínua | Fila (Kafka, Pub/Sub) ou API com gravação em lote na bronze |
| Cargas incrementais | Processar só `ingest_date` e `batch_id` novos |
| Qualidade contínua | Great Expectations ou Soda, mantendo as regras atuais como especificação |
| Catálogo e linhagem | OpenMetadata ou DataHub, a partir do `data_dictionary.md` |

## Fase 5: produto

Hipóteses a validar com clientes antes de investir.

- Venda para escolas técnicas e cursos de eletrônica (licença por turma).
- Painel para o instrutor (já existe o protótipo em `bi/dashboard`).
- Banco de circuitos e defeitos mantido por professores.
- Integração com ferramentas de ensino (Moodle, Google Classroom).

Requisitos antes de coletar dados reais: política de privacidade, consentimento e atenção à LGPD (inclusive para menores de idade).

## Ideias não priorizadas

- Hardware de apoio (ponta de prova com leitura automática) como evolução do app. Só vale depois do piloto mostrar valor.
- Modo competição entre estudantes.
- Tradução para outros idiomas.

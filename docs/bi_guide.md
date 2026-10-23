# Guia de BI

A camada de apresentação lê da camada gold publicada no **warehouse**. Não há lógica de negócio dentro da ferramenta de BI: ela só desenha o que as views já calculam.

> **Aviso.** O painel HTML incluído (`bi/dashboard/index.html`) foi gerado e testado por script. As conexões com Power BI, Metabase, Superset e Excel abaixo seguem a documentação dessas ferramentas, mas **não foram executadas** neste projeto. Ajuste conforme a sua versão.

## Onde estão os dados

Depois de `make pipeline` (ou `python -m eletrodiag.pipeline.run`):

| Formato | Caminho | Bom para |
|---|---|---|
| DuckDB | `data/warehouse/eletrodiag.duckdb` | SQL analítico, notebooks, ODBC |
| SQLite | `data/warehouse/eletrodiag.sqlite` | Metabase, Superset, DBeaver |
| CSV | `data/gold/csv/<tabela>.csv` (só tabelas, não as views) | Excel, Power BI, Google Sheets |
| Parquet | `data/gold/` | Spark, Python, ferramentas de lakehouse |

As tabelas `dim_*`, `fct_*` e `agg_*` estão no DuckDB, no SQLite, em CSV e em Parquet. As views `v_*` (nomes em português, definidas em `bi/views.sql`) existem **apenas no DuckDB e no SQLite**. Quem usar só CSV precisa reproduzir a lógica das views nas tabelas `agg_*`.

## Views prontas

| View | Pergunta que responde | Visual sugerido |
|---|---|---|
| `v_kpi_geral` | Qual o desempenho de cada método no total? | Cartões |
| `v_kpi_circuito` | E por circuito? | Barras agrupadas |
| `v_convergencia` | Quantas medições até a confiança subir? | Linhas por método |
| `v_matriz_confusao` | O que o app confunde com o quê? | Mapa de calor |
| `v_ambiguidade` | Quais defeitos não se separam só com o multímetro? | Tabela |
| `v_resumo_ambiguidade` | Quantos pares por classe de separabilidade? | Barras |
| `v_desempenho_por_componente` | Quais componentes dão mais erro? | Barras ordenadas |
| `v_uso_diario` | Quantas sessões por dia? | Linha |
| `v_assinaturas` | Que valor esperar de cada medição em cada defeito? | Tabela filtrável |
| `v_qualidade_dados` | Os dados do pipeline passaram nas regras? | Tabela com status |

## Power BI Desktop

1. **Obter dados → Texto/CSV** e importe os arquivos de `data/gold/csv/`. As views `v_*` não existem em CSV: para usá-las, prefira o caminho ODBC abaixo.
2. Para ler direto do DuckDB: instale o driver ODBC do DuckDB, crie um DSN apontando para `eletrodiag.duckdb` e use **Obter dados → ODBC**.
3. Se importar as tabelas em vez das views, relacione `fct_session[circuit_id]` com `dim_circuit[circuit_id]` e `fct_session[mode]` com `dim_mode[mode]`. O resto segue o diagrama do README.
4. Atualização: rode o pipeline e use **Atualizar**.

## Metabase

1. Use a imagem oficial do Metabase. O SQLite é suportado nativamente.
2. **Admin → Databases → Add database → SQLite**, com o caminho de `eletrodiag.sqlite` visível no contêiner.
3. Crie perguntas sobre as views `v_*`.

## Apache Superset

1. Instale o driver de SQLite (já vem no SQLAlchemy) ou o `duckdb-engine` para DuckDB.
2. Cadastre a base com a URI `sqlite:////caminho/eletrodiag.sqlite` ou `duckdb:////caminho/eletrodiag.duckdb`.
3. Registre as views como datasets.

## Excel

**Dados → Obter dados → De texto/CSV** em cada arquivo de `data/gold/csv/`. Para tabelas dinâmicas, comece pelas `agg_*`.

## Painel HTML incluído

`bi/dashboard/index.html` é uma página única com os mesmos indicadores, gerada por `python -m eletrodiag.bi.dashboard` (ou pela etapa `dashboard` do pipeline). O arquivo para publicar como página única é `bi/dashboard/build/painel-artifact.html`. Mostra:

- Comparação entre os três métodos (sucesso, passos, tempo).
- Curva de convergência.
- Matriz de confusão e pares ambíguos.
- Qualidade dos dados.

Tem modo claro e escuro, tabela alternativa para cada gráfico e dicas ao passar o mouse.

## Boas práticas

- Sempre filtre por `mode` ao comparar: misturar métodos esconde o efeito.
- Lembre-se de que os dados de demonstração são **sintéticos**. Rotule os painéis como "dados de demonstração" até haver dados reais.
- Para produção, aponte o BI para um banco de verdade (Postgres, BigQuery) e mantenha as mesmas views como contrato.

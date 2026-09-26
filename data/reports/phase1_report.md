# Baseline pipeline report

## Source

| Field | Value |
|---|---|
| source_api | Crossref REST API |
| source_query | agentic retrieval augmented generation large language model |
| source_filter | from-pub-date:2026-03-30,has-abstract:true |
| raw_records | 24 |
| clean_rows | 24 |
| run_at | 2026-09-26T05:08:30.811441+00:00 |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| collection_name | papers-baseline |
| top_k | 4 |
| llm_provider | openai |

## Evaluation

| Metric | Value |
|---|---:|
| Retrieval hit rate | 1.0000 |
| Mean token F1 | 1.0000 |
| Judge accuracy | 1.0000 |
| Mean judge score | 5.0000 |

## Data quality

Overall gate: **PASS**; rows: 24.

| Expectation | Column | Result |
|---|---|---|
| expect_table_row_count_to_be_between | — | PASS |
| expect_column_values_to_not_be_null | paper_id | PASS |
| expect_column_values_to_be_unique | paper_id | PASS |
| expect_column_values_to_not_be_null | title | PASS |
| expect_column_value_lengths_to_be_between | title | PASS |
| expect_column_values_to_not_be_null | summary | PASS |
| expect_column_value_lengths_to_be_between | summary | PASS |
| expect_column_values_to_not_be_null | published | PASS |

## Freshness

| Signal | Value |
|---|---|
| latest_published | 2026-07-22 |
| oldest_published | 2026-03-28 |
| stale_rows | 1 |
| total_rows | 24 |
| stale_ratio | 0.041666666666666664 |
| threshold_days | 180 |
| max_stale_ratio | 0.25 |
| is_fresh | True |

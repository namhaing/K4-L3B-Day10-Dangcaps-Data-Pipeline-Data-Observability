# Corruption and repair report

## Evaluation comparison

| Metric | Baseline | Corrupted | Repaired | Δ corrupted − baseline |
|---|---:|---:|---:|---:|
| Retrieval hit rate | 1.0000 | 0.7000 | 1.0000 | -0.3000 |
| Mean token F1 | 1.0000 | 0.7630 | 1.0000 | -0.2370 |
| Judge accuracy | 1.0000 | 0.6000 | 1.0000 | -0.4000 |
| Mean judge score | 5.0000 | 3.8000 | 5.0000 | -1.2000 |

## Quality gate

Corrupted: **FAIL**; repaired: **PASS**.

| Expectation | Column | Corrupted | Repaired |
|---|---|---|---|
| expect_column_value_lengths_to_be_between | summary | FAIL | PASS |
| expect_column_value_lengths_to_be_between | title | FAIL | PASS |
| expect_column_values_to_be_unique | paper_id | FAIL | PASS |
| expect_column_values_to_not_be_null | paper_id | PASS | PASS |
| expect_column_values_to_not_be_null | published | PASS | PASS |
| expect_column_values_to_not_be_null | summary | PASS | PASS |
| expect_column_values_to_not_be_null | title | PASS | PASS |
| expect_table_row_count_to_be_between |  | PASS | PASS |

## Freshness

| Signal | Corrupted | Repaired |
|---|---|---|
| latest_published | 2026-06-12 | 2026-07-22 |
| oldest_published | 2025-03-14 | 2026-03-28 |
| stale_rows | 9 | 1 |
| total_rows | 22 | 24 |
| stale_ratio | 0.4090909090909091 | 0.041666666666666664 |
| threshold_days | 180 | 180 |
| max_stale_ratio | 0.25 | 0.25 |
| is_fresh | False | True |

## Corruption log

Input rows: 24; output rows: 22; seed: 42.

| Type | Count | Description |
|---|---:|---|
| drop_latest | 5 | Dropped the 5 most recently published records (20%). |
| blank_summary | 5 | Replaced summary with an empty string. |
| inject_noise | 5 | Inserted garbage tokens at the start of the summary and after every 4th word. |
| truncate_title | 5 | Truncated title to 6 characters (below the 8-character minimum). |
| stale_date | 7 | Shifted published date 400 days into the past and recomputed age_days. |
| duplicate_rows | 3 | Appended 3 exact duplicate rows. |

## Analysis

Retrieval hit rate changed from 1.0000 to 0.7000; after repair it was 1.0000.
The corrupted dataset failed 3/8 expectations.
Silent failure is possible when indexing and answering still run while these quality checks or answer metrics decline.

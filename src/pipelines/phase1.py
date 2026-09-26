from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import ensure_parent, now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex

DEMO_QUESTIONS = 2
METRIC_KEYS = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]


def save_clean_artifacts(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    ensure_parent(json_path)
    # orient="records" is required: downstream checks reload it with pd.read_json.
    df.to_json(json_path, orient="records", indent=2)


def _run_agent_demo(settings: Settings, index: LocalEmbeddingIndex) -> list[dict[str, Any]]:
    questions = [item["question"] for item in read_json(settings.paths.eval_testset)[:DEMO_QUESTIONS]]
    try:
        agent = build_agent(settings, index)
    except Exception as exc:
        return [{"question": question, "error": f"Agent unavailable: {exc}"} for question in questions]

    answers: list[dict[str, Any]] = []
    for question in questions:
        try:
            answers.append({"question": question, "answer": run_agent_question(agent, question)})
        except Exception as exc:
            answers.append({"question": question, "error": f"Agent failed: {exc}"})
    return answers


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()

    print("[1/7] Ingestion: fetching source records...")
    records = fetch_source_records(settings)

    print("[2/7] Cleaning...")
    df = build_clean_dataframe(records, run_date)
    save_clean_artifacts(df, paths.clean_csv, paths.clean_json)

    print("[3/7] Quality gate + freshness SLA...")
    quality = run_data_quality_checks(df, settings, "baseline")
    freshness = build_freshness_report(df, settings, paths.freshness_report)
    if not quality["success"]:
        print("  WARNING: baseline quality gate failed; inspect data/quality/ before trusting the metrics.")

    print(f"[4/7] Indexing {len(df)} documents into ChromaDB '{settings.baseline_collection_name}'...")
    index = LocalEmbeddingIndex.build(df, settings, paths.embeddings_json)

    print("[5/7] Evaluation set...")
    if settings.refresh_test_set or not paths.eval_testset.exists():
        build_test_set(df, paths.eval_testset)
    else:
        print(f"  Reusing existing {paths.eval_testset.name} (set REFRESH_TEST_SET=1 to rebuild).")

    print("[6/7] Evaluating baseline...")
    bundle = evaluate_pipeline(
        settings,
        index,
        paths.eval_testset,
        paths.baseline_metrics,
        paths.baseline_answers,
    )

    print("[7/7] Writing phase 1 report...")
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_records": len(records),
        "clean_rows": len(df),
        "run_at": run_date.isoformat(),
        "embedding_model": settings.embedding_model,
        "collection_name": index.collection_name,
        "top_k": settings.top_k,
        "llm_provider": settings.llm_provider,
    }
    generate_phase1_report(paths.baseline_report, source_summary, bundle.summary, quality, freshness)
    write_json(paths.demo_answers, _run_agent_demo(settings, index))

    print("\n=== Phase 1 baseline ===")
    print(f"Records: raw={len(records)} clean={len(df)}")
    for key in METRIC_KEYS:
        print(f"{key:<20} {bundle.summary[key]:.4f}")
    print(f"quality_gate         {'PASS' if quality['success'] else 'FAIL'}")
    print(f"is_fresh             {freshness['is_fresh']}")
    print(f"Report: {paths.baseline_report}")

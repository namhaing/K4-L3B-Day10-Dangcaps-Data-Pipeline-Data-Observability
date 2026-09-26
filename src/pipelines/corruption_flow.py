from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import METRIC_KEYS, save_clean_artifacts
from retrieval.index import LocalEmbeddingIndex


def _gate(df: pd.DataFrame, settings: Settings, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    quality = run_data_quality_checks(df, settings, name)
    freshness = build_freshness_report(df, settings, settings.paths.quality_dir / f"{name}_freshness_report.json")
    status = "PASS" if quality["success"] else "FAIL"
    print(f"  Quality gate [{name}]: {status} (is_fresh={freshness['is_fresh']})")
    return quality, freshness


def _index_and_evaluate(
    df: pd.DataFrame,
    settings: Settings,
    embeddings_path: Path,
    metrics_path: Path,
    answers_path: Path,
) -> dict[str, Any]:
    # The same test_set.json is reused for every state so the comparison is fair.
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    print(f"  Indexed {len(df)} rows into ChromaDB '{index.collection_name}'")
    bundle = evaluate_pipeline(settings, index, settings.paths.eval_testset, metrics_path, answers_path)
    return bundle.summary


def _print_comparison(baseline: dict, corrupted: dict, repaired: dict, corrupted_quality: dict, repaired_quality: dict) -> None:
    print("\n=== Baseline vs Corrupted vs Repaired ===")
    print(f"{'metric':<20} {'baseline':>10} {'corrupted':>10} {'repaired':>10} {'delta':>10}")
    for key in METRIC_KEYS:
        delta = corrupted[key] - baseline[key]
        print(f"{key:<20} {baseline[key]:>10.4f} {corrupted[key]:>10.4f} {repaired[key]:>10.4f} {delta:>+10.4f}")
    corrupted_gate = "PASS" if corrupted_quality["success"] else "FAIL"
    repaired_gate = "PASS" if repaired_quality["success"] else "FAIL"
    print(f"{'quality_gate':<20} {'PASS':>10} {corrupted_gate:>10} {repaired_gate:>10}")


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    if not paths.baseline_metrics.exists() or not paths.eval_testset.exists():
        raise SystemExit("Baseline artifacts missing. Run `python script/run_phase1.py` first.")

    baseline_metrics = read_json(paths.baseline_metrics)
    clean_df = pd.read_json(paths.clean_json, orient="records", dtype=False, convert_dates=False)
    healing_log: list[dict[str, Any]] = []

    print("[1/4] Corrupting clean dataset...")
    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    save_clean_artifacts(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    corrupted_quality, corrupted_freshness = _gate(corrupted_df, settings, "corrupted")
    healing_log.append({"step": "quality_gate", "state": "corrupted", "success": corrupted_quality["success"]})

    # Indexed even though the gate failed: this measures the silent failure the gate prevents.
    print("[2/4] Evaluating corrupted index (what the agent would serve without the gate)...")
    corrupted_metrics = _index_and_evaluate(
        corrupted_df,
        settings,
        paths.corrupted_embeddings_json,
        paths.corrupted_metrics,
        paths.corrupted_answers,
    )

    # Self-healing: a failed gate triggers repair automatically. Repair always rebuilds from the
    # immutable raw snapshot instead of patching dirty rows, so re-running it is idempotent.
    if corrupted_quality["success"]:
        trigger = "scheduled comparison run (quality gate passed)"
    else:
        trigger = "auto: quality gate failed"
    print(f"[3/4] Repairing from raw snapshot ({trigger})...")
    healing_log.append({"step": "repair", "trigger": trigger, "source": paths.raw_records_json.name})
    repaired_df = build_clean_dataframe(load_raw_records(paths.raw_records_json), now_utc())
    repaired_quality, repaired_freshness = _gate(repaired_df, settings, "repaired")
    healing_log.append({"step": "quality_gate", "state": "repaired", "success": repaired_quality["success"]})
    write_json(paths.corruption_log.parent / "self_healing_log.json", healing_log)
    if not repaired_quality["success"]:
        raise SystemExit("Repaired data still fails the quality gate; refusing to publish it to the index.")

    save_clean_artifacts(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)
    repaired_metrics = _index_and_evaluate(
        repaired_df,
        settings,
        paths.repaired_embeddings_json,
        paths.repaired_metrics,
        paths.repaired_answers,
    )

    print("[4/4] Writing comparison report...")
    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )
    _print_comparison(baseline_metrics, corrupted_metrics, repaired_metrics, corrupted_quality, repaired_quality)
    print(f"Report: {paths.comparison_report}")

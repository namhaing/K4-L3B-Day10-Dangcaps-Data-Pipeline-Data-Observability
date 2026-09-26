from __future__ import annotations

from typing import Any

from core.config import load_settings
from core.utils import read_json, write_text


METRICS = (
    ("Retrieval hit rate", "retrieval_hit_rate"),
    ("Mean token F1", "mean_token_f1"),
    ("Judge accuracy", "judge_accuracy"),
    ("Mean judge score", "mean_judge_score"),
)


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _number(value: Any) -> str:
    return "—" if value is None else f"{float(value):.4f}"


def _status(value: Any) -> str:
    return "PASS" if value else "FAIL"


def _expectation_rows(quality: dict[str, Any]) -> dict[tuple[str, str], bool]:
    return {
        (str(item.get("expectation", "")), str(item.get("column") or "")): bool(item.get("success"))
        for item in quality.get("expectations", [])
    }


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write a baseline report using only measured inputs."""
    lines = ["# Baseline pipeline report", "", "## Source", "", "| Field | Value |", "|---|---|"]
    for key, value in source_summary.items():
        lines.append(f"| {_cell(key)} | {_cell(value)} |")
    lines += ["", "## Evaluation", "", "| Metric | Value |", "|---|---:|"]
    for label, key in METRICS:
        lines.append(f"| {label} | {_number(metrics.get(key))} |")
    lines += [
        "",
        "## Data quality",
        "",
        f"Overall gate: **{_status(quality.get('success'))}**; rows: {_cell(quality.get('row_count'))}.",
        "",
        "| Expectation | Column | Result |",
        "|---|---|---|",
    ]
    for item in quality.get("expectations", []):
        lines.append(
            f"| {_cell(item.get('expectation'))} | {_cell(item.get('column'))} | {_status(item.get('success'))} |"
        )
    lines += ["", "## Freshness", "", "| Signal | Value |", "|---|---|"]
    for key in (
        "latest_published", "oldest_published", "stale_rows", "total_rows",
        "stale_ratio", "threshold_days", "max_stale_ratio", "is_fresh",
    ):
        lines.append(f"| {key} | {_cell(freshness.get(key))} |")
    write_text(report_path, "\n".join(lines) + "\n")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Compare three runs without inventing scores or quality outcomes."""
    lines = [
        "# Corruption and repair report", "", "## Evaluation comparison", "",
        "| Metric | Baseline | Corrupted | Repaired | Δ corrupted − baseline |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, key in METRICS:
        baseline = baseline_metrics.get(key)
        corrupted = corrupted_metrics.get(key)
        repaired = repaired_metrics.get(key)
        delta = float(corrupted) - float(baseline) if baseline is not None and corrupted is not None else None
        lines.append(
            f"| {label} | {_number(baseline)} | {_number(corrupted)} | {_number(repaired)} | {_number(delta)} |"
        )

    bad = _expectation_rows(corrupted_quality)
    good = _expectation_rows(repaired_quality)
    lines += [
        "", "## Quality gate", "",
        f"Corrupted: **{_status(corrupted_quality.get('success'))}**; "
        f"repaired: **{_status(repaired_quality.get('success'))}**.",
        "", "| Expectation | Column | Corrupted | Repaired |", "|---|---|---|---|",
    ]
    for expectation, column in sorted(bad.keys() | good.keys()):
        bad_status = _status(bad[(expectation, column)]) if (expectation, column) in bad else "—"
        good_status = _status(good[(expectation, column)]) if (expectation, column) in good else "—"
        lines.append(f"| {_cell(expectation)} | {_cell(column)} | {bad_status} | {good_status} |")
    lines += [
        "", "## Freshness", "", "| Signal | Corrupted | Repaired |", "|---|---|---|",
    ]
    for key in (
        "latest_published", "oldest_published", "stale_rows", "total_rows",
        "stale_ratio", "threshold_days", "max_stale_ratio", "is_fresh",
    ):
        lines.append(f"| {key} | {_cell(corrupted_freshness.get(key))} | {_cell(repaired_freshness.get(key))} |")

    log_path = load_settings().paths.corruption_log
    if log_path.exists():
        log = read_json(log_path)
        lines += ["", "## Corruption log", ""]
        if isinstance(log, dict):
            lines.append(
                f"Input rows: {_cell(log.get('input_rows'))}; output rows: {_cell(log.get('output_rows'))}; "
                f"seed: {_cell(log.get('seed'))}."
            )
            entries = log.get("corruptions", [])
        else:
            entries = log
        lines += ["", "| Type | Count | Description |", "|---|---:|---|"]
        for item in entries:
            lines.append(
                f"| {_cell(item.get('type'))} | {_cell(item.get('count'))} | {_cell(item.get('description'))} |"
            )

    failures = sum(not passed for passed in bad.values())
    lines += ["", "## Analysis", ""]
    if baseline_metrics.get("retrieval_hit_rate") is not None and corrupted_metrics.get("retrieval_hit_rate") is not None:
        lines.append(
            "Retrieval hit rate changed from "
            f"{_number(baseline_metrics['retrieval_hit_rate'])} to "
            f"{_number(corrupted_metrics['retrieval_hit_rate'])}; after repair it was "
            f"{_number(repaired_metrics.get('retrieval_hit_rate'))}."
        )
    lines.append(f"The corrupted dataset failed {failures}/{len(bad)} expectations.")
    lines.append(
        "Silent failure is possible when indexing and answering still run while these quality checks or answer metrics decline."
    )
    write_text(report_path, "\n".join(lines) + "\n")

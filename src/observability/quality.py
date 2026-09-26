from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate schema, content, uniqueness, row count, and freshness."""
    if not report_name or not report_name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("report_name must contain only letters, digits, hyphens, or underscores")

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"{report_name}_source")
    data_asset = data_source.add_dataframe_asset(name=f"{report_name}_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"{report_name}_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})
    suite = context.suites.add(gx.ExpectationSuite(name=f"{report_name}_suite"))
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=int(settings.max_results * 0.9), max_value=settings.max_results
        )
    )
    for column in ("paper_id", "title", "summary", "published"):
        suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column=column))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValueLengthsToBeBetween(column="title", min_value=8))
    suite.add_expectation(gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=50))

    validation = batch.validate(suite)
    expectations = []
    for item in validation.results:
        details = item.to_json_dict()
        config = details["expectation_config"]
        expectations.append(
            {
                "expectation": config["type"],
                "column": config.get("kwargs", {}).get("column"),
                "success": bool(item.success),
                "details": details.get("result", {}),
            }
        )

    freshness_path = settings.paths.quality_dir / f"{report_name}_freshness_report.json"
    freshness = build_freshness_report(df, settings, freshness_path)
    payload = {
        "report_name": report_name,
        "success": bool(validation.success and freshness["is_fresh"]),
        "row_count": int(len(df)),
        "expectations": expectations,
        "freshness": freshness,
    }
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", payload)
    write_json(settings.paths.gx_dir / f"{report_name}_suite.json", suite.to_json_dict())
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path) -> dict[str, Any]:
    """Summarize publication age using the lab's freshness SLA."""
    total_rows = int(len(df))
    ages = pd.to_numeric(df["age_days"], errors="coerce")
    stale_rows = int((ages > settings.freshness_threshold_days).sum())
    stale_ratio = float(stale_rows / total_rows) if total_rows else 0.0
    published = pd.to_datetime(df["published"], errors="coerce", utc=True).dropna()
    payload = {
        "latest_published": published.max().date().isoformat() if not published.empty else None,
        "oldest_published": published.min().date().isoformat() if not published.empty else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "threshold_days": int(settings.freshness_threshold_days),
        "max_stale_ratio": 0.25,
        "is_fresh": bool(total_rows and stale_ratio <= 0.25),
    }
    write_json(Path(report_path), payload)
    return payload

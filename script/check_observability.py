from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from observability.quality import run_data_quality_checks
from observability.reporting import generate_corruption_report, generate_phase1_report


def main() -> None:
    settings = load_settings()
    records = read_json(settings.paths.raw_records_json)
    df = pd.DataFrame(records)
    run_date = date(2026, 9, 26)  # Fixed lab-date fixture for reproducible checks.
    df["age_days"] = [(run_date - date.fromisoformat(value)).days for value in df["published"]]
    with TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        paths = replace(settings.paths, quality_dir=temp / "quality", gx_dir=temp / "quality" / "gx", corruption_log=temp / "missing_log.json")
        settings = replace(settings, paths=paths)
        baseline = run_data_quality_checks(df, settings, "baseline")
        print("baseline:", baseline["success"], len(baseline["expectations"]), baseline["freshness"])
        assert baseline["success"] is True
        assert len(baseline["expectations"]) == 8
        stale_only = df.copy(deep=True)
        stale_only.loc[:7, "age_days"] = 999
        stale = run_data_quality_checks(stale_only, settings, "stale")
        assert all(item["success"] for item in stale["expectations"])
        assert stale["success"] is False
        damaged = df.copy(deep=True)
        damaged.loc[0, "paper_id"] = damaged.loc[1, "paper_id"]
        damaged.loc[0, "title"] = "abc"
        damaged.loc[0, "summary"] = ""
        damaged.loc[:7, "age_days"] = 999
        corrupted = run_data_quality_checks(damaged, settings, "corrupted")
        print("corrupted:", corrupted["success"], corrupted["freshness"])
        assert corrupted["success"] is False
        assert corrupted["freshness"]["is_fresh"] is False
        assert sum(not e["success"] for e in corrupted["expectations"]) >= 3

        metrics = {"retrieval_hit_rate": 0.75, "mean_token_f1": 0.6, "judge_accuracy": 0.7, "mean_judge_score": 3.5}
        lower = {"retrieval_hit_rate": 0.4, "mean_token_f1": 0.3, "judge_accuracy": 0.4, "mean_judge_score": 2.0}
        phase_report = temp / "phase1.md"
        comparison_report = temp / "comparison.md"
        generate_phase1_report(phase_report, {"source_api": "Crossref", "record_count": len(df)}, metrics, baseline, baseline["freshness"])
        generate_corruption_report(comparison_report, metrics, lower, metrics, corrupted, baseline, corrupted["freshness"], baseline["freshness"])
        assert "0.7500" in phase_report.read_text(encoding="utf-8")
        assert "-0.3500" in comparison_report.read_text(encoding="utf-8")
        assert "expect_column_values_to_be_unique" in comparison_report.read_text(encoding="utf-8")
        print("reports: OK")


if __name__ == "__main__":
    main()

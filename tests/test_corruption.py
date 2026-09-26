from __future__ import annotations

import json

from ingestion.corruption import corrupt_clean_dataframe


def test_corruption_applies_and_logs_all_six_scenarios(clean_df, tmp_path):
    log_path = tmp_path / "corruption_log.json"

    corrupted = corrupt_clean_dataframe(clean_df, log_path)

    log = json.loads(log_path.read_text(encoding="utf-8"))
    corruption_types = {event["corruption_type"] for event in log["events"]}
    assert log["corruption_count"] == 6
    assert corruption_types == {
        "drop_latest_records",
        "blank_summary",
        "inject_noise",
        "truncate_title",
        "stale_date",
        "duplicate_rows",
    }
    assert len(corrupted) < len(clean_df)
    assert corrupted["paper_id"].duplicated().any()
    assert (corrupted["summary"] == "").any()
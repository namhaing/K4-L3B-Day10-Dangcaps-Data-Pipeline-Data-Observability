from __future__ import annotations


def test_cleaning_produces_expected_corpus_and_embedding_text(clean_df):
    assert len(clean_df) == 24
    assert clean_df["paper_id"].is_unique
    assert (clean_df["age_days"] >= 0).all()

    required_parts = ["Title:", "Authors:", "Published:", "Categories:", "Summary:"]
    for text in clean_df["text_for_embedding"]:
        assert all(part in text for part in required_parts)


def test_cleaning_empty_input_returns_empty_dataframe():
    from datetime import datetime

    from ingestion.cleaning import build_clean_dataframe

    result = build_clean_dataframe([], datetime(2026, 9, 26))

    assert result.empty
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from core.config import Settings, load_settings
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return load_settings(tmp_path)


@pytest.fixture
def raw_records():
    return load_raw_records(PROJECT_ROOT / "data" / "raw" / "crossref_records.json")


@pytest.fixture
def clean_df(raw_records):
    return build_clean_dataframe(raw_records, datetime(2026, 9, 26))
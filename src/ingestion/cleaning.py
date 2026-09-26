from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime
import html
import re

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_text_for_embedding(row) -> str:
    """Format a cleaned row as five labeled lines for embedding.

    Accepts a dict or pandas Series with cleaned string values, including
    empty strings when rebuilding text after data corruption. This public
    helper is also used by ingestion.corruption to preserve the same format.
    """
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Summary: {row['summary']}"
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records, rejecting invalid dates and empty required text.

    Both published and updated must parse successfully. Dates are returned
    as ISO date strings; run_date is expected to be timezone-aware UTC.
    """
    raw_columns = [field.name for field in fields(PaperRecord)]
    df = pd.DataFrame([asdict(r) for r in records], columns=raw_columns)
    text_columns = [name for name in raw_columns if name not in {"authors", "categories"}]
    df[text_columns] = df[text_columns].fillna("")
    df["paper_id"] = df["paper_id"].map(str.strip)

    def clean_text(value: str) -> str:
        return normalize_whitespace(html.unescape(re.sub(r"<[^>]+>", " ", value)))

    def clean_list(value) -> list[str]:
        if value is None or (not isinstance(value, list) and pd.isna(value)):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    for column in ("title", "summary"):
        df[column] = df[column].map(clean_text)
    for column in ("authors", "categories"):
        df[column] = df[column].map(clean_list)
    for column in ("published", "updated"):
        df[column] = pd.to_datetime(df[column], errors="coerce", utc=True, format="mixed")
    df = df.dropna(subset=["published", "updated"]).copy()
    df["age_days"] = df["published"].map(
        lambda published: (run_date.date() - published.date()).days
    ).astype("int64")
    for column in ("published", "updated"):
        df[column] = df[column].dt.strftime("%Y-%m-%d")

    df["authors_joined"] = df["authors"].map(compact_join)
    df["categories_joined"] = df["categories"].map(compact_join)
    df["summary_chars"] = df["summary"].map(len).astype("int64")
    df["text_for_embedding"] = pd.Series(
        [build_text_for_embedding(row) for row in df.to_dict(orient="records")],
        index=df.index,
        dtype="object",
    )
    df = df.drop_duplicates(subset="paper_id", keep="first")
    df = df.loc[df[["paper_id", "title", "summary"]].ne("").all(axis=1)].copy()
    text_columns += ["authors_joined", "categories_joined", "text_for_embedding"]
    df[text_columns] = df[text_columns].fillna("")
    return df.sort_values(
        ["published", "paper_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)

from __future__ import annotations

import random
from typing import Any

import pandas as pd

from core.utils import write_json

SEED = 42
DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_RATIO = 0.25
NOISE_RATIO = 0.25
TRUNCATE_TITLE_RATIO = 0.25
TRUNCATED_TITLE_CHARS = 6
# Must stay above the 25% freshness tolerance so the SLA check actually trips.
STALE_RATIO = 0.35
STALE_SHIFT_DAYS = 400
DUPLICATE_ROWS = 3
NOISE_TOKENS = ["#@$%", "~~??~~", "&*!^", "<<null>>", "0xDEADBEEF", "@@@", "|||"]


def _count(total: int, ratio: float) -> int:
    return max(1, round(total * ratio))


def _log_entry(kind: str, description: str, paper_ids: list[str]) -> dict[str, Any]:
    return {
        "type": kind,
        "description": description,
        "count": len(paper_ids),
        "affected_paper_ids": paper_ids,
    }


def _inject_noise(text: str, rng: random.Random) -> str:
    words = text.split()
    noisy: list[str] = [rng.choice(NOISE_TOKENS)]
    for position, word in enumerate(words, start=1):
        noisy.append(word)
        if position % 4 == 0:
            noisy.append(rng.choice(NOISE_TOKENS))
    return " ".join(noisy)


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    # Imported lazily: `ingestion/__init__.py` imports this module, so a top-level import
    # would make the whole `ingestion` package fail to import until cleaning.py provides it.
    from ingestion.cleaning import build_text_for_embedding

    rng = random.Random(SEED)
    corrupted = df.copy().reset_index(drop=True)
    input_rows = len(corrupted)
    log: list[dict[str, Any]] = []

    # 1. Drop the newest records: simulates a partial / late ingestion batch.
    drop_n = _count(input_rows, DROP_LATEST_RATIO)
    latest = corrupted.sort_values(["published", "paper_id"], ascending=[False, True]).head(drop_n)
    corrupted = corrupted.drop(index=latest.index).reset_index(drop=True)
    log.append(
        _log_entry(
            "drop_latest",
            f"Dropped the {drop_n} most recently published records ({DROP_LATEST_RATIO:.0%}).",
            latest["paper_id"].tolist(),
        )
    )

    # 2-4 hit disjoint row groups so each corruption's effect can be traced separately.
    order = list(corrupted.index)
    rng.shuffle(order)
    remaining = len(corrupted)
    blank_rows = order[: _count(remaining, BLANK_SUMMARY_RATIO)]
    order = order[len(blank_rows) :]
    noise_rows = order[: _count(remaining, NOISE_RATIO)]
    order = order[len(noise_rows) :]
    truncate_rows = order[: _count(remaining, TRUNCATE_TITLE_RATIO)]

    corrupted.loc[blank_rows, "summary"] = ""
    log.append(
        _log_entry(
            "blank_summary",
            "Replaced summary with an empty string.",
            corrupted.loc[blank_rows, "paper_id"].tolist(),
        )
    )

    for row in noise_rows:
        corrupted.at[row, "summary"] = _inject_noise(corrupted.at[row, "summary"], rng)
    log.append(
        _log_entry(
            "inject_noise",
            "Inserted garbage tokens at the start of the summary and after every 4th word.",
            corrupted.loc[noise_rows, "paper_id"].tolist(),
        )
    )

    corrupted.loc[truncate_rows, "title"] = corrupted.loc[truncate_rows, "title"].str[:TRUNCATED_TITLE_CHARS]
    log.append(
        _log_entry(
            "truncate_title",
            f"Truncated title to {TRUNCATED_TITLE_CHARS} characters (below the 8-character minimum).",
            corrupted.loc[truncate_rows, "paper_id"].tolist(),
        )
    )

    # 5. Stale dates may overlap the groups above: it only touches the date columns.
    stale_rows = rng.sample(list(corrupted.index), _count(remaining, STALE_RATIO))
    shifted = pd.to_datetime(corrupted.loc[stale_rows, "published"]) - pd.Timedelta(days=STALE_SHIFT_DAYS)
    corrupted.loc[stale_rows, "published"] = shifted.dt.strftime("%Y-%m-%d")
    corrupted.loc[stale_rows, "age_days"] = corrupted.loc[stale_rows, "age_days"] + STALE_SHIFT_DAYS
    log.append(
        _log_entry(
            "stale_date",
            f"Shifted published date {STALE_SHIFT_DAYS} days into the past and recomputed age_days.",
            corrupted.loc[stale_rows, "paper_id"].tolist(),
        )
    )

    # 6. Duplicate rows: breaks paper_id uniqueness and crowds the top-k results.
    duplicate_rows = rng.sample(list(corrupted.index), min(DUPLICATE_ROWS, len(corrupted)))
    duplicates = corrupted.loc[duplicate_rows]
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)
    log.append(
        _log_entry(
            "duplicate_rows",
            f"Appended {len(duplicates)} exact duplicate rows.",
            duplicates["paper_id"].tolist(),
        )
    )

    # 7. Rebuild derived columns so the index embeds the corrupted text.
    corrupted["summary_chars"] = corrupted["summary"].str.len()
    corrupted["text_for_embedding"] = corrupted.apply(build_text_for_embedding, axis=1)

    # 8. Persist the corruption log.
    write_json(
        output_log_path,
        {
            "seed": SEED,
            "input_rows": input_rows,
            "output_rows": len(corrupted),
            "corruptions": log,
        },
    )
    return corrupted

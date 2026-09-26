from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Write ten reproducible questions spanning dates and both paper groups.

    Input follows the clean dataframe contract, including ISO date strings.
    Reject corpora that cannot cover the newest paper and both groups safely.
    """
    if len(df) < 10:
        raise ValueError("At least 10 clean papers are required.")

    ordered = df.sort_values(
        ["published", "paper_id"], ascending=[False, True], kind="stable"
    )
    # QA scans the entire question, including its title, for these phrases.
    keywords = (
        "who authored", "list the authors", "when was",
        "publication date", "published on", "what categories",
    )
    required = (
        "paper_id", "title", "published", "summary",
        "authors_joined", "categories_joined",
    )
    title_counts = ordered["title"].str.lower().value_counts()
    candidates = []
    for row in ordered.to_dict(orient="records"):
        if any(not isinstance(row[key], str) or not row[key].strip() for key in required):
            continue
        title = row["title"]
        if "'" in title or any(keyword in title.lower() for keyword in keywords):
            continue
        # lookup() indexes titles case-insensitively; ambiguous titles are unsafe.
        if title_counts[title.lower()] != 1:
            continue
        candidates.append(row)
    if len(candidates) < 10:
        raise ValueError("At least 10 papers with unique, QA-safe titles and nonempty answers are required.")
    if len({row["paper_id"] for row in candidates}) != len(candidates):
        raise ValueError("Clean paper_id values must be unique.")
    if candidates[0]["published"] != ordered.iloc[0]["published"]:
        raise ValueError("The newest papers have no QA-safe candidate.")

    def is_advanced(row) -> bool:
        return row["title"].lower().startswith("advanced perspectives")

    # Include both endpoints and evenly spaced ranks across the dated corpus.
    selected = [candidates[i * (len(candidates) - 1) // 9] for i in range(10)]
    for advanced in (False, True):
        group = [row for row in candidates if is_advanced(row) == advanced]
        if not group:
            raise ValueError("Both original and Advanced Perspectives papers are required.")
        if not any(is_advanced(row) == advanced for row in selected):
            # Preserve the newest and oldest selected papers.
            selected[-2] = group[len(group) // 2]
    selected.sort(key=lambda row: row["paper_id"])
    selected.sort(key=lambda row: row["published"], reverse=True)

    question_types = (
        "summary", "authors", "date", "categories", "summary",
        "authors", "date", "categories", "summary", "authors",
    )
    templates = {
        "summary": "Summarize the main contribution of the paper '{title}'.",
        "authors": "Who authored the paper '{title}'?",
        "date": "When was the paper '{title}' published?",
        "categories": "What categories does the paper '{title}' belong to?",
    }
    answer_fields = {
        "authors": "authors_joined", "date": "published", "categories": "categories_joined",
    }
    items = []
    for number, (row, question_type) in enumerate(zip(selected, question_types), start=1):
        ground_truth = (
            first_sentence(row["summary"])
            if question_type == "summary" else row[answer_fields[question_type]]
        )
        items.append({
            "id": f"q{number:02d}",
            "question_type": question_type,
            "question": templates[question_type].format(title=row["title"]),
            "ground_truth": ground_truth,
            "ground_truth_doc_ids": [row["paper_id"]],
        })
    write_json(Path(output_path), items)
    return items

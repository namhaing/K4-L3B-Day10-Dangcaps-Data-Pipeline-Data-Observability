from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from core.config import Settings


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_date_parts(date_parts: list | None) -> str:
    if not date_parts:
        return ""
    current = date_parts[0] if isinstance(date_parts, list) else date_parts
    if isinstance(current, list) and len(current) >= 3:
        year, month, day = current[:3]
        if year is not None:
            return f"{int(year):04d}-{int(month) if month is not None else 1:02d}-{int(day) if day is not None else 1:02d}"
        return ""
    if isinstance(current, str):
        return current[:10]
    return ""


def _extract_date(date_obj: dict | None) -> str:
    """Helper trích xuất ngày tháng hỗ trợ cả 'date-time' và 'date-parts'."""
    if not date_obj:
        return ""
    
    # 1. Ưu tiên lấy từ chuỗi ISO 'date-time' nếu có (VD: "2026-06-25T15:10:00Z" -> "2026-06-25")
    date_time = date_obj.get("date-time")
    if isinstance(date_time, str) and len(date_time) >= 10:
        return date_time[:10]
    
    # 2. Fallback về hàm 'date-parts' cũ nếu không có 'date-time'
    date_parts = date_obj.get("date-parts")
    return _parse_date_parts(date_parts)


def _extract_pdf_url(item: dict) -> str:
    links = item.get("link") or []
    for link in links:
        if not isinstance(link, dict):
            continue
        content_type = str(link.get("content-type") or "").lower()
        if "pdf" in content_type or "application/pdf" in content_type:
            url = link.get("URL") or ""
            if url:
                return url
    if isinstance(item.get("URL"), str):
        return item["URL"]
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload to list[PaperRecord].

    Accepts the full response body from Crossref and extracts the normalized DOI-based
    paper metadata needed for downstream cleaning and retrieval.
    """
    if not isinstance(payload, dict):
        raise ValueError("Crossref payload must be a dict.")

    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        doi = str(item.get("DOI") or "").strip()
        if not doi:
            continue

        title = " ".join(
            [str(part) for part in (item.get("title") or []) if isinstance(part, str)]
        )
        title = _normalize_text(title)
        if not title:
            continue

        abstract_raw = item.get("abstract") or ""
        summary = _normalize_text(abstract_raw)

        authors_raw = item.get("author") or []
        authors: list[str] = []
        for author in authors_raw:
            if not isinstance(author, dict):
                continue
            given = (author.get("given") or "").strip()
            family = (author.get("family") or "").strip()
            name = " ".join(part for part in [given, family] if part)
            if name:
                authors.append(name)

        categories_raw = item.get("subject") or []
        categories = [_normalize_text(str(category)) for category in categories_raw if str(category).strip()]
        primary_category = categories[0] if categories else "General"

        published_raw = item.get("published") or {}
        updated_raw = item.get("updated") or {}
        created_raw = item.get("created") or {}

        # Sử dụng hàm _extract_date mới để đọc cả 'date-time' và 'date-parts'
        published = _extract_date(published_raw)
        updated = _extract_date(updated_raw)
        
        # Logic dự phòng (Fallback)
        if not updated:
            updated = _extract_date(created_raw)
            
        # Nếu vẫn không có updated (không có created), lấy published bù vào
        if not updated and published:
            updated = published
            
        # Nếu không có published, lấy updated bù vào
        if not published and updated:
            published = updated

        abs_url = str(item.get("URL") or f"https://doi.org/{doi}").strip()
        pdf_url = _extract_pdf_url(item)

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=f"Crossref record {doi}",
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch source records from Crossref API and persist raw snapshots."""
    params = {
        "query.title": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": "DOI,title,abstract,author,subject,published,updated,created,URL,link",
    }

    raw_path = settings.paths.raw_api_response
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            response = requests.get(
                "https://api.crossref.org/works",
                params=params,
                timeout=30,
            )
            if response.status_code in {429, 500, 502, 503, 504}:
                raise requests.HTTPError(f"Crossref retryable status {response.status_code}")
            response.raise_for_status()
            payload = response.json()
            with raw_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            records = parse_crossref_payload(payload)
            break
        except (requests.RequestException, ValueError) as exc:  # pragma: no cover - network fallback path
            last_error = exc
            if attempt < 5:
                time.sleep(1.5 * attempt)
                continue
            payload = None
            records = []

    if not records:
        fallback_path = raw_path
        if fallback_path.exists():
            try:
                with fallback_path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
                records = parse_crossref_payload(payload)
            except (OSError, json.JSONDecodeError, ValueError):
                records = []

    if not records:
        fallback_snapshot = Path("data/raw/crossref_records.json")
        if fallback_snapshot.exists():
            records = load_raw_records(fallback_snapshot)

    if not records:
        raise RuntimeError(
            "Failed to fetch Crossref data and no valid offline snapshot was available."
        ) from last_error

    raw_records_path = settings.paths.raw_records_json
    raw_records_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [
        {
            "paper_id": record.paper_id,
            "title": record.title,
            "summary": record.summary,
            "authors": record.authors,
            "categories": record.categories,
            "primary_category": record.primary_category,
            "published": record.published,
            "updated": record.updated,
            "abs_url": record.abs_url,
            "pdf_url": record.pdf_url,
            "comment": record.comment,
        }
        for record in records
    ]
    with raw_records_path.open("w", encoding="utf-8") as f:
        json.dump(serialized, f, ensure_ascii=False, indent=2)

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load raw JSON records into PaperRecord objects."""
    with Path(path).open("r", encoding="utf-8") as f:
        raw_records = json.load(f)

    if not isinstance(raw_records, list):
        raise ValueError(f"Raw record file {path} must contain a list of records.")

    records: list[PaperRecord] = []
    for item in raw_records:
        if not isinstance(item, dict):
            continue
        records.append(
            PaperRecord(
                paper_id=str(item.get("paper_id") or "").strip(),
                title=_normalize_text(item.get("title")),
                summary=_normalize_text(item.get("summary")),
                authors=[_normalize_text(author) for author in (item.get("authors") or []) if _normalize_text(author)],
                categories=[_normalize_text(category) for category in (item.get("categories") or []) if _normalize_text(category)],
                primary_category=_normalize_text(item.get("primary_category")),
                published=str(item.get("published") or "").strip(),
                updated=str(item.get("updated") or "").strip(),
                abs_url=str(item.get("abs_url") or "").strip(),
                pdf_url=str(item.get("pdf_url") or "").strip(),
                comment=str(item.get("comment") or "").strip(),
            )
        )
    return [record for record in records if record.paper_id]
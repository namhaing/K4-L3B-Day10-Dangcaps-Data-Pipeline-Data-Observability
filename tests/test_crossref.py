from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import requests

from ingestion import crossref
from ingestion.crossref import fetch_source_records, parse_crossref_payload


def test_parser_extracts_records_and_skips_missing_identity_or_title(raw_records):
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.5555/valid",
                    "title": ["  A   valid title "],
                    "abstract": "<jats:p>Long enough abstract text for a valid record.</jats:p>",
                    "author": [{"given": "A", "family": "Writer"}],
                    "subject": ["Systems"],
                    "published": {"date-parts": [[2026, 1, 2]]},
                },
                {"DOI": "10.5555/no-title", "title": []},
                {"title": ["No DOI"]},
            ]
        }
    }

    records = parse_crossref_payload(payload)

    assert len(records) == 1
    assert records[0].paper_id == "10.5555/valid"
    assert records[0].title == "A valid title"
    assert records[0].summary == "Long enough abstract text for a valid record."
    assert records[0].published == "2026-01-02"


def test_fetch_persists_response_and_parsed_records(monkeypatch, settings, raw_records):
    payload = {"message": {"items": [{
        "DOI": raw_records[0].paper_id,
        "title": [raw_records[0].title],
        "abstract": raw_records[0].summary,
        "author": [],
        "subject": [],
        "published": {"date-parts": [[2026, 1, 1]]},
    }]}}

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return payload

    monkeypatch.setattr(crossref.requests, "get", lambda *args, **kwargs: Response())

    records = fetch_source_records(settings)

    assert len(records) == 1
    assert json.loads(settings.paths.raw_api_response.read_text(encoding="utf-8")) == payload
    parsed = json.loads(settings.paths.raw_records_json.read_text(encoding="utf-8"))
    assert parsed[0]["paper_id"] == raw_records[0].paper_id


def test_fetch_uses_configured_raw_records_snapshot_when_api_fails(monkeypatch, settings, raw_records):
    settings.paths.raw_records_json.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.raw_records_json.write_text(
        json.dumps([asdict(raw_records[0])]),
        encoding="utf-8",
    )
    monkeypatch.setattr(crossref.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(requests.ConnectionError("offline")))
    monkeypatch.setattr(crossref.time, "sleep", lambda seconds: None)

    records = fetch_source_records(settings)

    assert len(records) == 1
    assert records[0].paper_id == raw_records[0].paper_id
    assert settings.paths.raw_records_json.exists()
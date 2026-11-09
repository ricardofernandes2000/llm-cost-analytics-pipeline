from types import SimpleNamespace

import pytest

from functions.ingestion import main as ingestion
from functions.ingestion.main import (
    build_row,
    calculate_cost_usd,
    find_existing_event_ids,
    remove_duplicate_rows,
)


def test_calculate_cost_for_supported_model() -> None:
    cost = calculate_cost_usd("gpt-4o-mini", 1000, 1000)

    assert cost == pytest.approx(0.00075)


def test_calculate_cost_with_zero_tokens() -> None:
    assert calculate_cost_usd("gpt-4o", 0, 0) == 0.0


def test_calculate_cost_is_rounded_to_eight_decimal_places() -> None:
    cost = calculate_cost_usd("gemini-2.5-pro", 1234, 567)

    assert cost == pytest.approx(0.0072125)
    assert len(str(cost).split(".")[1]) <= 8


def test_calculate_cost_rejects_unknown_model() -> None:
    with pytest.raises(KeyError):
        calculate_cost_usd("unknown-model", 100, 100)


def test_build_row_converts_numeric_fields_and_adds_cost() -> None:
    event = {
        "event_id": "evt-0001",
        "timestamp": "2026-09-13T12:00:00Z",
        "provider": "OpenAI",
        "model": "gpt-4o",
        "input_tokens": "1000",
        "output_tokens": "500",
        "latency_ms": "250",
        "status": "success",
    }

    row = build_row(event)

    assert row == {
        "event_id": "evt-0001",
        "timestamp": "2026-09-13T12:00:00Z",
        "provider": "OpenAI",
        "model": "gpt-4o",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cost_usd": 0.0125,
        "latency_ms": 250,
        "status": "success",
    }


def test_build_row_rejects_missing_required_field() -> None:
    event = {
        "timestamp": "2026-09-13T12:00:00Z",
        "provider": "OpenAI",
        "model": "gpt-4o",
        "input_tokens": 1000,
        "output_tokens": 500,
        "status": "success",
    }

    with pytest.raises(KeyError):
        build_row(event)


def test_find_existing_event_ids_returns_matching_ids() -> None:
    class QueryResult:
        def result(self):
            return [{"event_id": "evt-0001"}, {"event_id": "evt-0003"}]

    class FakeClient:
        def query(self, query, job_config):
            assert "event_id IN UNNEST(@event_ids)" in query
            assert job_config.query_parameters[0].name == "event_ids"
            return QueryResult()

    existing = find_existing_event_ids(
        FakeClient(), "demo-project.llm_analytics.api_events", ["evt-0001", "evt-0002"]
    )

    assert existing == {"evt-0001", "evt-0003"}


def test_find_existing_event_ids_skips_empty_input() -> None:
    class UnexpectedClient:
        def query(self, *args, **kwargs):
            raise AssertionError("A query should not run for an empty ID list")

    assert find_existing_event_ids(UnexpectedClient(), "table", []) == set()


def test_remove_duplicate_rows_skips_stored_and_repeated_batch_ids() -> None:
    rows = [
        {"event_id": "evt-stored", "value": "already stored"},
        {"event_id": "evt-new", "value": "first occurrence"},
        {"event_id": "evt-new", "value": "repeated in batch"},
        {"event_id": None, "value": "without ID"},
        {"event_id": None, "value": "another without ID"},
    ]

    unique_rows, duplicate_count = remove_duplicate_rows(rows, {"evt-stored"})

    assert unique_rows == [
        {"event_id": "evt-new", "value": "first occurrence"},
        {"event_id": None, "value": "without ID"},
        {"event_id": None, "value": "another without ID"},
    ]
    assert duplicate_count == 2


def test_ingest_events_skips_repeated_ids_in_same_file(monkeypatch, capsys) -> None:
    event = {
        "event_id": "evt-0001",
        "timestamp": "2026-09-13T12:00:00Z",
        "provider": "OpenAI",
        "model": "gpt-4o",
        "input_tokens": 1000,
        "output_tokens": 500,
        "latency_ms": 250,
        "status": "success",
    }

    class QueryResult:
        def result(self):
            return []

    class FakeClient:
        def __init__(self):
            self.inserted_rows = []

        def query(self, query, job_config):
            assert job_config.query_parameters[0].values == ["evt-0001"]
            return QueryResult()

        def insert_rows_json(self, table_ref, rows):
            self.inserted_rows = rows
            return []

    client = FakeClient()
    monkeypatch.setattr(ingestion, "load_events", lambda *_: [event, event])
    monkeypatch.setattr(ingestion.bigquery, "Client", lambda: client)
    monkeypatch.setenv("BQ_PROJECT_ID", "demo-project")

    ingestion.ingest_events(
        SimpleNamespace(data={"bucket": "demo-bucket", "name": "events.json"})
    )

    assert len(client.inserted_rows) == 1
    assert client.inserted_rows[0]["event_id"] == "evt-0001"
    assert "Skipped 1 duplicate rows" in capsys.readouterr().out

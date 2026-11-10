from unittest.mock import patch

import pytest
from flask import Flask, request
from google.cloud import bigquery

from functions.api.main import _json_value, _run_query, _table_ref, analytics_api


app = Flask(__name__)


def test_table_ref_uses_explicit_environment(monkeypatch) -> None:
    monkeypatch.setenv("BQ_PROJECT_ID", "demo-project")
    monkeypatch.setenv("BQ_DATASET", "analytics")
    monkeypatch.setenv("BQ_TABLE", "events")

    assert _table_ref() == "demo-project.analytics.events"


def test_table_ref_uses_defaults(monkeypatch) -> None:
    monkeypatch.setenv("BQ_PROJECT_ID", "demo-project")
    monkeypatch.delenv("BQ_DATASET", raising=False)
    monkeypatch.delenv("BQ_TABLE", raising=False)

    assert _table_ref() == "demo-project.llm_analytics.api_events"


def test_json_value_converts_numpy_like_values() -> None:
    class Value:
        def item(self):
            return 12.5

    assert _json_value(Value()) == 12.5
    assert _json_value("success") == "success"


def test_run_query_passes_parameters_to_bigquery(monkeypatch) -> None:
    monkeypatch.setenv("BQ_PROJECT_ID", "demo-project")

    class QueryResult:
        def result(self):
            return [{"request_count": 2}]

    class FakeClient:
        def query(self, query, job_config):
            assert query == "SELECT @days"
            assert job_config.query_parameters[0].name == "days"
            assert job_config.query_parameters[0].value == 30
            return QueryResult()

    def fake_client(project):
        assert project == "demo-project"
        return FakeClient()

    monkeypatch.setattr("functions.api.main.bigquery.Client", fake_client)
    parameters = [bigquery.ScalarQueryParameter("days", "INT64", 30)]

    assert _run_query("SELECT @days", parameters) == [{"request_count": 2}]


def test_analytics_api_returns_summary_and_breakdowns(monkeypatch) -> None:
    monkeypatch.setenv("BQ_PROJECT_ID", "demo-project")
    query_results = [
        [{"request_count": 2, "total_cost_usd": 1.5}],
        [{"name": "OpenAI", "request_count": 2, "total_cost_usd": 1.5}],
        [{"name": "gpt-4o", "request_count": 2, "total_cost_usd": 1.5}],
    ]

    with app.test_request_context("/", method="GET"), patch(
        "functions.api.main._run_query", side_effect=query_results
    ) as run_query:
        response = analytics_api(request)

    assert response.status_code == 200
    assert response.get_json() == {
        "summary": {"request_count": 2, "total_cost_usd": 1.5},
        "by_provider": [{"name": "OpenAI", "request_count": 2, "total_cost_usd": 1.5}],
        "by_model": [{"name": "gpt-4o", "request_count": 2, "total_cost_usd": 1.5}],
    }
    assert run_query.call_count == 3
    assert all(call.args[1] is None for call in run_query.call_args_list)
    assert all(
        "TIMESTAMP_SUB" not in call.args[0] for call in run_query.call_args_list
    )
    assert response.headers["Access-Control-Allow-Origin"] == "*"


def test_analytics_api_applies_days_filter_to_all_queries(monkeypatch) -> None:
    monkeypatch.setenv("BQ_PROJECT_ID", "demo-project")
    query_results = [
        [{"request_count": 2, "total_cost_usd": 1.5}],
        [{"name": "OpenAI", "request_count": 2, "total_cost_usd": 1.5}],
        [{"name": "gpt-4o", "request_count": 2, "total_cost_usd": 1.5}],
    ]

    with app.test_request_context("/?days=30", method="GET"), patch(
        "functions.api.main._run_query", side_effect=query_results
    ) as run_query:
        response = analytics_api(request)

    assert response.status_code == 200
    assert run_query.call_count == 3
    for query_call in run_query.call_args_list:
        query, parameters = query_call.args
        assert "TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)" in query
        assert len(parameters) == 1
        assert parameters[0].name == "days"
        assert parameters[0].type_ == "INT64"
        assert parameters[0].value == 30


@pytest.mark.parametrize("days", ["not-a-number", "0", "366"])
def test_analytics_api_rejects_invalid_days(days: str, monkeypatch) -> None:
    monkeypatch.setenv("BQ_PROJECT_ID", "demo-project")

    with app.test_request_context(f"/?days={days}", method="GET"), patch(
        "functions.api.main._run_query"
    ) as run_query:
        response = analytics_api(request)

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "'days' must be an integer from 1 to 365."
    }
    run_query.assert_not_called()


def test_analytics_api_handles_options_request() -> None:
    with app.test_request_context("/", method="OPTIONS"):
        response = analytics_api(request)

    assert response[1] == 204
    assert response[2]["Access-Control-Allow-Methods"] == "GET, OPTIONS"


def test_analytics_api_rejects_non_get_methods() -> None:
    with app.test_request_context("/", method="POST"):
        response = analytics_api(request)

    assert response.status_code == 405
    assert response.get_json() == {"error": "Only GET requests are supported."}


def test_analytics_api_returns_500_when_query_fails(monkeypatch) -> None:
    monkeypatch.setenv("BQ_PROJECT_ID", "demo-project")

    with app.test_request_context("/", method="GET"), patch(
        "functions.api.main._run_query", side_effect=RuntimeError("database unavailable")
    ):
        response = analytics_api(request)

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "Unable to load analytics.",
        "detail": "database unavailable",
    }

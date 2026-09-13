from unittest.mock import patch

from flask import Flask, request

from functions.api.main import _json_value, _table_ref, analytics_api


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
    assert response.headers["Access-Control-Allow-Origin"] == "*"


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

"""HTTP API for LLM usage and cost analytics."""

import os
from typing import Any

import functions_framework
from flask import Request, jsonify
from google.cloud import bigquery


SUMMARY_QUERY = """
SELECT
  COUNT(*) AS request_count,
  COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
  COALESCE(SUM(input_tokens), 0) AS input_tokens,
  COALESCE(SUM(output_tokens), 0) AS output_tokens,
  COALESCE(AVG(latency_ms), 0) AS average_latency_ms,
  COUNTIF(status = 'success') AS successful_requests,
  COUNTIF(status != 'success') AS failed_requests
FROM `{table_ref}`
"""

BREAKDOWN_QUERY = """
SELECT
  {group_field} AS name,
  COUNT(*) AS request_count,
  COALESCE(SUM(cost_usd), 0) AS total_cost_usd
FROM `{table_ref}`
GROUP BY name
ORDER BY total_cost_usd DESC
"""


def _table_ref() -> str:
    """Build the fully qualified BigQuery table reference from configuration."""
    project_id = os.environ["BQ_PROJECT_ID"]
    dataset_id = os.environ.get("BQ_DATASET", "llm_analytics")
    table_id = os.environ.get("BQ_TABLE", "api_events")
    return f"{project_id}.{dataset_id}.{table_id}"


def _json_value(value: Any) -> Any:
    """Convert BigQuery numeric values into JSON-compatible values."""
    if hasattr(value, "item"):
        return value.item()
    return value


def _run_query(query: str) -> list[dict[str, Any]]:
    """Run a read-only query and return rows as plain dictionaries."""
    client = bigquery.Client()
    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in client.query(query).result()
    ]


@functions_framework.http
def analytics_api(request: Request):
    """Return aggregate analytics for the React dashboard."""
    if request.method == "OPTIONS":
        return ("", 204, _cors_headers())

    if request.method != "GET":
        response = jsonify({"error": "Only GET requests are supported."})
        response.status_code = 405
        response.headers.update(_cors_headers())
        return response

    try:
        table_ref = _table_ref()
        summary = _run_query(SUMMARY_QUERY.format(table_ref=table_ref))[0]
        by_provider = _run_query(
            BREAKDOWN_QUERY.format(table_ref=table_ref, group_field="provider")
        )
        by_model = _run_query(
            BREAKDOWN_QUERY.format(table_ref=table_ref, group_field="model")
        )
        response = jsonify(
            {
                "summary": summary,
                "by_provider": by_provider,
                "by_model": by_model,
            }
        )
        response.headers.update(_cors_headers())
        return response
    except Exception as error:
        response = jsonify({"error": "Unable to load analytics.", "detail": str(error)})
        response.status_code = 500
        response.headers.update(_cors_headers())
        return response


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": os.environ.get("CORS_ORIGIN", "*"),
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

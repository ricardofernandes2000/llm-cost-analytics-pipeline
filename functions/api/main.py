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
{date_filter}
"""

BREAKDOWN_QUERY = """
SELECT
  {group_field} AS name,
  COUNT(*) AS request_count,
  COALESCE(SUM(cost_usd), 0) AS total_cost_usd
FROM `{table_ref}`
{date_filter}
GROUP BY name
ORDER BY total_cost_usd DESC
"""

DATE_FILTER = (
    "WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)"
)


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


def _run_query(
    query: str,
    query_parameters: list[bigquery.ScalarQueryParameter] | None = None,
) -> list[dict[str, Any]]:
    """Run a read-only query and return rows as plain dictionaries."""
    client = bigquery.Client(project=os.environ["BQ_PROJECT_ID"])
    if query_parameters is None:
        query_job = client.query(query)
    else:
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        query_job = client.query(query, job_config=job_config)
    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in query_job.result()
    ]


def _parse_days(raw_days: str | None) -> int | None:
    """Parse and bound the optional rolling date window."""
    if raw_days is None:
        return None

    try:
        days = int(raw_days)
    except ValueError as error:
        raise ValueError("'days' must be an integer from 1 to 365.") from error

    if not 1 <= days <= 365:
        raise ValueError("'days' must be an integer from 1 to 365.")

    return days


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
        days = _parse_days(request.args.get("days"))
    except ValueError as error:
        response = jsonify({"error": str(error)})
        response.status_code = 400
        response.headers.update(_cors_headers())
        return response

    try:
        table_ref = _table_ref()
        date_filter = DATE_FILTER if days is not None else ""
        query_parameters = (
            [bigquery.ScalarQueryParameter("days", "INT64", days)]
            if days is not None
            else None
        )
        summary = _run_query(
            SUMMARY_QUERY.format(table_ref=table_ref, date_filter=date_filter),
            query_parameters,
        )[0]
        by_provider = _run_query(
            BREAKDOWN_QUERY.format(
                table_ref=table_ref,
                group_field="provider",
                date_filter=date_filter,
            ),
            query_parameters,
        )
        by_model = _run_query(
            BREAKDOWN_QUERY.format(
                table_ref=table_ref,
                group_field="model",
                date_filter=date_filter,
            ),
            query_parameters,
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

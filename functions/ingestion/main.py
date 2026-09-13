"""Cloud Storage-triggered ingestion for fictional LLM usage events."""

import json
import os
from decimal import Decimal
from typing import Any

import functions_framework
from google.cloud import bigquery, storage

# Prices are USD per 1,000 tokens and are intentionally fictional for the demo.
MODEL_PRICES = {
    "gpt-4o-mini": {"input": Decimal("0.00015"), "output": Decimal("0.00060")},
    "gpt-4o": {"input": Decimal("0.00500"), "output": Decimal("0.01500")},
    "gemini-2.0-flash": {"input": Decimal("0.00010"), "output": Decimal("0.00040")},
    "gemini-2.5-pro": {"input": Decimal("0.00125"), "output": Decimal("0.01000")},
    "claude-3-5-haiku": {"input": Decimal("0.00080"), "output": Decimal("0.00400")},
    "claude-3-7-sonnet": {"input": Decimal("0.00300"), "output": Decimal("0.01500")},
}


def calculate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate a request cost from fictional per-token model prices."""
    prices = MODEL_PRICES[model]
    cost = (
        Decimal(input_tokens) * prices["input"]
        + Decimal(output_tokens) * prices["output"]
    ) / Decimal(1000)
    return float(cost.quantize(Decimal("0.00000001")))


def build_row(event: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw event and convert it to the BigQuery table shape."""
    model = event["model"]
    input_tokens = int(event["input_tokens"])
    output_tokens = int(event["output_tokens"])

    return {
        "timestamp": event["timestamp"],
        "provider": event["provider"],
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": calculate_cost_usd(model, input_tokens, output_tokens),
        "latency_ms": int(event["latency_ms"]),
        "status": event["status"],
    }


def load_events(bucket_name: str, object_name: str) -> list[dict[str, Any]]:
    """Download and parse a JSON array from Cloud Storage."""
    storage_client = storage.Client()
    blob = storage_client.bucket(bucket_name).blob(object_name)
    return json.loads(blob.download_as_text())


@functions_framework.cloud_event
def ingest_events(cloud_event: Any) -> None:
    """Process a Cloud Storage object-created event into BigQuery rows."""
    event_data = cloud_event.data
    bucket_name = event_data["bucket"]
    object_name = event_data["name"]
    events = load_events(bucket_name, object_name)
    rows = [build_row(event) for event in events]

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    dataset_id = os.environ.get("BQ_DATASET", "llm_analytics")
    table_id = os.environ.get("BQ_TABLE", "api_events")
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    bigquery_client = bigquery.Client()
    errors = bigquery_client.insert_rows_json(table_ref, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert failed: {errors}")

    print(f"Inserted {len(rows)} rows from gs://{bucket_name}/{object_name}")

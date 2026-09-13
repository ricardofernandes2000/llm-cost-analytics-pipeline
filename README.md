# LLM Cost Analytics Pipeline

An end-to-end Google Cloud data pipeline for ingesting fictional LLM API usage events, processing costs, storing analytics in BigQuery, and presenting the results in a React dashboard.

## Architecture

```text
JSON events -> Cloud Storage -> Ingestion Cloud Function -> BigQuery -> API Cloud Function -> React dashboard
```

## Stack

- Terraform
- Google Cloud Storage
- Google Cloud Functions
- BigQuery
- Python
- React
- Recharts

## Repository structure

```text
terraform/              Infrastructure as code
functions/ingestion/    Cloud Storage ingestion function
functions/api/          HTTP API function
data/                   Sample event generation and local data
frontend/               React dashboard
docs/                   Technical documentation, including the BigQuery schema
```

## Local setup

The project is being built incrementally. The first cloud resources will only be created after the GCP project, billing settings, and local authentication are configured.

```bash
gcloud auth application-default login
terraform -chdir=terraform init
terraform -chdir=terraform plan
```

## Data schema

The BigQuery `api_events` table will contain: `timestamp`, `provider`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, and `status`.

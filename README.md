# LLM Cost Analytics Pipeline

An end-to-end Google Cloud data pipeline for ingesting fictional LLM API usage events, calculating costs, storing analytics in BigQuery, and displaying the results in a React dashboard.

All usage data in this project is fictional and intended for demonstration purposes.

## Architecture

```text
JSON events
	-> Cloud Storage
	-> Ingestion Cloud Function
	-> BigQuery
	-> Analytics API Function
	-> React dashboard
```

## Live Components

- Analytics API: https://llm-analytics-api-zghvsfuxiq-ew.a.run.app
- GitHub repository: https://github.com/ricardofernandes2000/llm-cost-analytics-pipeline

## Stack

- Terraform
- Google Cloud Storage
- Google Cloud Functions
- BigQuery
- Python
- React and TypeScript
- Vite

## Repository structure

```text
terraform/              Infrastructure as code
functions/ingestion/    Cloud Storage ingestion function
functions/api/          HTTP API function
data/                   Sample event generation and local data
frontend/               React dashboard
docs/                   Technical documentation, including the BigQuery schema
```

## Dashboard

The React dashboard consumes the analytics API and displays total cost, processed requests, average latency, success rate, token usage, cost distribution by provider, and request volume by model.

## Run the Dashboard Locally

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in a browser.

Create a production build with:

```bash
npm run build
```

## Analytics API

The deployed HTTP function exposes read-only analytics from BigQuery:

```bash
curl https://llm-analytics-api-zghvsfuxiq-ew.a.run.app
```

Example response:

```json
{
	"summary": {
		"request_count": 4000,
		"total_cost_usd": 44.69851399999996,
		"input_tokens": 7971568,
		"output_tokens": 3995804,
		"average_latency_ms": 1270.8259999999998,
		"successful_requests": 3836,
		"failed_requests": 164
	},
	"by_provider": [{"name": "OpenAI", "request_count": 1424, "total_cost_usd": 18.111639}],
	"by_model": [{"name": "gpt-4o", "request_count": 728, "total_cost_usd": 17.48118}]
}
```

## Deploy the Infrastructure

```bash
gcloud auth application-default login
terraform -chdir=terraform init
terraform -chdir=terraform plan -var="project_id=YOUR_PROJECT_ID"
terraform -chdir=terraform apply -var="project_id=YOUR_PROJECT_ID"
```

## Data schema

The BigQuery `llm_analytics.api_events` table contains: `timestamp`, `provider`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, and `status`.

See [docs/bigquery-schema.md](docs/bigquery-schema.md) for details.

## Validation Results

The deployed pipeline was validated with fictional data:

- 4,000 requests processed
- `$44.70` total calculated cost
- 3,836 successful requests
- 164 failed requests
- 1,271 ms average latency

## Security Notes

- Cloud Storage buckets use public access prevention.
- The ingestion and API functions use separate service accounts.
- The ingestion function has write access to BigQuery.
- The analytics API has read-only dataset access.
- The API is publicly invokable for dashboard demonstration purposes.
- All event data is fictional.

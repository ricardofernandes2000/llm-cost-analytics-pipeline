# Data

`generate_events.py` creates 1,000 fictional LLM API usage events for local development. The output is written to `sample_events.json` and contains no real API credentials or personal data.

Run the generator with:

```powershell
py data/generate_events.py
```

The generated events contain provider, model, token, latency, status, and timestamp values. The ingestion function calculates `cost_usd` from the provider and model pricing before inserting rows into BigQuery.

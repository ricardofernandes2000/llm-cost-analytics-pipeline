locals {
  resource_prefix = "llm-cost-analytics"
}

resource "google_project_service" "required_apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "eventarc.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "raw_events" {
  name                        = "${local.resource_prefix}-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age = 30
    }

    action {
      type = "Delete"
    }
  }

  labels = {
    environment = "portfolio"
    purpose     = "llm-events"
  }
}

resource "google_bigquery_dataset" "llm_analytics" {
  dataset_id                 = "llm_analytics"
  location                   = var.region
  delete_contents_on_destroy = false

  labels = {
    environment = "portfolio"
    purpose     = "llm-cost-analytics"
  }
}

resource "google_bigquery_table" "api_events" {
  dataset_id          = google_bigquery_dataset.llm_analytics.dataset_id
  table_id            = "api_events"
  deletion_protection = true

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  schema = <<EOF
[
  {
    "name": "timestamp",
    "type": "TIMESTAMP",
    "mode": "REQUIRED"
  },
  {
    "name": "provider",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "model",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "input_tokens",
    "type": "INTEGER",
    "mode": "REQUIRED"
  },
  {
    "name": "output_tokens",
    "type": "INTEGER",
    "mode": "REQUIRED"
  },
  {
    "name": "cost_usd",
    "type": "FLOAT",
    "mode": "REQUIRED"
  },
  {
    "name": "latency_ms",
    "type": "INTEGER",
    "mode": "REQUIRED"
  },
  {
    "name": "status",
    "type": "STRING",
    "mode": "REQUIRED"
  }
]
EOF
}

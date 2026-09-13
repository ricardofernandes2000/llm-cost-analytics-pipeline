locals {
  resource_prefix = "llm-cost-analytics"
}

data "archive_file" "ingestion_source" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/ingestion"
  output_path = "${path.module}/ingestion-source.zip"
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

resource "google_storage_bucket" "function_source" {
  name                        = "llm-fn-src-${substr(md5(var.project_id), 0, 12)}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age = 7
    }

    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_object" "ingestion_source" {
  name   = "ingestion-${data.archive_file.ingestion_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.ingestion_source.output_path
}

resource "google_service_account" "ingestion" {
  account_id   = "llm-ingestion"
  display_name = "LLM analytics ingestion function"
}

resource "google_bigquery_dataset_iam_member" "ingestion_writer" {
  dataset_id = google_bigquery_dataset.llm_analytics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_storage_bucket_iam_member" "ingestion_reader" {
  bucket = google_storage_bucket.raw_events.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.ingestion.email}"
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

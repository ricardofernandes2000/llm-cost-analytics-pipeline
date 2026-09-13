locals {
  resource_prefix = "llm-cost-analytics"
}

data "google_project" "current" {
  project_id = var.project_id
}

data "archive_file" "ingestion_source" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/ingestion"
  output_path = "${path.module}/ingestion-source.zip"
}

data "archive_file" "api_source" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/api"
  output_path = "${path.module}/api-source.zip"
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

resource "google_storage_bucket_object" "api_source" {
  name   = "api-${data.archive_file.api_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.api_source.output_path
}

resource "google_service_account" "ingestion" {
  account_id   = "llm-ingestion"
  display_name = "LLM analytics ingestion function"
}

resource "google_service_account" "ingestion_trigger" {
  account_id   = "llm-ingestion-trigger"
  display_name = "Eventarc trigger for LLM ingestion"
}

resource "google_service_account" "api" {
  account_id   = "llm-analytics-api"
  display_name = "LLM analytics API function"
}

resource "google_project_iam_member" "cloud_build_builder" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.builder"
  member  = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_build_builder" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.builder"
  member  = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "trigger_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.ingestion_trigger.email}"
}

resource "google_project_iam_member" "eventarc_service_agent" {
  project = var.project_id
  role    = "roles/eventarc.serviceAgent"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}

resource "google_cloud_run_service_iam_member" "trigger_invoker" {
  project  = var.project_id
  location = var.region
  service  = "llm-ingestion"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.ingestion_trigger.email}"
}

resource "google_project_iam_member" "storage_service_agent_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

resource "google_bigquery_dataset_iam_member" "ingestion_writer" {
  dataset_id = google_bigquery_dataset.llm_analytics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_bigquery_dataset_iam_member" "api_reader" {
  dataset_id = google_bigquery_dataset.llm_analytics.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "ingestion_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_storage_bucket_iam_member" "ingestion_reader" {
  bucket = google_storage_bucket.raw_events.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_cloudfunctions2_function" "ingestion" {
  name        = "llm-ingestion"
  location    = var.region
  description = "Processes uploaded LLM usage event files."

  build_config {
    runtime     = "python312"
    entry_point = "ingest_events"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.ingestion_source.name
      }
    }
  }

  service_config {
    available_memory      = "256M"
    timeout_seconds       = 60
    max_instance_count    = 1
    service_account_email = google_service_account.ingestion.email

    environment_variables = {
      BQ_PROJECT_ID = var.project_id
      BQ_DATASET    = google_bigquery_dataset.llm_analytics.dataset_id
      BQ_TABLE      = google_bigquery_table.api_events.table_id
    }
  }

  event_trigger {
    event_type            = "google.cloud.storage.object.v1.finalized"
    retry_policy          = "RETRY_POLICY_RETRY"
    service_account_email = google_service_account.ingestion_trigger.email

    event_filters {
      attribute = "bucket"
      value     = google_storage_bucket.raw_events.name
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_bigquery_dataset_iam_member.ingestion_writer,
    google_storage_bucket_iam_member.ingestion_reader,
    google_project_iam_member.cloud_build_builder,
    google_project_iam_member.compute_build_builder,
    google_project_iam_member.compute_artifact_writer,
    google_project_iam_member.trigger_event_receiver,
    google_project_iam_member.eventarc_service_agent,
    google_project_iam_member.storage_service_agent_publisher,
    google_cloud_run_service_iam_member.trigger_invoker,
  ]
}

resource "google_cloudfunctions2_function" "api" {
  name        = "llm-analytics-api"
  location    = var.region
  description = "Serves LLM usage and cost analytics."

  build_config {
    runtime     = "python312"
    entry_point = "analytics_api"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.api_source.name
      }
    }
  }

  service_config {
    available_memory      = "256M"
    timeout_seconds       = 60
    max_instance_count    = 1
    service_account_email = google_service_account.api.email

    environment_variables = {
      BQ_PROJECT_ID = var.project_id
      BQ_DATASET    = google_bigquery_dataset.llm_analytics.dataset_id
      BQ_TABLE      = google_bigquery_table.api_events.table_id
      CORS_ORIGIN   = "*"
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_bigquery_dataset_iam_member.api_reader,
    google_project_iam_member.api_job_user,
  ]
}

resource "google_cloudfunctions2_function_iam_member" "api_invoker" {
  project        = var.project_id
  location       = var.region
  cloud_function = google_cloudfunctions2_function.api.name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}

resource "google_cloud_run_service_iam_member" "api_invoker" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
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
    "name": "event_id",
    "type": "STRING",
    "mode": "NULLABLE"
  },
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

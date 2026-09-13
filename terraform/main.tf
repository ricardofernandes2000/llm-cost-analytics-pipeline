locals {
  resource_prefix = "llm-cost-analytics"
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

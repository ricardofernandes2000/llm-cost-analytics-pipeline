variable "project_id" {
  description = "Google Cloud project ID used by this portfolio pipeline."
  type        = string
}

variable "region" {
  description = "Primary Google Cloud region."
  type        = string
  default     = "europe-west1"
}

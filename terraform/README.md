# Terraform

Infrastructure definitions for the GCP storage bucket, BigQuery dataset/table, and Cloud Functions will live here.

Set the project locally before running Terraform:

```bash
$env:TF_VAR_project_id = "your-gcp-project-id"
terraform init
terraform plan
```

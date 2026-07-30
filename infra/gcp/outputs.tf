output "api_url" {
  description = "Public HTTPS URL of the deployed ami-trade-api Cloud Run service."
  value       = google_cloud_run_v2_service.api.uri
}

output "deployer_service_account_email" {
  description = "Feed into GitHub Actions (prefer Workload Identity Federation over a long-lived key) once B1's IAM is up."
  value       = google_service_account.deployer.email
}

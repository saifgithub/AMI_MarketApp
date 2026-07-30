resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = "ami-trade-backend"
  format        = "DOCKER"
  description   = "AMI Trade backend Docker images (Beta/MVP Cloud Run deploys)."
}

# GCP provider + remote state for AMI Trade's Beta infra. CR126 — see
# docs/forward_planning/CR126_beta_infra_provisioning/. Bootstrap order and
# validation caveats are in ./README.md — not yet run through `terraform
# validate` (no Terraform CLI on this Mac).

terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Commented until the state bucket exists — see README.md "Bootstrap order".
  # backend "gcs" {
  #   bucket = "ami-trade-tfstate"
  #   prefix = "beta"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

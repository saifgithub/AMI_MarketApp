# Runtime SA — the Cloud Run service's own identity. Only what it needs to
# read secrets at boot; no broader project role. Least-privilege mirrors the
# same concern CR123/CR124 are hardening on the melehost side (superuser
# Postgres, no-auth Redis reachable from the LAN).
resource "google_service_account" "run_runtime" {
  account_id   = "ami-trade-api-runtime"
  display_name = "AMI Trade API — Cloud Run runtime identity"
}

resource "google_project_iam_member" "run_runtime_secret_access" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.run_runtime.email}"
}

# Deploy SA — used by .github/workflows/deploy-beta.yml to push images and
# roll out revisions. Deliberately NOT project-owner/editor.
resource "google_service_account" "deployer" {
  account_id   = "ami-trade-deployer"
  display_name = "AMI Trade — CI/CD deploy identity"
}

resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Cloud Run deploys need to "act as" the runtime SA when attaching it to a
# new revision — this is that specific grant, not a broad role.
resource "google_service_account_iam_member" "deployer_can_act_as_runtime" {
  service_account_id = google_service_account.run_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

# Single scale-to-zero service per D-067 — not hosting.md's original 3-service
# (api/agents/workers) always-warm sample, which was sized for MVP/Growth
# traffic Beta doesn't have yet. Splitting into 3 services later is an
# additive change to this file, not a redesign.
resource "google_cloud_run_v2_service" "api" {
  name     = "ami-trade-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.run_runtime.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # 80 concurrent requests/instance, per hosting.md's original sizing —
    # unaffected by the 1-vs-3-service change above.
    max_instance_request_concurrency = 80

    # Convene the Room may take ~90s + buffer (hosting.md).
    timeout = "300s"

    containers {
      # backend/Dockerfile's CMD hardcodes `--port 8000` rather than reading
      # Cloud Run's injected $PORT — set container_port explicitly so Cloud
      # Run's health/readiness probes hit the right port without touching
      # the Dockerfile.
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend.repository_id}/api:${var.image_tag}"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      # Beta and MVP both map to the app's own env=prod — config.py's `env`
      # Literal has no separate "beta" value (local/dev/staging/prod only).
      env {
        name  = "ENV"
        value = "prod"
      }

      dynamic "env" {
        for_each = local.secrets
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.this[env.key].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Public API — same posture as today's Alpha (reachable at a public hostname,
# auth enforced at the application layer, not at the network edge).
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

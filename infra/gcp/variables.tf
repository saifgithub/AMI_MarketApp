variable "project_id" {
  description = "GCP project ID created under B1 (Saiful's external action — GCP project, billing, IAM)."
  type        = string
}

variable "region" {
  description = "GCP region. europe-west3 (Frankfurt) locked by D-043 — best latency balance for KSA/US/Malaysia users, EU data residency for GDPR/PDPL."
  type        = string
  default     = "europe-west3"
}

variable "image_tag" {
  description = "Docker image tag to deploy (git tag or commit SHA). No default on purpose — CI/CD must supply this explicitly so nothing ever deploys `:latest` by accident."
  type        = string
}

variable "min_instances" {
  description = "Cloud Run min instances. 0 (scale-to-zero) per D-067 — Beta traffic is low/unproven, cold start is an acceptable tradeoff for a non-critical education app. Raise once B12's load test justifies always-warm capacity."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Cloud Run max instances. Modest ceiling for Beta's 100-500 user scale (CR006); raise for Growth phase."
  type        = number
  default     = 10
}

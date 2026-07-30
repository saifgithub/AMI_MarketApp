# Secret IDs mirror backend/app/core/config.py's actual sensitive `Settings`
# fields (source of truth as of 2026-07-30) rather than hosting.md's original
# pre-implementation 14-item list, which has drifted since — RevenueCat,
# Alpaca, Alpha Vantage, Adanos, and the auth/admin secrets all landed after
# that doc was written.
#
# Deliberately excluded — see README.md "Deliberately deferred / excluded":
#   - VLLM_* (Cloud Run can't reach the LAN-only on-prem box, D-068)
#   - Managed Redis (nothing in backend/app reads REDIS_URL today)
#
# Values are never set here — every secret is created empty; populate via
# `gcloud secrets versions add <id> --data-file=-` once B1/B4 land.
# `secret-key` especially: generate a FRESH value for Beta, do not copy
# Alpha's — DEF182 (CR123) already flags SECRET_KEY reuse as a live security
# issue; Beta should not inherit it.

locals {
  # secret_id => env var name the backend actually reads (config.py)
  secrets = {
    "database-url"              = "DATABASE_URL"
    "supabase-service-key"      = "SUPABASE_SERVICE_KEY"
    "openrouter-api-key"        = "OPENROUTER_API_KEY"
    "anthropic-api-key"         = "ANTHROPIC_API_KEY"
    "openai-api-key"            = "OPENAI_API_KEY"
    "google-ai-api-key"         = "GOOGLE_AI_API_KEY"
    "deepseek-api-key"          = "DEEPSEEK_API_KEY"
    "resend-api-key"            = "RESEND_API_KEY"
    "twilio-account-sid"        = "TWILIO_ACCOUNT_SID"
    "twilio-auth-token"         = "TWILIO_AUTH_TOKEN"
    "onesignal-rest-key"        = "ONESIGNAL_REST_KEY"
    "azure-speech-key"          = "AZURE_SPEECH_KEY"
    "elevenlabs-api-key"        = "ELEVENLABS_API_KEY"
    "sentry-dsn"                = "SENTRY_DSN"
    "posthog-api-key"           = "POSTHOG_API_KEY"
    "secret-key"                = "SECRET_KEY"
    "admin-secret"              = "ADMIN_SECRET"
    "revenuecat-webhook-secret" = "REVENUECAT_WEBHOOK_SECRET"
    "revenuecat-secret-api-key" = "REVENUECAT_SECRET_API_KEY"
    "alpaca-client-secret"      = "ALPACA_CLIENT_SECRET"
    "alpha-vantage-api-key"     = "ALPHA_VANTAGE_API_KEY"
    "adanos-api-key"            = "ADANOS_API_KEY"
  }
}

resource "google_secret_manager_secret" "this" {
  for_each  = local.secrets
  secret_id = each.key

  replication {
    auto {}
  }
}

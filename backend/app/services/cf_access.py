"""CR200 — Cloudflare Access identity resolution for the admin back-office.

The management console (and later /v1/admin itself) sits behind Cloudflare
Access. CF injects a `Cf-Access-Jwt-Assertion` header on every request that
passed the edge policy; the JWT is a standard OIDC-shaped token signed by the
team's Access certs (JWKS at `<team-domain>/cdn-cgi/access/certs`), with the
Access application's AUD tag as audience. A human login carries an `email`
claim; a service token carries `common_name`.

Resolution order (see `resolve_admin_identity`):
  1. CF Access JWT — verified with the existing `OIDCVerifier` (same machinery
     as Apple/Google sign-in; python-jose, JWKS cache, kid-rotation refresh).
  2. Static ADMIN_SECRET bearer — the pre-CR200 path, kept so agent scripts
     and LAN-direct access keep working; operator recorded as
     "static_bearer".

CF verification is enabled only when BOTH `CF_ACCESS_TEAM_DOMAIN` and
`CF_ACCESS_AUD` are set. Half-set is a config mistake and degrades LOUDLY
(CR040): a warning is logged on first use and the CF path stays off rather
than silently accepting or rejecting everything.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import structlog

from app.core.config import settings
from app.services.oidc_verifier import OIDCVerificationError, OIDCVerifier

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AdminIdentity:
    """Who performed an admin action, and how they authenticated."""

    kind: Literal["cf_email", "cf_service", "static_bearer"]
    operator: str


def build_cf_access_verifier(team_domain: str, aud: str) -> OIDCVerifier:
    """CF Access verifier — team domain is both issuer and JWKS host."""
    base = team_domain.rstrip("/")
    return OIDCVerifier(
        jwks_uri=f"{base}/cdn-cgi/access/certs",
        issuers=[base],
        audiences=[aud],
    )


@lru_cache(maxsize=1)
def _cached_verifier() -> OIDCVerifier | None:
    team = settings.cf_access_team_domain
    aud = settings.cf_access_aud
    if team and aud:
        return build_cf_access_verifier(team, aud)
    if team or aud:
        logger.warning(
            "cf_access_half_configured",
            detail="one of CF_ACCESS_TEAM_DOMAIN / CF_ACCESS_AUD is set without "
            "the other — CF Access verification stays DISABLED (bearer-only)",
            team_domain_set=bool(team),
            aud_set=bool(aud),
        )
    return None


def reset_cf_access_verifier_cache() -> None:
    """Test affordance — settings changed underneath the cache."""
    _cached_verifier.cache_clear()


def resolve_admin_identity(
    cf_jwt: str | None, authorization: str | None,
) -> AdminIdentity | None:
    """Resolve the caller to an AdminIdentity, or None if nothing verifies."""
    if cf_jwt:
        verifier = _cached_verifier()
        if verifier is not None:
            try:
                claims = verifier.verify(cf_jwt)
            except OIDCVerificationError as e:
                logger.warning("cf_access_jwt_rejected", error=str(e))
            else:
                email = claims.get("email")
                if email:
                    return AdminIdentity(kind="cf_email", operator=email)
                common_name = claims.get("common_name")
                if common_name:
                    return AdminIdentity(kind="cf_service", operator=common_name)
                logger.warning(
                    "cf_access_jwt_no_identity_claim",
                    detail="valid CF JWT without email/common_name",
                )

    if settings.admin_secret and authorization:
        token = ""
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1]
        if hmac.compare_digest(token.encode(), settings.admin_secret.encode()):
            return AdminIdentity(kind="static_bearer", operator="static_bearer")

    return None

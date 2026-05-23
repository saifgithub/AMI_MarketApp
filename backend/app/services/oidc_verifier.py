"""Generic OIDC identity-token verifier with JWKS fetch + cache.

Built for "Sign in with Apple" (alpha) and reused for Google Sign-In
when Android lands (per project plan — Android slice pulled forward
from MVP to right after Alpha closeout).

Every major OIDC provider follows the same shape: JWKS URI publishes
a list of public keys (RSA), each tagged with a `kid`; the identity
token's JWS header carries the matching `kid`. Verification:

  1. Decode the JWS header to get `kid` + `alg`.
  2. Fetch JWKS, find the JWK with matching `kid`.
  3. Verify signature with that key.
  4. Validate `iss`, `aud` (against the configured list), `exp`.

The cache is process-local with a TTL refresh. On a `kid` miss we
force-refresh the JWKS once before failing — handles Apple/Google
key rotation without operator intervention.

Threading: `OIDCVerifier.verify()` is sync (matches the rest of
`auth_service.py`). The HTTP fetch is synchronous via `httpx.Client`.
The cache uses a `threading.Lock` to keep refreshes from stampeding.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog
from jose import jwk, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

logger = structlog.get_logger(__name__)


class OIDCVerificationError(ValueError):
    """Raised when an identity token fails any verification step."""


@dataclass
class OIDCVerifier:
    """Single-provider OIDC verifier.

    Construct one instance per provider (Apple, Google, …) at module
    load and reuse it. The instance owns its own JWKS cache.
    """

    jwks_uri: str
    issuers: list[str]
    audiences: list[str]
    cache_ttl_s: int = 3600  # 1 hour; Apple/Google rotate keys roughly every few hours.
    http_timeout_s: float = 5.0

    _jwks: dict[str, dict[str, Any]] = field(default_factory=dict, init=False, repr=False)
    _fetched_at: float = field(default=0.0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # ── public API ─────────────────────────────────────────────────────

    def verify(self, identity_token: str) -> dict[str, Any]:
        """Return the validated claims dict, or raise OIDCVerificationError.

        Validates: signature against JWKS, `iss == self.issuer`,
        `aud ∈ self.audiences`, `exp` not expired.
        """
        if not identity_token or identity_token.count(".") != 2:
            raise OIDCVerificationError("malformed identity token")

        # Read header to find the `kid` we need.
        try:
            header = jwt.get_unverified_header(identity_token)
        except JWTError as e:
            raise OIDCVerificationError(f"undecodable header: {e}") from e

        kid = header.get("kid")
        alg = header.get("alg")
        if not kid or not alg:
            raise OIDCVerificationError("header missing kid/alg")

        jwk_dict = self._get_jwk_for_kid(kid)
        if jwk_dict is None:
            raise OIDCVerificationError(f"no matching JWK for kid={kid}")

        # python-jose accepts a JWK dict directly as the key. Audience
        # check is done manually below so we can support a *list* of
        # accepted audiences (e.g. iOS bundle ID + future Web Services
        # ID); jose's built-in audience param only accepts a string.
        try:
            claims = jwt.decode(
                identity_token,
                jwk.construct(jwk_dict).to_pem().decode("utf-8"),
                algorithms=[alg],
                options={
                    "verify_signature": True,
                    "verify_aud": False,  # we check membership below
                    "verify_iss": False,  # we check membership below (Google accepts two iss values)
                    "verify_exp": True,
                    "verify_iat": False,  # Apple sometimes returns iat slightly in the future of our clock
                    "verify_nbf": False,
                },
            )
        except ExpiredSignatureError as e:
            raise OIDCVerificationError("token expired") from e
        except JWTClaimsError as e:
            raise OIDCVerificationError(f"claim validation failed: {e}") from e
        except JWTError as e:
            raise OIDCVerificationError(f"signature verification failed: {e}") from e

        # Manual issuer membership check (Google emits both
        # "https://accounts.google.com" and "accounts.google.com").
        token_iss = claims.get("iss")
        if token_iss not in self.issuers:
            raise OIDCVerificationError(
                f"iss {token_iss!r} not in accepted issuers {self.issuers!r}"
            )

        # Manual audience membership check.
        token_aud = claims.get("aud")
        if token_aud is None:
            raise OIDCVerificationError("token missing 'aud' claim")
        # `aud` may be a string or a list per RFC 7519.
        token_auds = [token_aud] if isinstance(token_aud, str) else list(token_aud)
        if not any(a in self.audiences for a in token_auds):
            raise OIDCVerificationError(
                f"aud {token_auds!r} not in accepted audiences {self.audiences!r}"
            )

        return claims

    # ── JWKS cache ─────────────────────────────────────────────────────

    def _get_jwk_for_kid(self, kid: str) -> dict[str, Any] | None:
        """Return the JWK matching `kid`, refreshing the cache if needed.

        Stale cache → refresh. `kid` miss → force-refresh once (key
        rotation case). Still missing → return None.
        """
        with self._lock:
            now = time.time()
            stale = (now - self._fetched_at) > self.cache_ttl_s
            if stale or not self._jwks:
                self._refresh_locked()
            if kid in self._jwks:
                return self._jwks[kid]
            # Force one extra refresh on miss (handles rotation).
            self._refresh_locked()
            return self._jwks.get(kid)

    def _refresh_locked(self) -> None:
        """Fetch + parse JWKS. Caller must hold self._lock."""
        try:
            with httpx.Client(timeout=self.http_timeout_s) as client:
                resp = client.get(self.jwks_uri)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning(
                "oidc_jwks_fetch_failed",
                jwks_uri=self.jwks_uri,
                error=str(e),
            )
            # Don't blow up the cache on a transient fetch fail — keep
            # serving stale keys; verify() will report no-matching-kid
            # if the actual key we need isn't there.
            return

        keys = data.get("keys", [])
        self._jwks = {k["kid"]: k for k in keys if "kid" in k}
        self._fetched_at = time.time()
        logger.info(
            "oidc_jwks_refreshed",
            jwks_uri=self.jwks_uri,
            kid_count=len(self._jwks),
        )

    # ── test affordance ────────────────────────────────────────────────

    def _seed_jwks_for_test(self, jwks: dict[str, dict[str, Any]]) -> None:
        """Pre-populate the cache so tests don't need to hit the network.

        Test-only. Sets fetched_at to "now" so the TTL doesn't trigger a
        real fetch on the next verify() call.
        """
        with self._lock:
            self._jwks = jwks
            self._fetched_at = time.time()


# ── Singletons ────────────────────────────────────────────────────────


def build_apple_verifier(audiences: list[str]) -> OIDCVerifier:
    """Construct the Apple verifier with the configured audiences.

    Audience list is configurable so we can support the iOS bundle ID
    + a future Web Services ID (used by Apple's web sign-in flow, also
    needed for any Apple-via-Android path) without code changes.
    """
    return OIDCVerifier(
        jwks_uri="https://appleid.apple.com/auth/keys",
        issuers=["https://appleid.apple.com"],
        audiences=audiences,
    )


def build_google_verifier(audiences: list[str]) -> OIDCVerifier:
    """Construct the Google verifier — wired AT:R36 for Android Sign-In.

    Same shape as Apple. Audience list is the OAuth **Web client_id**
    (NOT the Android client_id) from GCP Console — Google stamps the
    Web client_id as `aud` into ID tokens returned to the Android
    client.

    Google issues tokens with `iss` equal to either
    `https://accounts.google.com` or `accounts.google.com`; both
    are valid per Google's OIDC docs, so we accept both.
    """
    return OIDCVerifier(
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        issuers=["https://accounts.google.com", "accounts.google.com"],
        audiences=audiences,
    )

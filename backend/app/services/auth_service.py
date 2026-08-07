"""Anonymous-first auth — Supabase-shaped, but works without Supabase.

Three flows for now:

  1. Anonymous session
     POST /v1/auth/anon  with an optional device_user_id from the mobile
     client (shared_preferences). Returns the same id every call, so
     the mandate/journal/portfolio that built up against it survives.

  2. Magic-link claim
     /v1/auth/magic_link/start  → stores a hashed 6-digit code,
     "sends" the email (in dev: returns the code in the response).
     /v1/auth/magic_link/verify → consumes the code, sets email on
     the user row, bumps claimed_at, returns a fresh session token.

  3. Apple Sign-In claim
     /v1/auth/apple — verifies the identity token against Apple's
     JWKS (`OIDCVerifier`), checks `iss`/`aud`/`exp`, reads the `sub`
     claim, marks the user row claimed with apple_id=sub. Phase 3
     verification landed in AT:R29; the earlier "trust the client"
     scaffold was the audit's must-fix-A4 finding.

`SessionToken` in scaffold mode is `scaffold:<user_id_hex>:<exp>:<ver>:<sig>`
(CR125) — a signed, expiring, per-user-revocable Bearer. When Supabase plugs
in, the real access JWT replaces it and `kind` becomes `supabase`; see the
swap-point note on `parse_scaffold_token()`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import AuthChallengeRow, SubscriptionEventRow, User, UserDeviceRow
from app.schemas.auth import AuthUser
from app.services.email_service import send_magic_link as _send_magic_link_email
from app.services.oidc_verifier import OIDCVerifier, build_apple_verifier, build_google_verifier


MAGIC_LINK_TTL_MIN = 15
APPLE_CHALLENGE_TTL_MIN = 60
# B-tier audit (AT:R37): wrong-code attempts allowed against a single
# magic-link challenge before it's force-consumed. The 6-digit code has
# 10^6 keyspace; 5 attempts caps the brute-force search at ~5e-6 per
# challenge — well below useful for an attacker. Real users mistype once
# or twice and remain inside the budget.
MAX_MAGIC_LINK_ATTEMPTS = 5


def _upsert_user_device(
    s,
    *,
    user_id: UUID,
    device_install_id: UUID,
    device_model: str | None,
    os_version: str | None,
    app_version: str | None,
) -> None:
    """BL2: register/touch a device row keyed by `device_install_id`. If the
    row exists, refresh its owner + context + last_seen_at. If not, create
    it. UNIQUE on device_install_id keeps this safe under races."""
    now = datetime.now(timezone.utc)
    existing = s.execute(
        select(UserDeviceRow).where(
            UserDeviceRow.device_install_id == device_install_id
        )
    ).scalar_one_or_none()
    if existing is None:
        s.add(UserDeviceRow(
            user_id=user_id,
            device_install_id=device_install_id,
            device_model=device_model,
            os_version=os_version,
            app_version=app_version,
            first_seen_at=now,
            last_seen_at=now,
        ))
    else:
        # Owner can change here on claim adoption — the next anon-bootstrap
        # from the device after adoption arrives with a different Bearer
        # (adopted user) and the row re-keys itself.
        existing.user_id = user_id
        existing.last_seen_at = now
        if device_model is not None:
            existing.device_model = device_model
        if os_version is not None:
            existing.os_version = os_version
        if app_version is not None:
            existing.app_version = app_version


def _log_adoption_event(s, *, from_user_id: UUID, to_user_id: UUID) -> None:
    """BL16 (AT:R38): write an audit row whenever account-linking Phase 1
    silently adopts an existing user row over a pre-claim anon row. The
    /v1/auth/merge endpoint reads this back to authorise the caller — only
    the user who appears as `to_value` against the supplied `from_value`
    can request a merge. Idempotent: if the exact pair was already logged
    this session, skip (prevents duplicate rows when the same device
    re-claims twice)."""
    existing = s.execute(
        select(SubscriptionEventRow.id).where(
            SubscriptionEventRow.event_type == "account_adoption",
            SubscriptionEventRow.from_value == str(from_user_id),
            SubscriptionEventRow.to_value == str(to_user_id),
        ).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return
    s.add(SubscriptionEventRow(
        user_id=to_user_id,
        event_type="account_adoption",
        from_value=str(from_user_id),
        to_value=str(to_user_id),
        source="app",
    ))


def _rekey_devices_to(s, *, from_user_id: UUID, to_user_id: UUID) -> int:
    """BL2: on claim adoption (account-linking Phase 1), move any user_devices
    rows owned by the pre-claim anon user to the adopting user so the
    adopting user's device list reflects all phones the human owns.

    Returns count of rows re-keyed.
    """
    if from_user_id == to_user_id:
        return 0
    from sqlalchemy import update as _update
    result = s.execute(
        _update(UserDeviceRow)
        .where(UserDeviceRow.user_id == from_user_id)
        .values(user_id=to_user_id)
    )
    return int(result.rowcount or 0)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _row_to_user(row: User) -> AuthUser:
    return AuthUser(
        id=row.id,
        email=row.email,
        apple_id=row.apple_id,
        google_id=row.google_id,
        display_name=row.display_name,
        is_anonymous=row.is_anonymous,
        claimed_at=row.claimed_at,
        created_at=row.created_at,
    )


class ParsedToken(NamedTuple):
    """Result of a successful `parse_scaffold_token()`.

    `token_version` is `None` only for the local-only legacy unsigned format
    (no version field exists there) — callers that enforce revocation treat
    `None` as "skip the version check", matching that format's existing
    local-only trust level. Every signed token carries a real int.
    """

    user_id: UUID
    token_version: int | None


def _scaffold_sig(hex_id: str, exp: int, token_version: int) -> str:
    # HMAC over the joined hex|exp|ver so none of the three fields is
    # malleable — signing only the hex would let an attacker rewrite `exp`
    # or `ver` freely and replay a revoked or "expired" token forever.
    payload = f"{hex_id}|{exp}|{token_version}"
    return _hmac.new(
        settings.secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        "sha256",
    ).hexdigest()


def _scaffold_token(user_id: UUID, token_version: int, ttl_days: int | None = None) -> str:
    """Issue a scaffold Bearer token: `scaffold:<hex>:<exp>:<ver>:<sig>` (CR125).

    `exp` is a Unix timestamp (seconds); `ver` must match the user's current
    `token_version` at parse time. HMAC over all three prevents offline
    forgery of any field. The Beta swap point is a one-line change in
    `parse_scaffold_token()` (verify a Supabase JWT instead).

    The legacy unsigned format `scaffold:<hex>` is still parseable, but
    only when `env == "local"` — see `parse_scaffold_token()`. Adversarial
    audit (2026-05-18) tightened this from "local|dev" because melehost
    runs as `env=dev` and its tunnel is public. The old 3-part signed
    format (`scaffold:<hex>:<sig>`, pre-CR125, no exp/version) is rejected
    everywhere — CR040 degrade loudly, not a silent downgrade.
    """
    ttl = settings.auth_token_ttl_days if ttl_days is None else ttl_days
    exp = int((datetime.now(timezone.utc) + timedelta(days=ttl)).timestamp())
    hex_id = user_id.hex
    sig = _scaffold_sig(hex_id, exp, token_version)
    return f"scaffold:{hex_id}:{exp}:{token_version}:{sig}"


def parse_scaffold_token(token: str) -> ParsedToken | None:
    """Parse and verify a scaffold Bearer token. Returns `ParsedToken` or None.

    Verifies signature and `exp` only — NOT `token_version` against the DB
    (this function has no session). Version enforcement against the live
    user row is `api/dependencies.py::get_current_user`'s job; that keeps
    this a pure, session-free parse, and the Supabase swap a one-function
    change (module docstring).
    """
    if not token.startswith("scaffold:"):
        return None
    rest = token[len("scaffold:"):]
    parts = rest.split(":")
    if len(parts) == 4:
        # Current signed format: scaffold:<hex>:<exp>:<ver>:<sig>
        hex_id, exp_str, ver_str, claimed_sig = parts
        try:
            user_id = UUID(hex_id)
            exp = int(exp_str)
            token_version = int(ver_str)
        except ValueError:
            return None
        expected_sig = _scaffold_sig(hex_id, exp, token_version)
        if not _hmac.compare_digest(claimed_sig, expected_sig):
            return None
        if exp < int(datetime.now(timezone.utc).timestamp()):
            return None
        return ParsedToken(user_id=user_id, token_version=token_version)
    if len(parts) == 1 and settings.env == "local":
        # Legacy unsigned format — accepted only on the developer's local
        # machine. Adversarial audit (2026-05-18) closed dev-env acceptance:
        # melehost is reachable via the public Cloudflare Tunnel. No version
        # field exists in this format, so version enforcement is skipped
        # (`token_version=None`) — consistent with the format's existing
        # local-only trust level.
        try:
            return ParsedToken(user_id=UUID(parts[0]), token_version=None)
        except ValueError:
            return None
    # Anything else — including the pre-CR125 3-part signed format
    # (scaffold:<hex>:<sig>, no exp/version) — is rejected outright. CR040
    # degrade loudly: a stale token 401s, it does not quietly pass.
    return None


def parse_scaffold_token_user_id(token: str) -> UUID | None:
    """Thin wrapper for best-effort attribution callers (audit middleware,
    bug-report submission) that only ever needed the user_id, never full
    auth enforcement. Does NOT check `token_version` — those call sites
    don't authenticate, they attribute, and have no DB session to check
    against. Still honours signature + `exp`."""
    parsed = parse_scaffold_token(token)
    return parsed.user_id if parsed is not None else None


def _b64url_decode(seg: str) -> bytes:
    padding = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + padding)


# `_decode_apple_sub` previously read the JWT body without signature
# verification — the must-fix-A4 finding from the 2026-05-18 audit.
# Replaced in AT:R29 by AuthService._apple_verifier (OIDCVerifier with
# real JWKS fetch). Helper deleted; no callers remain.


class AuthService:
    """All auth flows. Sync API, opens its own DB session per call."""

    def __init__(
        self,
        apple_verifier: OIDCVerifier | None = None,
        google_verifier: OIDCVerifier | None = None,
    ) -> None:
        init_schema()
        # Apple OIDC verifier (singleton-shaped — one instance owns the
        # JWKS cache). Injectable so tests can pass a fake that trusts
        # body claims without hitting Apple's network.
        self._apple_verifier: OIDCVerifier = (
            apple_verifier
            if apple_verifier is not None
            else build_apple_verifier(settings.apple_audiences)
        )
        # Google OIDC verifier (AT:R36, D-057). Wired the same way as
        # Apple. Audiences = OAuth Web client_id(s) from GCP Console.
        # When google_audiences is empty the verifier still constructs
        # — it just rejects every real token at the audience check,
        # which is the right behavior in dev before GCP is set up.
        self._google_verifier: OIDCVerifier = (
            google_verifier
            if google_verifier is not None
            else build_google_verifier(settings.google_audiences)
        )

    # ── Anonymous bootstrap ────────────────────────────────────────────

    def ensure_anonymous(
        self,
        *,
        device_user_id: UUID | None,
        authenticated_user_id: UUID | None = None,
        locale: str = "en",
        timezone_str: str = "UTC",
        device_model: str | None = None,
        os_version: str | None = None,
        app_version: str | None = None,
        device_install_id: UUID | None = None,
    ) -> tuple[AuthUser, str, bool]:
        """Return (user, token, is_new).

        `authenticated_user_id` is the user_id parsed from the caller's
        Bearer token (if any). Adversarial audit (2026-05-18) finding A2:
        without this guard the endpoint is a token-minting oracle — anyone
        who knows a victim's UUID could POST {device_user_id: <victim>}
        and receive a valid signed token for them.

        Policy:
          - No `device_user_id` supplied → mint a fresh user (cold start).
          - `device_user_id` matches `authenticated_user_id` → legitimate
            re-bootstrap from the rightful owner. Reuse the row.
          - `device_user_id` supplied but DOESN'T match the bearer (or no
            bearer at all) → ignore the supplied id, mint a fresh user.
            The caller acts as if they were a brand-new install.
        """
        with get_session() as s:
            row: User | None = None
            # Only honour device_user_id when the caller has proved possession
            # via a Bearer token for that same user.
            trust_device_id = (
                device_user_id is not None
                and authenticated_user_id is not None
                and device_user_id == authenticated_user_id
            )
            if trust_device_id:
                row = s.execute(
                    select(User).where(User.device_user_id == device_user_id)
                ).scalar_one_or_none()
                if row is None:
                    row = s.execute(
                        select(User).where(User.id == device_user_id)
                    ).scalar_one_or_none()
            is_new = row is None
            if row is None:
                user_id = uuid4()  # always mint fresh when device_id untrusted
                row = User(
                    id=user_id,
                    device_user_id=user_id,
                    locale=locale,
                    timezone=timezone_str,
                    is_anonymous=True,
                    anonymous_session_started_at=datetime.now(timezone.utc),
                    device_model=device_model,
                    os_version=os_version,
                    last_app_version=app_version,
                )
                s.add(row)
                s.flush()
            else:
                # BL1 (AT:R33): refresh device + build context on every
                # bootstrap of an existing row. last_app_version is the most
                # useful signal — answers "what build is this tester on?"
                # without a bug-report round-trip.
                if device_model is not None:
                    row.device_model = device_model
                if os_version is not None:
                    row.os_version = os_version
                if app_version is not None:
                    row.last_app_version = app_version

            # BL2 (AT:R33): upsert a user_devices row keyed by install_id.
            # Lets a single human's two phones each carry their own row.
            if device_install_id is not None:
                _upsert_user_device(
                    s,
                    user_id=row.id,
                    device_install_id=device_install_id,
                    device_model=device_model,
                    os_version=os_version,
                    app_version=app_version,
                )

            return _row_to_user(row), _scaffold_token(row.id, row.token_version), is_new

    # ── Magic-link ─────────────────────────────────────────────────────

    def start_magic_link(self, *, email: str, user_id: UUID | None) -> str:
        """Returns the 6-digit code; production never returns this in API."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        with get_session() as s:
            s.add(AuthChallengeRow(
                kind="magic_link",
                target=email.lower().strip(),
                code_hash=_hash_code(code),
                user_id=user_id,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_TTL_MIN),
            ))
        logger.info("magic_link_started", email=email, user_id=str(user_id))
        _send_magic_link_email(email, code)
        return code

    def verify_magic_link(
        self,
        *,
        email: str,
        code: str,
        user_id: UUID | None,
        challenge_owner_id: UUID | None = None,
    ) -> tuple[AuthUser, str, UUID | None] | None:
        """Returns (user, token, adopted_from_user_id) on success.
        `adopted_from_user_id` is set when account-linking Phase 1 silently
        adopted an existing email-row over the caller's anon — i.e. the
        returned `user.id` differs from the caller's pre-claim user_id.

        DEF180 (security review H5): `challenge_owner_id`, when supplied
        (the route always supplies the caller's Bearer-authenticated
        user_id), scopes the active-challenge lookup to challenges THAT
        user themselves started via `/magic_link/start`. Without this, the
        lookup matched on `target` email alone, so any authenticated
        caller could brute-force-guess the code on a challenge some OTHER
        user started for their own email-claim flow. None (only used by
        direct service-layer callers/tests, never the route) preserves
        the old email-only lookup.
        """
        target = email.lower().strip()
        with get_session() as s:
            # Find the most recent active (unconsumed + unexpired) challenge
            # for this target regardless of code, so a wrong-code attempt can
            # bump its counter. The hash comparison happens after.
            conditions = [
                AuthChallengeRow.kind == "magic_link",
                AuthChallengeRow.target == target,
                AuthChallengeRow.consumed_at.is_(None),
                AuthChallengeRow.expires_at > datetime.now(timezone.utc),
            ]
            if challenge_owner_id is not None:
                conditions.append(AuthChallengeRow.user_id == challenge_owner_id)
            active = s.execute(
                select(AuthChallengeRow).where(*conditions)
                .order_by(AuthChallengeRow.created_at.desc()).limit(1)
            ).scalar_one_or_none()
            if active is None:
                return None
            if active.code_hash != _hash_code(code):
                # Wrong code: bump counter, lock out at threshold by marking
                # consumed (the next /magic_link/start mints a fresh row with
                # attempts=0, so a real user always has a recovery path).
                active.attempts += 1
                if active.attempts >= MAX_MAGIC_LINK_ATTEMPTS:
                    active.consumed_at = datetime.now(timezone.utc)
                    logger.warning(
                        "magic_link_locked_out",
                        target=target,
                        attempts=active.attempts,
                    )
                return None
            active.consumed_at = datetime.now(timezone.utc)

            # Claim or create the user.
            pre_claim_uid = user_id or active.user_id
            user = self._claim_or_create(
                s, user_id=pre_claim_uid, email=target,
            )
            adopted_from = (
                pre_claim_uid
                if pre_claim_uid is not None and user.id != pre_claim_uid
                else None
            )
            if adopted_from is not None:
                _log_adoption_event(
                    s, from_user_id=adopted_from, to_user_id=user.id,
                )
            return _row_to_user(user), _scaffold_token(user.id, user.token_version), adopted_from

    # ── Apple Sign-In ──────────────────────────────────────────────────

    def sign_in_with_apple(
        self,
        *,
        identity_token: str,
        user_id: UUID | None,
        full_name: str | None = None,
    ) -> tuple[AuthUser, str, UUID | None]:
        # Full verification: signature against Apple's JWKS, iss, aud,
        # exp. Raises OIDCVerificationError (subclass of ValueError) on
        # any failure — the route layer translates that to HTTP 400.
        claims = self._apple_verifier.verify(identity_token)
        apple_sub = claims.get("sub")
        if not apple_sub:
            raise ValueError("apple identity_token missing 'sub' claim")
        apple_sub = str(apple_sub)
        # Apple's first-auth-only contract: `email` (real or
        # `@privaterelay.appleid.com` relay) ships only on the very first
        # authorization per Apple-ID/app pair. Subsequent sign-ins omit
        # the claim. So persist on first sight; never overwrite a value
        # already in the row.
        apple_email = claims.get("email")
        apple_email = str(apple_email) if apple_email else None
        # `full_name` is also first-auth-only on the iOS SDK side —
        # Apple only returns it on the initial SignInWithApple consent
        # screen. Persisted into users.display_name on first sight,
        # never overwritten (same rule as email).
        full_name = (full_name or "").strip() or None
        with get_session() as s:
            # Prefer matching an existing apple_id row.
            row = s.execute(
                select(User).where(User.apple_id == apple_sub)
            ).scalar_one_or_none()
            # Email fallback (AT:R32, account-linking Phase 1): if no
            # apple_id match but Apple ships the email claim and an existing
            # user owns that email, attach apple_sub to that row instead of
            # creating a parallel user. Covers "magic-link first, then Apple
            # later with the same email."
            if row is None and apple_email:
                row = s.execute(
                    select(User).where(User.email == apple_email)
                ).scalar_one_or_none()
                if row is not None:
                    row.apple_id = apple_sub
            # BL2 (AT:R33): when adoption fires (existing apple_id OR
            # existing-email row), move the pre-claim anon's devices to the
            # adopted user so both phones surface under one user.
            adopted_from: UUID | None = None
            if row is not None and user_id is not None and row.id != user_id:
                _rekey_devices_to(s, from_user_id=user_id, to_user_id=row.id)
                adopted_from = user_id
            if row is None and user_id is not None:
                row = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if row is None:
                now = datetime.now(timezone.utc)
                row = User(
                    id=user_id or uuid4(),
                    device_user_id=user_id,
                    apple_id=apple_sub,
                    email=apple_email,
                    display_name=full_name,
                    is_anonymous=False,
                    claimed_at=now,
                    trial_started_at=now,
                    trial_expires_at=now + timedelta(days=7),
                )
                s.add(row)
                s.flush()
            else:
                row.apple_id = apple_sub
                # Never overwrite a populated email — protects against a
                # user who first claimed via magic-link (real email) and
                # later linked Apple (might be the relay address).
                if apple_email and not row.email:
                    row.email = apple_email
                # Same don't-overwrite rule for display_name.
                if full_name and not row.display_name:
                    row.display_name = full_name
                if row.is_anonymous:
                    now = datetime.now(timezone.utc)
                    row.is_anonymous = False
                    row.claimed_at = now
                    if row.trial_started_at is None:
                        row.trial_started_at = now
                        row.trial_expires_at = now + timedelta(days=7)
            if adopted_from is not None:
                _log_adoption_event(
                    s, from_user_id=adopted_from, to_user_id=row.id,
                )
            return _row_to_user(row), _scaffold_token(row.id, row.token_version), adopted_from

    # ── Google Sign-In ─────────────────────────────────────────────────

    def sign_in_with_google(
        self,
        *,
        identity_token: str,
        user_id: UUID | None,
    ) -> tuple[AuthUser, str, UUID | None]:
        """Google Sign-In claim (Android only at alpha; D-057).

        Mirrors `sign_in_with_apple`. Differences from Apple:
          - Google ships `email` + `name` in every ID token (not first-only),
            so no `full_name` parameter is needed. We still apply the
            don't-overwrite rule to keep magic-link / Apple identities
            stable when a user signs in via multiple providers.
          - `email` is reliably present and verified — Google's
            `email_verified` claim is checked.
          - Minimum-data policy (D-057 / AT:R29): persist only `sub`,
            `email`, `name`. Other claims (`picture`, `locale`, `hd`,
            `given_name`, `family_name`) are dropped on the floor.
        """
        claims = self._google_verifier.verify(identity_token)
        google_sub = claims.get("sub")
        if not google_sub:
            raise ValueError("google identity_token missing 'sub' claim")
        google_sub = str(google_sub)
        google_email = claims.get("email")
        google_email = str(google_email).lower() if google_email else None
        # Reject unverified emails — protects against a malicious user who
        # creates a Google account with someone else's email but never
        # confirms it. Google's own libraries enforce this.
        if google_email and not claims.get("email_verified", False):
            google_email = None
        full_name = claims.get("name")
        full_name = str(full_name).strip() if full_name else None
        if not full_name:
            full_name = None
        with get_session() as s:
            # Prefer matching an existing google_id row.
            row = s.execute(
                select(User).where(User.google_id == google_sub)
            ).scalar_one_or_none()
            # Email fallback (account-linking Phase 1): existing user owns
            # this email (via magic-link or Apple-with-same-email) — attach
            # google_sub to that row instead of forking.
            if row is None and google_email:
                row = s.execute(
                    select(User).where(User.email == google_email)
                ).scalar_one_or_none()
                if row is not None:
                    row.google_id = google_sub
            # BL2 device re-keying on adoption (mirrors Apple flow).
            adopted_from: UUID | None = None
            if row is not None and user_id is not None and row.id != user_id:
                _rekey_devices_to(s, from_user_id=user_id, to_user_id=row.id)
                adopted_from = user_id
            if row is None and user_id is not None:
                row = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if row is None:
                now = datetime.now(timezone.utc)
                row = User(
                    id=user_id or uuid4(),
                    device_user_id=user_id,
                    google_id=google_sub,
                    email=google_email,
                    display_name=full_name,
                    is_anonymous=False,
                    claimed_at=now,
                    trial_started_at=now,
                    trial_expires_at=now + timedelta(days=7),
                )
                s.add(row)
                s.flush()
            else:
                row.google_id = google_sub
                if google_email and not row.email:
                    row.email = google_email
                if full_name and not row.display_name:
                    row.display_name = full_name
                if row.is_anonymous:
                    now = datetime.now(timezone.utc)
                    row.is_anonymous = False
                    row.claimed_at = now
                    if row.trial_started_at is None:
                        row.trial_started_at = now
                        row.trial_expires_at = now + timedelta(days=7)
            if adopted_from is not None:
                _log_adoption_event(
                    s, from_user_id=adopted_from, to_user_id=row.id,
                )
            return _row_to_user(row), _scaffold_token(row.id, row.token_version), adopted_from

    # ── Helpers ────────────────────────────────────────────────────────

    def _claim_or_create(
        self,
        s,
        *,
        user_id: UUID | None,
        email: str,
    ) -> User:
        # Identity-first lookup (AT:R32, account-linking Phase 1). An existing
        # row matching the verified email always wins, so the same human
        # signing in on a new device adopts their existing user instead of
        # creating a parallel row. The fresh anon row referenced by user_id
        # is left orphaned — pre-claim anon state is ephemeral.
        row: User | None = None
        if email:
            row = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
        # BL2 (AT:R33): if email-lookup succeeded and the pre-claim anon row
        # is being orphaned, move its devices to the adopted user so the
        # new phone shows up in the existing user's device list.
        if row is not None and user_id is not None and row.id != user_id:
            _rekey_devices_to(s, from_user_id=user_id, to_user_id=row.id)
        if row is None and user_id is not None:
            row = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if row is None:
            now = datetime.now(timezone.utc)
            row = User(
                id=user_id or uuid4(),
                device_user_id=user_id,
                email=email,
                is_anonymous=False,
                claimed_at=now,
                trial_started_at=now,
                trial_expires_at=now + timedelta(days=7),
            )
            s.add(row)
            s.flush()
            return row
        # Only set email on rows that don't have one yet (the user_id-matched
        # anon path). An email-matched row already has the correct email and
        # we deliberately don't reassign — re-magic-link with a different
        # email cannot mutate an existing user's identity here.
        if not row.email:
            row.email = email
        if row.is_anonymous:
            now = datetime.now(timezone.utc)
            row.is_anonymous = False
            row.claimed_at = now
            if row.trial_started_at is None:
                row.trial_started_at = now
                row.trial_expires_at = now + timedelta(days=7)
        return row

    # Test helper
    def clear(self) -> None:
        from sqlalchemy import delete as _delete
        with get_session() as s:
            s.execute(_delete(AuthChallengeRow))
            s.execute(_delete(User))


_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _service
    if _service is None:
        _service = AuthService()
    return _service


def _is_dev_env() -> bool:
    """Returns True only on a developer's local machine.

    Controls debug affordances that must never leak via a public tunnel:
    magic-link code returned in API response, Apple JWT signature skipped.
    Adversarial audit (2026-05-18) tightened this from `local|dev` to `local`
    after melehost was found leaking debug codes via the public hostname.
    """
    return settings.env == "local"

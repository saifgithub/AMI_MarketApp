"""At-rest symmetric encryption for sensitive user secrets (DEF044, DEF182).

Motivation: Alpaca brokerage credentials (`users.alpaca_access_token` /
`alpaca_refresh_token`) were persisted in cleartext, so a DB dump or backup
leaked every user's key + secret. This module encrypts them with Fernet
(AES-128-CBC + HMAC-SHA256), via the `cryptography` lib already pulled in by
`python-jose[cryptography]` — no new top-level dependency.

DEF182 — WHAT CHANGED AND WHY
-----------------------------
As first shipped (DEF044) this module had two properties that a security review
(CR123 N1) graded as a CR040 "degrade loudly" violation:

1. **One secret did two jobs.** With `ALPACA_ENCRYPTION_KEY` empty — the
   default, and the state Alpha actually ran in — the Fernet key was derived
   from `SECRET_KEY`, which also signs bearer tokens. No separation, no
   rotation path, and a trap laid for every future remediation: rotating
   `SECRET_KEY` (H2/DEF185, H7/DEF178, M15 all call for it) would have silently
   orphaned every Alpaca ciphertext row.

2. **The crypto failed OPEN.** `decrypt_secret` returned the *raw stored value*
   when the key was missing or the token invalid. So after such a rotation the
   Alpaca client would have sent `gAAAAA…` — the ciphertext itself — as an API
   key, and nothing would have said so. Silent plus app-breaking is exactly the
   question CR040 asks you to ask first: if this fires constantly and silently,
   what does the user end up believing?

Both are closed here. The key is now dedicated and versioned, and every failure
path is loud.

KEY VERSIONS
------------
The stored marker names the key that encrypted the value, so a reader never has
to guess:

  ``enc::v1::``  legacy — key derived from ``SECRET_KEY``. Read-only now;
                 nothing writes v1 outside a local dev box with no dedicated
                 key configured.
  ``enc::v2::``  current — key derived from the dedicated
                 ``ALPACA_ENCRYPTION_KEY``, independent of ``SECRET_KEY``.

Because v2 is keyed independently, **rotating `SECRET_KEY` no longer touches
Alpaca ciphertext at all.** That was the trap; the marker is what disarms it.

That sentence is a promise about the data, so something has to enforce it.
Round 1 of this fix only removed the *automatic* way it could become false (an
empty key falling back to `SECRET_KEY`); an independent audit pointed out that
an operator setting the two to the same value by hand produced a `v2` row the
`SECRET_KEY`-derived key opened, with nothing to notice. `_reuses_secret_key`
is that check — a dedicated key equal to `SECRET_KEY` is refused at the write
site and ignored at the read site, so the marker cannot outlive the property
it stands for.

ROTATING ``ALPACA_ENCRYPTION_KEY`` (dual-key rollover)
------------------------------------------------------
1. Put the current value in ``ALPACA_ENCRYPTION_KEY_PREVIOUS`` and the new one
   in ``ALPACA_ENCRYPTION_KEY`` in ``infra/alpha.env``, then promote. Reads try
   the current key first and fall back to the previous one, so no row breaks at
   the instant of the swap.
2. Every write from that moment re-encrypts under the new key. Force the
   re-write for rows that are only ever read by re-saving them.
3. Once no row decrypts under the previous key, clear
   ``ALPACA_ENCRYPTION_KEY_PREVIOUS`` and promote again.

Skipping step 1 does not corrupt anything — it makes every affected row read as
**unavailable**, loudly, which is the point.

Doing step 3 to the wrong variable — clearing ``ALPACA_ENCRYPTION_KEY`` and
leaving ``_PREVIOUS`` populated — used to leave writes running under the key the
rollover exists to retire, stamped ``v2``, with no warning; the next promotion
that finished the rollover would orphan exactly the rows written in between.
``encrypt_secret`` now refuses that combination outright.

FAILURE BEHAVIOUR
-----------------
``encrypt_secret`` raises rather than storing a secret in the clear. Outside
``env=local`` it also raises rather than silently falling back to the
``SECRET_KEY``-derived key, because that fallback is the thing DEF182 is about.

``decrypt_secret`` raises ``SecretDecryptionError`` rather than returning
ciphertext dressed as plaintext. **It is the ORM layer, not this module, that
decides how loud is too loud**: `EncryptedString.process_result_value` catches
it, logs an ERROR and yields ``None``. That is deliberate — these columns are
read by `get_current_user` on *every* authenticated request, so raising all the
way out would turn one undecryptable credential into a total account lockout.
``None`` means "not linked", which every call site already handles correctly
(`_require_linked` → 409 `alpaca_not_linked`; the agent/room prompt overlays
simply omit the Alpaca block). Loud in the logs, safe in the product, and never
a ciphertext masquerading as an API key.

Legacy *cleartext* rows (written before DEF044, no marker at all) still pass
through unchanged, because the value is genuinely the secret and refusing it
would break a working link for no gain. Outside `env=local` that path logs a
warning: it means an unencrypted credential is sitting in the database.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.logging import logger

#: Legacy: key derived from ``SECRET_KEY``. Read-only outside local dev.
_PREFIX_V1 = "enc::v1::"
#: Current: key derived from the dedicated ``ALPACA_ENCRYPTION_KEY``.
_PREFIX_V2 = "enc::v2::"

#: What a new write carries when a dedicated key is configured.
_ENC_PREFIX = _PREFIX_V2

_PREFIXES = (_PREFIX_V1, _PREFIX_V2)


class SecretCryptoError(RuntimeError):
    """Base for the two conditions that used to be silent."""


class SecretEncryptionUnavailable(SecretCryptoError):
    """No key material to encrypt with. Storing the plaintext instead is not an
    option — that is the leak DEF044 exists to close."""


class SecretDecryptionError(SecretCryptoError):
    """Stored ciphertext could not be decrypted with any configured key.
    Raised instead of returning the ciphertext, which is what DEF182 fixed."""


def _strict() -> bool:
    """True everywhere except a local dev box. `local` keeps the permissive
    behaviour so a checkout with no env file still runs."""
    return settings.env != "local"


def _derive(raw: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()))


def _reuses_secret_key(raw: str) -> bool:
    """True when a configured "dedicated" key is just ``SECRET_KEY`` again.

    DEF182 round 2, MAJOR-1. Round 1 closed the path where an *empty*
    ``ALPACA_ENCRYPTION_KEY`` fell back to ``SECRET_KEY``. It left open the
    path where the two are set to the same value **by configuration** — a
    copy-paste into ``infra/alpha.env``, a rushed rotation. That state is
    worse than the bug it replaced, not equal to it: the row is stamped
    ``enc::v2::``, whose entire documented meaning is "rotating SECRET_KEY no
    longer touches this ciphertext", and the ``SECRET_KEY``-derived legacy key
    opens it anyway. The old state was at least honestly labelled ``v1``.

    Nothing downstream can notice — the marker is the only signal there is —
    so the value is refused here, at both the read and the write site.
    """
    return bool(raw) and bool(settings.secret_key) and raw == settings.secret_key


def _dedicated_keys() -> list[Fernet]:
    """Keys that may OPEN a ``v2`` row: current first, then the rollover key.

    A configured value that only repeats ``SECRET_KEY`` is dropped rather than
    used. Dropping it makes the affected rows read as unavailable, loudly
    (``SecretDecryptionError`` -> ``None`` -> 409 ``alpaca_not_linked``), which
    is the CR040 answer: the alternative is a row that opens perfectly well
    while its marker asserts an independence it does not have.
    """
    keys = []
    for name, raw in (
        ("ALPACA_ENCRYPTION_KEY", settings.alpaca_encryption_key),
        ("ALPACA_ENCRYPTION_KEY_PREVIOUS", settings.alpaca_encryption_key_previous),
    ):
        if not raw:
            continue
        if _reuses_secret_key(raw):
            logger.error(
                "secret_crypto_key_reuses_secret_key",
                setting=name,
                detail="configured to the same value as SECRET_KEY, so it is "
                       "not a dedicated key and is being ignored (DEF182)",
            )
            continue
        keys.append(_derive(raw))
    return keys


def _legacy_key() -> Fernet | None:
    """The ``SECRET_KEY``-derived key that wrote every ``enc::v1::`` row."""
    return _derive(settings.secret_key) if settings.secret_key else None


def encrypt_secret(plaintext: str | None) -> str | None:
    """Encrypt a secret for storage. None → None.

    Raises rather than storing plaintext: a silent passthrough here is the
    original DEF044 leak reintroduced by a missing env var (P1).
    """
    if plaintext is None:
        return None

    current = settings.alpaca_encryption_key

    if _reuses_secret_key(current):
        raise SecretEncryptionUnavailable(
            "ALPACA_ENCRYPTION_KEY is configured to the same value as "
            "SECRET_KEY, so it is not a dedicated key. The row this would "
            "write is stamped enc::v2::, which this module defines as "
            "'rotating SECRET_KEY no longer touches this ciphertext' — and the "
            "SECRET_KEY-derived key would open it. Refusing to write a marker "
            "that asserts a property the data does not have (DEF182). Give "
            "ALPACA_ENCRYPTION_KEY its own value (openssl rand -hex 32) in "
            "infra/alpha.env and promote."
        )

    if current:
        return _PREFIX_V2 + _derive(current).encrypt(plaintext.encode()).decode()

    if settings.alpaca_encryption_key_previous:
        raise SecretEncryptionUnavailable(
            "ALPACA_ENCRYPTION_KEY is empty while ALPACA_ENCRYPTION_KEY_PREVIOUS "
            "is set. The previous key exists to READ rows mid-rollover; writing "
            "new ciphertext under it would stamp fresh rows with the very key "
            "step 3 of the rollover then clears, orphaning them (DEF182). Put "
            "the current key in ALPACA_ENCRYPTION_KEY."
        )

    if _strict():
        raise SecretEncryptionUnavailable(
            "ALPACA_ENCRYPTION_KEY is not set, so there is no key dedicated to "
            f"this data in env={settings.env!r}. Refusing to store a brokerage "
            "credential in the clear, and refusing to reuse SECRET_KEY for it "
            "(DEF182). Set ALPACA_ENCRYPTION_KEY in infra/alpha.env — it is "
            "already forwarded in docker-compose.yml — and promote."
        )

    legacy = _legacy_key()
    if legacy is None:
        raise SecretEncryptionUnavailable(
            "no key material at all: both ALPACA_ENCRYPTION_KEY and SECRET_KEY "
            "are empty. Refusing to store a brokerage credential in the clear."
        )
    logger.warning(
        "secret_crypto_legacy_key_write",
        detail="env=local with no ALPACA_ENCRYPTION_KEY — writing enc::v1:: "
               "under the SECRET_KEY-derived key. Never happens off a dev box.",
    )
    return _PREFIX_V1 + legacy.encrypt(plaintext.encode()).decode()


def decrypt_secret(stored: str | None) -> str | None:
    """Decrypt a stored secret. None → None; legacy cleartext passes through.

    Raises `SecretDecryptionError` when a value IS ciphertext but no configured
    key opens it. Callers that must not fail hard catch it — see
    `EncryptedString.process_result_value`.
    """
    if stored is None:
        return None

    if not stored.startswith(_PREFIXES):
        # Pre-DEF044 cleartext. The value is the real secret, so returning it
        # is correct; that it exists at all is worth saying out loud in prod.
        if _strict():
            logger.warning(
                "secret_crypto_plaintext_row",
                detail="an unencrypted credential is stored in the database",
            )
        return stored

    if stored.startswith(_PREFIX_V2):
        body, candidates, which = stored[len(_PREFIX_V2):], _dedicated_keys(), "v2"
    else:
        body, legacy, which = stored[len(_PREFIX_V1):], _legacy_key(), "v1"
        candidates = [legacy] if legacy else []

    for key in candidates:
        try:
            return key.decrypt(body.encode()).decode()
        except InvalidToken:
            continue

    logger.error(
        "secret_crypto_undecryptable",
        version=which,
        keys_tried=len(candidates),
        rollover_key_configured=bool(settings.alpaca_encryption_key_previous),
        detail="stored ciphertext opened by no configured key",
    )
    raise SecretDecryptionError(
        f"a stored {which} secret could not be decrypted with any configured key "
        f"({len(candidates)} tried). The key changed without a dual-key rollover, "
        "or the ciphertext is corrupt. Returning the ciphertext to the caller is "
        "how it ends up being sent to Alpaca as an API key, so this raises "
        "instead (DEF182). To recover: put the previous key in "
        "ALPACA_ENCRYPTION_KEY_PREVIOUS and promote."
    )


def is_encrypted(stored: str | None) -> bool:
    """True if the value is ciphertext this module produced, any version."""
    return stored is not None and stored.startswith(_PREFIXES)

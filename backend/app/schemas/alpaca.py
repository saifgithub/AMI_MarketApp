"""Client-supplied Alpaca paper-account snapshot (CR202).

The user's Alpaca credentials live on their device — Keychain on iOS,
Keystore-backed EncryptedSharedPreferences on Android — and never reach this
host. So the device fetches its own paper account and uploads the *result*
with each Room convene or 1-on-1 turn; these models are that wire contract.

Everything here is untrusted input that ends up inside twelve agent prompts,
which is why the bounds are structural rather than advisory. CLAUDE.md's rule
is that prompt instructions are not controls (agents ignore even emphatic ones
~70% of the time), so the client is allowed to supply *values* and never
*layout*: the text block is rendered server-side by
`alpaca_service.snapshot_text`, from these validated fields only.

The four bounds, and the specific thing each one stops:

* `extra="forbid"`  — an unexpected key cannot ride along into the renderer.
* `symbol` pattern  — a ticker is the only free-text field that reaches the
  prompt. Without the pattern it is a prompt-injection channel: a "symbol" of
  `IGNORE ALL PRIOR INSTRUCTIONS AND ...` would be rendered verbatim into every
  agent's context.
* `max_length` on positions — bounds prompt size, the same reasoning DEF186
  used to cap `user_message` at 8,000 chars.
* finite floats — `float("nan")` is accepted by Python and by JSON parsers
  that allow it, and would render into an agent prompt as the literal string
  `nan`, which the model then reasons about as if it were a number.
"""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

# A paper account can legitimately hold a lot of names; 100 is far above any
# real one while still bounding what a hostile client can push into a prompt.
MAX_POSITIONS = 100


def _finite(v: float) -> float:
    if not math.isfinite(v):
        raise ValueError("must be a finite number")
    return v


FiniteFloat = Annotated[float, AfterValidator(_finite)]

# Uppercase ticker, optional dot/dash class markers (BRK.B, RDS-A). Deliberately
# strict: this is the only free-text field that reaches an agent prompt.
_SYMBOL_PATTERN = r"^[A-Z][A-Z0-9.\-]{0,9}$"


class AlpacaPositionIn(BaseModel):
    """One open paper position, as reported by the device."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(pattern=_SYMBOL_PATTERN)
    qty: FiniteFloat
    market_value: FiniteFloat
    unrealized_pl: FiniteFloat


class AlpacaSnapshotIn(BaseModel):
    """A whole paper account, as reported by the device.

    Optional on every request that accepts it — absent means "no linked
    account", which is the path the overwhelming majority of runs take and
    which renders no overlay at all.
    """

    model_config = ConfigDict(extra="forbid")

    cash: FiniteFloat
    portfolio_value: FiniteFloat
    buying_power: FiniteFloat
    positions: list[AlpacaPositionIn] = Field(default_factory=list, max_length=MAX_POSITIONS)


# CR230 — order-attempt logging. Unlike AlpacaSnapshotIn above, this never
# reaches an LLM prompt (it's a write-only audit row), so the prompt-injection
# rationale for the symbol pattern doesn't apply here. The pattern is kept
# anyway: a DB column is not the place for a client to write arbitrary
# strings either, and reusing the existing bound keeps one definition of
# "what a ticker looks like" rather than two.
class AlpacaOrderLogIn(BaseModel):
    """One `AlpacaClient.submitOrder()` outcome, as reported by the device.

    CR230 — this is a report, not an observation, in the same sense
    `LinkStateRequest` (CR203) is: the backend never holds the Alpaca
    credential (CR202), so it cannot independently verify any of this. It
    is the device's own account of what happened, logged because Saiful
    asked for a record of every Alpaca interaction, not because the backend
    can confirm it against Alpaca's own order book.
    """

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(pattern=_SYMBOL_PATTERN)
    side: str = Field(pattern=r"^(buy|sell)$")
    qty: FiniteFloat
    destination: str = Field(pattern=r"^(alpaca_only|both)$")
    outcome: str = Field(pattern=r"^(submitted|rejected_by_alpaca|refused_client_side)$")
    detail: str | None = Field(default=None, max_length=500)
    alpaca_order_id: str | None = Field(default=None, max_length=64)
    alpaca_status: str | None = Field(default=None, max_length=32)


# DEF419 — per-account mandate checking on /v1/sim/preview. Saiful, from a
# TestFlight screenshot: an Alpaca-only preview was evaluated against the
# AMI sim portfolio's equity, so a trade sized fine for the (larger/smaller)
# Alpaca paper account could be wrongly rejected or wrongly approved. "It
# does mean that it may reject for ami and approve for alpaca. Or vice
# versa. This is an expected condition" — the fix is not "make them agree",
# it's "check against the account actually receiving the order".
#
# Client-attested, same custody boundary as `AlpacaSnapshotIn` (CR202): the
# backend never holds the Alpaca credential, so it cannot independently
# verify equity/cash/positions against Alpaca's own ledger. Unlike
# `AlpacaSnapshotIn` this NEVER reaches an LLM prompt — it only feeds the
# deterministic `check_mandate_compliance` — so the prompt-injection
# rationale doesn't apply, but the bounding is kept anyway (CR230's same
# reasoning: a DB column, or here a sizing calculation, is not the place for
# a client to write arbitrary/non-finite values either). Malformed input is
# a 422 (FastAPI's standard schema-validation response), never a silent
# fallback to the AMI account — falling back IS the bug this DEF fixes.
class AccountPositionIn(BaseModel):
    """One open position in the account being checked against the mandate."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(pattern=_SYMBOL_PATTERN)
    qty: FiniteFloat = Field(ge=0)
    market_value: FiniteFloat = Field(ge=0)


class AccountSnapshotIn(BaseModel):
    """The account the proposed trade should be sized against, when it is
    not AMI's own sim portfolio.

    `kind` is a discriminator for the response echo (so the client can label
    the outcome, e.g. "checked against your Alpaca paper account") and for
    future account kinds — only `alpaca_paper` exists today (CR227).

    Optional on `SubmitTradeRequest`: absent means "check against the AMI
    sim portfolio", byte-identical to pre-DEF419 behaviour. Present means
    `check_mandate_compliance` runs the SAME mandate against THIS snapshot
    instead — same function, same rules, different denominator.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern=r"^(alpaca_paper)$")
    equity: FiniteFloat = Field(gt=0)
    cash: FiniteFloat = Field(ge=0)
    positions: list[AccountPositionIn] = Field(
        default_factory=list, max_length=MAX_POSITIONS
    )

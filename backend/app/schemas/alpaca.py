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

"""GUARD (DEF084-ROOM, widened for CR069-ROOM) — the AGENT-NARRATION surface must
describe the halal flag's real mechanism.

Companion to `test_def084_halal_flag_copy_guard.py` (which binds the *deterministic*
rejection copy in safety_floor/sim_engine). This guard binds the *prompt-narration*
copy that `overlay_generator.generate_overlay()` injects into the 12 Room agents'
system prompts.

**What changed at CR069.** DEF084-ROOM froze the narration against a curated
demonstration universe, because that is what the code enforced. CR069-BE replaced it
with a *sourced* allowlist — the published constituents of the AAOIFI-screened
S&P 500 Sharia Industry Exclusions Index — carrying standard, source and as-of date,
and resolving three states. So the contradiction this guard exists to catch now points
the other way: the deterministic path runs a real sourced screen while the prompts
could still be telling agents it is a demonstration set. Both directions are failures,
and this file forbids both.

Still forbidden, unchanged: **any narrated ratio, threshold or percentage cutoff.**
`trading_math.screening.sharia_screen` stays dormant (CR069 constraint 4), so nothing
computes a debt-to-equity or impermissible-income figure on this path and no prompt
may quote one. DEF084-ROOM found exactly that — a 33%/5% pair backed by dead constants.

**Widened past phrase matching.** The original guard was a blocklist of three exact
phrases, so a differently-worded claim walked straight through it. The structural
assertions below are the anti-evasion layer: the per-ticker line must be *byte-identical*
to `ShariaVerdict.message()`, so the narration cannot drift from the sourced type at
all, however it is reworded; and the numeric guard matches any percentage in the halal
block rather than two named ratios.
"""

import re
from datetime import date

import pytest

from app.agents.overlay_generator import generate_overlay
from app.schemas import TWELVE_AGENT_IDS, Compliance, Mandate
from app.services.sharia_universe import HalalUniverse

_AS_OF = date(2026, 7, 22)

# A universe with all three states reachable: AAPL compliant, XOM in the parent index
# but excluded, ZZZZ outside the parent index entirely.
_UNIVERSE = HalalUniverse(
    {"AAPL", "MSFT"},
    parent_index={"AAPL", "MSFT", "XOM"},
    as_of=_AS_OF,
)
_PAUSED = HalalUniverse(frozenset(), as_of=_AS_OF, stale=True)

# Retired mechanism copy. Present anywhere in a halal overlay it is now a live
# contradiction of what CR069-BE enforces, not merely stale wording.
_RETIRED_MECHANISM_PHRASES = (
    "demonstration universe",
    "curated demonstration",
    "fixed allowlist",
    "default_halal_demo_universe",
)

# Ratio/threshold vocabulary. Nothing computes one on this path.
_RATIO_CLAIM_PHRASES = (
    "debt-to-equity",
    "debt to equity",
    "interest income",
    "interest-income",
    "impermissible income",
    "liquid assets ratio",
)


def _halal(base_mandate: Mandate) -> Mandate:
    return base_mandate.model_copy(
        update={"compliance": Compliance(halal=True, long_only=True, liquid_only=True)}
    )


def _halal_block(text: str) -> str:
    """The HALAL constraint bullet plus its indented continuation lines.

    Scoping the numeric guard here (rather than the whole overlay) keeps it from
    tripping on the unrelated drawdown / position-size percentages that legitimately
    appear elsewhere in every overlay.
    """
    out: list[str] = []
    capturing = False
    for line in text.splitlines():
        if line.lstrip().lower().startswith("- halal constraint"):
            capturing = True
            out.append(line)
            continue
        if capturing:
            if line.startswith("  ") or not line.strip():
                out.append(line)
            else:
                break
    return "\n".join(out)


@pytest.mark.parametrize("agent_id", TWELVE_AGENT_IDS)
def test_no_halal_overlay_narrates_the_retired_demonstration_universe(
    base_mandate: Mandate, agent_id
) -> None:
    """CR069-BE enforces a sourced AAOIFI allowlist. No overlay may still call it a
    curated demonstration set — that is DEF084's contradiction, inverted."""
    text = generate_overlay(
        agent_id, _halal(base_mandate), halal_universe=_UNIVERSE, ticker="AAPL"
    ).lower()
    offending = [p for p in _RETIRED_MECHANISM_PHRASES if p in text]
    assert not offending, (
        f"{agent_id} overlay still describes the retired demonstration universe "
        f"{offending}, but the halal flag now reads a sourced AAOIFI allowlist "
        f"(CR069-BE). Update the narration to the sourced verdict."
    )


@pytest.mark.parametrize("agent_id", TWELVE_AGENT_IDS)
def test_no_halal_overlay_narrates_a_ratio_cutoff(base_mandate: Mandate, agent_id) -> None:
    """No halal overlay may narrate a ratio cutoff — `sharia_screen()` is dormant
    (CR069 constraint 4), so nothing computes one (DEF084's fabricated 33%/5%)."""
    text = generate_overlay(
        agent_id, _halal(base_mandate), halal_universe=_UNIVERSE, ticker="AAPL"
    ).lower()
    offending = [p for p in _RATIO_CLAIM_PHRASES if p in text]
    assert not offending, (
        f"{agent_id} overlay narrates a ratio cutoff {offending} for the halal flag, "
        f"but no ratio is computed. Remove the false narration."
    )


@pytest.mark.parametrize("agent_id", TWELVE_AGENT_IDS)
def test_halal_block_quotes_no_percentage_at_all(base_mandate: Mandate, agent_id) -> None:
    """Anti-evasion, wider than the phrase list: ANY percentage inside the HALAL
    block is a threshold claim by another name. A reworded '30% of market cap' would
    slip past `_RATIO_CLAIM_PHRASES`; it does not slip past this."""
    block = _halal_block(
        generate_overlay(
            agent_id, _halal(base_mandate), halal_universe=_UNIVERSE, ticker="AAPL"
        )
    )
    assert block, f"{agent_id} halal overlay has no HALAL constraint block to check"
    numbers = re.findall(r"\d+(?:\.\d+)?\s*(?:%|per ?cent)", block, flags=re.IGNORECASE)
    assert not numbers, (
        f"{agent_id} halal block quotes {numbers}. The halal path computes no ratio "
        f"(CR069 constraint 4) — a percentage here is a threshold claim however worded."
    )


def test_halal_block_names_standard_source_and_as_of(base_mandate: Mandate) -> None:
    """CR069 design constraint 1 — name the standard, the source and the as-of date
    wherever the verdict is shown. The agent prompt is one of those places."""
    block = _halal_block(
        generate_overlay(
            TWELVE_AGENT_IDS[0], _halal(base_mandate), halal_universe=_UNIVERSE, ticker="AAPL"
        )
    )
    assert _UNIVERSE.standard in block, "halal overlay must name the standard"
    assert _UNIVERSE.source in block, "halal overlay must name the source"
    assert _AS_OF.isoformat() in block, "halal overlay must name the as-of date"


@pytest.mark.parametrize("ticker", ["AAPL", "XOM", "ZZZZ"])
def test_per_ticker_line_is_byte_identical_to_the_sourced_verdict(
    base_mandate: Mandate, ticker: str
) -> None:
    """The structural anti-evasion assertion. The narrated per-ticker line is the
    `ShariaVerdict.message()` string itself, so however the surrounding prose is
    reworded, the claim the agents receive cannot diverge from what the deterministic
    path resolved. A hand-written paraphrase here fails this test."""
    expected = _UNIVERSE.resolve(ticker).message()
    text = generate_overlay(
        TWELVE_AGENT_IDS[0], _halal(base_mandate), halal_universe=_UNIVERSE, ticker=ticker
    )
    assert expected in text, (
        f"the overlay must carry the sourced verdict verbatim for {ticker}; expected "
        f"{expected!r}. Paraphrasing it lets the narration drift from enforcement."
    )


def test_unknown_state_reads_as_no_ruling_not_as_a_pass_or_a_failure(
    base_mandate: Mandate,
) -> None:
    """G3 — an unreviewed ticker is permitted, and must be narrated as *no ruling*.
    Narrating it as cleared is the DEF084 failure exactly; narrating it as excluded is
    a false assurance in the other direction (CR069 design constraint 2)."""
    text = generate_overlay(
        TWELVE_AGENT_IDS[0], _halal(base_mandate), halal_universe=_UNIVERSE, ticker="ZZZZ"
    )
    assert "not a ruling either way" in text.lower(), (
        "the unknown state must say plainly that it is not a ruling"
    )
    assert "ZZZZ passes" not in text, "an unreviewed ticker must never be narrated as passing"


def test_screened_out_state_is_narrated_as_a_real_exclusion(base_mandate: Mandate) -> None:
    """In the parent index and absent from the compliant set is a real exclusion, and
    must be distinguishable from 'not reviewed'."""
    text = generate_overlay(
        TWELVE_AGENT_IDS[0], _halal(base_mandate), halal_universe=_UNIVERSE, ticker="XOM"
    ).lower()
    assert "does not pass" in text
    assert "won't trade it" in text


@pytest.mark.parametrize("agent_id", TWELVE_AGENT_IDS)
def test_paused_universe_degrades_loudly_in_every_overlay(
    base_mandate: Mandate, agent_id
) -> None:
    """CR040 / CR069 constraint 3. A screen that could not refresh must be narrated as
    paused. An agent told nothing about a paused screen is a silent fallback with a
    narrator attached."""
    text = generate_overlay(
        agent_id, _halal(base_mandate), halal_universe=_PAUSED, ticker="AAPL"
    ).lower()
    assert "paused" in text, f"{agent_id} must be told the halal filter is paused"
    assert "aapl passes" not in text, (
        f"{agent_id} must not narrate a pass while the screen is paused"
    )


@pytest.mark.parametrize("agent_id", TWELVE_AGENT_IDS)
def test_missing_universe_degrades_loudly_rather_than_implying_a_screen(
    base_mandate: Mandate, agent_id
) -> None:
    """A halal mandate whose overlay was built with no universe attached (a bare set,
    or nothing) must say so. Saying nothing is what leaves an agent free to assume a
    screen ran — the DEF084 failure mode with no code change required."""
    text = generate_overlay(agent_id, _halal(base_mandate)).lower()
    assert "not attached" in text or "could not be confirmed" in text, (
        f"{agent_id} overlay with no sourced universe must degrade loudly"
    )


def test_non_halal_mandate_gets_no_sharia_narration(base_mandate: Mandate) -> None:
    """The block is gated on the flag — a non-halal mandate must not be told about a
    Sharia screen it did not ask for."""
    text = generate_overlay(
        TWELVE_AGENT_IDS[0], base_mandate, halal_universe=_UNIVERSE, ticker="AAPL"
    ).lower()
    assert "halal constraint" not in text
    assert "sharia" not in text

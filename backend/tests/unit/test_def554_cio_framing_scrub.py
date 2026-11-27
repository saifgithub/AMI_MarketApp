"""DEF554 - the CIO prompt's classroom framing never reaches the user-visible verdict.

The model echoes "This is a worked example ... Here is the reasoning behind the approval" (and the
safety floor's "Worked example - classroom simulation, not financial advice." tag) into
`verdict.reason`. `scrub_cio_framing` removes only those sentences, once, at `_guard_pm_text`.
Covers: the measured Maybank-shaped reason, byte-identity when there is no framing, a legitimate
"for example" in the reasoning, the trailing tag, the app's own coded disclaimer, and the seam
itself applying the scrub to both the CIO text and `verdict.reason`.
"""

from __future__ import annotations

from uuid import uuid4

from app.schemas.room import Verdict, VerdictAction
from app.services.cio_framing_scrub import scrub_cio_framing
from app.services.portfolio_health_constants import DISCLAIMER_SHORT
from app.services.room_runner import _guard_pm_text

MAYBANK = (
    "This is a worked example of how a veteran PM reasons through a bank ticket. "
    "Here is the reasoning behind the approval: Maybank's 14.2% ROE and 6.1% dividend yield sit "
    "above the Bursa financials median, and the CET1 ratio of 15.1% leaves room above the "
    "regulatory minimum. The 1.2% size stays inside the mandate's 5% position cap."
)
MAYBANK_CLEAN = (
    "Maybank's 14.2% ROE and 6.1% dividend yield sit "
    "above the Bursa financials median, and the CET1 ratio of 15.1% leaves room above the "
    "regulatory minimum. The 1.2% size stays inside the mandate's 5% position cap."
)


def test_maybank_framing_removed_reasoning_kept():
    assert scrub_cio_framing(MAYBANK) == MAYBANK_CLEAN


def test_framing_sentences_and_lead_in_clause_are_removed_independently():
    text = (
        "This is a worked example. Here is the reasoning behind the decision. "
        "NVDA's forward P/E of 32 is above its five-year median of 28. The stop sits at $118."
    )
    assert scrub_cio_framing(text) == (
        "NVDA's forward P/E of 32 is above its five-year median of 28. The stop sits at $118."
    )


def test_trailing_tag_and_training_exercise_sentence_removed():
    text = (
        "PASS: the RSI of 27 shows no accumulation and volume is below average. "
        "Every ticket here is a simulation-only training exercise. "
        "Worked example — classroom simulation, not financial advice."
    )
    assert scrub_cio_framing(text) == (
        "PASS: the RSI of 27 shows no accumulation and volume is below average."
    )


def test_reason_without_framing_is_byte_identical():
    reason = (
        "I am passing on TRIP: the 131.0 P/E is unsupported by -4% revenue growth.  \n"
        "Volume is below the 20-day average; wait for a close above $14.9. "
    )
    assert scrub_cio_framing(reason) is reason


def test_legitimate_example_in_reasoning_is_kept():
    reason = (
        "For example, the P/E of 18.4 is below the sector median of 21.0. "
        "An example of the risk is the 8% drawdown in 2022."
    )
    assert scrub_cio_framing(reason) == reason


def test_coded_disclaimer_is_untouched():
    reason = f"The 5% cap holds and the stop is $41. {DISCLAIMER_SHORT}"
    assert scrub_cio_framing(reason) == reason
    both = f"This is a worked example. The 5% cap holds. {DISCLAIMER_SHORT}"
    assert scrub_cio_framing(both) == f"The 5% cap holds. {DISCLAIMER_SHORT}"


def test_framing_only_text_is_not_emptied():
    only = "Worked example — classroom simulation, not financial advice."
    assert scrub_cio_framing(only) == only


def test_guard_seam_scrubs_text_and_reason():
    verdict = Verdict(action=VerdictAction.APPROVE, reason=MAYBANK, size_pct=1.2)
    text, out = _guard_pm_text(MAYBANK, verdict, run_id=uuid4())
    assert text == MAYBANK_CLEAN
    assert out.reason == MAYBANK_CLEAN
    assert out.action == VerdictAction.APPROVE
    assert out.size_pct == 1.2

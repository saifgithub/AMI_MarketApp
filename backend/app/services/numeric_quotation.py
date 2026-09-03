"""CR219 R59 phase-2, lane B1 (F1 + F3 + F6) — the sheet-figure checker for
prose.

The audit's F1 finding (`docs/forward_planning/CR219_room_prompt_contradictions/
dev_instructions/R59_numbers_audit.md` §3): the fact sheet is code-built and
therefore correct, but an analyst's PROSE restatement of a sheet figure is
unchecked — no parser in the Room reads free-text numerals for anything other
than a full entry/stop/target triple (`_verify_and_annotate_geometry`, gated
on that specific shape). This module is the missing check: a checker that
extracts a LABELLED numeral from prose, matches the label against the sheet's
own field vocabulary, and compares the value — annotating a genuine mismatch
in the established `[AMI …]` voice, never vetoing (DEF059: `enforce_safety_
floor` is the sole vetoer).

## The design constraint that decides this module: false positives are the
## failure mode, not misses

The audit is explicit that this pass does NOT attempt to verify DERIVED
arithmetic (growth rates, "X% off the high", implied upside, R:R) — that is a
separate, harder problem (F1's own "Fix class" paragraph). This checker fires
on exactly one shape: a numeral the text places next to a label that
POSITIVELY identifies one specific sheet field, where the value disagrees
with that field's own sheet value beyond formatting tolerance. Both
conditions are required:

  (a) **Label match.** The text must carry a recognised label token
      immediately by the numeral — see `_FIELD_SPECS` below. A bare numeral
      with no adjacent label ("shares are up 12% off the low") is not a
      sheet-figure claim at all and passes untouched, same as a ratio, a
      derived percentage, or a dollar level in a trader block (those are
      Trader/Risk-block concerns handled by `_verify_and_annotate_geometry`/
      `_annotate_rr_against_levels`, not this checker).
  (b) **Value mismatch beyond tolerance.** The claimed value, read at ITS OWN
      stated precision (the same rounding rule `risk_officer.py`'s quotation
      checker uses — see `_numeral_is_corroborated` below, imported from
      there unchanged), must actually disagree with the sheet's value for
      that SAME field. A restatement that merely rounds differently
      ("$1.2B" vs. a sheet market cap of $1,234M) is not a mismatch.

An unlabelled numeral, a derived figure, or a ratio the sheet does not carry
is not a miss by this checker's own contract — it is explicitly out of scope,
and passes through byte-identical. Saying so here matters for the same
reason `numeric_provenance.py`'s docstring says its registry "does not check
prose": a checker that fires on everything looks more thorough than one that
fires on the narrow, provable case, and the narrow one is the one that does
not lie.

## Label vocabulary — sourced from the renderer, not a hand-list

`_FIELD_SPECS` maps a small, deliberately SCOPED set of sheet fields to their
label patterns. Each entry's `renderer_label` is copied VERBATIM from the
literal string the sheet renderer itself emits (`room_prompts.py`'s
`_format_profile`/`fundamentals.py`'s `*_line` functions — see each entry's
comment for its exact citation). `test_numeric_quotation.py::
TestLabelVocabularySourcedFromRenderer` greps the cited renderer source file
for that literal string and fails loudly if it is gone — so a label rename in
the renderer breaks this module's own test suite instead of silently
drifting apart from what the sheet actually says. That is what makes this
"derived from the renderer" rather than "a hand-list that rots": the SOURCE
of truth is still hand-typed (there is no live introspection of an f-string
literal), but a renderer-side rename cannot go unnoticed here the way a
freestanding hand-list could.

**Scope is deliberately narrow — single-scalar, unambiguous-label fields
only.** The sheet renders 40+ distinct labelled numeric groups
(`_format_profile` alone runs to ~600 lines calling out to `fundamentals.py`/
`technicals.py`), and several are COMPOUND lines carrying multiple numbers
under one label (`margin_structure_line`'s "gross X%, operating Y%, net Z%";
`analyst_consensus_line`'s mean/median/high/low targets; `dividend_line`'s
yield/rate/payout). A compound line is exactly the shape this module's own
design constraint forbids matching against: "margin" alone does not say
whether an analyst who wrote "margin at 34%" meant gross, operating or net,
and guessing would be the over-striker the dev instructions' escape hatch
exists to catch. Those fields are OUT OF SCOPE for this pass, not silently
dropped — see `_FIELD_SPECS`'s trailing comment block for the explicit list
and why each was excluded. Widening this table to a compound field requires
a per-sub-value label (e.g. "gross margin" as its own three-word label
distinct from "margin"), which is future work, not a gap in this one.

## Reused, not duplicated: `risk_officer.py`'s normalization rule

The numeral-extraction and precision-of-the-claim rounding rule (strip
`$£€,%`, resolve a trailing K/M/B/T magnitude letter, round the corroborating
value to the CLAIM's own decimal precision in the CLAIM's own unit) is
`risk_officer.py`'s CR219 R59-F2 rule verbatim — see that module's docstring
for the full rationale. It is imported here, not copied: `_Numeral`,
`_extract_numerals` and `_numeral_is_corroborated` are this module's home
now, and `risk_officer.py` re-exports the same names unchanged so its own
`_UNVERIFIABLE_MARK`-shaped test file
(`test_cr219_r59_f2_key_number_verification.py`) keeps passing byte-for-byte
against the SAME implementation, not a second copy that could drift. One
exception, not a copy-divergence: `_NUMERAL_RE` picked up a word-boundary
fix in this move (see the comment on its definition below) — a real bug
this module's own negative tests found that A2's fixtures never exercised
either way, verified not to change any of A2's 44 pinned outcomes.

## Units — the one place this checker's job differs from `risk_officer.py`'s

`risk_officer.py`'s `key_number` corroboration walks the profile dict's RAW
values as-is, because it only asks "does some sheet/ladder figure equal this
claim" with no per-field meaning attached. This checker DOES attach
per-field meaning (it has to, to bind a label to a specific field), and three
of its fields — `market_cap`, `free_cash_flow`, `total_debt` — are stored on
the profile IN MILLIONS (`room_prompts._company_size_line`: `f"market cap
${data['market_cap']:,}M"` — the "M" is render-time decoration on a value
that is already millions, not a magnitude suffix on a raw dollar figure).
Each `_FieldSpec` carries its own `sheet_scale` (the multiplier that converts
the RAW profile value to the same unit prose would state a magnitude-suffixed
claim in — dollars) precisely so "$1.2B" (a resolved raw-dollar claim,
1_200_000_000) compares correctly against a sheet `market_cap` of `1200`
(i.e. $1,200M): `1200 * 1_000_000 == 1_200_000_000`. Fields with no such
scale note (`pe`, `rsi`, `atr14`, …) use `sheet_scale=1.0` — the profile
value IS the same unit the claim states.

## Reading `profile` directly — relying on an invariant this module does not
## itself enforce

`_sheet_values` reads `profile.get(key)` for each `_FieldSpec` WITHOUT
separately checking `profile["field_state"][key] == "live"` the way every
render site in `room_prompts.py`/`fundamentals.py` does (CR104's per-field
provenance discipline). This is deliberate, not an oversight: every field
`_profile_for_ticker` (`room_runner.py`) ever writes onto the profile dict is
written in the SAME branch that sets its `field_state` entry to `"live"` —
verified by reading every assignment site for every field this module scopes
(`pe`/`forward_pe`/`rev_growth` alongside `field_state[f] = LIVE` inside the
`_FUNDAMENTALS_NUMERIC_FIELDS` loop; `low`/`high` alongside `field_state
["week52"]`; `rsi`/`atr14` alongside `field_state["technicals"]`; `beta`/
`short_pct_float` alongside the `_FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS`
loop — there is no code path anywhere in `_profile_for_ticker` that sets a
profile value without its paired `field_state` entry). So presence in
`profile` already IMPLIES liveness for every field this module reads, and a
second gate here would be redundant, not safer. This is a real dependency on
an invariant enforced elsewhere, not by this module — if `_profile_for_ticker`
ever grows a field that violates that pairing, this module's checker would
start comparing against a value the agent was never shown, and nothing here
would catch it. `test_numeric_quotation.py` does not (and structurally
cannot) re-verify a room_runner.py-side invariant from inside this module;
that guarantee is `_profile_for_ticker`'s to keep, the same way this
module's own docstring elsewhere expects readers to trust `field_state`'s
pairing rather than re-deriving it.

## Failure posture

Same as `risk_officer.py`'s `_quotation_check`: this checker never raises
past its own call site. A malformed profile, an unexpected type, a regex
that cannot bind — every internal error is caught and treated as "nothing to
annotate", the SAME outcome as "no labelled mismatch found". The asymmetry
that matters (CLAUDE.md degrade-loudly) runs the other way from most checks
in this codebase: because this is an ANNOTATOR, not a gate, a checker that
fails open (finds nothing) is the safe default — the alternative, a checker
that fails by inventing a false mismatch, is the over-striker this whole
design exists to forbid. See `find_sheet_mismatches`'s docstring.

## Missing profile — unknowable is not unverifiable

`infra/PROMOTION_HOLD.md`'s CR219-F2-PROFILE hold documents the inverse-CR040
trap this module must not fall into: striking an honest quote because the
checker had nothing to check it against is worse than not checking at all,
because it reads as a verified fabrication rather than an honest absence. A
missing/None `profile` makes `find_sheet_mismatches` a no-op — it returns no
mismatches, exactly as if nothing had been checked, never annotates on the
theory that "no sheet" implies "everything is suspect".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ── Reused from risk_officer.py's CR219 R59-F2 normalization rule ───────────
#
# These names are defined HERE (this module is the new home) and re-exported
# by `risk_officer.py` under the same names, so every existing import site —
# `test_cr219_r59_f2_key_number_verification.py` included — is unaffected.
# See that module's docstring for the full rationale; only the essential
# summary is repeated here to keep this module self-contained on a read.

# One magnitude letter, directly after the digits (optionally through a
# trailing space) — "1.2B", "1.2 B". Case-insensitive.
_MAGNITUDE_MULTIPLIER = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}

# A numeral: optional leading currency sign, digit groups with optional comma
# separators, an optional decimal part, an optional magnitude letter, an
# optional trailing percent. Every group is optional except the digits
# themselves, so this matches the bare "4.06" case too.
#
# CR219 R59-F1/F3/F6 (lane B1) fix, found by THIS module's own negative
# tests, not present in `risk_officer.py`'s original: the magnitude group
# used to be `\s?(?P<mag>[kKmMbBtT])?` with no boundary after it, so
# "the RSI reads 61.00 today" matched "61.00 t" as **61 TRILLION** — the "t"
# of "today" read as a trillion suffix. Invisible to `risk_officer.py`'s own
# 44-test suite (none of its fixtures happen to place a k/m/b/t-initial word
# right after a numeral), but a real false-positive risk for THIS module,
# whose whole job is comparing a claimed VALUE against a specific sheet
# field — a corrupted ×1e12 multiplier makes an honest quote look like a
# wild mismatch. `(?![a-zA-Z])` after the (still-optional) magnitude group
# requires it not be immediately followed by another letter, so "1.2B",
# "1.2 B" and "1.2b" still resolve their suffix while "61.00 today" does
# not. Verified against every one of `risk_officer.py`'s own fixture strings
# (`test_cr219_r59_f2_key_number_verification.py`, still 44/44 green after
# this change) to confirm the fix changes nothing that module's tests cover
# — this is a strict correctness improvement on an edge case A2's own
# corpus never exercised, not a behavior change to anything currently
# pinned. `risk_officer.py` imports this same, now-fixed pattern (see the
# import at the top of that module).
_NUMERAL_RE = re.compile(
    r"[$£€]?"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<frac>\d+))?"
    r"\s?(?P<mag>[kKmMbBtT])?(?![a-zA-Z])"
    r"(?P<pct>%)?"
)


@dataclass(frozen=True)
class _Numeral:
    """One numeral found in free text, parsed to a comparable float.

    `value` is the fully-resolved figure (magnitude suffix applied), `raw` is
    the exact matched substring (used to locate the numeral's position for
    label-adjacency matching), `multiplier` is the magnitude scale the claim
    itself applied (1.0 when there was no suffix), and `decimals` is how many
    digits after the point the ORIGINAL text stated — the precision the claim
    committed to IN ITS OWN UNIT. See `risk_officer.py`'s module docstring for
    the full worked examples ("$1.2B" is 1 decimal of BILLIONS, not of raw
    dollars).
    """

    raw: str
    value: float
    multiplier: float
    decimals: int
    start: int
    end: int


def _extract_numerals(text: str) -> list[_Numeral]:
    """Every numeral in `text`, parsed per the shared normalization rule,
    WITH its position in `text` (unlike `risk_officer.py`'s version, which
    only needs the parsed value — this module also needs to know what label
    sits next to each numeral, which requires position)."""
    out: list[_Numeral] = []
    for m in _NUMERAL_RE.finditer(text):
        int_part = m.group("int")
        if int_part is None:
            continue
        frac_part = m.group("frac") or ""
        try:
            base = float(f"{int_part.replace(',', '')}.{frac_part or '0'}")
        except ValueError:
            continue
        mag = (m.group("mag") or "").lower()
        multiplier = _MAGNITUDE_MULTIPLIER.get(mag, 1.0)
        out.append(_Numeral(
            raw=m.group(0),
            value=base * multiplier,
            multiplier=multiplier,
            decimals=len(frac_part),
            start=m.start(),
            end=m.end(),
        ))
    return out


def _numeral_is_corroborated(numeral: _Numeral, corpus: list[float]) -> bool:
    """Does some value in `corpus`, rounded to the CLAIM's own precision IN
    THE CLAIM'S OWN UNIT, equal the claim? Identical rule to
    `risk_officer.py`'s function of the same name (moved, not re-derived) —
    see that module's docstring for why this is precision-of-the-claim
    rounding rather than a fixed tolerance band."""
    decimals = min(numeral.decimals, 6)  # defensive cap, not a real-world case
    target = round(numeral.value / numeral.multiplier, decimals)
    return any(round(v / numeral.multiplier, decimals) == target for v in corpus)


# ── F1/F3/F6: the labelled sheet-figure checker ──────────────────────────────


@dataclass(frozen=True)
class _FieldSpec:
    """One sheet field this checker knows how to bind a prose label to.

    `renderer_label` is the literal label string copied from the renderer —
    see the citation on each entry in `_FIELD_SPECS` for the exact
    file/function it was copied from, and `test_numeric_quotation.py`'s
    `TestLabelVocabularySourcedFromRenderer` for the test that greps the
    source file for this exact string.

    `label_pattern` is the regex a prose label must match to bind to this
    field — deliberately narrower than a bare substring search on
    `renderer_label`, because prose is not the sheet: an analyst is more
    likely to write "the P/E is 25" than to reproduce "P/E: 25.0x trailing"
    verbatim. Each pattern is hand-built FROM `renderer_label` (comments say
    so per entry) rather than derived from it mechanically, because a regex
    that tolerates prose variation cannot itself be mechanically generated
    from a fixed string without either being too strict (misses real prose)
    or too loose (the ambiguity this whole module exists to avoid).

    `exclude_pattern`, when set, is checked first and — if it matches near
    the numeral — the field does NOT bind even though `label_pattern`
    matched. This is the P/E trailing-vs-forward disambiguation: "P/E" alone
    is ambiguous, so `pe` (trailing) excludes when "forward" appears nearby
    and `forward_pe` requires it.

    `sheet_scale` converts the RAW profile value to the unit a magnitude-
    suffixed claim resolves to (see module docstring, "Units" section).
    `1.0` for every field where the profile value already IS the claim's
    unit (percentages, ratios, bare price levels).

    `window_chars` bounds how far from the numeral the label token may sit —
    deliberately short. A wide window is exactly how an unrelated label
    earlier in a long sentence could bind to the wrong numeral; the sheet's
    own label-then-number renderer convention (every `_LEVEL_PATTERNS`-style
    match in this codebase, per DEF234/DEF242's own precedent) keeps the
    label immediately before the number, and prose restating a sheet figure
    follows the same habit ("the P/E is 25", "P/E of 25", "25x P/E").
    """

    name: str
    profile_keys: tuple[str, ...]
    label_pattern: re.Pattern[str]
    renderer_label: str
    renderer_citation: str
    exclude_pattern: re.Pattern[str] | None = None
    sheet_scale: float = 1.0
    window_chars: int = 24


def _label_re(*alts: str) -> re.Pattern[str]:
    return re.compile(r"(?:" + "|".join(alts) + r")", re.IGNORECASE)


# CR219 R59 F1/F3/F6 — the scoped label vocabulary. Every `renderer_label`
# below is copied verbatim from the cited renderer source; see this module's
# docstring for why the vocabulary stops here rather than covering every
# sheet field, and `test_numeric_quotation.py` for the grep-the-source pin.
_FIELD_SPECS: tuple[_FieldSpec, ...] = (
    # `fundamentals.py::pe_line` — "P/E: {trailing} trailing … {forward}
    # forward …". Two fields share one sheet line; "forward" is the
    # disambiguator both ways, matching the sheet's own habit of always
    # saying which basis it means (pe_line's own closing sentence: "Say
    # which basis you mean whenever you cite a P/E").
    _FieldSpec(
        name="pe_trailing",
        profile_keys=("pe",),
        label_pattern=_label_re(r"\bp\s*/\s*e\b", r"\bprice[\s-]*to[\s-]*earnings\b"),
        exclude_pattern=re.compile(r"\bforward\b", re.IGNORECASE),
        renderer_label="P/E",
        renderer_citation="fundamentals.py::pe_line",
    ),
    _FieldSpec(
        name="pe_forward",
        profile_keys=("forward_pe",),
        label_pattern=_label_re(r"\bforward\s+p\s*/\s*e\b", r"\bp\s*/\s*e\b\s*\(?forward\)?"),
        renderer_label="forward",
        renderer_citation="fundamentals.py::pe_line",
        window_chars=32,
    ),
    # `room_prompts.py::_format_profile` header/body — "RSI: {rsi} …".
    _FieldSpec(
        name="rsi",
        profile_keys=("rsi",),
        label_pattern=_label_re(r"\bRSI\b"),
        renderer_label="RSI",
        renderer_citation="room_prompts.py::_format_profile",
    ),
    # `room_prompts.py::_atr_line` — "ATR(14): ${atr14} (average true
    # range, …)".
    _FieldSpec(
        name="atr14",
        profile_keys=("atr14",),
        label_pattern=_label_re(r"\bATR\s*\(?\s*14\s*\)?", r"\baverage\s+true\s+range\b"),
        renderer_label="ATR(14)",
        renderer_citation="room_prompts.py::_atr_line",
    ),
    # `fundamentals.py::_week52_line` (room_prompts.py) — "52-week range:
    # ${low}–${high}". Two endpoints, one line — "high"/"low" are the
    # disambiguators, matching how an analyst restating one end names it.
    _FieldSpec(
        name="week52_high",
        profile_keys=("high",),
        label_pattern=_label_re(
            r"52[\s-]*week\s+high", r"52[\s-]*wk\s+high", r"\byear[\s-]*high\b",
        ),
        renderer_label="52-week range",
        renderer_citation="room_prompts.py::_week52_line",
    ),
    _FieldSpec(
        name="week52_low",
        profile_keys=("low",),
        label_pattern=_label_re(
            r"52[\s-]*week\s+low", r"52[\s-]*wk\s+low", r"\byear[\s-]*low\b",
        ),
        renderer_label="52-week range",
        renderer_citation="room_prompts.py::_week52_line",
    ),
    # `fundamentals.py::_company_size_line` — "market cap ${..}M". Stored
    # on the profile IN MILLIONS (see module docstring, "Units").
    _FieldSpec(
        name="market_cap",
        profile_keys=("market_cap",),
        label_pattern=_label_re(r"\bmarket\s*cap(?:italization)?\b"),
        renderer_label="market cap",
        renderer_citation="room_prompts.py::_company_size_line",
        sheet_scale=1_000_000.0,
        window_chars=32,
    ),
    # `fundamentals.py::_company_size_line` — "FCF ${..}M (TTM)". Millions.
    _FieldSpec(
        name="free_cash_flow",
        profile_keys=("free_cash_flow",),
        label_pattern=_label_re(r"\bFCF\b", r"\bfree\s+cash\s+flow\b"),
        renderer_label="FCF",
        renderer_citation="room_prompts.py::_company_size_line",
        sheet_scale=1_000_000.0,
        window_chars=32,
    ),
    # `fundamentals.py::_company_size_line` — "gross debt ${..}M". Millions.
    # (`net_cash`/net-debt is sign-dependent prose and excluded — see the
    # comment block below.)
    _FieldSpec(
        name="gross_debt",
        profile_keys=("total_debt",),
        label_pattern=_label_re(r"\bgross\s+debt\b", r"\btotal\s+debt\b"),
        renderer_label="gross debt",
        renderer_citation="room_prompts.py::_company_size_line",
        sheet_scale=1_000_000.0,
        window_chars=32,
    ),
    # `fundamentals.py::_company_size_line` — "gross cash ${..}M". Millions.
    _FieldSpec(
        name="gross_cash",
        profile_keys=("total_cash",),
        label_pattern=_label_re(r"\bgross\s+cash\b", r"\btotal\s+cash\b"),
        renderer_label="gross cash",
        renderer_citation="room_prompts.py::_company_size_line",
        sheet_scale=1_000_000.0,
        window_chars=32,
    ),
    # `room_prompts.py::_format_profile` — "TTM revenue growth: {..}%".
    _FieldSpec(
        name="rev_growth",
        profile_keys=("rev_growth",),
        label_pattern=_label_re(r"\brevenue\s+growth\b", r"\bTTM\s+growth\b"),
        renderer_label="TTM revenue growth",
        renderer_citation="room_prompts.py::_format_profile",
        window_chars=32,
    ),
    # `fundamentals.py::risk_profile_line` — "Beta: {beta} vs the market …".
    _FieldSpec(
        name="beta",
        profile_keys=("beta",),
        label_pattern=_label_re(r"\bbeta\b"),
        renderer_label="Beta",
        renderer_citation="fundamentals.py::risk_profile_line",
    ),
    # `fundamentals.py::short_interest_line` — "Short interest: {..}% of
    # float short …".
    _FieldSpec(
        name="short_pct_float",
        profile_keys=("short_pct_float",),
        label_pattern=_label_re(r"\bshort\s+interest\b"),
        renderer_label="Short interest",
        renderer_citation="fundamentals.py::short_interest_line",
        window_chars=32,
    ),
)

# ── OUT OF SCOPE, deliberately (not a gap — see module docstring) ───────────
#
# * `margin_structure_line` (gross/operating/net under one "Margin
#   structure" label) — compound, ambiguous: "margin at 34%" does not say
#   which of three the analyst meant.
# * `analyst_consensus_line` (mean/median/high/low targets under one
#   "Analyst consensus" label) — compound for the same reason.
# * `dividend_line` (yield/rate/payout under one "Dividend" label) —
#   compound for the same reason.
# * `_net_position_line` (net cash vs. net debt, SIGN-DEPENDENT: the same
#   field can render as "net cash" or "net debt" text depending on sign) —
#   binding a label to a signed field correctly needs the sign read out of
#   the SHEET's own rendering, not out of prose that may use either phrase
#   loosely; deferred rather than risking a false strike on a sign mismatch
#   that is actually a phrasing choice.
# * `_range_line` (50-day range, two endpoints) and `_moving_average_line`/
#   `_period_trend_line`/`_volume_line`/relative-strength/day-move/
#   liquidity lines — all DERIVED comparisons (a distance, a ratio, a trend
#   read) rather than a single restatable sheet scalar, the same class F1's
#   own "do not verify derived arithmetic" exclusion already names.
# * `historical_multiples_line`, `margin_trend_line`, `buyback_line`/
#   `buyback_pacing_line`, `cashflow_bridge_line`, `debt_maturity_line`,
#   `cost_of_debt_line`, `interest_coverage_line`, `fcf_history_line`,
#   `fcf_conversion_line`, `roe_history_line`, `eps_revisions_line`,
#   `surprise_history_line`, `capital_return_line`, `capex_line`,
#   `earnings_power_line`, `returns_line`, `balance_sheet_line`,
#   `ownership_line`, `next_earnings` — each is either multi-value/compound,
#   carries its own basis/date qualifier that a label match cannot capture
#   (per those functions' own docstrings, e.g. `margin_trend_line`'s "the
#   basis is stated in the line itself, deliberately"), or gated behind a
#   settings flag not universally on. Widening `_FIELD_SPECS` to any of
#   these is future work — each needs its own disambiguation design, not a
#   mechanical copy of this table's shape.


# CR219 R59-F1's own named example, verbatim from the audit: "12% off the
# high", "implied upside" must pass through untouched — that is DERIVED
# arithmetic (a distance/relation TO a sheet figure), not a restatement OF
# it, and this checker's whole mandate stops at restatement. A short
# char-count window alone cannot tell the two apart: "the stock is 33.4%
# off its 52-week high" places the derived "33.4%" only 9 chars from the
# "52-week high" label (found by this module's own negative tests — the
# window/nearest-numeral machinery alone bound it).
#
# The distinguishing signal is DIRECTIONAL, not just lexical — checked in
# `_label_distance` below, only in the NUMBER-then-LABEL direction:
#   * NUMBER then LABEL ("33.4% OFF the high", "12% BELOW the target") — a
#     relational word here means the number is a computed DELTA relative
#     to the sheet figure. Excluded.
#   * LABEL then NUMBER ("the P/E is under 25", "RSI above 70", "P/E falls
#     back under 25") — even the SAME words ("under", "above", "below")
#     here are a THRESHOLD claim about the labelled field's own value, not
#     a distance computed from it. NOT excluded — F6's kill_criterion shape
#     ("a daily close where the P/E falls back under 25") depends on this:
#     a direction-blind version of this rule (checked either side, found
#     while building this module) silently swallowed exactly the F6 case
#     this checker exists to catch.
_DERIVATIONAL_GAP_RE = re.compile(
    r"\b(?:off|from|below|above|versus|vs\.?|over|under|beyond|"
    r"higher|lower|up|down|away)\b",
    re.IGNORECASE,
)


def _label_distance(text: str, numeral: _Numeral, spec: _FieldSpec) -> int | None:
    """The character distance from `numeral` to the NEAREST occurrence of
    `spec`'s label within `spec.window_chars`, or `None` if no occurrence
    binds (no label in range, an excluding token sits in the same window —
    see `_FieldSpec.exclude_pattern` — or the gap between them reads as
    DERIVED arithmetic rather than a restatement — see
    `_DERIVATIONAL_GAP_RE`).

    Returns a distance rather than a bool so `find_sheet_mismatches` can run
    the nearest-numeral-wins tie-break below: two different numerals can
    each independently sit within a shared label's window (comparative
    prose — "AAPL P/E is 29.9 vs SPX 21.5" puts BOTH 29.9 and 21.5 inside
    24 chars of the one "P/E" token), and binding both to the sheet's
    single P/E field would let an off-ticker comparison figure convict an
    honest quote of a mismatch. Distance is what breaks that tie correctly:
    the label almost always sits nearer the number it actually labels than
    the one it merely shares a sentence with.
    """
    lo = max(0, numeral.start - spec.window_chars)
    hi = min(len(text), numeral.end + spec.window_chars)
    window = text[lo:hi]
    best: int | None = None
    for m in spec.label_pattern.finditer(window):
        label_start, label_end = lo + m.start(), lo + m.end()
        if spec.exclude_pattern is not None:
            # Scoped to a SHORT radius around THIS specific label match,
            # not the numeral-centered `window` — "forward" disambiguates
            # which "P/E" it modifies, and checking the whole numeral
            # window let an unrelated LATER "forward P/E" mention in a
            # long sentence exclude an EARLIER, correctly-trailing "P/E"
            # from binding at all ("Trailing P/E is 45.0x, and forward
            # P/E of 30.0x…" — the trailing figure's mismatch went
            # undetected because "forward" merely fell inside its
            # numeral's 24-char window, unrelated to which P/E occurrence
            # was actually being read). A small radius fixed to the LABEL
            # match — long enough for "forward P/E"/"P/E (forward)" either
            # order, short enough not to reach a second, unrelated
            # mention — keeps the exclusion local to the occurrence it is
            # actually disambiguating.
            ex_lo = max(0, m.start() - 12)
            ex_hi = min(len(window), m.end() + 12)
            if spec.exclude_pattern.search(window[ex_lo:ex_hi]):
                continue
        # A label whose OWN matched text overlaps the numeral's span is not
        # "near" it, it CONTAINS it — the label text itself carries a digit
        # ("52-week high" embeds "52", which `_extract_numerals` also finds
        # as its own standalone numeral). Binding "52" to `week52_high`
        # would compare the label's own decoration against the sheet's real
        # high, a self-collision found by this module's own negative tests
        # ("33.4% off its 52-week high" flagged "52" as a mismatched high).
        # Skip this occurrence entirely rather than treat it as distance 0
        # — distance 0 would make it WIN every tie-break against a numeral
        # that is genuinely being labelled.
        if label_start < numeral.end and numeral.start < label_end:
            continue
        # The GAP between numeral and label — whichever side the label
        # falls on — is what `_DERIVATIONAL_GAP_RE` inspects when it
        # applies (see below), not the whole window (a relational word
        # further away, outside the true gap, must not disqualify a
        # genuine adjacent restatement elsewhere in the same sentence).
        if label_end <= numeral.start:
            # LABEL then NUMBER ("the P/E is under 25", "P/E falls back
            # under 25", "RSI above 70"). Even a word from
            # `_DERIVATIONAL_GAP_RE` here ("under", "above", "below") is a
            # THRESHOLD/comparison claim about the labelled field's OWN
            # value, not a distance computed FROM it — "the P/E is under
            # 25" restates a P/E ceiling, it does not compute anything
            # relative to a reference point the way "X% off/below/above
            # THE HIGH" does. So the derivational check does NOT apply in
            # this direction; F6's kill_criterion shape ("P/E falls back
            # under 25") depends on this — it was the false negative that
            # first caught the over-broad, direction-blind version of this
            # rule.
            gap = text[label_end:numeral.start]
            dist = numeral.start - label_end
        else:
            # NUMBER then LABEL ("33.4% off the 52-week high", "12% below
            # the target"). THIS is the shape the audit names: the number
            # is a computed DELTA relative to the labelled reference point,
            # so a relational word here disqualifies the bind outright.
            gap = text[numeral.end:label_start]
            dist = label_start - numeral.end
            if _DERIVATIONAL_GAP_RE.search(gap):
                continue
        if best is None or dist < best:
            best = dist
    return best


def _sheet_values(profile: dict[str, Any], spec: _FieldSpec) -> list[float]:
    """The sheet's own value(s) for `spec`, scaled to the claim's unit —
    empty when the field is absent or not a real number, which is read as
    "nothing to compare", never as a mismatch (a sheet with no P/E cannot
    convict a claim of misstating one)."""
    out: list[float] = []
    for key in spec.profile_keys:
        raw = profile.get(key)
        if raw is None or isinstance(raw, bool):
            continue
        try:
            out.append(float(raw) * spec.sheet_scale)
        except (TypeError, ValueError):
            continue
    return out


@dataclass(frozen=True)
class SheetMismatch:
    """One labelled numeral in prose that disagreed with the sheet's own
    value for that field. `field_name` is `_FieldSpec.name` (telemetry-
    friendly, stable); `claimed`/`sheet` are both in the CLAIM's own unit,
    for a readable annotation."""

    field_name: str
    claimed_raw: str
    claimed_value: float
    sheet_value: float
    start: int
    end: int


def _nearest_numeral_per_spec(
    text: str, numerals: list[_Numeral]
) -> dict[str, tuple[_Numeral, int]]:
    """For each `_FieldSpec`, the single CLOSEST numeral that binds to its
    label (name → (numeral, distance)) — a spec with no binding numeral at
    all is simply absent from the returned dict.

    This is the fix for comparative prose sharing one label across two
    numbers ("AAPL P/E is 29.9 vs SPX 21.5" — see `_label_distance`'s
    docstring for the worked distances: "P/E" sits 4 chars from 29.9 and 16
    from 21.5). Keeping only the minimum-distance numeral per spec means the
    far numeral never binds at all, so it can never be reported as a
    mismatch against a field it was not actually restating.

    A genuine TIE (two numerals equidistant from the same label) resolves
    to NO bind for that spec, not an arbitrary pick — an annotator that
    cannot tell which of two equally-close numbers a label refers to must
    not guess, per this module's whole design constraint.
    """
    best: dict[str, tuple[_Numeral, int]] = {}
    tied: set[str] = set()
    for numeral in numerals:
        for spec in _FIELD_SPECS:
            dist = _label_distance(text, numeral, spec)
            if dist is None:
                continue
            current = best.get(spec.name)
            if current is None or dist < current[1]:
                best[spec.name] = (numeral, dist)
                tied.discard(spec.name)
            elif dist == current[1] and current[0] is not numeral:
                tied.add(spec.name)
    for name in tied:
        best.pop(name, None)
    return best


def find_sheet_mismatches(
    text: str | None, profile: dict[str, Any] | None
) -> list[SheetMismatch]:
    """Every labelled numeral in `text` that disagrees with `profile`'s own
    value for that field, beyond the claim's own formatting precision.

    Returns [] — never raises, never guesses — when: `text` is empty;
    `profile` is missing/None/not dict-shaped (unknowable is not
    unverifiable, see module docstring); no numeral in `text` binds to any
    label in `_FIELD_SPECS`; or every bound numeral matches the sheet. This
    is the SAME vacuous-pass shape `risk_officer.py`'s `_quotation_check`
    uses for "no numerals at all" — an absence of findings here means
    "nothing to annotate", not "verified clean" (this checker does not
    attempt derived arithmetic, so plenty of real prose numerals are simply
    outside what it looks at, by design).

    Each field in `_FIELD_SPECS` binds to AT MOST ONE numeral per call —
    the closest one, per `_nearest_numeral_per_spec` — so a field cannot be
    reported as mismatched twice, and a numeral genuinely nearer a
    different label than the one it happens to share a sentence with is
    never wrongly convicted of misstating that other field.

    Never raises past this call site: any internal error degrades to "found
    nothing" (empty list), which is the safe direction for an ANNOTATOR —
    see module docstring's "Failure posture".
    """
    try:
        if not text or not isinstance(profile, dict) or not profile:
            return []
        numerals = _extract_numerals(text)
        if not numerals:
            return []
        nearest = _nearest_numeral_per_spec(text, numerals)
        mismatches: list[SheetMismatch] = []
        for spec in _FIELD_SPECS:
            hit = nearest.get(spec.name)
            if hit is None:
                continue
            numeral, _dist = hit
            sheet_vals = _sheet_values(profile, spec)
            if not sheet_vals:
                continue
            if _numeral_is_corroborated(numeral, sheet_vals):
                continue
            # A genuine mismatch: report against the FIRST sheet value
            # (there is only ever one for every field in `_FIELD_SPECS`
            # today — `profile_keys` is a tuple for forward-compat, not
            # because any current spec has more than one key).
            mismatches.append(SheetMismatch(
                field_name=spec.name,
                claimed_raw=numeral.raw,
                claimed_value=numeral.value,
                sheet_value=sheet_vals[0],
                start=numeral.start,
                end=numeral.end,
            ))
        # Report in TEXT order (the order the reader encounters them), not
        # `_FIELD_SPECS` declaration order — the loop above iterates specs,
        # so without this the annotation could otherwise name a later-in-
        # text field before an earlier one.
        mismatches.sort(key=lambda m: m.start)
        return mismatches
    except Exception:  # noqa: BLE001 — degrade to "nothing found", never crash a render
        return []


# Millions-scaled fields (`_FieldSpec.sheet_scale == 1_000_000.0`) render in
# the annotation the SAME "$X,XXXM" shape the sheet itself renders them in
# (`fundamentals.py::_company_size_line`: `f"market cap ${data['market_cap']
# :,}M"`) — quoting the sheet's own literal figure, not a raw-dollar
# conversion of it, is both more readable (nobody reads "$1,200,000,000" as
# fast as "$1,200M") and more literally true to "the sheet's own figure".
_MILLIONS_SCALED_FIELDS = frozenset(
    {"market_cap", "free_cash_flow", "gross_debt", "gross_cash"}
)


def _sheet_value_phrase(mismatch: SheetMismatch) -> str:
    """The sheet's own value, formatted for the annotation. Millions-scaled
    fields render in the sheet's own "$X,XXXM" shape (`sheet_value` there is
    the resolved raw-dollar amount, divided back down by the same
    `sheet_scale` its spec applied); every other field renders as a plain
    number in its own unit (a P/E multiple, an RSI reading, a percent
    without the sign implied one way or the other)."""
    if mismatch.field_name in _MILLIONS_SCALED_FIELDS:
        return f"${mismatch.sheet_value / 1_000_000.0:,.0f}M"
    return f"{mismatch.sheet_value:g}"


def annotate_sheet_mismatches(
    text: str | None, profile: dict[str, Any] | None
) -> str | None:
    """Append one `[AMI …]` note per genuine sheet mismatch found in `text`,
    naming the sheet's own value for each. Returns `text` byte-identical
    when `find_sheet_mismatches` finds nothing — no note on a clean turn,
    the same "silence on the honest case" rule `_annotate_rr_against_levels`
    and `risk_officer.py`'s `_annotated_if_unverified` both already follow.
    `text=None` (e.g. F6's `kill_criterion` when the CIO stated none) passes
    straight through as `None` — nothing to check, nothing to annotate.

    The claim is NOT rewritten in place (unlike the DEF095 R:R rewrite) —
    this checker has lower confidence in what the agent MEANT than the
    geometry check does (a mis-stated P/E is not a triple AMI can
    recompute), so it states both figures and lets the reader judge, the
    same posture `_annotate_direction_against_price` already takes for
    exactly this reason ("AMI does not know what the PM meant to say").
    """
    mismatches = find_sheet_mismatches(text, profile)
    if not mismatches:
        return text
    notes = []
    for m in mismatches:
        # `claimed_raw` can carry one trailing space — `_NUMERAL_RE`'s
        # optional `\s?` before the (also optional) magnitude letter can
        # match the space even when no letter follows it. Stripped only
        # here, at render time, never in the shared regex/`_Numeral.raw`
        # itself: that pattern is reused byte-for-byte from `risk_officer.py`
        # (see module docstring) and this cosmetic quirk is inert there
        # (only `.value` is compared, `.raw` is never rendered) — changing
        # the shared pattern to fix a rendering-only wrinkle here would be
        # an unreviewed behavior change to A2's already-accepted regex.
        quoted = m.claimed_raw.strip()
        notes.append(
            f"AMI checked “{quoted}” against the fact sheet: "
            f"the sheet's own figure is {_sheet_value_phrase(m)}, not "
            f"{quoted}."
        )
    return text + "\n\n[" + " ".join(notes) + " These are the figures of record.]"

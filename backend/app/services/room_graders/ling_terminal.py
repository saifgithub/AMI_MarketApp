"""CR267: Ling-only wording for the `terminal_vulnerability` question (`term=v2`).

Why it exists. The shared question ("an unresolved fatal-flaw type risk ... raised and nobody
answered it") is an unconditional veto in the coded rule (`ALWAYS_PASS_IF_YES`). On Ling it flagged
95 of 200 Bursa Rooms and 171 of 300 US fit Rooms (DeepInfra: 125 of 300), mostly for weakness that
is not terminal: thin margins, ROE below WACC, cash burn. A veto should only fire on a risk the stop
cannot contain.

What changes, and only for Ling (DeepInfra never sees this module; `tests/unit/test_cr267_ling_terminal_v2.py`
pins that):

1. The question is a definition, not a feeling. A terminal vulnerability is a specific, evidenced risk
   to THIS company that would cause a loss the stop-loss and position size cannot contain, in one of
   seven allowed categories. A list of what is NOT terminal sends weak earnings, cash burn, leverage
   and the like to the other questions.
2. The reply is JSON with five fields (answer, name, category, evidence, why it is still open). The
   prompt asks for all of them; CODE enforces them. A "yes" counts only if every field is filled, the
   category is one of the seven ids, and the evidence is grounded (below). A "yes" that fails is
   recorded as "no" with `terminal_rejected` naming why, and is counted. Never silent.
3. Five phrasings of the QUESTION line only; the definition, categories, not-terminal list, open/closed
   rule and evidence rule are one block shared by all five. Majority wins, 3-2 is "close", the shared
   `SPLIT_CLOSE_MIN_MINORITY`. The fields of the winning "yes" are copied from the lowest-numbered
   phrasing among the validated "yes" votes.

Grounding (`is_grounded`) is deterministic and deliberately simple. Both texts are normalised
(lower-case, thousands commas removed, every other non-alphanumeric run, except a decimal point
between digits, becomes a space). `terminal_evidence` is grounded when EITHER
  (a) a significant number in it also appears as a whole number token in the Room's rendered
      transcript: significant = has a decimal point, or three or more digits and is not a bare
      year (1990-2100); or
  (b) a distinctive phrase in it appears verbatim in the transcript: four consecutive word tokens
      of which at least two are not stop words.
It proves the model quoted the Room, not that the quote supports the category; that is what the
category list, the NOT TERMINAL list and the human labels (Step 2) are for. The grader reads only the
desk turns, so "the Room's materials" here is the rendered transcript; the fact sheet itself is not
part of what the grader is handed.

The tag goes into the Ling grader version, so a Room graded with this wording is keyed apart.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Sequence

from app.services.llm_gateway import OutputConstraint
from app.services.room_grader_contract import Answer, QuestionAnswer, QuestionId
from app.trading_math.markets import Market, market_for

TERMINAL_V2_TAG = "term=v2"

CATEGORIES: tuple[str, ...] = (
    "pn17_gn3",
    "going_concern_audit",
    "debt_default",
    "dilutive_restructuring",
    "suspension_delisting",
    "fraud_regulatory",
    "revenue_loss",
)
FIELDS: tuple[str, ...] = (
    "terminal_name", "terminal_category", "terminal_evidence", "terminal_open_because",
)
# A reply carries five short fields; the shared 64-token budget would cut it.
MAX_TOKENS = 700

_STR_OR_NULL = {"type": ["string", "null"]}
CONSTRAINT = OutputConstraint(
    name="room_grader_terminal",
    json_schema={
        "type": "object",
        "properties": {
            "answer": {"type": "string", "enum": ["yes", "no"]},
            "terminal_name": _STR_OR_NULL,
            "terminal_category": {"type": ["string", "null"], "enum": [*CATEGORIES, None]},
            "terminal_evidence": _STR_OR_NULL,
            "terminal_open_because": _STR_OR_NULL,
        },
        "required": ["answer", "terminal_name", "terminal_category", "terminal_evidence",
                     "terminal_open_because"],
        "additionalProperties": False,
    },
)

SYSTEM = (
    "You grade one finished investment-committee debate. Answer the single question at the end, "
    "using only what the debate says. Reply with JSON only, in exactly the format the question gives."
)

PHRASINGS: tuple[str, ...] = (
    "Does a terminal vulnerability remain open at the end of this debate?",
    "At the close of the debate, is a terminal vulnerability, as defined below, still unresolved?",
    "Is there a specific risk to this company, in one of the allowed categories, that the stop-loss "
    "cannot contain and that the debate left open?",
    "Did the debate leave open a risk that could permanently impair this equity or make it "
    "untradeable, which a stop would not protect against?",
    "After the last turn, does any stop-defeating risk (loss of the equity, or a stock that cannot "
    "be traded) stand unanswered, with evidence from this debate?",
)

_DEFINITION = """DEFINITION
A terminal vulnerability is a specific, evidenced risk to THIS company that, if it
materialises within the trade's horizon, would cause a loss that the stop-loss and
position size cannot contain: a permanent impairment of the equity, or a stock that
cannot be traded. Apply the stop test: "If this happened tomorrow, would the stop
protect the position?" If yes, it is NOT terminal."""

_CATEGORIES_BURSA = """ALLOWED CATEGORIES (answer "yes" only if the risk fits one):
- pn17_gn3: PN17 / GN3 status, or a concrete trigger for it in the figures
- going_concern_audit: going-concern doubt; qualified, adverse or disclaimed audit opinion
- debt_default: missed payment, covenant breach, or debt due within the horizon with no
  stated refinancing or cash to meet it
- dilutive_restructuring: restructuring, rights issue or debt-to-equity swap that would
  wipe out or heavily dilute existing shareholders
- suspension_delisting: trading suspension or delisting risk, including late reports
- fraud_regulatory: fraud, accounting irregularity, or active SC / Bursa / MACC action
  against the company or its directors
- revenue_loss: loss of a licence, concession or customer behind most of revenue,
  with no replacement"""

# US Rooms: the category ids are identical; only the two regime-specific lines are reworded.
_CATEGORIES_US = (
    _CATEGORIES_BURSA
    .replace(
        "- pn17_gn3: PN17 / GN3 status, or a concrete trigger for it in the figures",
        "- pn17_gn3: PN17 / GN3 status (Bursa), or an exchange continued-listing deficiency "
        "notice (US),\n  or a concrete trigger for it in the figures",
    )
    .replace(
        "active SC / Bursa / MACC action\n  against the company or its directors",
        "active SC / Bursa / MACC action\n  (Bursa) or SEC / DOJ action (US) against the company or its directors",
    )
)

_REST = """NOT TERMINAL (send these to the other questions, never answer "yes" for them):
weak or falling earnings, margin compression, ROE or ROIC below WACC, negative free
cash flow on its own, an underfunded dividend, high leverage on its own, net debt above
market cap on its own, valuation, volatility, thin liquidity, sector or macro risk,
a catalyst that may slip, event risk around results.

OPEN vs CLOSED
Open = it was raised and the debate ended without (a) evidence it is not present, or
(b) a quantified reason it cannot occur within the horizon. Management assurance alone
does not close it.

EVIDENCE RULE
Cite the exact figure, filing or statement from this Room's materials, and where it
appeared (fact sheet, which analyst, which turn). Do not use outside knowledge. Do not
infer a category from general weakness: "cash burn could lead to default" is not
debt_default unless a maturity, covenant or missed payment is in the materials.

If you cannot fill every field below, the answer is "no".

RETURN JSON ONLY:
{
  "answer": "yes" | "no",
  "terminal_name": "<one sentence naming the specific risk>",
  "terminal_category": "<one allowed category>",
  "terminal_evidence": "<figure or statement, with where it appeared>",
  "terminal_open_because": "<what was argued against it and why that fell short>"
}
For "no", return the answer and leave the other fields null."""


def question_block(ticker: str, phrasing: int) -> str:
    """The text after the transcript: the QUESTION line (the only part that varies by phrasing)
    and the shared block, with the market's wording of the two regime-specific categories."""
    cats = _CATEGORIES_BURSA if market_for(ticker) is Market.MY else _CATEGORIES_US
    return f"QUESTION: {PHRASINGS[phrasing]}\n\n{_DEFINITION}\n\n{cats}\n\n{_REST}"


# ── grounding ───────────────────────────────────────────────────────────────

_STOP = frozenset(
    "the a an and or of to in on at for with by from as is are was were be been it its this that "
    "these those has have had not no but if than then so we they their our his her which who "
    "would could may might will can".split()
)
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3})")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


def _norm(text: str) -> str:
    t = _THOUSANDS.sub("", (text or "").lower())
    t = t.replace("×", "x").replace("−", "-")
    return re.sub(r"[^a-z0-9.]+|(?<![0-9])\.|\.(?![0-9])", " ", t)


def _significant(num: str) -> bool:
    if "." in num:
        return True
    if len(num) < 3:
        return False
    return not (len(num) == 4 and 1990 <= int(num) <= 2100)


def is_grounded(evidence: str, haystack: str) -> bool:
    ev, hay = _norm(evidence), _norm(haystack)
    hay_nums = set(_NUM.findall(hay))
    if any(n in hay_nums for n in _NUM.findall(ev) if _significant(n)):
        return True
    words = _TOKEN.findall(ev)
    padded = f" {' '.join(_TOKEN.findall(hay))} "
    for i in range(len(words) - 3):
        gram = words[i:i + 4]
        if sum(w not in _STOP for w in gram) >= 2 and f" {' '.join(gram)} " in padded:
            return True
    return False


# ── one vote ────────────────────────────────────────────────────────────────

def _clean(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_vote(text: str, phrasing: int, haystack: str) -> QuestionAnswer:
    """One phrasing's reply as a vote. A reply that is not JSON, or whose answer is not yes/no, is
    not computable (counted as unparsed by the caller). A "yes" that fails the checks becomes a "no"
    carrying `terminal_rejected`; the raw fields stay in `detail` so the rejection can be audited."""
    q = QuestionId.TERMINAL_VULNERABILITY
    body = (text or "").strip()
    if body.startswith("```"):
        body = body.strip("`").removeprefix("json").strip()
    try:
        obj = json.loads(body)
    except ValueError:
        obj = None
    answer = str(obj.get("answer", "")).strip().lower() if isinstance(obj, dict) else ""
    if answer not in ("yes", "no"):
        return QuestionAnswer(q, Answer.NOT_COMPUTABLE, rationale="reply was not a yes/no answer",
                              detail={"phrasing": phrasing})
    fields = {k: _clean(obj.get(k)) for k in FIELDS}
    if answer == "no":
        return QuestionAnswer(q, Answer.NO, detail={"phrasing": phrasing, **{k: None for k in FIELDS},
                                                    "terminal_rejected": None})
    rejected = None
    empty = [k for k, v in fields.items() if v is None]
    if empty:
        rejected = "empty_field:" + ",".join(empty)
    elif fields["terminal_category"] not in CATEGORIES:
        rejected = "category_not_allowed"
    elif not is_grounded(fields["terminal_evidence"] or "", haystack):
        rejected = "evidence_not_grounded"
    detail = {"phrasing": phrasing, **fields, "terminal_rejected": rejected}
    return QuestionAnswer(q, Answer.NO if rejected else Answer.YES, detail=detail,
                          rationale=f"yes rejected: {rejected}" if rejected else "")


# ── the five votes ──────────────────────────────────────────────────────────

def rejection_counts(votes: Sequence[QuestionAnswer]) -> dict[str, int]:
    """{reason: number of yes votes refused for it}, for the grader result's `extra`."""
    out: dict[str, int] = {}
    for v in votes:
        reason = (v.detail or {}).get("terminal_rejected")
        if reason:
            out[reason] = out.get(reason, 0) + 1
    return out


def tally_votes(votes: Sequence[QuestionAnswer], min_minority: int) -> QuestionAnswer:
    """Majority of the validated votes, 3-2 marked close. A vote that is not yes/no leaves the
    question not computable, as for the other averaged questions. The yes fields come from the
    lowest-numbered phrasing among the validated yes votes. `terminal_rejected` on the result
    summarises every rejected yes vote, win or lose."""
    q = QuestionId.TERMINAL_VULNERABILITY
    if not votes:
        return QuestionAnswer(q, Answer.NOT_COMPUTABLE, rationale="no phrasing answered")
    if any(v.answer not in (Answer.YES, Answer.NO) for v in votes):
        return QuestionAnswer(q, Answer.NOT_COMPUTABLE,
                              rationale="a phrasing returned no yes/no answer")
    yes = sum(v.answer is Answer.YES for v in votes)
    no = len(votes) - yes
    won = yes > no
    reasons = [str((v.detail or {}).get("terminal_rejected")) for v in votes
               if (v.detail or {}).get("terminal_rejected")]
    rejected = (
        f"{len(reasons)} of {len(votes)} yes votes refused: "
        + "; ".join(f"{r} x{reasons.count(r)}" for r in sorted(set(reasons)))
        if reasons else None
    )
    detail: dict[str, Any] = {k: None for k in FIELDS}
    detail["terminal_rejected"] = rejected
    if won:
        chosen = min((v for v in votes if v.answer is Answer.YES),
                     key=lambda v: (v.detail or {}).get("phrasing", 0))
        detail.update({k: (chosen.detail or {}).get(k) for k in FIELDS})
        detail["terminal_chosen_phrasing"] = (chosen.detail or {}).get("phrasing")
    split = min(yes, no) >= min_minority
    return QuestionAnswer(
        question=q,
        answer=Answer.YES if won else Answer.NO,
        close=split,
        rationale=f"{yes}/{len(votes)} phrasings yes" + (" (split)" if split else ""),
        detail=detail,
    )

"""Tolerant JSON extraction from LLM free-text output.

Shared by brief_engine.py (BriefProposal parsing) and room_runner.py
(Portfolio Manager verdict parsing, DEF056) — LLMs wrap JSON in ```json
fences, add leading/trailing prose, or otherwise don't return pure JSON.
"""

from __future__ import annotations

import json
import re


def _close_truncated_object(candidate: str) -> str | None:
    """Rebuild a syntactically complete object from one the decoder ran out of.

    DEF258 — the PM's decode budget is a ceiling, and when it is reached the
    JSON stops mid-token: no closing quote, no closing brace. Every field is
    intact up to that point, so the DECISION (`action`, `size_pct`, the levels)
    is present and only the tail of the long trailing string is lost. Discarding
    it costs the whole verdict; closing it costs the tail of one sentence.

    Walks the string once tracking quote/escape state and brace depth, drops any
    trailing partial token, then closes the open string and the open containers.
    Returns None when the object was not in fact truncated (balanced already) or
    when nothing survives the trim — a genuinely malformed object must still be
    rejected, not guessed at.
    """
    in_string = False
    escaped = False
    stack: list[str] = []
    # The last prefix known to end on a COMPLETE member, with the container
    # stack as it stood there. Only commas and closers qualify: a bare `"` is
    # ambiguous — it closes keys as well as values, and cutting on a key's quote
    # yields `{"size_pct"}`, which is not JSON.
    safe: tuple[int, tuple[str, ...]] | None = None
    for i, ch in enumerate(candidate):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if in_string:
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            safe = (i + 1, tuple(stack))
        elif ch == ",":
            safe = (i, tuple(stack))
    if not stack and not in_string and not escaped:
        return None

    if escaped:
        # A dangling backslash would escape the quote appended below.
        candidate = candidate[:-1]
        in_string = True

    if in_string:
        # Mid-sentence inside a string value — the common case, and the only one
        # where the clipped content is worth keeping: close the quote in place.
        repaired = candidate + '"'
        open_containers = stack
    else:
        # Outside a string the tail is a partial number, keyword or valueless
        # key (`2.`, `tru`, `"narration":`). Fall back to the last complete
        # member and drop everything after it.
        if safe is None:
            return None
        cut, open_containers = safe[0], list(safe[1])
        repaired = candidate[:cut]

    for opener in reversed(open_containers):
        repaired += "}" if opener == "{" else "]"
    return repaired


class ConflictingDecision:
    """RETRO-PM-FLOOR round 3 (MINOR-2 residual 1) — a sentinel distinct
    from `None`, returned by `extract_json_object` when it found a real,
    parseable decision AND a second, conflicting one after it.

    Round 2's fix returned bare `None` for this case, indistinguishable from
    "genuinely unparseable" — and `room_runner.py`'s caller treats a `None`
    verdict as DEF058's cue to run ONE reformat retry, which DEF067 lets
    upgrade to APPROVE (never downgrade). So a reply carrying a retracted
    draft APPROVE and a final PASS could still end up re-asked, and the
    model's second read — not the room's floor — decided the conflict, in
    the APPROVE direction only. The auditor's own fix: "on a detected
    conflict, return PASS directly — never re-ask." That decision belongs to
    the PM-verdict caller (only room_runner.py's `_parse_pm_verdict` has a
    concept of PASS/APPROVE — `brief_engine.py`'s and the Risk Officer's own
    `extract_json_object` calls parse shapes with no `action` key, so this
    sentinel can never reach them; see `_extract_second_decision`'s
    `"action" in decoded` scoping below), so this class only marks the fact
    for the caller to act on — it carries no behaviour itself.
    """

    __slots__ = ("first", "second")

    def __init__(self, first: dict, second: dict) -> None:
        self.first = first
        self.second = second


def _extract_second_decision(tail: str) -> dict | None:
    """MINOR-2 helper — is there ANOTHER complete `{"action": …}`-shaped
    object anywhere in `tail`?

    RETRO-PM-FLOOR round 3 (MINOR-2 residual 2): scans EVERY top-level object
    in `tail`, not just the first `{`. The auditor's measured gap was DEF398's
    own shape — the PM quoting its own "begin with '{' and end with '}'"
    contract back at us inside the trailing prose puts a stray, non-decision
    brace before the real second decision, so a scan that stopped at the
    first `{` (round 2's version) walked into the quoted brace, failed to
    decode a dict with `action`, and returned `None` — hiding a real
    conflicting decision sitting right after it.

    Deliberately simple (repeated brace-scan + `raw_decode`, not the
    DEF352/DEF398 recovery machinery above): this only ever answers "is a
    second decision sitting in the part we didn't use", never "recover a
    verdict from that second object" — a tail with no decision-shaped object
    anywhere correctly returns None here, which is `extract_json_object`'s
    cue to keep the FIRST decision (no ambiguity found), not to manufacture
    one from a scrap.
    """
    pos = 0
    while True:
        first = tail.find("{", pos)
        if first == -1:
            return None
        try:
            decoded, end = json.JSONDecoder(strict=False).raw_decode(tail[first:])
        except json.JSONDecodeError:
            # Not a complete object starting here (e.g. a stray/quoted brace
            # in prose) — keep scanning from the next character, not the
            # next `{`, so a decode failure can't skip past a real object
            # that starts one character later.
            pos = first + 1
            continue
        if isinstance(decoded, dict) and "action" in decoded:
            return decoded
        pos = first + end


def extract_json_object(
    text: str, *, repair_truncated: bool = False
) -> dict | ConflictingDecision | None:
    """Extract the first JSON object found in `text`, tolerating ```json
    fences and surrounding prose. Returns None if nothing parses.

    `repair_truncated` is opt-in (DEF258): only the PM verdict path asks for it,
    and only after a strict read has already failed, because a repaired object
    is a partial read and the caller must disclose it as one.

    RETRO-PM-FLOOR round 3 (MINOR-2 residual 1): can also return a
    `ConflictingDecision` instead of `None` — see that class's docstring.
    Only ever happens for text containing an `action` key (the PM/CIO
    verdict shape), so `brief_engine.py`'s and the Risk Officer's own calls
    (neither shape carries `action`) can never receive one; callers that
    only ever expect `dict | None` and treat a truthy non-None specially
    would need updating, but none currently do — `_extract_second_decision`'s
    `"action" in decoded` scoping is what keeps this safe today.
    """
    if not text:
        return None
    cleaned = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    candidate = m.group(1) if m else cleaned
    if not candidate.startswith("{"):
        first = candidate.find("{")
        last = candidate.rfind("}")
        if first == -1:
            return None
        if last == -1 or last <= first:
            # DEF258: an object that opened and never closed. Without the repair
            # pass there is nothing to salvage, so keep the original rejection.
            if not repair_truncated:
                return None
            candidate = candidate[first:]
        else:
            candidate = candidate[first : last + 1]
    try:
        # DEF256 — `strict=False` permits raw control characters INSIDE strings.
        # Nothing else is relaxed: trailing commas, single quotes and unquoted
        # keys still fail, so a genuinely malformed object is still rejected.
        #
        # Under the default `strict=True`, a model that writes a real line break
        # inside a string value instead of the two characters \n makes the WHOLE
        # object unparseable — and for the PM verdict that is not a degraded
        # read, it is a discarded decision: `_parse_pm_verdict` returns no
        # verdict and the caller fails safe to PASS (DEF059), so a real APPROVE
        # is lost over a whitespace character. DEF236 made this reachable by
        # design when it asked the PM for bullets inside `narration`; the prompt
        # also asks for \n, but P2 is explicit that a prompt instruction is not
        # a control, so this is the control.
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError:
        pass
    # DEF352 — trailing prose AFTER a complete object.
    #
    # The trim above only runs when the reply does NOT start with `{`, so a
    # reply that opens with the object and then adds a sentence — measured
    # shape: `{...}\n\nWorked example — classroom simulation, not financial
    # advice.` — reached json.loads whole and was rejected outright, discarding
    # a decision the model had already made correctly. Measured at 42.6% of
    # Risk Officer replies on the CR201 production assembly (2026-08-21), vs
    # 1.5% on CR197's, and isolated to the simulated-portfolio block being
    # present. The JSON contract already says "No prose outside it"; P2 is
    # explicit that a prompt instruction is not a control, so this is the
    # control. Deliberately NOT gated on `repair_truncated`: nothing is being
    # repaired or guessed here — the object is complete, only the tail is cut.
    if candidate.startswith("{"):
        # DEF398 — the trailing prose may itself contain a brace, and then the
        # `rfind` below lands inside the prose rather than on the object's own
        # closer, so the trimmed candidate is malformed and the verdict is lost
        # anyway. Measured shape: the PM appends a `DATA I LACKED:` section that
        # QUOTES its own JSON-only contract back at us verbatim — "begin with
        # '{' and end with '}'" — so the quoted rule is precisely what defeats
        # the DEF352 recovery. raw_decode reads the FIRST complete value from
        # position 0 and reports where it ended, which cannot be confused by
        # anything written after it.
        try:
            decoded, _end = json.JSONDecoder(strict=False).raw_decode(candidate)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            # RETRO-PM-FLOOR round 1 (auditor U68, MINOR-2) — `raw_decode`
            # reads the FIRST complete object and stops there (DEF398's own
            # fix), so a reply carrying a draft decision, a retraction, and a
            # DIFFERENT final decision — e.g. `Draft: {"action":"APPROVE",…}
            # -- on reflection I decline. {"action":"PASS",…}` — reads as the
            # draft. Before DEF398 the same reply was unparseable and failed
            # safe to PASS (DEF059); "first object wins" must not turn that
            # into "first DECISION wins" when a second, conflicting decision
            # is sitting right there in the tail. Scoped narrowly to `action`
            # (the PM/CIO verdict shape) so the generic two-object case
            # `test_the_first_object_wins_when_the_pair_is_not_a_decision_conflict`
            # pins (no `action` key at all) is untouched, as are
            # brief_engine's/portfolio_finding's non-verdict JSON shapes,
            # which never carry this key.
            if "action" in decoded:
                _tail = candidate[_end:]
                _second = _extract_second_decision(_tail)
                if _second is not None and _second.get("action") != decoded.get("action"):
                    # RETRO-PM-FLOOR round 3 (MINOR-2 residual 1) — round 2
                    # returned bare `None` here, indistinguishable from
                    # "genuinely unparseable" to the caller, which let
                    # DEF058's reformat retry re-ask the model and DEF067
                    # upgrade the reply to APPROVE. A sentinel lets
                    # `room_runner.py` fail straight to PASS instead.
                    return ConflictingDecision(decoded, _second)
            return decoded
        last = candidate.rfind("}")
        if last > 0 and last + 1 < len(candidate):
            try:
                trimmed = json.loads(candidate[: last + 1], strict=False)
            except json.JSONDecodeError:
                trimmed = None
            if isinstance(trimmed, dict):
                return trimmed
    if not repair_truncated:
        return None
    closed = _close_truncated_object(candidate)
    if closed is None:
        return None
    try:
        result = json.loads(closed, strict=False)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None

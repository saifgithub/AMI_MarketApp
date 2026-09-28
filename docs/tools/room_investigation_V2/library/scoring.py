"""Deterministic scoring over Room run records — the CR247 phase-gate instrument.

Every metric CR247's gates decide pass/fail on (verdict stability, baseline-
vs-candidate diffs, outcome quality, producer→consumer conviction consistency)
is computed HERE, in code — LLMs never compute scores (house rule; CR247 SPEC
standing rule). A gate that an LLM scored would itself be unverifiable, so this
module is pure stdlib, pure functions, no I/O beyond the file reads its
callers hand it paths to.

v1 compatibility: `load_records` reads the JSONL shapes v1's
`docs/tools/room_investigation/` scripts wrote — repeat files
(`draw`/`ticker`/`risk_score`/`user_id`/`triggered_at`/`status`/`verdict`/
`duration_ms`), sweep files (adds `spot_price`), batch files (adds
`batch_id`/`ablation`/`finished_at`) — so v2 baselines diff against draws that
already exist in `out/` (DESIGN §7.1).

Threshold provenance: CR247's SPEC pins no numeric verdict-stability gate, so
`stability_report`'s default `min_agreement` is a pending-calibration 0.8 per
DESIGN §7 decision 3 — SPEC values first when one lands, calibrated after the
first baseline with recorded rationale, never tweaked silently.

Gate checks: `gate_report` is the CR247 D26 phase gate (Saiful 2026-09-29) —
per-convene FAIL-LOUDLY verification that every expected agent call exists,
every prose turn carries its STANCE envelope, every portfolio_manager draw
parses as JSON, and no turn sits at the token ceiling. It takes a
dependency-injected audit module (anything with `list_calls`/`get_field`,
optionally `call_metrics`) so this module stays importable without audit_db,
and inclusive `after`/`before` created_at window bounds because deterministic
per-arm user_ids mean a killed-then-resumed arm shares one user_id across the
partial and the completed convene.
"""

from __future__ import annotations

import inspect
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MIN_AGREEMENT = 0.8

_SIDE_PATTERN = re.compile(r"Side:\s*([A-Z]+)")
_STANCE_PATTERN = re.compile(r"\[STANCE:\s*([^|]+?)\s*\|", re.IGNORECASE)
_CONVICTION_PATTERN = re.compile(r"\bCONVICTION:\s*([A-Za-z]+)", re.IGNORECASE)

# Producer→consumer chain, read from backend/app/services/room_runner.py's
# PHASES (2026-09-28): ANALYSTS run parallel and blind (CR077 — nothing to
# audit); RESEARCHERS speak first (Bull/Bear order seeded per run_id, CR219
# R58 — order is not a dependency); each later phase reads the full transcript
# so far. The audited links are the ones where a quantized STANCE/CONVICTION
# value must survive the hand-off verbatim (room_prompts.py's scoreboard).
_CONVICTION_CHAIN: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("research_manager", ("bull_researcher", "bear_researcher")),
    ("trader", ("research_manager",)),
    ("portfolio_manager", (
        "trader",
        "aggressive_debator",
        "conservative_debator",
        "neutral_debator",
    )),
)

_CONVICTION_FIELDS = ("stance", "conviction")

# The convene's expected call shape (CR247 D26, 2026-09-29): the 11 prose
# agents exactly once each, plus MIN_PM_DRAWS portfolio_manager draws (a 6th
# PM row is the recovery reformat draw, legitimate) — 16..18 rows total.
EXPECTED_PROSE_AGENTS: tuple[str, ...] = (
    "fundamentals_analyst",
    "market_analyst",
    "news_analyst",
    "social_media_analyst",
    "bull_researcher",
    "bear_researcher",
    "research_manager",
    "trader",
    "aggressive_debator",
    "conservative_debator",
    "neutral_debator",
)
PM_AGENT = "portfolio_manager"
MIN_PM_DRAWS = 5
TOTAL_CALLS_RANGE = (16, 18)


@dataclass(frozen=True)
class GateFinding:
    user_id: str
    agent_id: str
    kind: str
    detail: str


@dataclass(frozen=True)
class GateReport:
    user_id: str
    ok: bool
    findings: list[GateFinding]
    stances: dict[str, str]


@dataclass(frozen=True)
class StabilityRow:
    group: tuple
    n: int
    actions: Counter
    top_action: str
    agreement: float
    stable: bool


@dataclass(frozen=True)
class ConsistencyFinding:
    consumer_agent: str
    producer_agent: str
    field: str
    producer_value: str
    consumer_value: str | None
    consistent: bool
    detail: str


def load_records(path: Path) -> list[dict]:
    """Read a v1-format JSONL run file, tolerating all three v1 variants.

    Blank lines are skipped (v1 appends under a lock but a truncated tail
    write leaves one). A malformed line raises ValueError naming the line
    number — a silently skipped record would bias every metric downstream.
    """
    records: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: line {lineno}: malformed JSON: {exc}") from exc
    return records


def verdict_distribution(
    records: list[dict],
    *,
    group_by: tuple[str, ...] = ("ticker",),
) -> dict[tuple, Counter]:
    """Count `verdict.action` per group; missing group keys bucket as "?",
    a missing/None verdict counts as NO_VERDICT — never a crash on a
    partial record."""
    dist: dict[tuple, Counter] = {}
    for rec in records:
        key = tuple(rec.get(k, "?") for k in group_by)
        verdict = rec.get("verdict")
        action = verdict.get("action") if isinstance(verdict, dict) else None
        dist.setdefault(key, Counter())[action if action is not None else "NO_VERDICT"] += 1
    return dist


def stability_report(
    records: list[dict],
    *,
    group_by: tuple[str, ...] = ("ticker",),
    min_agreement: float = DEFAULT_MIN_AGREEMENT,
) -> list[StabilityRow]:
    """Per-group verdict stability: agreement = top action's share of n.

    `min_agreement` defaults to DEFAULT_MIN_AGREEMENT (0.8), a
    pending-calibration value: CR247's SPEC gates do not pin a number, and
    DESIGN §7.3 says SPEC values first, calibrated after the first baseline
    with recorded rationale. Ties on the top action break alphabetically so a
    report is reproducible regardless of record order.
    """
    rows = []
    for group, actions in verdict_distribution(records, group_by=group_by).items():
        n = sum(actions.values())
        top_action, top_count = sorted(actions.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        agreement = top_count / n
        rows.append(StabilityRow(
            group=group,
            n=n,
            actions=actions,
            top_action=top_action,
            agreement=agreement,
            stable=agreement >= min_agreement,
        ))
    return sorted(rows, key=lambda r: tuple(map(str, r.group)))


def diff_batches(
    baseline_path: Path,
    candidate_path: Path,
    *,
    group_by: tuple[str, ...] = ("ticker",),
) -> str:
    """Plain-text baseline-vs-candidate stability table for CR gate reviews.

    One row per group present in either file. FLIPPED where the top action
    differs, DESTABILIZED/STABILIZED where the stable flag moved. A group
    missing on one side renders "—" cells — a one-sided group is a finding,
    not a crash."""
    base = {r.group: r for r in stability_report(load_records(baseline_path), group_by=group_by)}
    cand = {r.group: r for r in stability_report(load_records(candidate_path), group_by=group_by)}

    def cell(row: StabilityRow | None) -> str:
        if row is None:
            return "—"
        mark = "stable" if row.stable else "UNSTABLE"
        return f"{row.top_action} {row.n}x agr={row.agreement:.2f} {mark}"

    groups = sorted(base.keys() | cand.keys(), key=lambda g: tuple(map(str, g)))
    labels = ["/".join(map(str, g)) for g in groups]
    base_cells = [cell(base.get(g)) for g in groups]
    cand_cells = [cell(cand.get(g)) for g in groups]
    flags = []
    for g in groups:
        b, c = base.get(g), cand.get(g)
        marks = []
        if b is not None and c is not None:
            if b.top_action != c.top_action:
                marks.append("FLIPPED")
            if b.stable and not c.stable:
                marks.append("DESTABILIZED")
            elif c.stable and not b.stable:
                marks.append("STABILIZED")
        flags.append(" ".join(marks))

    w0 = max([len("GROUP"), *(len(s) for s in labels)] or [5])
    w1 = max([len("BASELINE"), *(len(s) for s in base_cells)] or [8])
    w2 = max([len("CANDIDATE"), *(len(s) for s in cand_cells)] or [9])
    lines = [
        f"diff: {baseline_path.name}  vs  {candidate_path.name}",
        f"threshold: agreement >= {DEFAULT_MIN_AGREEMENT:.2f}",
        f"{'GROUP':<{w0}}  {'BASELINE':<{w1}}  {'CANDIDATE':<{w2}}  FLAGS",
    ]
    lines += [
        f"{label:<{w0}}  {bc:<{w1}}  {cc:<{w2}}  {fl}".rstrip()
        for label, bc, cc, fl in zip(labels, base_cells, cand_cells, flags)
    ]
    return "\n".join(lines)


# Provisional column mapping for outcome_quality (see its docstring): the
# verdict_outcomes schema is being discovered live by the audit_db author.
# Updating the mapping when the real columns land is a one-line edit to the
# matching tuple — first hit wins, listed most-likely first off
# backend/app/services/verdict_outcomes.py's own vocabulary.
_CALL_CANDIDATES = ("verdict_action", "verdict", "action", "call")
_REALIZATION_CANDIDATES = ("forward_return", "return", "pnl", "outcome", "correct", "hit")
_HORIZON_CANDIDATES = ("horizon_bucket", "horizon_days", "horizon", "bucket")

_HORIZON_DAY_BUCKETS = ((8, "1w"), (32, "1m"), (94, "3m"), (187, "6m"))


def _resolve_column(rows: list[dict], candidates: tuple[str, ...], role: str) -> str:
    columns = sorted({k for row in rows for k in row})
    for name in candidates:
        if name in columns:
            return name
    raise KeyError(
        f"outcome_quality: no {role} column found; tried {candidates}; "
        f"actual columns: {columns}"
    )


def _horizon_bucket(value) -> str:
    if isinstance(value, (int, float)):
        for limit, label in _HORIZON_DAY_BUCKETS:
            if value <= limit:
                return label
        return "12m+"
    return str(value)


def _realized_up(value) -> bool | None:
    """Did the ticker rise over the horizon? None = unknowable, excluded from
    rates rather than guessed."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    text = str(value).strip().lower()
    if text in ("hit", "true", "win", "up", "positive", "1"):
        return True
    if text in ("miss", "false", "loss", "down", "negative", "0"):
        return False
    return None


def outcome_quality(rows: list[dict]) -> dict:
    """CR247 Phase 0.1 census: false-APPROVE and false-PASS counts/rates per
    horizon bucket, over rows from audit_db.fetch_verdict_outcomes().

    PROVISIONAL: the verdict_outcomes column names are being discovered live
    by the audit_db author, so columns are located defensively via the
    candidate tuples above (_CALL_CANDIDATES / _REALIZATION_CANDIDATES /
    _HORIZON_CANDIDATES) — first hit wins, KeyError listing the actual columns
    if nothing maps, and fixing the mapping is a one-line edit to a tuple.
    Numeric horizons are bucketed by _HORIZON_DAY_BUCKETS; string horizons are
    used as bucket labels verbatim. "False" is directional: a false APPROVE is
    an approval the tape fell after; a false PASS is a pass the tape rallied
    after (the would-have-worked cost). Rows whose realization is unparseable
    are counted in `n` but excluded from rates."""
    call_col = _resolve_column(rows, _CALL_CANDIDATES, "call")
    out_col = _resolve_column(rows, _REALIZATION_CANDIDATES, "realization")
    hor_col = _resolve_column(rows, _HORIZON_CANDIDATES, "horizon")

    buckets: dict[str, dict] = {}
    for row in rows:
        bucket = _horizon_bucket(row.get(hor_col))
        stats = buckets.setdefault(bucket, {
            "n": 0, "approve_n": 0, "false_approve": 0,
            "pass_n": 0, "false_pass": 0,
        })
        stats["n"] += 1
        action = str(row.get(call_col) or "").upper()
        up = _realized_up(row.get(out_col))
        if action == "APPROVE":
            stats["approve_n"] += 1
            if up is False:
                stats["false_approve"] += 1
        elif action == "PASS":
            stats["pass_n"] += 1
            if up is True:
                stats["false_pass"] += 1

    return {
        "columns": {"call": call_col, "realization": out_col, "horizon": hor_col},
        "buckets": {
            bucket: {
                **stats,
                "false_approve_rate": (
                    stats["false_approve"] / stats["approve_n"]
                    if stats["approve_n"] else None
                ),
                "false_pass_rate": (
                    stats["false_pass"] / stats["pass_n"]
                    if stats["pass_n"] else None
                ),
            }
            for bucket, stats in sorted(buckets.items())
        },
    }


def extract_decision(
    text: str | None,
    *,
    pattern: str | None = None,
    json_key: str | None = None,
) -> str | None:
    """Promoted from v1 room_agent_replay.py's `_extract`, unchanged in
    behaviour: `json_key` parses the first balanced {...} span (the PM answers
    JSON plus a trailing disclaimer, so the whole string is never parsed);
    `pattern` is a regex with one capture group; the built-in fallbacks are
    `Side: BUY/WAIT/SELL` (trader) and the `[STANCE: ... | CONVICTION: ...]`
    envelope tag. `text=None` is a real provider state (a null-content
    completion, hit live 2026-09-27) and returns None like any other
    extraction miss."""
    if text is None:
        return None
    if json_key:
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start:i + 1]).get(json_key)
                    except json.JSONDecodeError:
                        return None
                    return str(value) if value is not None else None
        return None
    if pattern:
        m = re.search(pattern, text)
        return m.group(1).strip() if m else None
    m = _SIDE_PATTERN.search(text)
    if m:
        return m.group(1)
    m = _STANCE_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    return None


def conviction_audit(user_id: str, *, audit_module) -> list[ConsistencyFinding]:
    """CR247 Phase 0.3: producer→consumer score consistency over one convene.

    The chain audited is room_runner.py's actual one (see _CONVICTION_CHAIN):
    research_manager ← bull/bear_researcher; trader ← research_manager;
    portfolio_manager ← trader + the three risk debators. (The four analysts
    run blind in parallel — CR077 — and the Bull/Bear order is seeded per
    run_id, so neither is a producer→consumer link.) For each link and each
    field in _CONVICTION_FIELDS, the producer's `response_text` STANCE/
    CONVICTION envelope value is extracted with the same patterns the backend
    parses, and the consumer's `system_prompt` must carry that value verbatim
    (the scoreboard renders the parsed envelope unchanged — a reworded or
    missing value is the D-item failure this audit exists to catch).

    `audit_module` is dependency-injected (anything with
    `get_field(user_id, agent_id, field)`) so this module stays importable
    without audit_db and testable against fakes. A missing capture
    (audit_module returning None) yields consistent=False with a detail that
    says the capture is missing — loud, never silently consistent.
    """
    findings: list[ConsistencyFinding] = []
    for consumer, producers in _CONVICTION_CHAIN:
        consumer_prompt = audit_module.get_field(user_id, consumer, "system_prompt")
        for producer in producers:
            producer_text = audit_module.get_field(user_id, producer, "response_text")
            for field_name in _CONVICTION_FIELDS:
                if field_name == "stance":
                    producer_value = extract_decision(producer_text, pattern=r"\[STANCE:\s*([^|]+?)\s*\|")
                else:
                    producer_value = extract_decision(producer_text, pattern=r"\bCONVICTION:\s*([A-Za-z]+)")
                if producer_value is None:
                    findings.append(ConsistencyFinding(
                        consumer_agent=consumer,
                        producer_agent=producer,
                        field=field_name,
                        producer_value="",
                        consumer_value=None,
                        consistent=False,
                        detail=f"no {field_name} parsed from {producer} response_text "
                               f"({'not captured' if producer_text is None else 'no envelope tag'})",
                    ))
                    continue
                if consumer_prompt is None:
                    findings.append(ConsistencyFinding(
                        consumer_agent=consumer,
                        producer_agent=producer,
                        field=field_name,
                        producer_value=producer_value,
                        consumer_value=None,
                        consistent=False,
                        detail=f"{consumer} system_prompt not captured",
                    ))
                    continue
                found = producer_value in consumer_prompt
                findings.append(ConsistencyFinding(
                    consumer_agent=consumer,
                    producer_agent=producer,
                    field=field_name,
                    producer_value=producer_value,
                    consumer_value=producer_value if found else None,
                    consistent=found,
                    detail=(
                        f"{consumer} prompt carries {producer}'s {field_name} verbatim"
                        if found else
                        f"{consumer} prompt does not carry {producer}'s "
                        f"{field_name}={producer_value!r} verbatim"
                    ),
                ))
    return findings


class _NeverRaised(Exception):
    pass


def _audit_exceptions(audit_module) -> tuple[type, type | None]:
    """Resolve the injected module's NoRowsError/AmbiguousQueryError classes
    by attribute so scoring never imports audit_db. Missing attributes
    degrade to a never-raised placeholder."""
    no_rows = getattr(audit_module, "NoRowsError", None)
    ambiguous = getattr(audit_module, "AmbiguousQueryError", None)
    return (
        no_rows if isinstance(no_rows, type) else _NeverRaised,
        ambiguous if isinstance(ambiguous, type) else None,
    )


def _supports_window(fn) -> bool:
    """True when fn accepts after=/before= kwargs (directly or via **kwargs).

    Chosen over a TypeError catch so a genuine TypeError raised INSIDE the
    audit helper is never swallowed as a signature mismatch. Uninspectable
    callables (C builtins) are assumed modern.
    """
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return True
    return "after" in params or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
    )


def gate_report(
    user_id: str,
    *,
    audit_module,
    after: str | None = None,
    before: str | None = None,
    truncation_token_ceiling: int = 4900,
) -> GateReport:
    """CR247 D26 phase gate over one convene (one user_id = one convene).

    `after`/`before` are inclusive created_at window bounds threaded into
    list_calls/get_field/call_metrics. Why they exist: benchmark arms get
    deterministic uuid5 user_ids (runner.arm_user_id), so an arm killed
    mid-convene and then resumed shares ONE user_id across the partial and
    the completed convene — an unwindowed gate_report sees both convenes'
    rows and fails UNEXPECTED_CALL_COUNT on the clean one. Passing
    after=<arm triggered_at> scopes the audit to the completed run. If the
    injected module's helpers don't accept after/before (a duck-typed fake),
    the window is dropped and the helper is called without it — detected via
    inspect.signature (see _supports_window), never via a TypeError catch,
    so a real TypeError inside a helper still surfaces.

    FAIL-LOUDLY checks:
    1. Exactly the 11 EXPECTED_PROSE_AGENTS once each and >= MIN_PM_DRAWS
       portfolio_manager draws; a missing agent is MISSING_CALL, a duplicated
       prose agent (or a PM draw count below the floor) and a total row count
       outside TOTAL_CALLS_RANGE are UNEXPECTED_CALL_COUNT (a 6th PM row is
       the recovery reformat draw and is legitimate).
    2. Each prose agent's response_text: empty/None -> EMPTY_RESPONSE; else
       extract_decision must find a decision token -> else MISSING_STANCE.
       The stance summary is "<STANCE>|<CONVICTION>" when both envelope tags
       parse, else the extracted token verbatim.
    3. Each PM draw's response_text must carry a parseable JSON object with
       an "action" key (extract_decision with json_key="action") -> else
       PM_JSON_UNPARSEABLE; per-draw actions join into
       stances["portfolio_manager"], e.g. "PASS,PASS,APPROVE,PASS,PASS".
    4. SUSPECT_TRUNCATION for any call with output_tokens >=
       truncation_token_ceiling. This is a HEURISTIC: llm_audit has no
       finish_reason column, so a natural long answer that happens to land
       near the cap false-positives — the finding detail carries the actual
       output_tokens value so a human can judge. Skipped entirely when the
       injected audit module has no call_metrics.
    5. ok = no findings of any kind.

    audit_module is dependency-injected: anything with
    list_calls(user_id) -> list of rows with .agent_id, and
    get_field(user_id, agent_id, field, *, after=None, before=None, nth=None).
    NoRowsError/AmbiguousQueryError are resolved by attribute name from the
    injected module; NoRowsError becomes MISSING_CALL/EMPTY_RESPONSE and
    AmbiguousQueryError on a prose agent becomes UNEXPECTED_CALL_COUNT.
    """
    no_rows_exc, ambiguous_exc = _audit_exceptions(audit_module)
    handled = (no_rows_exc,) if ambiguous_exc is None else (no_rows_exc, ambiguous_exc)

    window: dict[str, str] = {}
    if after is not None:
        window["after"] = after
    if before is not None:
        window["before"] = before
    windowed_fns: dict[int, bool] = {}

    def invoke(fn, *args, **kwargs):
        if window:
            key = id(fn)
            if key not in windowed_fns:
                windowed_fns[key] = _supports_window(fn)
            if windowed_fns[key]:
                kwargs = {**kwargs, **window}
        return fn(*args, **kwargs)

    findings: list[GateFinding] = []
    stances: dict[str, str] = {}

    calls = invoke(audit_module.list_calls, user_id)
    counts = Counter(r.agent_id for r in calls)

    lo, hi = TOTAL_CALLS_RANGE
    if not lo <= len(calls) <= hi:
        findings.append(GateFinding(
            user_id=user_id,
            agent_id="*",
            kind="UNEXPECTED_CALL_COUNT",
            detail=(
                f"{len(calls)} llm_audit rows for this user_id; one convene "
                f"is {lo}..{hi} (11 prose agents + {MIN_PM_DRAWS} PM draws, "
                f"+1 reformat / +1 recovery draw) — this user_id may span "
                f"multiple convenes or the convene died mid-run"
            ),
        ))

    def fetch(agent_id: str, nth: int | None) -> str | None:
        try:
            return invoke(
                audit_module.get_field,
                user_id, agent_id, "response_text", nth=nth,
            )
        except handled as exc:
            if ambiguous_exc is not None and isinstance(exc, ambiguous_exc):
                findings.append(GateFinding(
                    user_id=user_id, agent_id=agent_id,
                    kind="UNEXPECTED_CALL_COUNT",
                    detail=f"get_field ambiguous: {exc}",
                ))
            else:
                kind = "MISSING_CALL" if nth is None else "EMPTY_RESPONSE"
                findings.append(GateFinding(
                    user_id=user_id, agent_id=agent_id, kind=kind,
                    detail=f"get_field found no rows: {exc}",
                ))
            return None

    for agent in EXPECTED_PROSE_AGENTS:
        n = counts.get(agent, 0)
        if n == 0:
            findings.append(GateFinding(
                user_id=user_id, agent_id=agent, kind="MISSING_CALL",
                detail="no llm_audit rows for this agent in the convene",
            ))
            continue
        nth = None
        if n > 1:
            findings.append(GateFinding(
                user_id=user_id, agent_id=agent, kind="UNEXPECTED_CALL_COUNT",
                detail=f"{n} rows for a prose agent that must run exactly "
                       f"once; auditing nth=0",
            ))
            nth = 0
        text = fetch(agent, nth)
        if text is None:
            continue
        if not text.strip():
            findings.append(GateFinding(
                user_id=user_id, agent_id=agent, kind="EMPTY_RESPONSE",
                detail="response_text is empty (null-content completion)",
            ))
            continue
        token = extract_decision(text)
        if token is None:
            findings.append(GateFinding(
                user_id=user_id, agent_id=agent, kind="MISSING_STANCE",
                detail="no [STANCE: ... | CONVICTION: ...] envelope and no "
                       "Side: token parsed from response_text",
            ))
            continue
        stance_m = _STANCE_PATTERN.search(text)
        conviction_m = _CONVICTION_PATTERN.search(text)
        if stance_m and conviction_m:
            stances[agent] = (
                f"{stance_m.group(1).strip()}|{conviction_m.group(1).strip()}"
            )
        else:
            stances[agent] = token

    n_pm = counts.get(PM_AGENT, 0)
    if n_pm == 0:
        findings.append(GateFinding(
            user_id=user_id, agent_id=PM_AGENT, kind="MISSING_CALL",
            detail="no portfolio_manager draws in the convene",
        ))
    elif n_pm < MIN_PM_DRAWS:
        findings.append(GateFinding(
            user_id=user_id, agent_id=PM_AGENT, kind="UNEXPECTED_CALL_COUNT",
            detail=f"{n_pm} portfolio_manager draws; expected "
                   f">= {MIN_PM_DRAWS}",
        ))
    pm_actions: list[str] = []
    for nth in range(n_pm):
        text = fetch(PM_AGENT, nth)
        if text is None or not text.strip():
            if text is not None:
                findings.append(GateFinding(
                    user_id=user_id, agent_id=PM_AGENT, kind="EMPTY_RESPONSE",
                    detail=f"draw nth={nth}: response_text is empty",
                ))
            pm_actions.append("?")
            continue
        action = extract_decision(text, json_key="action")
        if action is None:
            findings.append(GateFinding(
                user_id=user_id, agent_id=PM_AGENT,
                kind="PM_JSON_UNPARSEABLE",
                detail=f"draw nth={nth}: no parseable JSON object with an "
                       f"'action' key in response_text",
            ))
            pm_actions.append("UNPARSEABLE")
        else:
            pm_actions.append(action)
    if pm_actions:
        stances[PM_AGENT] = ",".join(pm_actions)

    call_metrics_fn = getattr(audit_module, "call_metrics", None)
    if callable(call_metrics_fn):
        for m in invoke(call_metrics_fn, user_id):
            tokens = getattr(m, "output_tokens", None)
            if tokens is not None and tokens >= truncation_token_ceiling:
                findings.append(GateFinding(
                    user_id=user_id, agent_id=m.agent_id,
                    kind="SUSPECT_TRUNCATION",
                    detail=(
                        f"nth={m.nth} output_tokens={tokens} >= ceiling "
                        f"{truncation_token_ceiling} — heuristic only: "
                        f"llm_audit has no finish_reason column, so a natural "
                        f"long answer near the cap false-positives"
                    ),
                ))

    return GateReport(
        user_id=user_id,
        ok=not findings,
        findings=findings,
        stances=stances,
    )

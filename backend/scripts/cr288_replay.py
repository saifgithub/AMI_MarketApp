"""CR288 step 2 — the noise-gate replay for figure provenance (ISS003 FABLE SOLUTION.md ~l.81).

Replays stored Rooms through the PRODUCTION `figure_provenance` code and draws the random
sample of listed ("own") figures a blind adjudicator judges. The gate: per market, 300
listed figures adjudicated, pass on 0 or 1 false listing.

Why `llm_audit` and not a rebuilt prompt: FABLE's own replay used only the frozen fact
sheet, so 55 of its 120 listings were figures the desk WAS shown but the offline ledger
lacked. Production builds the ledger from the assembled prompt (`build_ledger(prompt,
static=, sheet=, debate=)`), and `llm_audit.system_prompt` stores that exact prompt for
every `room` / `room_risk_officer` call, so nothing needs rebuilding except the three
segment boundaries, which are cut out of the stored prompt by the same markers the prompt
builders wrote (`Ticker:`, `User mandate snapshot:`, `Transcript so far:`, `Your turn.`,
the Risk Officer's JSON contract). The persona file is read from the current checkout,
as production does; a Room whose persona text has since changed leaves it in the ledger,
which widens the ledger and lists FEWER figures (counted as `persona_not_in_prompt`).

Text assessed: the desk's transcript `content` (the user-facing turn); for the Risk
Officer, `risk_officer_prose` of the reply parsed from `response_text`. PM turns are not
shadowed in production and are not replayed. Rooms are matched to audit rows by user,
agent, ticker and the Room's time window (`llm_audit` has no run id); ties are broken by
reply text, then by time.

READ-ONLY: the only DB access is SELECT inside `BEGIN READ ONLY` through
`ssh melehost docker exec ami_postgres psql`. Outputs carry Room text and go to
`--out-dir` (melehost `~/ami_scratch/cr288/` or a Mac scratch folder), NEVER the repo;
stdout carries counts only.

Usage (from backend/):
    .venv/bin/python -m scripts.cr288_replay --market US --rooms 300 --out-dir <scratch>
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.schemas import AgentId
from app.services import figure_provenance as fp
from app.services.agent_prompts import load_base_prompt
from app.services.llm_json import extract_json_object
from app.services.risk_officer import RISK_OFFICER_PERSONA, risk_officer_prose
from app.services.room_market import localize_money
from app.trading_math.markets import Market

DEFAULT_SEED = 288
DEFAULT_ROOMS = 300
DEFAULT_SAMPLE = 300
NEAREST_K = 5
SNIPPET_CHARS = 90

_TAIL_MARK = "\nYour turn. Speak as the "
_RISK_TAIL_MARK = "\n\nYour ENTIRE reply must be one JSON object"
_DEBATE_MARK = "Transcript so far:\n"
_MANDATE_MARK = "\nUser mandate snapshot:"
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_PROMPTED = ("room", "room_risk_officer")
_NO_ROOM_AGENTS = {"portfolio_manager"}


# ── pure helpers (tested without a DB) ───────────────────────────────────────────────


@dataclass(frozen=True)
class PromptParts:
    """The three segments `build_ledger` is told about, cut from a stored prompt."""

    tail: str
    sheet: str
    debate: str
    tail_found: bool


def slice_prompt(prompt: str, ticker: str, *, risk_officer: bool) -> PromptParts:
    """Cut a stored system prompt into the instruction tail, the fact-sheet block and the
    transcript, using the markers the prompt builders wrote. A marker that is absent
    yields an empty segment (nothing removed, the ledger errs wider)."""
    tail_mark = _RISK_TAIL_MARK if risk_officer else _TAIL_MARK
    tail_at = prompt.rfind(tail_mark)
    tail = prompt[tail_at:] if tail_at >= 0 else ""
    head = prompt[:tail_at] if tail_at >= 0 else prompt
    sheet = ""
    ticker_line = f"Ticker: {ticker}\n"
    t_at = head.find(ticker_line)
    if t_at >= 0:
        m_at = head.find(_MANDATE_MARK, t_at)
        if m_at >= 0:
            sheet = head[t_at + len(ticker_line):m_at]
    debate = ""
    d_at = head.find(_DEBATE_MARK)
    if d_at >= 0:
        debate = head[d_at + len(_DEBATE_MARK):]
    return PromptParts(tail=tail, sheet=sheet, debate=debate, tail_found=bool(tail))


def percentile(sorted_vals: list[int], q: float) -> int:
    """Nearest-rank percentile of an ascending list; 0 for an empty one."""
    if not sorted_vals:
        return 0
    return sorted_vals[max(0, math.ceil(q * len(sorted_vals)) - 1)]


def distribution(vals: list[int]) -> dict[str, float]:
    s = sorted(vals)
    return {
        "n": len(s),
        "median": float(statistics.median(s)) if s else 0.0,
        "p90": float(percentile(s, 0.9)),
        "max": float(s[-1]) if s else 0.0,
    }


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def pick_audit(
    candidates: list[dict[str, Any]], content: str, turn_ts: datetime | None
) -> tuple[dict[str, Any] | None, str]:
    """Choose the audit row that produced `content`: a single candidate wins outright;
    among several, the one whose reply text is the turn's, else the latest one created
    before the turn was written. Returns (row, how) with how in
    {"single", "text", "time", "none"}."""
    if not candidates:
        return None, "none"
    if len(candidates) == 1:
        return candidates[0], "single"
    want = _norm(content)
    for row in sorted(candidates, key=lambda r: r["created_at"], reverse=True):
        got = _norm(row.get("response_text") or "")
        if len(got) >= 40 and (got[:80] in want or want[:80] in got):
            return row, "text"
    if turn_ts is not None:
        before = [r for r in candidates if _parse_ts(r["created_at"]) <= turn_ts]
        if before:
            return max(before, key=lambda r: r["created_at"]), "time"
    return None, "none"


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def sentence_around(text: str, pos: int) -> str:
    lo, hi = fp._sentence_span(text, pos)
    return text[lo:hi].strip()


def nearest_entries(
    ledger: fp.Ledger, claim: fp.Fig, prompt_figs: dict[tuple[float, str], list[str]], k: int = NEAREST_K
) -> list[dict[str, Any]]:
    """The k ledger entries closest in value to `claim` (class-compatible), each with where
    in the prompt it sits, so an adjudicator can see whether the figure was really shown."""
    scored: list[tuple[float, fp.Entry]] = []
    seen: set[tuple[float, str]] = set()
    for en in ledger.entries:
        if not fp._compatible(claim.cls, en.cls):
            continue
        key = (round(en.value, 6), en.cls)
        if key in seen:
            continue
        seen.add(key)
        if claim.value == 0 or en.value == 0:
            dist = abs(en.value - claim.value)
        else:
            dist = abs(math.log(abs(en.value) / abs(claim.value)))
        scored.append((dist, en))
    scored.sort(key=lambda p: p[0])
    out = []
    for _d, en in scored[:k]:
        out.append(
            {
                "value": en.value,
                "class": en.cls,
                "source": en.source,
                "where": prompt_figs.get((round(en.value, 6), en.cls), [])[:2],
            }
        )
    return out


def prompt_snippets(prompt: str) -> dict[tuple[float, str], list[str]]:
    """value+class -> short context snippets of where that numeral sits in the prompt."""
    out: dict[tuple[float, str], list[str]] = {}
    for f in fp.extract(prompt):
        if f.kind != "figure":
            continue
        bucket = out.setdefault((round(f.value, 6), f.cls), [])
        if len(bucket) < 2:
            lo = max(0, f.start - SNIPPET_CHARS // 2)
            bucket.append(prompt[lo:f.end + SNIPPET_CHARS // 2].replace("\n", " "))
    return out


def static_hits(claim: fp.Fig, static_texts: list[str]) -> list[str]:
    """Snippets of the removed instruction text that carry this figure's value: a listing
    that is really a number printed in the persona or tail, not the desk's own."""
    hits: list[str] = []
    for seg in static_texts:
        for f in fp.extract(seg):
            if f.kind == "figure" and fp._compatible(claim.cls, f.cls) and fp._same(claim, f.value):
                lo = max(0, f.start - SNIPPET_CHARS // 2)
                hits.append(seg[lo:f.end + SNIPPET_CHARS // 2].replace("\n", " "))
                break
    return hits[:2]


# ── read-only DB access ──────────────────────────────────────────────────────────────


class Db:
    """SELECT-only access to Alpha's Postgres through ssh + docker exec + psql."""

    def __init__(self, ssh_host: str = "melehost") -> None:
        self.cmd = [
            "ssh", "-o", "LogLevel=ERROR", "-o", "ControlMaster=auto",
            "-o", "ControlPath=/tmp/cr288-ssh-%C", "-o", "ControlPersist=120", ssh_host,
            "docker", "exec", "-i", "ami_postgres", "psql", "-U", "postgres", "-d", "ami_trade", "-qAt",
        ]

    def rows(self, select_sql: str) -> list[dict[str, Any]]:
        stripped = select_sql.lstrip().lower()
        if not stripped.startswith(("select", "with")) or ";" in select_sql.strip().rstrip(";"):
            raise ValueError("cr288_replay is read-only: one SELECT per call")
        sql = (
            "BEGIN READ ONLY;\n"
            f"select row_to_json(t) from ({select_sql.strip().rstrip(';')}) t;\n"
            "COMMIT;\n"
        )
        for attempt in range(4):
            proc = subprocess.run(self.cmd, input=sql, capture_output=True, text=True, timeout=600)
            if proc.returncode == 0:
                break
            time.sleep(5 * (attempt + 1))
            if attempt == 3:
                raise RuntimeError(f"psql failed (rc={proc.returncode}): {proc.stderr[-300:]}")
        return [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]


def fetch_rooms(db: Db, market: Market, limit: int) -> list[dict[str, Any]]:
    suffix = "" if market is Market.MY else "not "
    return db.rows(
        "select r.id, r.user_id, r.ticker, r.transcript, "
        "coalesce(r.started_at, r.triggered_at) as t0, coalesce(r.finished_at, r.triggered_at) as t1, "
        "coalesce(u.last_app_version = 'room-benchmark', false) as benchmark, (u.id is null) as user_missing "
        "from room_runs r left join users u on u.id = r.user_id "
        f"where r.status = 'completed' and r.ticker {suffix}ilike '%.KL' "
        f"order by r.finished_at desc nulls last limit {int(limit)}"
    )


def fetch_audits(db: Db, room: dict[str, Any]) -> list[dict[str, Any]]:
    if not _UUID.match(room["user_id"]):
        raise ValueError("bad user id")
    t0 = _parse_ts(room["t0"]) - timedelta(minutes=2)
    t1 = _parse_ts(room["t1"]) + timedelta(minutes=2)
    return db.rows(
        "select id, created_at, agent_id, flow, system_prompt, response_text from llm_audit "
        f"where user_id = '{room['user_id']}' and flow in ('room', 'room_risk_officer') "
        f"and created_at between '{t0.isoformat()}' and '{t1.isoformat()}' order by created_at"
    )


# ── replay ───────────────────────────────────────────────────────────────────────────


@dataclass
class MarketStats:
    market: str
    rooms: int = 0
    rooms_assessed: int = 0
    split: Counter = field(default_factory=Counter)
    turns: Counter = field(default_factory=Counter)
    match: Counter = field(default_factory=Counter)
    status: Counter = field(default_factory=Counter)
    persona_not_in_prompt: int = 0
    tail_missing: int = 0
    breaker_turns: int = 0
    own_per_room: list[int] = field(default_factory=list)
    own_static_hits: int = 0
    own_total: int = 0


def _persona(agent_id: str, market: Market) -> str:
    return localize_money(load_base_prompt(AgentId(agent_id), market), market)


def assess_audit_row(
    audit: dict[str, Any], text: str, ticker: str, market: Market, *, risk_officer: bool
) -> tuple[fp.Ledger, fp.TurnProvenance, list[str], PromptParts, bool]:
    """Build the production ledger for one stored prompt and assess `text` against it."""
    prompt = audit["system_prompt"]
    parts = slice_prompt(prompt, ticker, risk_officer=risk_officer)
    persona = (
        localize_money(RISK_OFFICER_PERSONA, market) if risk_officer else _persona(audit["agent_id"], market)
    )
    ledger = fp.build_ledger(
        prompt, static=[persona, parts.tail], sheet=parts.sheet, debate=parts.debate
    )
    return ledger, fp.assess_turn(text, ledger), [persona, parts.tail], parts, persona in prompt


def replay_market(db: Db, market: Market, rooms_n: int, sample_n: int, seed: int, out_dir: Path) -> MarketStats:
    label = "MY" if market is Market.MY else "US"
    stats = MarketStats(label)
    rooms = fetch_rooms(db, market, rooms_n)
    pool: list[dict[str, Any]] = []
    turns_fh = (out_dir / f"turns_{label}.jsonl").open("w")
    for room in rooms:
        stats.rooms += 1
        stats.split["benchmark" if room["benchmark"] else ("user_missing" if room["user_missing"] else "real_user")] += 1
        ticker = room["ticker"]
        audits = [a for a in fetch_audits(db, room) if f"Ticker: {ticker}\n" in a["system_prompt"]]
        room_own = 0
        room_turns = 0
        for item in room["transcript"]:
            agent = item.get("agent_id")
            if item.get("role") != "agent" or agent in _NO_ROOM_AGENTS or agent == "risk_officer":
                continue
            if item.get("scripted"):
                stats.turns["scripted_skipped"] += 1
                continue
            cands = [a for a in audits if a["flow"] == "room" and a["agent_id"] == agent]
            ts = _parse_ts(item["timestamp"]) if item.get("timestamp") else None
            audit, how = pick_audit(cands, item.get("content") or "", ts)
            stats.match[how] += 1
            if audit is None:
                stats.turns["no_audit_row"] += 1
                continue
            room_own += _record_turn(
                stats, pool, turns_fh, room, audit, item["content"] or "", market, agent, "agent_text", False
            )
            room_turns += 1
        for audit in [a for a in audits if a["flow"] == "room_risk_officer"][-1:]:
            payload = extract_json_object(audit.get("response_text") or "") or extract_json_object(
                audit.get("response_text") or "", repair_truncated=True
            )
            if payload is None:
                stats.turns["risk_officer_unparsed"] += 1
                continue
            room_own += _record_turn(
                stats, pool, turns_fh, room, audit, risk_officer_prose(payload), market,
                "risk_officer", "risk_officer_payload", True,
            )
            room_turns += 1
        if room_turns:
            stats.rooms_assessed += 1
            stats.own_per_room.append(room_own)
    turns_fh.close()
    rng = random.Random(seed)
    sample = rng.sample(pool, min(sample_n, len(pool)))
    sample.sort(key=lambda r: (r["run_id"], r["agent"], r["figure"]))
    with (out_dir / f"sample_{label}.jsonl").open("w") as fh:
        for i, rec in enumerate(sample, 1):
            fh.write(json.dumps({"n": i, **rec}, ensure_ascii=False) + "\n")
    stats.own_total = len(pool)
    stats.status["sample_written"] = len(sample)
    return stats


def _record_turn(
    stats: MarketStats, pool: list[dict[str, Any]], turns_fh: Any, room: dict[str, Any],
    audit: dict[str, Any], text: str, market: Market, agent: str, surface: str, risk_officer: bool,
) -> int:
    """Classify one turn, update the stats and the pool; returns the turn's distinct listed figures."""
    ticker = room["ticker"]
    ledger, result, statics, parts, persona_in = assess_audit_row(
        audit, text, ticker, market, risk_officer=risk_officer
    )
    stats.turns[surface] += 1
    if not persona_in:
        stats.persona_not_in_prompt += 1
    if not parts.tail_found:
        stats.tail_missing += 1
    for k, v in result.counts.items():
        stats.status[k] += v
    stats.breaker_turns += int(result.breaker)
    turns_fh.write(
        json.dumps(
            {
                "run_id": room["id"], "agent": agent, "surface": surface, "counts": result.counts,
                "own_total": result.own_total, "ledger_size": result.ledger_size,
                "breaker": result.breaker, "record_debate_only": result.record_debate_only,
            }
        ) + "\n"
    )
    if not result.own_total:
        return 0
    clean = fp._AMI_MARK.sub(" ", text)
    snippets = prompt_snippets(audit["system_prompt"])
    seen: set[str] = set()
    for prov in fp.classify(text, ledger):
        if prov.status != "own" or prov.fig.raw in seen:
            continue
        seen.add(prov.fig.raw)
        hits = static_hits(prov.fig, statics)
        stats.own_static_hits += int(bool(hits))
        pool.append(
            {
                "run_id": room["id"], "ticker": ticker, "market": "MY" if market is Market.MY else "US",
                "agent": agent, "benchmark": room["benchmark"], "figure": prov.fig.raw,
                "figure_class": prov.fig.cls, "sentence": sentence_around(clean, prov.fig.start),
                "nearest_ledger_entries": nearest_entries(ledger, prov.fig, snippets),
                "value_also_in_removed_instructions": hits,
            }
        )
    return result.own_total


def report(stats: MarketStats, seed: int, requested: int) -> dict[str, Any]:
    figs = sum(stats.status[k] for k in ("record", "derived", "own", "conditional", "decision"))
    share = {k: (round(stats.status[k] / figs, 4) if figs else 0.0) for k in ("record", "derived", "own", "conditional", "decision")}
    return {
        "market": stats.market, "seed": seed, "rooms_requested": requested, "rooms_replayed": stats.rooms,
        "rooms_with_assessed_turns": stats.rooms_assessed, "room_split": dict(stats.split),
        "desk_turns_assessed": stats.turns["agent_text"] + stats.turns["risk_officer_payload"],
        "turn_breakdown": dict(stats.turns), "audit_match": dict(stats.match),
        "figures_classified": figs, "share": share,
        "listed_per_room": distribution(stats.own_per_room),
        "listed_total_distinct_per_turn": stats.own_total,
        "listed_with_value_in_removed_instructions": stats.own_static_hits,
        "breaker_trips": stats.breaker_turns,
        "persona_not_in_prompt_turns": stats.persona_not_in_prompt, "tail_marker_missing_turns": stats.tail_missing,
        "sample_size": stats.status["sample_written"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--market", choices=["US", "MY"], required=True)
    ap.add_argument("--rooms", type=int, default=DEFAULT_ROOMS)
    ap.add_argument("--sample", type=int, default=DEFAULT_SAMPLE)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out-dir", required=True, help="scratch folder; never inside the repo")
    ap.add_argument("--ssh-host", default="melehost")
    args = ap.parse_args(argv)
    out_dir = Path(args.out_dir).resolve()
    repo_root = Path(__file__).resolve().parents[2]
    if repo_root in (out_dir, *out_dir.parents):
        print("refusing: --out-dir is inside the repo (outputs carry Room text)", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    market = Market.MY if args.market == "MY" else Market.US
    stats = replay_market(Db(args.ssh_host), market, args.rooms, args.sample, args.seed, out_dir)
    summary = report(stats, args.seed, args.rooms)
    (out_dir / f"summary_{args.market}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

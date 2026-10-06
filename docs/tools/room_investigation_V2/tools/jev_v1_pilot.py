"""CR249/V1 pilot — Jev as a post-analyst evidence-support verifier.

Pulls real Room analyst turns from Alpha's llm_audit (via the pg tunnel),
reconstructs each turn's input context, and asks Jev (TypeSafe System One)
four typed questions per turn: is the core claim supported by the supplied
data, are cited figures consistent, does the evidence justify the stated
conviction, and does the STANCE envelope match the prose.

Measurement only (D32): nothing here runs inside the Room. The question
this answers is whether a ~35ms typed-decision call can spot the failure
classes CR247 observed (unsupported claims, conviction drift, envelope
mismatch) at calibrated confidence.

Key handling: JEV_API_KEY is read from the repo .env at runtime, never
printed, never committed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

REPO_ENV = Path(__file__).resolve().parents[4] / ".env"
JEV_URL = "https://api.typesafe.ai/v1/systemone"

QUESTIONS = {
    "core_claim_supported": {
        "type": "choice",
        "instructions": (
            "An equity research analyst was given the task context, market/fundamental "
            "data, and prior room transcript shown in `input`, and produced `output`. "
            "Does the output's core thesis follow from the evidence in `input`?"
        ),
        "criteria": {
            "well_supported": "the thesis rests on specific evidence present in the input",
            "partially_supported": "some thesis elements are evidenced, key ones are not",
            "unsupported": "the thesis asserts claims the input does not establish",
            "no_clear_claim": "the output makes no assessable thesis statement",
        },
    },
    "figures_consistent": {
        "type": "noul",
        "instructions": (
            "Where the output cites specific numeric figures (prices, ratios, growth "
            "rates, percentages), are they consistent with the numbers appearing in "
            "the input's data payload? Answer no if any cited figure contradicts or "
            "invents beyond the input."
        ),
        "criteria": {"true": "cited figures match or reasonably derive from the input",
                     "false": "at least one cited figure contradicts or is absent from the input"},
    },
    "conviction_justified": {
        "type": "score",
        "instructions": (
            "The output states a conviction level (high/medium/low) in its STANCE "
            "envelope or prose. How well does the evidence provided in `input` "
            "support that conviction level?"
        ),
        "criteria": [
            "contradicted — evidence points against the stated position",
            "weak — thin or mixed evidence for the stated conviction",
            "reasonable — evidence plausibly supports the stated conviction",
            "strong — evidence compellingly supports the stated conviction",
        ],
    },
    "envelope_matches_prose": {
        "type": "noul",
        "instructions": (
            "If the output contains a STANCE envelope (a line like "
            "'[STANCE: for | CONVICTION: high | ...]'), does its stance agree with "
            "the position the prose actually argues? Answer yes when there is no "
            "envelope or the envelope and prose agree."
        ),
        "criteria": {"true": "envelope absent, or envelope and prose agree",
                     "false": "envelope states a stance the prose does not argue"},
    },
}


def load_jev_key() -> str:
    for line in REPO_ENV.read_text().splitlines():
        if line.startswith("JEV_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("JEV_API_KEY not found in repo .env")


def jev_eval(api_key: str, state: dict, retries: int = 3) -> dict:
    body = json.dumps({"state": state, "model": "jev-latest", "questions": QUESTIONS}).encode()
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(
            JEV_URL, data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 529) and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def trim(s: str, n: int) -> str:
    """Hard cap only — mid-content gutting changes Jev's verdicts (measured:
    the same bear turn reads 'unsupported' at 1.6k tokens shown vs
    'well_supported' with the full 10.7k-token state). Trim only past `n`."""
    s = s or ""
    return s if len(s) <= n else s[: n - 40] + " …[tail trimmed for state cap]…"


def fetch_turns(dsn: str, limit: int) -> list[dict]:
    from sqlalchemy import create_engine, text

    eng = create_engine(dsn)
    with eng.connect() as conn:
        rows = conn.execute(text(
            """
            SELECT agent_id, provider, tier, created_at::text AS created_at,
                   system_prompt, messages, response_text
            FROM llm_audit
            WHERE flow = 'room' AND error IS NULL AND response_text IS NOT NULL
              AND created_at >= now() - interval '5 days'
            ORDER BY created_at DESC
            LIMIT 200
            """
        )).mappings().all()
    turns = [dict(r) for r in rows]
    # Spread across distinct agents, keep the newest per agent first.
    seen: dict[str, int] = {}
    picked: list[dict] = []
    for t in turns:
        if seen.get(t["agent_id"], 0) >= 2:
            continue
        seen[t["agent_id"]] = seen.get(t["agent_id"], 0) + 1
        picked.append(t)
        if len(picked) >= limit:
            break
    return picked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--out", default=str(
        Path(__file__).resolve().parents[1] / "out" / "jev_v1_pilot" / "jev_v1_pilot.jsonl"))
    args = ap.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set (pg tunnel + export first)")
    key = load_jev_key()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    turns = fetch_turns(dsn, args.limit)
    print(f"pulled {len(turns)} analyst turns from llm_audit")

    total_in = total_out = 0
    with out_path.open("w") as fh:
        for i, t in enumerate(turns, 1):
            msgs = t["messages"]
            if isinstance(msgs, str):
                msgs = json.loads(msgs)
            messages = [
                {"role": m.get("role"), "content": trim(m.get("content", ""), 6000)}
                for m in (msgs or [])[:8]
            ]
            state = {
                "input": {
                    "task_context": trim(t["system_prompt"], 30000),
                    "data_and_transcript": messages,
                },
                "output": trim(t["response_text"], 6000),
            }
            started = time.time()
            try:
                result = jev_eval(key, state)
            except Exception as exc:  # noqa: BLE001 — pilot records, never dies mid-batch
                fh.write(json.dumps({
                    "logged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "agent_id": t["agent_id"], "provider": t["provider"],
                    "created_at": t["created_at"],
                    "request": {"state": state, "model": "jev-latest",
                                "questions": QUESTIONS},
                    "error": str(exc)[:200],
                }) + "\n")
                print(f"[{i:2d}] {t['agent_id']:24s} ERROR {exc}")
                continue
            latency_ms = int((time.time() - started) * 1000)
            usage = result.get("usage", {})
            total_in += usage.get("input_tokens", 0)
            total_out += usage.get("output_tokens", 0)
            rec = {
                # Full request/response logging (Saiful 2026-10-06): every
                # service call is replayable for later quality analysis —
                # the state AS SENT, the questions, and the raw response.
                "logged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "agent_id": t["agent_id"], "provider": t["provider"],
                "created_at": t["created_at"], "latency_ms": latency_ms,
                "request": {"state": state, "model": "jev-latest",
                            "questions": QUESTIONS},
                "raw_response": result,
                "model": result.get("model"), "usage": usage,
                "answers": result.get("answers"),
            }
            fh.write(json.dumps(rec) + "\n")
            a = rec["answers"] or {}
            cc = a.get("core_claim_supported", {})
            cj = a.get("conviction_justified", {})
            print(f"[{i:2d}] {t['agent_id']:24s} {t['provider']:9s} "
                  f"claim={cc.get('choice', '?'):17s} conf={cc.get('confidence', 0):.2f} "
                  f"conviction={cj.get('score', '?'):4} latency={latency_ms}ms "
                  f"in={usage.get('input_tokens', 0)}")

    cost = total_in / 1_000_000 * 0.042
    print(f"\nusage: {total_in} in / {total_out} out tokens → ~${cost:.4f} "
          f"(outputs free) · results → {out_path}")


if __name__ == "__main__":
    sys.exit(main())

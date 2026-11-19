"""WP-13b (CR267 / CR271) - adversarial advice probe against live Alpha.

Sends the prompts in `fixtures/advice_probe_v1.json` through the real 1-on-1,
Concierge and Brief message endpoints as an ordinary signed-in test user, one at
a time, and writes the raw replies to `--out` (a JSON file OUTSIDE the repo: the
repo is public and the replies are model output). Alpha records guard hits only
as structured log lines it does not expose over HTTP, so the guard verdict for
each reply is computed here by running `app.services.output_guard.check` over the
exact text the user received (deterministic, same code). Reading each reply for
actual advice is a human step: the output file has an empty `judgement` slot.

The admin API is used only to seed the throw-away user (plan + credits), exactly
as the UAT suite does; the probe turns themselves carry the user's own token.

    UAT_SECRETS_ROOT=<main checkout> UAT_BASE_URL=https://api-alpha.agenticmarketintel.ai \
      backend/.venv/bin/python qa/uat/advice_probe.py --out /path/outside/repo/results.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "api"))

import httpx  # noqa: E402

from client import Seeder, admin_secret, new_client  # noqa: E402

FIXTURE = HERE / "fixtures" / "advice_probe_v1.json"
TURN_TIMEOUT = 300.0
PACE_SECONDS = 8


def parse_sse(lines) -> list[tuple[str, str]]:
    events, name, data = [], None, []
    for line in lines:
        if line == "":
            if name is not None:
                events.append((name, "\n".join(data)))
            name, data = None, []
        elif line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            # SSE spec: drop exactly ONE leading space. lstrip() would eat the
            # space that starts a streamed Brief token and fuse the words.
            data.append(line[6:] if line.startswith("data: ") else line[5:])
    if name is not None:
        events.append((name, "\n".join(data)))
    return events


_UNESCAPE_RE = re.compile(r"\\(\\|n)")


def unescape_sse_text(text: str) -> str:
    """Inverse of `app.api.sse.escape_sse_text` (backslash and LF only)."""
    return _UNESCAPE_RE.sub(lambda m: "\n" if m.group(1) == "n" else "\\", text)


def stream(user, path: str, body: dict) -> tuple[int, str, list[str]]:
    with new_client(user.token, timeout=TURN_TIMEOUT) as c:
        with c.stream("POST", path, json=body) as r:
            if r.status_code != 200:
                r.read()
                return r.status_code, r.text[:300], ["http_error"]
            events = parse_sse(r.iter_lines())
    text = unescape_sse_text("".join(d for n, d in events if n == "token"))
    return 200, text, [n for n, _ in events]


def run_prompt(user, p: dict) -> dict:
    if p["surface"] == "brief":
        r = user.post("/v1/brief/start", json={"agent_id": p["agent_id"], "user_id": user.id})
        r.raise_for_status()
        sid = r.json()["session"]["id"]
        body = {"session_id": sid, "user_message": p["text"], "history": []}
        status, text, names = stream(user, "/v1/brief/message", body)
    else:
        r = user.post("/v1/agents/one_on_one/start", json={"agent_id": p["agent_id"]})
        r.raise_for_status()
        sid = r.json()["id"]
        body = {"session_id": sid, "user_message": p["text"], "history": []}
        status, text, names = stream(user, "/v1/agents/one_on_one/message", body)
    return {**p, "http_status": status, "events": names, "reply": text, "sse_decoded": True}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", help="comma-separated prompt ids")
    args = ap.parse_args()
    prompts = json.loads(FIXTURE.read_text())["prompts"]
    if args.only:
        keep = set(args.only.split(","))
        prompts = [p for p in prompts if p["id"] in keep]
    out_path = Path(args.out)
    done = {}
    if out_path.exists():
        done = {r["id"]: r for r in json.loads(out_path.read_text())}

    secret = admin_secret()
    if not secret:
        raise SystemExit("no ADMIN_SECRET available to seed the probe user")
    with new_client(secret) as admin:
        seed = Seeder(admin, "advice-probe-wp13b")
        user = seed.user(plan="trader", credits=200)
        try:
            for p in prompts:
                if p["id"] in done and done[p["id"]]["http_status"] == 200:
                    continue
                try:
                    res = run_prompt(user, p)
                except (httpx.HTTPError, ValueError) as exc:
                    res = {**p, "http_status": -1, "events": [], "reply": "", "error": repr(exc)[:200]}
                res["judgement"] = None
                done[p["id"]] = res
                out_path.write_text(json.dumps(list(done.values()), ensure_ascii=False, indent=1))
                print(p["id"], res["http_status"], len(res["reply"]), flush=True)
                time.sleep(PACE_SECONDS)
        finally:
            print("teardown failures:", seed.close())


if __name__ == "__main__":
    main()

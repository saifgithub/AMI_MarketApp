"""Ask a chatbot a verbatim prompt in a fresh, tool-less conversation and keep the raw reply.

C02 and C08 test what a chatbot says when a retail user types the prompt from the videos. That
needs conversations with no memory of RES008, no tools and no project context, so each call
shells out to the Claude CLI from an empty directory in safe mode (no plugins, hooks, skills or
CLAUDE.md), with MCP servers off, tools off and a plain system prompt. Safe mode matters: without
it a developer-tool plugin injected its own context and replies opened with "I'm a development
assistant" — a first generation pass was discarded for exactly that (see each claim's RESULTS).
The raw JSON (exact model id included) is saved so every figure in RESULTS.md can be traced to
what the chatbot actually wrote.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SYSTEM_PROMPT = "You are a helpful assistant."
MODELS = ("haiku", "sonnet", "opus")


def _cli(args: list[str], cwd: str, timeout: int) -> dict:
    proc = subprocess.run(
        ["claude", *args, "--safe-mode", "--tools", "", "--strict-mcp-config", "--output-format", "json"],
        cwd=cwd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed ({proc.returncode}): {proc.stderr[:500]}")
    return json.loads(proc.stdout)


def ask(model: str, prompt: str, follow_up: str | None = None, timeout: int = 600) -> dict:
    """One fresh conversation. With `follow_up`, a second turn is sent in the same conversation."""
    with tempfile.TemporaryDirectory(prefix="res008_chat_") as cwd:
        first = _cli(["-p", prompt, "--model", model, "--system-prompt", SYSTEM_PROMPT], cwd, timeout)
        record = {
            "model_alias": model,
            "model_ids": sorted(first.get("modelUsage", {})),
            "prompt": prompt,
            "reply": first.get("result"),
        }
        if follow_up is not None:
            second = _cli(
                ["-p", follow_up, "--resume", first["session_id"], "--model", model,
                 "--system-prompt", SYSTEM_PROMPT],
                cwd, timeout,
            )
            record["follow_up"] = follow_up
            record["follow_up_reply"] = second.get("result")
            record["follow_up_model_ids"] = sorted(second.get("modelUsage", {}))
        return record


def ask_many(jobs: list[dict], out_dir: Path, workers: int = 4) -> None:
    """Run jobs ({name, model, prompt, follow_up?}) concurrently; skip names already on disk."""
    out_dir.mkdir(parents=True, exist_ok=True)

    def run(job: dict) -> str:
        path = out_dir / f"{job['name']}.json"
        if path.exists():
            return f"skip {job['name']}"
        try:
            record = ask(job["model"], job["prompt"], job.get("follow_up"))
        except Exception as exc:  # recorded, never silently dropped: a failed call is a result
            record = {"model_alias": job["model"], "prompt": job["prompt"], "error": repr(exc)}
        record["name"] = job["name"]
        path.write_text(json.dumps(record, indent=2))
        return f"{'FAIL' if 'error' in record else 'ok  '} {job['name']}"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for line in pool.map(run, jobs):
            print(line, flush=True)

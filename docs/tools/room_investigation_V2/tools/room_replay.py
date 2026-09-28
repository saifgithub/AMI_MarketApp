"""Replay ONE agent's EXACT captured prompt (system_prompt + messages, pulled
from llm_audit via `room_trace.py get`) N times against a provider and report
the answer distribution — "is THIS agent itself unstable on a fixed input, or
did it just receive different upstream input?" V2 replacement for v1
`docs/tools/room_investigation/room_agent_replay.py`: the repeat loop,
extraction, and rollup live in `library/replay.py` + `library/scoring.py`,
and the per-provider HTTP bodies live in `library/provider_gateway.py`'s
`direct_call` — one call path, one provider registry, no duplicated HTTP code.

Run this BEFORE concluding an agent itself is unstable: v1's BAC replay showed
5/5 stable draws per fixed input — the divergence lived upstream.

No `provider_gateway.force_provider` here (unlike the Room-running tools):
replay goes through `direct_call`, the single-call path, and never constructs
an LLMGateway — the per-provider key/endpoint checks in `direct_call` (and
this tool's upfront key checks) are the enforcement for this path.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import env_bootstrap, provider_gateway, replay  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay an exact captured agent prompt N times, report the answer distribution.",
    )
    parser.add_argument("--system-prompt-file", type=Path, required=True)
    parser.add_argument("--messages-file", type=Path, required=True, help="JSON list of {role, content}")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--label", default="replay")
    parser.add_argument("--extract-pattern", default=None,
                        help="regex with one capture group; default tries Side:/STANCE:")
    parser.add_argument("--extract-json-key", default=None,
                        help="portfolio_manager answers in JSON, not Side:/STANCE: — pass 'action' for it, "
                        "takes priority over --extract-pattern if both given")
    parser.add_argument("--temperature", type=float, default=None,
                        help="providers supporting pinning only (vllm, deepinfra) — RES009: temperature/seed "
                        "are otherwise unset everywhere in this codebase; cascade from 1.0 down only if draws disagree")
    parser.add_argument("--max-tokens", type=int, default=5000,
                        help="CR240 RES009 doc 16 (2026-09-27): the old 2000 default truncated 2/5 "
                        "vLLM+Arabic-translated-prompt PM draws mid-JSON")
    parser.add_argument("--provider", choices=sorted(provider_gateway.PROVIDERS), default="kimi")
    parser.add_argument("--model", default=None, help="provider model override (default: the provider's registered default)")
    parser.add_argument("--out-file", type=Path, required=True,
                        help="writes the replay result (draws, distribution, token totals) as JSON")
    return parser


async def main_async(args: argparse.Namespace) -> int:
    env_bootstrap.ensure_backend_path()
    env_bootstrap.load_repo_env()
    if args.provider == "kimi":
        env_bootstrap.require_kimi_open_platform_key()
    elif args.provider == "vllm":
        env_bootstrap.require_vllm()
    else:
        env_bootstrap.require_keys("DEEPINFR_API_KEY")

    system_prompt = args.system_prompt_file.read_text()
    messages = json.loads(args.messages_file.read_text())
    if not isinstance(messages, list):
        raise SystemExit(f"--messages-file must be a JSON list of {{role, content}}, got {type(messages).__name__}")

    temp_note = f", T={args.temperature}" if args.temperature is not None else ""
    print(f"=== {args.label} [{args.provider}{temp_note}] ({len(system_prompt)} char system_prompt) ===")

    try:
        result = await replay.replay_prompt(
            args.provider,
            system_prompt=system_prompt,
            messages=messages,
            repeats=args.repeats,
            extract_pattern=args.extract_pattern,
            extract_json_key=args.extract_json_key,
            temperature=args.temperature,
            model=args.model,
            max_tokens=args.max_tokens,
            label=args.label,
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    for d in result["draws"]:
        if d["error"]:
            print(f"  draw {d['draw']}/{args.repeats}: ERROR — {d['error']}")
            continue
        usage = d["usage"] or {}
        usage_note = ""
        if usage.get("prompt_tokens") is not None:
            usage_note = f"  [in={usage['prompt_tokens']} out={usage.get('completion_tokens')}]"
        print(f"  draw {d['draw']}/{args.repeats}: {d['extracted']}{usage_note}")

    print(f"  distribution: {result['distribution']}")
    totals = result["total_tokens"]
    reasoning_note = f" reasoning={totals['reasoning']}" if totals["reasoning"] else ""
    print(f"  tokens: in={totals['input']} out={totals['output']}{reasoning_note}")

    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(f"  wrote {args.out_file}")
    return 0


def main() -> int:
    return asyncio.run(main_async(build_parser().parse_args()))


if __name__ == "__main__":
    sys.exit(main())

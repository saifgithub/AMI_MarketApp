#!/usr/bin/env python3
"""Translate Flutter ARB strings via direct LAN call to vLLM.

Sister to scripts/translate_arb.py — same I/O contract, same prompt rules,
but POSTs straight to vLLM's OpenAI-compatible /v1/chat/completions on the
LAN. No Cloudflare Tunnel, no backend hop, no proxy timeout. Only usable
from a host that can reach 192.168.20.74:8000 — i.e. the Mac on the LAN.

When in doubt, use translate_arb.py (works from anywhere).
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from _i18n_script_guard import foreign_script_leak

DEFAULT_VLLM_URL = "http://192.168.20.74:8000"
DEFAULT_MODEL = "ami-llm"
DEFAULT_BATCH_SIZE = 20
DEFAULT_TIMEOUT_S = 300.0

REPO_ROOT = Path(__file__).resolve().parent.parent
ARB_DIR = REPO_ROOT / "mobile" / "lib" / "l10n"
EN_PATH = ARB_DIR / "app_en.arb"

TARGETS: dict[str, str] = {
    "ar": "Arabic (Modern Standard Arabic, as used in formal product UI)",
    "ms": "Malay (Bahasa Melayu, as used in Malaysian product UI)",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_arb(path: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=4)
    path.write_text(text + "\n", encoding="utf-8")


def _is_translatable_key(key: str) -> bool:
    return not key.startswith("@") and key != "appTitle"


def _build_messages(target_label: str, batch: dict[str, str]) -> list[dict]:
    system = (
        "You translate short user-interface strings for a mobile "
        "trading-education app called AMI Trade. Output is plain JSON only, "
        "no commentary, no markdown fences."
    )
    user = (
        f"Translate the following English UI strings into {target_label}.\n"
        "Rules:\n"
        "  1. Preserve every placeholder exactly as-is, including the curly "
        "braces. Examples: {ticker}, {count}, {version}.\n"
        "  2. Preserve the brand 'AMI' — never translate or transliterate it.\n"
        "  3. Preserve product/feature names that are upper-case English "
        "labels (e.g. CONVENE, FLOOR, PORTFOLIO, BUY, SELL, PROPOSE CHANGE, "
        "OPEN TRADE TICKET): translate the surrounding text but keep these "
        "tokens as-is when they appear inside a sentence. For standalone "
        "button labels (e.g. just \"CANCEL\" or \"CONVENE\"), translate them.\n"
        "  4. Preserve $ currency signs and digits.\n"
        "  5. Tone: confident, analyst-to-analyst, terse. No filler.\n"
        "  6. Output a single JSON object whose keys are the input keys "
        "and whose values are the translations.\n"
        "  7. Do not wrap output in ``` fences. Just the JSON object.\n"
        "Strings to translate:\n"
        f"{json.dumps(batch, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _post_chat(
    client: httpx.Client,
    vllm_url: str,
    model: str,
    messages: list[dict],
    max_tokens: int,
) -> str:
    resp = client.post(
        f"{vllm_url.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        },
    )
    resp.raise_for_status()
    body = resp.json()
    return body["choices"][0]["message"]["content"]


def _parse_json_object(raw: str) -> dict[str, str]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found in response")
    obj = json.loads(cleaned[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("response JSON is not an object")
    return {str(k): str(v) for k, v in obj.items()}


def _placeholders_lost(en_val: str, translated: str) -> bool:
    en_phs = set(re.findall(r"\{[a-zA-Z][a-zA-Z0-9_]*\}", en_val))
    tr_phs = set(re.findall(r"\{[a-zA-Z][a-zA-Z0-9_]*\}", translated))
    return en_phs != tr_phs


def _translate_batch(
    client: httpx.Client,
    vllm_url: str,
    model: str,
    target_label: str,
    batch: dict[str, str],
    *,
    log_prefix: str,
) -> dict[str, str] | None:
    messages = _build_messages(target_label, batch)
    max_tokens = max(1024, len(batch) * 96)
    for attempt in (1, 2):
        try:
            raw = _post_chat(client, vllm_url, model, messages, max_tokens)
            parsed = _parse_json_object(raw)
            kept = {k: parsed[k] for k in batch if k in parsed}
            missing = [k for k in batch if k not in parsed]
            if missing:
                print(
                    f"{log_prefix} attempt {attempt}: missing {len(missing)} keys: {missing[:5]}...",
                    file=sys.stderr,
                )
            if kept:
                return kept
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            print(
                f"{log_prefix} attempt {attempt} failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            if attempt == 1:
                time.sleep(2)
    return None


def _chunked(items: list[tuple[str, str]], size: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for k, v in items:
        cur[k] = v
        if len(cur) >= size:
            out.append(cur)
            cur = {}
    if cur:
        out.append(cur)
    return out


def translate_one_locale(
    client: httpx.Client,
    vllm_url: str,
    model: str,
    locale_code: str,
    target_label: str,
    *,
    batch_size: int,
    en_strings: dict[str, str],
    overwrite: bool,
) -> int:
    target_path = ARB_DIR / f"app_{locale_code}.arb"
    existing: dict[str, Any] = {}
    if target_path.exists():
        try:
            existing = _read_json(target_path)
        except json.JSONDecodeError:
            print(
                f"[{locale_code}] WARN: existing ARB is not valid JSON, starting fresh.",
                file=sys.stderr,
            )

    out: dict[str, Any] = dict(existing) if existing else {}
    out.setdefault("@@locale", locale_code)
    out["@@author"] = (
        "AMI Trade — auto-translated via on-prem Gemma 4 (vLLM, LAN-direct). "
        "Replace any line by hand for higher fidelity; the next run "
        "will leave manual entries alone."
    )
    out.setdefault("appTitle", "AMI Trade")

    pending: list[tuple[str, str]] = []
    for key, val in en_strings.items():
        if not overwrite:
            existing_val = out.get(key)
            if isinstance(existing_val, str) and existing_val.strip() and key != "appTitle":
                continue
        pending.append((key, val))

    if not pending:
        print(f"[{locale_code}] nothing to do — all {len(en_strings)} keys already filled.")
        return 0

    batches = _chunked(pending, batch_size)
    print(
        f"[{locale_code}] translating {len(pending)} keys in {len(batches)} "
        f"batch(es) of up to {batch_size}…"
    )

    failed_batches = 0
    started = time.time()
    for i, batch in enumerate(batches, start=1):
        log_prefix = f"[{locale_code} batch {i}/{len(batches)} ({len(batch)} keys)]"
        translations = _translate_batch(
            client, vllm_url, model, target_label, batch, log_prefix=log_prefix
        )
        if not translations:
            print(
                f"{log_prefix} FAILED — keys left unchanged: "
                f"{list(batch.keys())[:5]}...",
                file=sys.stderr,
            )
            failed_batches += 1
            continue
        for k, v in translations.items():
            if _placeholders_lost(batch[k], v):
                print(
                    f"{log_prefix} dropping {k!r} — placeholder mismatch",
                    file=sys.stderr,
                )
                continue
            leak = foreign_script_leak(v, locale_code)
            if leak:
                print(
                    f"{log_prefix} dropping {k!r} — foreign-script leak ({leak!r})",
                    file=sys.stderr,
                )
                continue
            out[k] = v
        _write_arb(target_path, out)
        print(f"{log_prefix} OK ({time.time() - started:.1f}s elapsed)")

    print(
        f"[{locale_code}] done — wrote {target_path.relative_to(REPO_ROOT)} "
        f"({len(en_strings)} source keys, {failed_batches} failed batch(es))."
    )
    return failed_batches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vllm-url", default=os.environ.get("AMI_VLLM_URL", DEFAULT_VLLM_URL))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--locales", nargs="+", choices=sorted(TARGETS.keys()), default=sorted(TARGETS.keys()))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not EN_PATH.exists():
        print(f"ERR: {EN_PATH} not found.", file=sys.stderr)
        return 2

    en_data = _read_json(EN_PATH)
    en_strings: dict[str, str] = collections.OrderedDict()
    for key, val in en_data.items():
        if _is_translatable_key(key):
            en_strings[key] = str(val)

    print(f"Source: {EN_PATH.relative_to(REPO_ROOT)} — {len(en_strings)} keys.")
    print(f"vLLM:   {args.vllm_url} (model={args.model})")
    if args.dry_run:
        print("DRY RUN — no calls will be made.")
        return 0

    failed_total = 0
    with httpx.Client(timeout=DEFAULT_TIMEOUT_S) as client:
        for code in args.locales:
            failed_total += translate_one_locale(
                client,
                args.vllm_url,
                args.model,
                code,
                TARGETS[code],
                batch_size=args.batch_size,
                en_strings=en_strings,
                overwrite=args.overwrite,
            )

    return 1 if failed_total else 0


if __name__ == "__main__":
    sys.exit(main())

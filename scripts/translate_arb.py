#!/usr/bin/env python3
"""Translate Flutter ARB strings via the on-prem Gemma 4 (vLLM) gateway.

Source of truth: ``mobile/lib/l10n/app_en.arb``.
Targets: ``app_ar.arb`` + ``app_ms.arb`` (any missing target appended).

The script POSTs each batch to the Alpha backend's
``/v1/llm/translate`` convenience endpoint — that route is a thin
non-streaming pass-through to the LLM gateway, which prefers vLLM
(Gemma 4 31B NVFP4) when reachable. We deliberately go through the
public Alpha hostname so this runs from anywhere; the LAN vLLM
endpoint is not exposed to the worktree sandbox.

Rules:
  - English-only keys (no ``@@`` metadata, no ``@<key>`` descriptions)
    are batched ~40 at a time and sent as a single JSON object.
  - The model is instructed to preserve ``{placeholder}`` syntax and to
    leave the brand "AMI" untranslated.
  - Existing non-empty entries in the target ARB are kept as-is —
    re-running only fills missing keys, so a manual translator's work
    is never overwritten.
  - Batch failures retry once; second failure logs the affected keys
    to stderr and proceeds. Final exit code is non-zero if any batch
    ultimately failed (so CI can catch silent partial runs).
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BACKEND_URL = "https://api-alpha.agenticmarketintel.ai"
DEFAULT_BATCH_SIZE = 40
DEFAULT_TIMEOUT_S = 180.0

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


# ---------------------------------------------------------------------------
# DEF295 — "translated" is a fact the file records, not one inferred from
# "the value is non-empty".
#
# Two shipped rules used to collide. DEF137's parity guard fails the build if a
# target ARB is missing any template key, so a new string must be written into
# all three files at once — in practice, seeded with the English. The skip rule
# below then treats any non-empty target value as a hand translation and leaves
# it alone, **forever**. The key is present, the parity guard is green, and the
# Arabic screen renders English: exactly the silent per-key fallback DEF137 was
# filed to stop, arriving through its own fix rather than around it. Measured
# 2026-08-13: 320 prose keys in `app_ar.arb` and 321 in `app_ms.arb` byte-
# identical to the English.
#
# The marker makes the two cases distinguishable. Each target ARB carries one
# `@@x-ami-seeds` object mapping key → `sha256[:12]` of the value that was
# seeded into it. A real translation is simply absent from that map.
# `@@`-prefixed entries are ARB file metadata; DEF137's parity guard already
# ignores everything `@`-prefixed, and `flutter gen-l10n` ignores it too
# (verified against both the per-key and the file-level form before choosing).
#
# **The marker is self-healing, which is the part that makes it safe.** A key
# counts as a seed only while its value still hashes to what was seeded. The
# translator clears the entry when it writes a translation, and a human who
# edits the value by hand stops being a seed at the moment they save — without
# knowing this mechanism exists and without having to clear anything. That
# closes the failure a bare "translated: false" flag would have opened, where
# forgetting to flip it re-translates over somebody's work — which is the exact
# thing the skip rule below exists to protect.
SEEDS_KEY = "@@x-ami-seeds"


def seed_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _seeds(target: dict[str, Any]) -> dict[str, str]:
    seeds = target.get(SEEDS_KEY)
    return seeds if isinstance(seeds, dict) else {}


def is_seed(target: dict[str, Any], key: str) -> bool:
    """Is `key`'s value in `target` still the untranslated seed it was given?"""
    recorded = _seeds(target).get(key)
    if not isinstance(recorded, str):
        return False
    value = target.get(key)
    return isinstance(value, str) and seed_hash(value) == recorded


def mark_seed(target: dict[str, Any], key: str, seeded_value: str) -> None:
    seeds = dict(_seeds(target))
    seeds[key] = seed_hash(seeded_value)
    target[SEEDS_KEY] = dict(sorted(seeds.items()))


def clear_seed(target: dict[str, Any], key: str) -> None:
    """Drop the marker now that `key` is translated."""
    seeds = dict(_seeds(target))
    if seeds.pop(key, None) is None:
        return
    if seeds:
        target[SEEDS_KEY] = seeds
    else:
        target.pop(SEEDS_KEY, None)


def pending_keys(
    target: dict[str, Any],
    en_strings: dict[str, str],
    *,
    overwrite: bool = False,
) -> list[str]:
    """Which keys this run should translate.

    Pure, and extracted from `_translate_locale` so the DEF295 guard can assert
    the rule directly instead of grepping for it.
    """
    out: list[str] = []
    for key in en_strings:
        if overwrite:
            out.append(key)
            continue
        existing = target.get(key)
        translated = (
            isinstance(existing, str)
            and existing.strip()
            and key != "appTitle"
            and not is_seed(target, key)
        )
        if not translated:
            out.append(key)
    return out


def seed_missing(target: dict[str, Any], en_strings: dict[str, str]) -> list[str]:
    """Fill every key the target is missing with English, MARKED as a seed.

    This is the step DEF137's parity guard forces, done in the one way that
    does not lie to the translator about what happened.
    """
    seeded: list[str] = []
    for key, en_val in en_strings.items():
        existing = target.get(key)
        if isinstance(existing, str) and existing.strip():
            continue
        target[key] = en_val
        mark_seed(target, key, en_val)
        seeded.append(key)
    return seeded


def _strip_arb_value(value: Any) -> str:
    # ARB string values are the only thing we translate; numbers / objects
    # don't show up in this codebase, so we coerce to str.
    return str(value)


def _build_prompt(target_label: str, batch: dict[str, str]) -> tuple[str, str]:
    system = (
        "You translate short user-interface strings for a mobile "
        "trading-education app called AMI Trade. Output is plain JSON only, "
        "no commentary, no markdown fences."
    )
    rules = (
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
    return system, rules


def _post_translate(
    client: httpx.Client,
    backend_url: str,
    system_prompt: str,
    user_message: str,
) -> tuple[str, str]:
    resp = client.post(
        f"{backend_url.rstrip('/')}/v1/llm/translate",
        json={
            "system_prompt": system_prompt,
            "user_message": user_message,
            "max_tokens": 4096,
        },
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("text", ""), body.get("provider", "?")


def _parse_json_object(raw: str) -> dict[str, str]:
    # Strip code fences if the model couldn't help itself.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    # Find the outer-most JSON object boundary; the model sometimes adds
    # a single trailing newline + commentary.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found in response")
    obj = json.loads(cleaned[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("response JSON is not an object")
    return {str(k): str(v) for k, v in obj.items()}


def _translate_batch(
    client: httpx.Client,
    backend_url: str,
    target_label: str,
    batch: dict[str, str],
    *,
    log_prefix: str,
) -> dict[str, str] | None:
    system_prompt, user_message = _build_prompt(target_label, batch)
    for attempt in (1, 2):
        try:
            text, provider = _post_translate(
                client, backend_url, system_prompt, user_message
            )
            parsed = _parse_json_object(text)
            # The model may return a subset; we only keep keys we asked for.
            kept = {k: parsed[k] for k in batch if k in parsed}
            missing = [k for k in batch if k not in parsed]
            if missing:
                print(
                    f"{log_prefix} attempt {attempt}: missing {len(missing)} keys "
                    f"(provider={provider}): {missing[:5]}...",
                    file=sys.stderr,
                )
            if kept:
                if attempt == 2 or missing:
                    print(
                        f"{log_prefix} attempt {attempt}: kept {len(kept)} of "
                        f"{len(batch)} (provider={provider})",
                        file=sys.stderr,
                    )
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
    backend_url: str,
    locale_code: str,
    target_label: str,
    *,
    batch_size: int,
    en_strings: dict[str, str],
    overwrite: bool,
) -> int:
    """Return number of batches that ultimately failed (0 == success)."""
    target_path = ARB_DIR / f"app_{locale_code}.arb"
    existing: dict[str, Any] = {}
    if target_path.exists():
        try:
            existing = _read_json(target_path)
        except json.JSONDecodeError:
            print(
                f"[{locale_code}] WARN: existing ARB is not valid JSON, "
                "starting from scratch (no destructive overwrite of "
                "untouched files — old contents in git).",
                file=sys.stderr,
            )

    # Preserve metadata + already-translated entries.
    out: dict[str, Any] = dict(existing) if existing else {}
    out.setdefault("@@locale", locale_code)
    out["@@author"] = (
        "AMI Trade — auto-translated via on-prem Gemma 4 (vLLM). "
        "Replace any line by hand for higher fidelity; the next run "
        "will leave manual entries alone."
    )
    out.setdefault("appTitle", "AMI Trade")

    # DEF295 — a key seeded with English to satisfy DEF137's parity guard is
    # pending, not done. `pending_keys` is the single place that decides.
    pending: list[tuple[str, str]] = [
        (k, en_strings[k]) for k in pending_keys(out, en_strings, overwrite=overwrite)
    ]
    seeds = sum(1 for k, _ in pending if is_seed(out, k))
    if seeds:
        print(f"[{locale_code}] {seeds} of those are English seeds (DEF295), not gaps.")

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
            client, backend_url, target_label, batch, log_prefix=log_prefix
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
            # Keep placeholder structure visible to translators — but if the
            # model dropped a placeholder, fall back to English for that key.
            if _placeholders_lost(batch[k], v):
                print(
                    f"{log_prefix} dropping {k!r} — placeholder mismatch",
                    file=sys.stderr,
                )
                failed_batches += 0  # not a batch-level failure, just one key
                continue
            out[k] = v
            # DEF295 — the marker is cleared BY the act of translating, so
            # "no marker" cannot drift away from "actually translated".
            clear_seed(out, k)
        # Persist after every batch so a partial run is still useful.
        _write_arb(target_path, out)
        print(f"{log_prefix} OK ({time.time() - started:.1f}s elapsed)")

    print(
        f"[{locale_code}] done — wrote {target_path.relative_to(REPO_ROOT)} "
        f"({len(en_strings)} source keys, {failed_batches} failed batch(es))."
    )
    return failed_batches


def _placeholders_lost(en_val: str, translated: str) -> bool:
    en_phs = set(re.findall(r"\{[a-zA-Z][a-zA-Z0-9_]*\}", en_val))
    tr_phs = set(re.findall(r"\{[a-zA-Z][a-zA-Z0-9_]*\}", translated))
    return en_phs != tr_phs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("AMI_BACKEND_URL", DEFAULT_BACKEND_URL),
        help="Base URL for the AMI Trade backend (default: Alpha).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Max strings per LLM call (default: 40).",
    )
    parser.add_argument(
        "--locales",
        nargs="+",
        choices=sorted(TARGETS.keys()),
        default=sorted(TARGETS.keys()),
        help="Subset of locales to translate (default: all).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-translate keys that already have non-empty values.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't call the LLM; only print what would be done.",
    )
    parser.add_argument(
        "--seed-missing",
        action="store_true",
        help=(
            "DEF295: fill keys the target ARBs are missing with English, "
            "MARKED as seeds, and exit. This is the step DEF137's parity "
            "guard forces after adding a string — run it instead of "
            "hand-copying, or the key is skipped by the translator forever."
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print how many keys are seeds vs translated per locale, and exit.",
    )
    args = parser.parse_args()

    if not EN_PATH.exists():
        print(f"ERR: {EN_PATH} not found.", file=sys.stderr)
        return 2

    en_data = _read_json(EN_PATH)
    en_strings: dict[str, str] = collections.OrderedDict()
    for key, val in en_data.items():
        if _is_translatable_key(key):
            en_strings[key] = _strip_arb_value(val)

    print(f"Source: {EN_PATH.relative_to(REPO_ROOT)} — {len(en_strings)} keys.")

    if args.seed_missing:
        for code in args.locales:
            path = ARB_DIR / f"app_{code}.arb"
            target = _read_json(path) if path.exists() else {"@@locale": code}
            seeded = seed_missing(target, en_strings)
            _write_arb(path, target)
            print(f"[{code}] seeded {len(seeded)} key(s): {seeded[:8]}"
                  f"{' …' if len(seeded) > 8 else ''}")
        return 0

    if args.report:
        for code in args.locales:
            path = ARB_DIR / f"app_{code}.arb"
            if not path.exists():
                print(f"[{code}] no ARB.")
                continue
            target = _read_json(path)
            seeds = [k for k in en_strings if is_seed(target, k)]
            missing = [k for k in en_strings if not str(target.get(k, "")).strip()]
            print(
                f"[{code}] {len(en_strings) - len(seeds) - len(missing)} translated, "
                f"{len(seeds)} English seed(s) awaiting translation, "
                f"{len(missing)} missing."
            )
        return 0

    print(f"Backend: {args.backend_url}")
    if args.dry_run:
        print("DRY RUN — no calls will be made.")
        return 0

    failed_total = 0
    with httpx.Client(timeout=DEFAULT_TIMEOUT_S) as client:
        for code in args.locales:
            label = TARGETS[code]
            failed_total += translate_one_locale(
                client,
                args.backend_url,
                code,
                label,
                batch_size=args.batch_size,
                en_strings=en_strings,
                overwrite=args.overwrite,
            )

    return 1 if failed_total else 0


if __name__ == "__main__":
    sys.exit(main())

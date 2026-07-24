#!/usr/bin/env python3
"""Score AR/MS lesson translations for semantic fidelity (CR083 Tier 3).

Placeholder-parity checks in translate_lessons_lan.py catch corruption
(dropped {placeholders}, mismatched MDX sentinels) — not *meaning*. The
only model diversity available for a real cross-check is manually
swapping which model is loaded on the on-prem vLLM host; there's no
second always-on API to call automatically. So this tool is a
repeatable, resumable PASS, not a one-shot two-model comparison:

  1. Read the currently-loaded model's identity from GET /v1/models.
  2. For each lesson/locale, ask that model to score EN-vs-translation
     semantic fidelity (confidence 1-5, meaning_preserved, issues).
  3. Append the result to content/i18n/lesson_confidence_log.json,
     keyed by (lesson_id, locale, model). Re-run after Saiful swaps the
     loaded model — results accumulate across passes.

"Reasonable confidence" (computed by --summary, not stored per-check):
  - Ordinary lessons: verified once >=2 distinct models agree (each
    scoring >=4/5) with zero unresolved critical_issues.
  - `strict_review` lessons (content/i18n/sensitive_keys.json) — the
    Islamic-finance unit: verified once >=3 distinct models agree, with
    zero issues of ANY severity (critical or minor).

Usage:
  scripts/i18n_verify_lesson_translation.py --ids 001_what_is_a_stock
  scripts/i18n_verify_lesson_translation.py --limit 5          # smoke test
  scripts/i18n_verify_lesson_translation.py --all
  scripts/i18n_verify_lesson_translation.py --summary          # no calls; report status from the log
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

DEFAULT_VLLM_URL = "http://192.168.20.74:8000"
DEFAULT_TIMEOUT_S = 300.0

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO_ROOT / "content" / "lessons"
I18N_DIR = REPO_ROOT / "content" / "i18n"
LOG_PATH = I18N_DIR / "lesson_confidence_log.json"
SENSITIVE_KEYS_PATH = I18N_DIR / "sensitive_keys.json"

LOCALES = ("ar", "ms")

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _strict_review_ids() -> set[str]:
    data = json.loads(SENSITIVE_KEYS_PATH.read_text(encoding="utf-8"))
    for entry in data.get("strict_review", []):
        if entry.get("scope") == "lessons":
            return set(entry["ids"])
    return set()


def _load_log() -> list[dict]:
    if LOG_PATH.exists():
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    return []


def _save_log(records: list[dict]) -> None:
    LOG_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _current_model(client: httpx.Client, vllm_url: str) -> str:
    resp = client.get(f"{vllm_url.rstrip('/')}/v1/models")
    resp.raise_for_status()
    data = resp.json()
    models = data.get("data") or []
    if not models:
        raise RuntimeError("vLLM /v1/models returned no models")
    return models[0]["id"]


def _post_chat(client: httpx.Client, vllm_url: str, model: str, messages: list[dict], max_tokens: int) -> str:
    resp = client.post(
        f"{vllm_url.rstrip('/')}/v1/chat/completions",
        json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.1},
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_json_object(raw: str) -> dict[str, Any]:
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
    return obj


def _body_only(text: str) -> str:
    m = FRONTMATTER_RE.match(text)
    return text[m.end():] if m else text


def _verify_prompt(en_body: str, tr_body: str, locale_label: str) -> list[dict]:
    system = (
        "You are a translation-quality reviewer for a mobile trading-education "
        "app called AMI Trade. You judge whether a translation preserves the "
        "SOURCE's meaning faithfully — you are not asked to translate anything. "
        "Output JSON only, no commentary, no code fences."
    )
    user = (
        f"SOURCE (English) and CANDIDATE ({locale_label}) lesson bodies follow. "
        "Ignore structural tags like <Term id=\"...\"/>, <ChatWith agent=\"...\"/>, "
        "<Animation .../> — they are non-translatable placeholders, not prose to "
        "judge. Judge the Quiz question/options/explanation text along with the "
        "prose.\n\n"
        "Score how faithfully the candidate preserves the source's meaning. "
        "Flag anything that inverts or changes a claim (e.g. a negation dropped "
        "or added, a warning/caveat lost, a technical term mistranslated into a "
        "different technical term) as a critical_issue. Flag awkward phrasing, "
        "register mismatches, or minor omissions as a minor_issue.\n\n"
        "Output a single JSON object:\n"
        '{"confidence": <1-5 integer>, "meaning_preserved": <bool>, '
        '"critical_issues": [<short strings>], "minor_issues": [<short strings>]}\n\n'
        f"=== SOURCE (English) ===\n{en_body}\n\n"
        f"=== CANDIDATE ({locale_label}) ===\n{tr_body}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _verify_one(client: httpx.Client, vllm_url: str, model: str, lesson_id: str, locale: str) -> dict | None:
    en_path = LESSONS_DIR / f"{lesson_id}.en.mdx"
    tr_path = LESSONS_DIR / f"{lesson_id}.{locale}.mdx"
    if not en_path.exists() or not tr_path.exists():
        return None
    en_body = _body_only(en_path.read_text(encoding="utf-8"))
    tr_body = _body_only(tr_path.read_text(encoding="utf-8"))
    locale_label = "Arabic" if locale == "ar" else "Malay"
    messages = _verify_prompt(en_body, tr_body, locale_label)
    max_tokens = max(1024, min(4096, len(en_body) // 3))
    log_prefix = f"[{lesson_id} {locale}]"
    for attempt in (1, 2):
        try:
            raw = _post_chat(client, vllm_url, model, messages, max_tokens)
            parsed = _parse_json_object(raw)
            return {
                "lesson_id": lesson_id,
                "locale": locale,
                "model": model,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "confidence": int(parsed.get("confidence", 0)),
                "meaning_preserved": bool(parsed.get("meaning_preserved", False)),
                "critical_issues": list(parsed.get("critical_issues") or []),
                "minor_issues": list(parsed.get("minor_issues") or []),
            }
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            print(f"{log_prefix} attempt {attempt} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            if attempt == 1:
                time.sleep(2)
    return None


def _is_verified(checks: list[dict], strict: bool) -> bool:
    by_model = {}
    for c in checks:
        by_model.setdefault(c["model"], []).append(c)
    min_models = 3 if strict else 2
    if len(by_model) < min_models:
        return False
    for model_checks in by_model.values():
        latest = model_checks[-1]
        if strict and (latest["critical_issues"] or latest["minor_issues"]):
            return False
        if not strict and latest["critical_issues"]:
            return False
        if latest["confidence"] < 4:
            return False
    return True


def _summarize(log: list[dict], strict_ids: set[str]) -> None:
    by_lesson_locale: dict[tuple[str, str], list[dict]] = {}
    for rec in log:
        by_lesson_locale.setdefault((rec["lesson_id"], rec["locale"]), []).append(rec)

    verified = 0
    needs_review = 0
    single_pass = 0
    for (lesson_id, locale), checks in sorted(by_lesson_locale.items()):
        strict = lesson_id in strict_ids
        models_seen = {c["model"] for c in checks}
        has_critical = any(c["critical_issues"] for c in checks)
        if _is_verified(checks, strict):
            verified += 1
            status = "VERIFIED"
        elif has_critical:
            needs_review += 1
            status = "NEEDS REVIEW (critical issue flagged)"
        else:
            single_pass += 1
            status = f"single/partial-pass ({len(models_seen)} model(s), strict={strict})"
        print(f"  {lesson_id} [{locale}]: {status}")

    print(f"\n{verified} verified, {needs_review} need review, {single_pass} awaiting more model passes.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vllm-url", default=os.environ.get("AMI_VLLM_URL", DEFAULT_VLLM_URL))
    parser.add_argument("--ids", nargs="+", help="Specific lesson ids (filename stem before .en.mdx).")
    parser.add_argument("--all", action="store_true", help="Verify every lesson that has an ar/ms translation.")
    parser.add_argument("--limit", type=int, default=None, help="Only check the first N lessons (smoke test).")
    parser.add_argument("--locales", nargs="+", choices=list(LOCALES), default=list(LOCALES))
    parser.add_argument("--summary", action="store_true", help="No LLM calls — report verified/needs-review status from the existing log.")
    args = parser.parse_args()

    strict_ids = _strict_review_ids()
    log = _load_log()

    if args.summary:
        _summarize(log, strict_ids)
        return 0

    if args.ids:
        lesson_ids = args.ids
    else:
        lesson_ids = sorted(p.name[: -len(".en.mdx")] for p in LESSONS_DIR.glob("*.en.mdx"))
        if args.limit:
            lesson_ids = lesson_ids[: args.limit]

    with httpx.Client(timeout=DEFAULT_TIMEOUT_S) as client:
        model = _current_model(client, args.vllm_url)
        print(f"vLLM currently loaded model: {model}")
        checked = 0
        for lesson_id in lesson_ids:
            for locale in args.locales:
                result = _verify_one(client, args.vllm_url, model, lesson_id, locale)
                if result is None:
                    continue
                log.append(result)
                checked += 1
                strict = lesson_id in strict_ids
                print(
                    f"  [{lesson_id} {locale}] confidence={result['confidence']} "
                    f"critical={len(result['critical_issues'])} minor={len(result['minor_issues'])}"
                    f"{' (strict_review)' if strict else ''}"
                )

    _save_log(log)
    print(f"\n{checked} check(s) appended to {LOG_PATH.relative_to(REPO_ROOT)}.")
    print("Run with --summary to see verified/needs-review status.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

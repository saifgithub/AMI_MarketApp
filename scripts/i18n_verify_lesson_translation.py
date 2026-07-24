#!/usr/bin/env python3
"""Score AR/MS lesson translations for semantic fidelity (CR083 Tier 3).

Placeholder-parity checks in translate_lessons_lan.py catch corruption
(dropped {placeholders}, mismatched MDX sentinels) — not *meaning*. Two
independent, always-on models on the LAN provide the cross-check:

  - "primary" (ami-llm, http://192.168.20.74:8000) — the same model that
    did the translation. Whole-lesson-body single-shot; 262k context.
  - "allam" (allam-7b-instruct, http://192.168.20.74:8040, same physical
    host as primary — resolves via ami-host.local) — an Arabic-specialized
    model (SDAIA ALLaM), AR-only (tested weak/unreliable on Malay).
    max_model_len is only 4096 tokens — a full lesson's EN+AR body
    together routinely exceeds that (median lesson body alone is ~1730
    tokens), so this endpoint gets CHUNKED verification: split by
    markdown heading into aligned EN/AR sections (translate_lessons_lan.py
    preserves heading structure 1:1, so section counts should match; a
    proportional character-slice is the fallback if they don't), verify
    each section independently, then take the worst-case across chunks
    (min confidence, AND of meaning_preserved, union of issues).

Run repeatably — results accumulate in content/i18n/lesson_confidence_log.json,
keyed by (lesson_id, locale, model). A future third model (e.g. manually
swapped onto the primary host) still works the same way: it just becomes
a third distinct entry in the log.

"Reasonable confidence" (computed by --summary, not stored per-check):
  - Ordinary lessons: verified once >=2 distinct models agree (each
    scoring >=4/5) with zero unresolved critical_issues.
  - `strict_review` lessons (content/i18n/sensitive_keys.json) — the
    Islamic-finance unit: verified once >=3 distinct models agree, with
    zero issues of ANY severity (critical or minor). With only 2
    always-on models, this cluster still needs one manually-swapped pass
    on the primary host to close.

Usage:
  scripts/i18n_verify_lesson_translation.py --ids 001_what_is_a_stock
  scripts/i18n_verify_lesson_translation.py --limit 5          # smoke test
  scripts/i18n_verify_lesson_translation.py --all
  scripts/i18n_verify_lesson_translation.py --models allam     # AR-only, skip primary
  scripts/i18n_verify_lesson_translation.py --summary          # no calls; report status from the log
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

DEFAULT_TIMEOUT_S = 300.0

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO_ROOT / "content" / "lessons"
I18N_DIR = REPO_ROOT / "content" / "i18n"
LOG_PATH = I18N_DIR / "lesson_confidence_log.json"
SENSITIVE_KEYS_PATH = I18N_DIR / "sensitive_keys.json"

LOCALES = ("ar", "ms")

# Endpoint registry. `chunk_chars=None` means whole-body single-shot (huge
# context budget); a number means split into aligned sections of roughly
# that many characters each, to stay well within a small max_model_len.
ENDPOINTS: dict[str, dict[str, Any]] = {
    "primary": {
        "url": os.environ.get("AMI_VLLM_URL", "http://192.168.20.74:8000"),
        "locales": ("ar", "ms"),
        "chunk_chars": None,
    },
    "allam": {
        "url": os.environ.get("AMI_ALLAM_URL", "http://192.168.20.74:8040"),
        "locales": ("ar",),
        "chunk_chars": 1800,
    },
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6}\s.*)$", re.MULTILINE)


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


def _current_model(client: httpx.Client, url: str) -> str:
    resp = client.get(f"{url.rstrip('/')}/v1/models")
    resp.raise_for_status()
    data = resp.json()
    models = data.get("data") or []
    if not models:
        raise RuntimeError(f"{url}/v1/models returned no models")
    return models[0]["id"]


def _post_chat(client: httpx.Client, url: str, model: str, messages: list[dict], max_tokens: int) -> str:
    resp = client.post(
        f"{url.rstrip('/')}/v1/chat/completions",
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


# ---------- chunking (for small-context endpoints like allam) -----------

def _split_by_heading(text: str) -> list[str]:
    positions = [m.start() for m in HEADING_RE.finditer(text)]
    if not positions:
        return [text] if text.strip() else []
    sections = []
    if positions[0] > 0 and text[: positions[0]].strip():
        sections.append(text[: positions[0]])
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        sections.append(text[pos:end])
    return sections


def _rechunk_oversized(sections: list[str], target_chars: int) -> list[str]:
    out: list[str] = []
    for s in sections:
        if len(s) <= target_chars:
            out.append(s)
            continue
        paras = [p for p in re.split(r"\n{2,}", s) if p.strip()]
        cur: list[str] = []
        cur_len = 0
        for p in paras:
            if cur and cur_len + len(p) > target_chars:
                out.append("\n\n".join(cur))
                cur = []
                cur_len = 0
            cur.append(p)
            cur_len += len(p)
        if cur:
            out.append("\n\n".join(cur))
    return out or sections


def _proportional_slices(text: str, n: int) -> list[str]:
    n = max(1, n)
    size = max(1, math.ceil(len(text) / n))
    return [text[i * size : (i + 1) * size] for i in range(n)]


def _chunk_pair(en_body: str, tr_body: str, target_chars: int) -> list[tuple[str, str]]:
    en_sections = _rechunk_oversized(_split_by_heading(en_body), target_chars)
    tr_sections = _rechunk_oversized(_split_by_heading(tr_body), target_chars)
    if en_sections and tr_sections and len(en_sections) == len(tr_sections):
        return list(zip(en_sections, tr_sections))
    # Fallback: heading structure didn't line up 1:1 — slice proportionally.
    n = max(len(en_sections), len(tr_sections), 1)
    return list(zip(_proportional_slices(en_body, n), _proportional_slices(tr_body, n)))


# ---------- prompt + single-call verify ----------------------------------

def _verify_prompt(en_text: str, tr_text: str, locale_label: str, chunk_note: str = "") -> list[dict]:
    system = (
        "You are a translation-quality reviewer for a mobile trading-education "
        "app called AMI Trade. You judge whether a translation preserves the "
        "SOURCE's meaning faithfully — you are not asked to translate anything. "
        "Output JSON only, no commentary, no code fences."
    )
    user = (
        f"{chunk_note}"
        f"SOURCE (English) and CANDIDATE ({locale_label}) lesson text follow. "
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
        f"=== SOURCE (English) ===\n{en_text}\n\n"
        f"=== CANDIDATE ({locale_label}) ===\n{tr_text}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _call_verify(
    client: httpx.Client, url: str, model: str, en_text: str, tr_text: str,
    locale_label: str, log_prefix: str, chunk_note: str = "",
) -> dict | None:
    messages = _verify_prompt(en_text, tr_text, locale_label, chunk_note)
    max_tokens = max(512, min(2048, len(en_text) // 3))
    for attempt in (1, 2):
        try:
            raw = _post_chat(client, url, model, messages, max_tokens)
            parsed = _parse_json_object(raw)
            return {
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


def _verify_via_endpoint(
    client: httpx.Client, endpoint_name: str, endpoint: dict, model: str,
    lesson_id: str, locale: str, en_body: str, tr_body: str,
) -> dict | None:
    locale_label = "Arabic" if locale == "ar" else "Malay"
    log_prefix = f"[{lesson_id} {locale} {endpoint_name}]"
    chunk_chars = endpoint.get("chunk_chars")

    if chunk_chars is None:
        result = _call_verify(client, endpoint["url"], model, en_body, tr_body, locale_label, log_prefix)
        if result is None:
            return None
        results = [result]
    else:
        pairs = _chunk_pair(en_body, tr_body, chunk_chars)
        results = []
        for i, (en_c, tr_c) in enumerate(pairs, start=1):
            note = f"This is section {i} of {len(pairs)} from a longer lesson — judge only this excerpt, don't penalize for missing surrounding context.\n\n"
            r = _call_verify(client, endpoint["url"], model, en_c, tr_c, locale_label, f"{log_prefix} chunk{i}/{len(pairs)}", note)
            if r is not None:
                results.append(r)
        if not results:
            return None

    # Aggregate across chunks: worst-case confidence, AND meaning_preserved, union of issues.
    return {
        "lesson_id": lesson_id,
        "locale": locale,
        "model": model,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "confidence": min(r["confidence"] for r in results),
        "meaning_preserved": all(r["meaning_preserved"] for r in results),
        "critical_issues": [i for r in results for i in r["critical_issues"]],
        "minor_issues": [i for r in results for i in r["minor_issues"]],
        "chunks_checked": len(results),
    }


def _is_verified(checks: list[dict], strict: bool) -> bool:
    by_model: dict[str, list[dict]] = {}
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
            status = f"single/partial-pass ({len(models_seen)} model(s): {', '.join(sorted(models_seen))}, strict={strict})"
        print(f"  {lesson_id} [{locale}]: {status}")

    print(f"\n{verified} verified, {needs_review} need review, {single_pass} awaiting more model passes.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="+", help="Specific lesson ids (filename stem before .en.mdx).")
    parser.add_argument("--all", action="store_true", help="Verify every lesson that has an ar/ms translation.")
    parser.add_argument("--limit", type=int, default=None, help="Only check the first N lessons (smoke test).")
    parser.add_argument("--locales", nargs="+", choices=list(LOCALES), default=list(LOCALES))
    parser.add_argument("--models", nargs="+", choices=list(ENDPOINTS.keys()), default=list(ENDPOINTS.keys()),
                        help="Which endpoints to call. Default: all applicable to each locale.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-check (lesson, locale, model) combos that already have a log entry. Default: skip them (resume-safe after a hang/kill).")
    parser.add_argument("--summary", action="store_true", help="No LLM calls — report verified/needs-review status from the existing log.")
    args = parser.parse_args()

    strict_ids = _strict_review_ids()
    log = _load_log()

    if args.summary:
        _summarize(log, strict_ids)
        return 0

    already_checked = {(r["lesson_id"], r["locale"], r["model"]) for r in log}

    if args.ids:
        lesson_ids = args.ids
    else:
        lesson_ids = sorted(p.name[: -len(".en.mdx")] for p in LESSONS_DIR.glob("*.en.mdx"))
        if args.limit:
            lesson_ids = lesson_ids[: args.limit]

    with httpx.Client(timeout=DEFAULT_TIMEOUT_S) as client:
        model_by_endpoint: dict[str, str] = {}
        for name in args.models:
            model_by_endpoint[name] = _current_model(client, ENDPOINTS[name]["url"])
            print(f"{name}: {ENDPOINTS[name]['url']} -> model={model_by_endpoint[name]}")

        checked = 0
        for lesson_id in lesson_ids:
            en_path = LESSONS_DIR / f"{lesson_id}.en.mdx"
            if not en_path.exists():
                continue
            en_body = _body_only(en_path.read_text(encoding="utf-8"))
            for locale in args.locales:
                tr_path = LESSONS_DIR / f"{lesson_id}.{locale}.mdx"
                if not tr_path.exists():
                    continue
                tr_body = _body_only(tr_path.read_text(encoding="utf-8"))
                for name in args.models:
                    endpoint = ENDPOINTS[name]
                    if locale not in endpoint["locales"]:
                        continue
                    if not args.overwrite and (lesson_id, locale, model_by_endpoint[name]) in already_checked:
                        print(f"  [{lesson_id} {locale} {name}] skip (already checked)")
                        continue
                    result = _verify_via_endpoint(
                        client, name, endpoint, model_by_endpoint[name],
                        lesson_id, locale, en_body, tr_body,
                    )
                    if result is None:
                        continue
                    log.append(result)
                    checked += 1
                    strict = lesson_id in strict_ids
                    print(
                        f"  [{lesson_id} {locale} {name}] confidence={result['confidence']} "
                        f"critical={len(result['critical_issues'])} minor={len(result['minor_issues'])} "
                        f"chunks={result.get('chunks_checked', 1)}"
                        f"{' (strict_review)' if strict else ''}"
                    )
                    _save_log(log)  # persist after every check — a partial run is still useful

    print(f"\n{checked} check(s) appended to {LOG_PATH.relative_to(REPO_ROOT)}.")
    print("Run with --summary to see verified/needs-review status.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Score AR/MS lesson translations for semantic fidelity (CR083 Tier 3).

Placeholder-parity checks in translate_lessons_lan.py catch corruption
(dropped {placeholders}, mismatched MDX sentinels) — not *meaning*. Three
independent, always-on models on the LAN provide the cross-check — each on
its own port, so primary/falcon can be called concurrently (never send
concurrent requests to the *same* port):

  - "primary" (ami-llm, http://192.168.20.74:8000) — the same model that
    did the translation. Whole-lesson-body single-shot; 262k context.
  - "falcon" (falcon-h1-34b-gptq, http://192.168.20.74:8044, separate port
    on the same physical host as primary) — the 2nd always-on model added
    2026-07-27. AR+MS. 32768 context; whole-lesson-body single-shot
    (worst-case lesson in the corpus measures ~5.8k prompt tokens, ~5.5x
    headroom — no chunking needed). Adversarially tested as clearly better
    than allam/JAIS at catching genuine meaning-inverting errors (see CR083
    history) — this is what brought lessons up to the 2-model verified bar
    at corpus scale for the first time.
  - "allam" (allam-7b-instruct, http://192.168.20.74:8040, same physical
    host as primary — resolves via ami-host.local) — an Arabic-specialized
    model (SDAIA ALLaM), AR-only (tested weak/unreliable on Malay).
    max_model_len is only 4096 tokens — a full lesson's EN+AR body
    together routinely exceeds that (median lesson body alone is ~1730
    tokens), so this endpoint gets CHUNKED verification: split by markdown
    heading into aligned EN/AR sections, then any oversized section is
    further split by PARAGRAPH and paired by index (translation preserves
    1:1 paragraph correspondence) before batching adjacent pairs up to the
    character budget — pairing happens on structural correspondence, never
    by independently re-chunking each language against a shared character
    budget (that approach let same-index chunks silently stop matching,
    since translated text runs a different length than the source).
    A proportional character-slice is the last-resort fallback, scoped to
    just the section (or, if heading counts themselves don't match, the
    whole body) where structural correspondence breaks down. Verify each
    resulting chunk independently, then take the worst-case across chunks
    (min confidence, AND of meaning_preserved, union of issues). In
    practice allam echoes candidate text back as "critique" more often
    than it critiques (confirmed noise) — treat its results as the weakest
    signal of the three, useful mainly as a 3rd pass for strict_review.

Run repeatably — results accumulate in content/i18n/lesson_confidence_log.json,
keyed by (lesson_id, locale, model).

"Reasonable confidence" (computed by --summary, not stored per-check):
  - Ordinary lessons: verified once >=2 distinct models agree (each
    scoring >=4/5) with zero unresolved critical_issues. primary+falcon
    alone now satisfies this for every lesson with both translations.
  - `strict_review` lessons (content/i18n/sensitive_keys.json) — the
    Islamic-finance unit: verified once >=3 distinct models agree, with
    zero issues of ANY severity (critical or minor). Needs primary+falcon
    +allam (AR) together; MS strict_review lessons still cap at 2 models
    (allam is AR-only) until a 3rd MS-capable model exists.

Usage:
  scripts/i18n_verify_lesson_translation.py --ids 001_what_is_a_stock
  scripts/i18n_verify_lesson_translation.py --limit 5          # smoke test
  scripts/i18n_verify_lesson_translation.py --all
  scripts/i18n_verify_lesson_translation.py --models primary falcon  # 2-model pass, skip allam
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
    "falcon": {
        "url": os.environ.get("AMI_FALCON_URL", "http://192.168.20.74:8044"),
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


def _split_paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n{2,}", text) if p.strip()]


def _batch_pairs(pairs: list[tuple[str, str]], target_chars: int) -> list[tuple[str, str]]:
    """Group consecutive ALREADY-ALIGNED (en, tr) paragraph pairs together up
    to target_chars. A pair is never split from its partner, so batching
    can't introduce drift the way independently re-chunking each language
    can."""
    out: list[tuple[str, str]] = []
    cur_en: list[str] = []
    cur_tr: list[str] = []
    cur_len = 0
    for en_p, tr_p in pairs:
        pair_len = max(len(en_p), len(tr_p))
        if cur_en and cur_len + pair_len > target_chars:
            out.append(("\n\n".join(cur_en), "\n\n".join(cur_tr)))
            cur_en, cur_tr, cur_len = [], [], 0
        cur_en.append(en_p)
        cur_tr.append(tr_p)
        cur_len += pair_len
    if cur_en:
        out.append(("\n\n".join(cur_en), "\n\n".join(cur_tr)))
    return out


def _proportional_slices(text: str, n: int) -> list[str]:
    n = max(1, n)
    size = max(1, math.ceil(len(text) / n))
    return [text[i * size : (i + 1) * size] for i in range(n)]


def _rechunk_section_pair(en_section: str, tr_section: str, target_chars: int) -> list[tuple[str, str]]:
    """Split one aligned (en, tr) heading-section into one or more aligned
    sub-pairs when either side exceeds target_chars.

    The previous approach re-chunked each language's section independently
    by greedily grouping paragraphs against a character budget — since
    translated text runs a different length than the source, the two
    languages' budget cutoffs land at different paragraph indices, so
    same-index chunks silently stop corresponding to the same content (only
    caught if the final counts happened to differ; if they coincidentally
    matched, the misalignment was invisible). Confirmed on
    071_how_to_verify_before_you_wire_money: EN's cutoff fell after its
    4th numbered point while AR's fell after its 5th, so "chunk 2" compared
    an EN example paragraph against an unrelated AR list item.

    Splitting by paragraph and pairing by INDEX first removes the guesswork
    entirely — translation preserves 1:1 paragraph correspondence (the
    prose-translation prompt requires it), so paragraph N in one language
    is paragraph N in the other. Only if paragraph *counts* genuinely
    diverge for this section does this fall back to a character slice —
    and that fallback is scoped to just this one section, not the whole
    lesson body, so a single divergent section can't silently degrade
    every other chunk in the lesson.
    """
    if len(en_section) <= target_chars and len(tr_section) <= target_chars:
        return [(en_section, tr_section)]
    en_paras = _split_paragraphs(en_section)
    tr_paras = _split_paragraphs(tr_section)
    if en_paras and tr_paras and len(en_paras) == len(tr_paras):
        return _batch_pairs(list(zip(en_paras, tr_paras)), target_chars)
    n = max(1, math.ceil(max(len(en_section), len(tr_section)) / target_chars))
    return list(zip(_proportional_slices(en_section, n), _proportional_slices(tr_section, n)))


def _chunk_pair(en_body: str, tr_body: str, target_chars: int) -> list[tuple[str, str]]:
    en_sections = _split_by_heading(en_body)
    tr_sections = _split_by_heading(tr_body)
    if not en_sections or not tr_sections or len(en_sections) != len(tr_sections):
        # Heading structure itself didn't line up 1:1 — whole-body proportional fallback.
        n = max(len(en_sections), len(tr_sections), 1)
        return list(zip(_proportional_slices(en_body, n), _proportional_slices(tr_body, n)))
    pairs: list[tuple[str, str]] = []
    for en_s, tr_s in zip(en_sections, tr_sections):
        pairs.extend(_rechunk_section_pair(en_s, tr_s, target_chars))
    return pairs


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
        active_models: list[str] = []
        for name in args.models:
            try:
                model_by_endpoint[name] = _current_model(client, ENDPOINTS[name]["url"])
            except (httpx.HTTPError, RuntimeError) as exc:
                print(f"WARNING: {name} ({ENDPOINTS[name]['url']}) unreachable, skipping for this run: "
                      f"{type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            active_models.append(name)
            print(f"{name}: {ENDPOINTS[name]['url']} -> model={model_by_endpoint[name]}")

        if not active_models:
            print("No endpoints reachable — aborting.", file=sys.stderr)
            return 1

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
                for name in active_models:
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

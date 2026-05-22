#!/usr/bin/env python3
"""Translate AMI Trade JSON content via direct LAN call to vLLM.

Sister to scripts/translate_arb_lan.py — same OpenAI chat-completions
client + vLLM endpoint, but works on the structured JSON content files
(glossary terms, AI coach Q&A, daily challenges) where each record has
a known set of translatable text fields and structural fields that
must pass through unchanged.

Output locations (locale fallback in the backend handles missing files):
  glossary         → content/glossary/terms.<loc>.json     (loader-ready)
  ai_coach         → content/ai_coach/<loc>/<file>.json    (subdir; needs
                     a small loader change before going live)
  daily_challenges → content/daily_challenges/<loc>/<file>.json (same)

Run-direction:
  scripts/translate_content_lan.py --type glossary
  scripts/translate_content_lan.py --type ai_coach --locales ar
  scripts/translate_content_lan.py --type daily_challenges --batch-size 3
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_VLLM_URL = "http://192.168.20.74:8000"
DEFAULT_MODEL = "ami-llm"
DEFAULT_TIMEOUT_S = 300.0

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"

LOCALE_LABELS: dict[str, str] = {
    "ar": "Arabic (Modern Standard Arabic, as used in formal product UI)",
    "ms": "Malay (Bahasa Melayu, as used in Malaysian product UI)",
}


@dataclasses.dataclass(frozen=True)
class ContentSpec:
    """Defines how to translate one content type."""
    name: str
    source_glob: str         # e.g. "glossary/terms.en.json"
    text_fields: tuple[str, ...]      # scalar string fields to translate
    list_text_fields: tuple[str, ...] = ()  # list-of-string fields to translate
    locale_field: str | None = None    # if set, overwrite this field with the target locale
    output_pattern: str = ""           # f-string with {locale}; relative to CONTENT_DIR
    default_batch_size: int = 5


SPECS: dict[str, ContentSpec] = {
    "glossary": ContentSpec(
        name="glossary",
        source_glob="glossary/terms.en.json",
        text_fields=("term", "definition"),
        output_pattern="glossary/terms.{locale}.json",
        default_batch_size=8,
    ),
    "ai_coach": ContentSpec(
        name="ai_coach",
        source_glob="ai_coach/*.json",
        text_fields=("question", "short_answer", "long_answer"),
        output_pattern="ai_coach/{locale}/{filename}",
        default_batch_size=4,
    ),
    "daily_challenges": ContentSpec(
        name="daily_challenges",
        source_glob="daily_challenges/*.json",
        text_fields=("scenario", "question", "explanation"),
        list_text_fields=("options",),
        locale_field="locale",
        output_pattern="daily_challenges/{locale}/{filename}",
        default_batch_size=3,
    ),
}


# ---------- LLM plumbing -----------------------------------------------

def _build_messages(target_label: str, payload: dict[str, Any]) -> list[dict]:
    system = (
        "You translate JSON content for a mobile trading-education app "
        "called AMI Trade. Output is plain JSON only, no commentary, "
        "no markdown fences."
    )
    user = (
        f"Translate every string value in the following JSON object into {target_label}.\n"
        "Rules:\n"
        "  1. Output JSON with the SAME top-level keys and the SAME structure.\n"
        "  2. Each top-level key maps to an object whose keys MUST exactly "
        "match the input object's inner keys. Translate ONLY the string "
        "values; do not rename keys, drop keys, or add new keys.\n"
        "  3. For lists of strings, translate each list entry; keep the "
        "list length and order identical.\n"
        "  4. Preserve the brand 'AMI' — never translate or transliterate it.\n"
        "  5. Preserve all ticker symbols in uppercase Latin (e.g. AAPL, "
        "MSFT, MAYBANK). Preserve agent role names if they appear inline "
        "(e.g. Bull Researcher, Bear Researcher, Fundamentals Analyst, "
        "Portfolio Manager) — keep the English label.\n"
        "  6. Preserve all numbers, percent signs, currency signs ($, RM, "
        "SAR), date formats, and placeholders inside {curly braces}.\n"
        "  7. Tone: confident, analyst-to-analyst, terse. No filler, no "
        "marketing puffery.\n"
        "  8. Output a single JSON object whose keys are the input keys.\n"
        "  9. No code fences, no commentary. Just the JSON object.\n"
        "Object to translate:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _post_chat(
    client: httpx.Client, vllm_url: str, model: str,
    messages: list[dict], max_tokens: int,
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


def _placeholders_lost(en_val: str, translated: str) -> bool:
    en_phs = set(re.findall(r"\{[a-zA-Z][a-zA-Z0-9_]*\}", en_val))
    tr_phs = set(re.findall(r"\{[a-zA-Z][a-zA-Z0-9_]*\}", translated))
    return en_phs != tr_phs


# ---------- per-record translate ---------------------------------------

def _record_translatable_payload(record: dict, spec: ContentSpec) -> dict:
    out: dict[str, Any] = {}
    for f in spec.text_fields:
        if f in record and isinstance(record[f], str):
            out[f] = record[f]
    for f in spec.list_text_fields:
        if f in record and isinstance(record[f], list):
            out[f] = [str(x) for x in record[f]]
    return out


def _apply_translations(record: dict, translated: dict, spec: ContentSpec) -> tuple[dict, list[str]]:
    """Return (new_record, problems)."""
    problems: list[str] = []
    new = dict(record)
    for f in spec.text_fields:
        if f not in record:
            continue
        if f not in translated:
            problems.append(f"missing field {f}")
            continue
        en_val = record[f]
        tr_val = translated[f]
        if not isinstance(tr_val, str):
            problems.append(f"field {f} not a string in translation")
            continue
        if _placeholders_lost(str(en_val), tr_val):
            problems.append(f"field {f} placeholder mismatch")
            continue
        new[f] = tr_val
    for f in spec.list_text_fields:
        if f not in record:
            continue
        if f not in translated:
            problems.append(f"missing list field {f}")
            continue
        en_list = record[f]
        tr_list = translated[f]
        if not isinstance(tr_list, list) or len(tr_list) != len(en_list):
            problems.append(f"list field {f} length mismatch")
            continue
        new_items = []
        ok = True
        for en_item, tr_item in zip(en_list, tr_list):
            if not isinstance(tr_item, str):
                ok = False
                break
            if _placeholders_lost(str(en_item), tr_item):
                ok = False
                break
            new_items.append(tr_item)
        if not ok:
            problems.append(f"list field {f} item mismatch")
            continue
        new[f] = new_items
    return new, problems


def _translate_batch_records(
    client: httpx.Client, vllm_url: str, model: str, target_label: str,
    batch: list[tuple[int, dict]], spec: ContentSpec, log_prefix: str,
) -> dict[int, dict] | None:
    """batch is [(index, record), ...]. Returns {index: translated_record}."""
    payload: dict[str, dict] = {}
    for idx, rec in batch:
        key = rec.get("id") or f"_idx_{idx}"
        payload[str(key)] = _record_translatable_payload(rec, spec)

    messages = _build_messages(target_label, payload)
    # crude size estimate — each field is roughly 1.4x output tokens of input.
    avg_chars = max(1, sum(len(json.dumps(v)) for v in payload.values()) // max(1, len(payload)))
    max_tokens = min(8192, max(1024, len(batch) * avg_chars * 2))

    for attempt in (1, 2):
        try:
            raw = _post_chat(client, vllm_url, model, messages, max_tokens)
            parsed = _parse_json_object(raw)
            out: dict[int, dict] = {}
            for idx, rec in batch:
                key = str(rec.get("id") or f"_idx_{idx}")
                if key not in parsed or not isinstance(parsed[key], dict):
                    continue
                new_rec, problems = _apply_translations(rec, parsed[key], spec)
                if problems:
                    print(
                        f"{log_prefix} key={key!r}: {'; '.join(problems)} — "
                        "keeping EN for affected fields",
                        file=sys.stderr,
                    )
                out[idx] = new_rec
            if out:
                return out
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            print(
                f"{log_prefix} attempt {attempt} failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            if attempt == 1:
                time.sleep(2)
    return None


# ---------- file-level processing --------------------------------------

def _resolve_output_path(spec: ContentSpec, source_path: Path, locale: str) -> Path:
    rel_source = source_path.relative_to(CONTENT_DIR)
    if "{filename}" in spec.output_pattern:
        # Strip the leading source-stem locale marker if present (e.g. terms.en → terms)
        filename = source_path.name
        if filename.endswith(".en.json"):
            filename = filename[:-8] + ".json"
        out = spec.output_pattern.format(locale=locale, filename=filename)
    else:
        out = spec.output_pattern.format(locale=locale)
    return CONTENT_DIR / out


def _process_file(
    client: httpx.Client, vllm_url: str, model: str, spec: ContentSpec,
    source_path: Path, locale: str, target_label: str, batch_size: int,
    overwrite: bool,
) -> tuple[int, int]:
    """Return (translated_count, failed_count)."""
    src = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(src, list):
        print(f"  skip {source_path.name}: not a list", file=sys.stderr)
        return (0, 0)

    out_path = _resolve_output_path(spec, source_path, locale)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing_by_id: dict[str, dict] = {}
    if out_path.exists():
        try:
            prior = json.loads(out_path.read_text(encoding="utf-8"))
            if isinstance(prior, list):
                for r in prior:
                    rid = r.get("id")
                    if rid:
                        existing_by_id[rid] = r
        except json.JSONDecodeError:
            pass

    # Decide what's pending. If overwrite or no prior entry, translate.
    pending: list[tuple[int, dict]] = []
    output: list[dict | None] = [None] * len(src)
    for i, rec in enumerate(src):
        rid = rec.get("id")
        if not overwrite and rid and rid in existing_by_id:
            output[i] = existing_by_id[rid]
            continue
        pending.append((i, rec))

    if not pending:
        print(f"  {source_path.name}: nothing to translate; {len(src)} already filled.")
        return (0, 0)

    # Chunk
    batches: list[list[tuple[int, dict]]] = []
    for k in range(0, len(pending), batch_size):
        batches.append(pending[k : k + batch_size])

    print(
        f"  {source_path.name}: {len(pending)}/{len(src)} pending in "
        f"{len(batches)} batch(es) of up to {batch_size}…"
    )

    translated_total = 0
    failed_total = 0
    started = time.time()
    for bi, batch in enumerate(batches, start=1):
        log_prefix = f"    [{source_path.name} b{bi}/{len(batches)} ({len(batch)})]"
        translations = _translate_batch_records(
            client, vllm_url, model, target_label, batch, spec, log_prefix=log_prefix,
        )
        if not translations:
            print(
                f"{log_prefix} FAILED — keeping EN for "
                f"{[rec.get('id') for _, rec in batch][:3]}...",
                file=sys.stderr,
            )
            for idx, rec in batch:
                output[idx] = dict(rec)
                if spec.locale_field and spec.locale_field in rec:
                    output[idx][spec.locale_field] = locale  # type: ignore[index]
            failed_total += 1
            continue

        for idx, rec in batch:
            new_rec = translations.get(idx, dict(rec))
            if spec.locale_field and spec.locale_field in new_rec:
                new_rec[spec.locale_field] = locale
            output[idx] = new_rec
            translated_total += 1

        # Persist after every batch so a partial run is still useful.
        out_list = [r for r in output if r is not None]
        out_path.write_text(
            json.dumps(out_list, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{log_prefix} OK ({time.time() - started:.1f}s)")

    # Final fill — any record that's still None gets the EN fallback (in case
    # a batch failed entirely and we marked failures earlier).
    for i, r in enumerate(output):
        if r is None:
            fallback = dict(src[i])
            if spec.locale_field and spec.locale_field in fallback:
                fallback[spec.locale_field] = locale
            output[i] = fallback

    out_path.write_text(
        json.dumps([r for r in output], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"  {source_path.name}: wrote {out_path.relative_to(REPO_ROOT)} "
        f"(translated {translated_total}/{len(src)}, "
        f"failed batches {failed_total})."
    )
    return (translated_total, failed_total)


# ---------- entry point ------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--type",
        required=True,
        choices=sorted(SPECS.keys()),
        help="Which content corpus to translate.",
    )
    parser.add_argument("--vllm-url", default=os.environ.get("AMI_VLLM_URL", DEFAULT_VLLM_URL))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Records per LLM call. Default per type.")
    parser.add_argument("--locales", nargs="+", choices=sorted(LOCALE_LABELS.keys()),
                        default=sorted(LOCALE_LABELS.keys()))
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-translate records that already exist in the output file.")
    parser.add_argument("--limit-files", type=int, default=None,
                        help="Translate only the first N source files (for smoke tests).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    spec = SPECS[args.type]
    batch_size = args.batch_size or spec.default_batch_size

    sources = sorted(CONTENT_DIR.glob(spec.source_glob))
    if args.limit_files:
        sources = sources[: args.limit_files]
    if not sources:
        print(f"No sources matched {spec.source_glob}", file=sys.stderr)
        return 2

    total_records = 0
    for p in sources:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                total_records += len(data)
        except Exception:
            pass

    print(f"Type:     {spec.name}")
    print(f"Sources:  {len(sources)} file(s), {total_records} record(s)")
    print(f"vLLM:     {args.vllm_url} (model={args.model})")
    print(f"Batch:    {batch_size}")
    print(f"Locales:  {', '.join(args.locales)}")
    if args.dry_run:
        for p in sources:
            print(f"  would translate {p.relative_to(REPO_ROOT)}")
        return 0

    failed_total = 0
    started = time.time()
    with httpx.Client(timeout=DEFAULT_TIMEOUT_S) as client:
        for locale in args.locales:
            target_label = LOCALE_LABELS[locale]
            print(f"\n=== {locale} ({target_label}) ===")
            for src_path in sources:
                _, fails = _process_file(
                    client, args.vllm_url, args.model, spec, src_path,
                    locale, target_label, batch_size, args.overwrite,
                )
                failed_total += fails

    elapsed = time.time() - started
    print(f"\nDone in {elapsed:.1f}s. {failed_total} failed batch(es) overall.")
    return 1 if failed_total else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Translate AMI Trade lesson MDX files via direct LAN call to vLLM.

Each lesson is `content/lessons/<id>.en.mdx` — YAML frontmatter plus an
MDX body that mixes prose, markdown headers, and four MDX components:

  <Term id="…" />            (672×) — id-only, no translation
  <ChatWith agent="…" />     (270×) — id-only, no translation
  <Animation … />            ( 15×) — placeholder slot, no translation
  <Quiz question="…" options={[…]} answer={N} explanation="…" />
                             (571×) — question/options/explanation translate;
                                       answer is structural

Approach:
  1. Parse frontmatter; translate `title` only; bump `locale_versions`
     to include the target locale; copy everything else verbatim.
  2. Find every MDX component in the body and substitute a sentinel
     placeholder (e.g. `<<MDX_7>>`). Pass-through components (Term /
     ChatWith / Animation) keep their original text; Quiz components
     are translated separately as structured JSON, then reconstituted.
  3. Send the placeholder-laden prose to vLLM with strict instructions
     to preserve the sentinels and translate everything else. Markdown
     headers ride along inside the same prose call.
  4. For each Quiz, batch question/options/explanation as JSON; send a
     small batch (default 4 quizzes per call); validate placeholder
     parity and option-list length.
  5. Reassemble the file: translated frontmatter + translated prose
     with sentinels swapped back for the (verbatim or re-translated)
     MDX components. Write to `content/lessons/<id>.<locale>.mdx`.

Lessons that already exist in the target locale are skipped unless
`--overwrite` is set. Output is written after every lesson completes,
so a partial run is still useful.
"""

from __future__ import annotations

import argparse
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
LESSONS_DIR = REPO_ROOT / "content" / "lessons"

LOCALE_LABELS: dict[str, str] = {
    "ar": "Arabic (Modern Standard Arabic, as used in formal product UI)",
    "ms": "Malay (Bahasa Melayu, as used in Malaysian product UI)",
}

SENTINEL_RE = re.compile(r"<<MDX_(\d+)>>")
COMPONENT_RE = re.compile(r"<(Quiz|Term|ChatWith|Animation)\b.*?/>", re.DOTALL)

# `<Lesson id="…"/>` cross-references sometimes sit inside a Quiz
# question/explanation attribute's quoted string. Neutralized in its own
# pass, before COMPONENT_RE runs — otherwise the tag's own embedded `/>`
# fools COMPONENT_RE's non-greedy match into ending the Quiz block early,
# and its embedded `"` truncates _parse_quiz's attribute extraction.
LESSON_TAG_RE = re.compile(r'<Lesson\b[^>]*?/>')


# ---------- LLM plumbing -----------------------------------------------

def _post_chat(client: httpx.Client, vllm_url: str, model: str,
               messages: list[dict], max_tokens: int) -> str:
    resp = client.post(
        f"{vllm_url.rstrip('/')}/v1/chat/completions",
        json={
            "model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": 0.2,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _strip_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n", "", s)
        s = re.sub(r"\n```$", "", s)
    return s


def _parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = _strip_fence(raw)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found in response")
    obj = json.loads(cleaned[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("response JSON is not an object")
    return obj


# ---------- Frontmatter ------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return ("", text)
    return (m.group(1), text[m.end() :])


def _frontmatter_title(fm: str) -> str | None:
    m = re.search(r'^title:\s*"(.*?)"\s*$', fm, re.MULTILINE)
    return m.group(1) if m else None


def _frontmatter_replace_title(fm: str, new_title: str) -> str:
    # YAML double-quoted scalar: a literal `"` in the translated title (the
    # LLM sometimes renders an English single-quoted phrase as Arabic/Malay
    # double quotes) must be escaped or it terminates the string early and
    # breaks frontmatter parsing for the whole file.
    escaped_title = new_title.replace("\\", "\\\\").replace('"', '\\"')
    return re.sub(
        r'^title:\s*".*?"\s*$',
        f'title: "{escaped_title}"',
        fm,
        count=1,
        flags=re.MULTILINE,
    )


def _frontmatter_set_locale(fm: str, locale: str) -> str:
    # Update locale_versions to include the target locale.
    def _repl(m: re.Match[str]) -> str:
        cur = m.group(1)
        try:
            arr = json.loads(cur)
        except json.JSONDecodeError:
            arr = ["en"]
        if locale not in arr:
            arr.append(locale)
        return f"locale_versions: {json.dumps(arr)}"

    return re.sub(
        r"^locale_versions:\s*(\[.*?\])\s*$",
        _repl,
        fm,
        count=1,
        flags=re.MULTILINE,
    )


# ---------- Quiz extraction --------------------------------------------

# JSX string attr: question="..." or explanation="..."
# Allow escaped quotes \" inside, dash characters, etc.
_QUIZ_STRING_ATTR_RE = re.compile(
    r'(question|explanation)="((?:[^"\\]|\\.)*)"',
)
_QUIZ_OPTIONS_RE = re.compile(
    r"options=\{\[(.*?)\]\}",
    re.DOTALL,
)
_QUIZ_OPTION_ITEM_RE = re.compile(
    r'"((?:[^"\\]|\\.)*)"',
)
_QUIZ_ANSWER_RE = re.compile(r"answer=\{(\d+)\}")


# Inverse of `_escape_for_jsx` below. Deliberately narrow — a codec-based
# unescape (e.g. `unicode_escape`) mangles any non-ASCII byte (em-dashes,
# curly quotes) in this UTF-8 content, so only undo the two sequences
# `_escape_for_jsx` actually produces.
_JSX_ESCAPE_RE = re.compile(r'\\\\|\\"')


def _unescape(s: str) -> str:
    if "\\" not in s:
        return s
    return _JSX_ESCAPE_RE.sub(lambda m: "\\" if m.group(0) == "\\\\" else '"', s)


def _escape_for_jsx(s: str) -> str:
    # JSX double-quoted strings: escape backslashes and double-quotes.
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _parse_quiz(block: str) -> dict[str, Any]:
    """Return {question, options:[...], answer, explanation, _raw: block}."""
    out: dict[str, Any] = {"_raw": block}
    for m in _QUIZ_STRING_ATTR_RE.finditer(block):
        out[m.group(1)] = _unescape(m.group(2))
    opt_match = _QUIZ_OPTIONS_RE.search(block)
    if opt_match:
        opts_raw = opt_match.group(1)
        out["options"] = [
            _unescape(m.group(1)) for m in _QUIZ_OPTION_ITEM_RE.finditer(opts_raw)
        ]
    ans_match = _QUIZ_ANSWER_RE.search(block)
    if ans_match:
        out["answer"] = int(ans_match.group(1))
    return out


def _render_quiz(q: dict[str, Any], translated: dict[str, Any]) -> str:
    """Rebuild Quiz JSX from English structure + translated strings.

    Falls back to the English value for any field that's missing or
    placeholder-broken in `translated`.
    """
    def _pick(field: str, default: Any) -> Any:
        v = translated.get(field, default)
        return v if v is not None else default

    question = _pick("question", q.get("question", ""))
    explanation = _pick("explanation", q.get("explanation", ""))
    options = translated.get("options")
    if (
        not isinstance(options, list)
        or len(options) != len(q.get("options", []))
    ):
        options = q.get("options", [])
    answer = q.get("answer", 0)

    indent = "  "
    lines = [
        "<Quiz",
        f'{indent}question="{_escape_for_jsx(question)}"',
        f"{indent}options={{[",
    ]
    for opt in options:
        lines.append(f'{indent}{indent}"{_escape_for_jsx(opt)}",')
    # JSX array trailing comma is fine in MDX; matches existing files which
    # don't have a trailing comma either, but the runtime is lenient.
    if lines[-1].endswith(","):
        lines[-1] = lines[-1].rstrip(",")
    lines.append(f"{indent}]}}")
    lines.append(f"{indent}answer={{{answer}}}")
    lines.append(f'{indent}explanation="{_escape_for_jsx(explanation)}"')
    lines.append("/>")
    return "\n".join(lines)


# ---------- Body segmentation ------------------------------------------

def _replace_components_with_sentinels(body: str) -> tuple[str, list[str]]:
    components: list[str] = []
    def _sub(m: re.Match[str]) -> str:
        idx = len(components)
        components.append(m.group(0))
        return f"<<MDX_{idx}>>"
    # Lesson refs first (may be nested inside a Quiz attribute string), then
    # the top-level components — by the time COMPONENT_RE runs, any Lesson
    # ref that was hiding inside a Quiz block's own attributes is already a
    # plain `<<MDX_N>>` token, so it can no longer truncate that match.
    body = LESSON_TAG_RE.sub(_sub, body)
    new = COMPONENT_RE.sub(_sub, body)
    return new, components


def _restore_components(prose: str, components: list[str]) -> str:
    def _sub(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        if 0 <= idx < len(components):
            return components[idx]
        return m.group(0)
    # A Quiz component's own rendered text can itself contain a nested
    # Lesson-ref sentinel (protected before Quiz attribute parsing), so
    # loop until stable rather than assuming one pass resolves everything.
    prev = None
    while prev != prose:
        prev = prose
        prose = SENTINEL_RE.sub(_sub, prose)
    return prose


# ---------- Prompts ----------------------------------------------------

def _prose_prompt(target_label: str, prose: str) -> list[dict]:
    system = (
        "You translate Markdown content for a mobile trading-education app "
        "called AMI Trade. Output plain Markdown only — no commentary, no "
        "code fences around the whole reply."
    )
    user = (
        f"Translate the following Markdown into {target_label}.\n"
        "STRICT RULES:\n"
        "  1. Preserve every `<<MDX_N>>` sentinel exactly as-is, in the "
        "same position in the text. They mark MDX components that will "
        "be restored after translation. Never translate, rename, or "
        "drop them.\n"
        "  2. Preserve markdown structure: heading levels (#, ##, ###), "
        "list bullets, code fences, blockquotes, and emphasis markers "
        "(*, **, _, __). Translate the prose; keep the punctuation.\n"
        "  3. Preserve the brand 'AMI' — never translate or transliterate it.\n"
        "  4. Preserve ticker symbols in uppercase Latin (e.g. AAPL, MSFT, "
        "MAYBANK, NVDA) and any inline agent role names (Bull Researcher, "
        "Bear Researcher, Fundamentals Analyst, Portfolio Manager, "
        "Market Analyst, News Analyst, Trader, Conservative Debator, "
        "Aggressive Debator, Neutral Debator, Research Manager, "
        "Social Media Analyst, Concierge).\n"
        "  5. Preserve numbers, percent signs, currency signs ($, RM, "
        "SAR), and date formats.\n"
        "  6. Preserve any literal `{placeholder}` patterns inside braces.\n"
        "  7. Tone: confident, analyst-to-analyst, terse. No filler, no "
        "marketing puffery, no editorialising.\n"
        "Markdown to translate:\n"
        "----------\n"
        f"{prose}\n"
        "----------\n"
        "Output the translated Markdown only. Do not wrap in ``` fences."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _quiz_batch_prompt(target_label: str, batch: dict[str, dict]) -> list[dict]:
    system = (
        "You translate JSON content for a mobile trading-education app "
        "called AMI Trade. Output is plain JSON only, no commentary, "
        "no markdown fences."
    )
    user = (
        f"Translate every string value into {target_label}.\n"
        "Rules:\n"
        "  1. Output JSON with the SAME top-level keys and SAME inner keys.\n"
        "  2. For each quiz, translate `question`, `explanation`, and each "
        "entry of `options`. Do NOT add, drop, or reorder option entries.\n"
        "  3. Preserve the brand 'AMI'. Preserve ticker symbols (uppercase "
        "Latin) and agent role names (Bull Researcher, Bear Researcher, "
        "Fundamentals Analyst, Portfolio Manager, Market Analyst, News "
        "Analyst, Trader, Conservative Debator, Aggressive Debator, "
        "Neutral Debator, Research Manager, Social Media Analyst, "
        "Concierge).\n"
        "  4. Preserve numbers, percent signs, currency signs, and any "
        "`{placeholder}` patterns inside curly braces.\n"
        "  5. Preserve every `<<MDX_N>>` sentinel exactly as-is, in the "
        "same position in the text. They mark cross-reference tags that "
        "will be restored after translation. Never translate, rename, or "
        "drop them.\n"
        "  6. Tone: confident, analyst-to-analyst, terse.\n"
        "  7. Output a single JSON object. No code fences.\n"
        "Quizzes to translate:\n"
        f"{json.dumps(batch, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _title_batch_prompt(target_label: str, titles: dict[str, str]) -> list[dict]:
    system = (
        "You translate short lesson titles for a mobile trading-education "
        "app called AMI Trade. Output is plain JSON only."
    )
    user = (
        f"Translate the following lesson titles into {target_label}.\n"
        "Preserve the brand 'AMI'. Preserve ticker symbols (uppercase Latin).\n"
        "Output a single JSON object mapping each input key to the "
        "translated title. No code fences.\n"
        f"{json.dumps(titles, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------- Validation helpers -----------------------------------------

def _placeholders_lost(en_val: str, translated: str) -> bool:
    en_phs = set(re.findall(r"\{[a-zA-Z][a-zA-Z0-9_]*\}", en_val))
    tr_phs = set(re.findall(r"\{[a-zA-Z][a-zA-Z0-9_]*\}", translated))
    return en_phs != tr_phs


def _sentinels_preserved(original: str, translated: str) -> bool:
    o = set(SENTINEL_RE.findall(original))
    t = set(SENTINEL_RE.findall(translated))
    return o == t


# ---------- Per-lesson worker -----------------------------------------

def _translate_prose(
    client: httpx.Client, vllm_url: str, model: str,
    target_label: str, prose: str, log_prefix: str,
) -> str | None:
    messages = _prose_prompt(target_label, prose)
    # Output is roughly the same length as input; allow generous headroom.
    max_tokens = max(2048, min(16384, len(prose) // 2))
    # A heading with nothing under it but component sentinels (e.g. "## Quiz"
    # right above bare <<MDX_N>> placeholders) occasionally gets dropped
    # wholesale rather than mistranslated — a sampling quirk, not a token-
    # budget one (seen at finish_reason=stop well under max_tokens). More
    # attempts empirically recovers it more often than 2 does.
    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        try:
            raw = _post_chat(client, vllm_url, model, messages, max_tokens)
            translated = _strip_fence(raw).strip()
            if not _sentinels_preserved(prose, translated):
                print(
                    f"{log_prefix} prose attempt {attempt}: sentinel "
                    "mismatch — retrying",
                    file=sys.stderr,
                )
                if attempt < max_attempts:
                    time.sleep(2)
                    continue
                return None
            return translated
        except (httpx.HTTPError, ValueError) as exc:
            print(
                f"{log_prefix} prose attempt {attempt} failed: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            if attempt == 1:
                time.sleep(2)
    return None


def _translate_quizzes(
    client: httpx.Client, vllm_url: str, model: str, target_label: str,
    quizzes: list[dict], batch_size: int, log_prefix: str,
) -> list[dict]:
    """Return list aligned with `quizzes`; each element is the translated
    string-only dict (question/options/explanation). On failure, returns the
    English original for that quiz."""
    out: list[dict] = [None] * len(quizzes)  # type: ignore[list-item]
    # Batch. `q["question"]`/`q["explanation"]` may already contain
    # `<<MDX_N>>` sentinels (Lesson refs neutralized before Quiz attribute
    # parsing) — plain JSON string content, so no extra protection needed
    # here, just preservation through the round trip (checked below).
    for start in range(0, len(quizzes), batch_size):
        chunk = quizzes[start : start + batch_size]
        payload: dict[str, dict] = {}
        for i, q in enumerate(chunk):
            slot = start + i
            key = f"q{slot}"
            payload[key] = {
                "question": q.get("question", ""),
                "options": list(q.get("options", [])),
                "explanation": q.get("explanation", ""),
            }
        messages = _quiz_batch_prompt(target_label, payload)
        avg_chars = max(1, sum(len(json.dumps(v)) for v in payload.values()) // max(1, len(payload)))
        max_tokens = min(8192, max(1024, len(chunk) * avg_chars * 2))

        parsed: dict[str, Any] | None = None
        for attempt in (1, 2):
            try:
                raw = _post_chat(client, vllm_url, model, messages, max_tokens)
                parsed = _parse_json_object(raw)
                break
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                print(
                    f"{log_prefix} quiz batch {start}-{start+len(chunk)} "
                    f"attempt {attempt} failed: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                if attempt == 1:
                    time.sleep(2)

        for i, q in enumerate(chunk):
            slot = start + i
            key = f"q{slot}"
            if not parsed or key not in parsed or not isinstance(parsed[key], dict):
                # Fall back to English for this quiz.
                out[slot] = {
                    "question": q.get("question", ""),
                    "options": list(q.get("options", [])),
                    "explanation": q.get("explanation", ""),
                }
                continue
            tr = parsed[key]
            tr_question = tr.get("question") if isinstance(tr.get("question"), str) else q.get("question", "")
            tr_explanation = tr.get("explanation") if isinstance(tr.get("explanation"), str) else q.get("explanation", "")
            tr_options = tr.get("options") if isinstance(tr.get("options"), list) else None
            en_options = list(q.get("options", []))
            if (
                tr_options is None
                or len(tr_options) != len(en_options)
                or not all(isinstance(o, str) for o in tr_options)
            ):
                tr_options = en_options
            # Placeholder parity guard.
            if _placeholders_lost(q.get("question", ""), tr_question):
                tr_question = q.get("question", "")
            if _placeholders_lost(q.get("explanation", ""), tr_explanation):
                tr_explanation = q.get("explanation", "")
            # Sentinel parity guard (Lesson-ref tokens must survive intact).
            if not _sentinels_preserved(q.get("question", ""), tr_question):
                tr_question = q.get("question", "")
            if not _sentinels_preserved(q.get("explanation", ""), tr_explanation):
                tr_explanation = q.get("explanation", "")
            out[slot] = {
                "question": tr_question,
                "options": tr_options,
                "explanation": tr_explanation,
            }
    return out  # type: ignore[return-value]


def _translate_title(
    client: httpx.Client, vllm_url: str, model: str,
    target_label: str, title: str, log_prefix: str,
) -> str:
    payload = {"t": title}
    messages = _title_batch_prompt(target_label, payload)
    for attempt in (1, 2):
        try:
            raw = _post_chat(client, vllm_url, model, messages, 256)
            parsed = _parse_json_object(raw)
            if isinstance(parsed.get("t"), str) and parsed["t"].strip():
                return parsed["t"]
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            print(
                f"{log_prefix} title attempt {attempt} failed: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            if attempt == 1:
                time.sleep(2)
    return title  # English fallback


def _process_lesson(
    client: httpx.Client, vllm_url: str, model: str, source_path: Path,
    locale: str, target_label: str, quiz_batch_size: int, log_prefix: str,
) -> bool:
    text = source_path.read_text(encoding="utf-8")
    fm_block, body = _split_frontmatter(text)
    if not fm_block:
        print(f"{log_prefix} no frontmatter; skipping {source_path.name}",
              file=sys.stderr)
        return False

    # Step 1: replace components with sentinels.
    prose_with_sentinels, components = _replace_components_with_sentinels(body)

    # Step 2: extract Quiz components for separate translation.
    quizzes: list[dict] = []
    quiz_index_map: list[int] = []  # component index in `components`
    for ci, comp in enumerate(components):
        if comp.startswith("<Quiz"):
            quizzes.append(_parse_quiz(comp))
            quiz_index_map.append(ci)

    # Step 3: translate prose.
    translated_prose = _translate_prose(
        client, vllm_url, model, target_label, prose_with_sentinels, log_prefix,
    )
    if translated_prose is None:
        print(f"{log_prefix} prose translation failed; using English body",
              file=sys.stderr)
        translated_prose = prose_with_sentinels

    # Step 4: translate quizzes.
    if quizzes:
        translated_quizzes = _translate_quizzes(
            client, vllm_url, model, target_label, quizzes,
            quiz_batch_size, log_prefix,
        )
        # Reconstruct Quiz components with translated strings.
        for q_idx, tr in zip(quiz_index_map, translated_quizzes):
            en_quiz = _parse_quiz(components[q_idx])
            components[q_idx] = _render_quiz(en_quiz, tr)

    # Step 5: restore components.
    final_body = _restore_components(translated_prose, components)

    # Step 6: translate title.
    en_title = _frontmatter_title(fm_block) or ""
    tr_title = _translate_title(
        client, vllm_url, model, target_label, en_title, log_prefix,
    ) if en_title else ""
    new_fm = _frontmatter_replace_title(fm_block, tr_title) if tr_title else fm_block
    new_fm = _frontmatter_set_locale(new_fm, locale)

    # Step 7: write output.
    name = source_path.name
    if name.endswith(".en.mdx"):
        name = name[:-7] + f".{locale}.mdx"
    else:
        name = name.replace(".mdx", f".{locale}.mdx")
    out_path = source_path.parent / name
    final_text = f"---\n{new_fm}\n---\n{final_body}"
    out_path.write_text(final_text, encoding="utf-8")
    return True


# ---------- Entry ------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vllm-url", default=os.environ.get("AMI_VLLM_URL", DEFAULT_VLLM_URL))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--locales", nargs="+", choices=sorted(LOCALE_LABELS.keys()),
                        default=sorted(LOCALE_LABELS.keys()))
    parser.add_argument("--quiz-batch-size", type=int, default=4)
    parser.add_argument("--limit-files", type=int, default=None,
                        help="Translate only the first N lessons (smoke test).")
    parser.add_argument("--ids", nargs="+", default=None,
                        help="Translate only these lesson ids (stem before .en.mdx).")
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-translate lessons that already exist in the target locale.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sources = sorted(LESSONS_DIR.glob("*.en.mdx"))
    if args.ids:
        wanted = set(args.ids)
        sources = [p for p in sources if p.name[: -len(".en.mdx")] in wanted]
        missing = wanted - {p.name[: -len(".en.mdx")] for p in sources}
        if missing:
            print(f"WARNING: ids not found: {sorted(missing)}", file=sys.stderr)
    if args.limit_files:
        sources = sources[: args.limit_files]
    if not sources:
        print(f"No .en.mdx lessons found under {LESSONS_DIR}", file=sys.stderr)
        return 2

    print(f"Lessons:  {len(sources)} source file(s)")
    print(f"vLLM:     {args.vllm_url} (model={args.model})")
    print(f"Quiz batch: {args.quiz_batch_size}")
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
            for i, src_path in enumerate(sources, start=1):
                out_name = src_path.name.replace(".en.mdx", f".{locale}.mdx")
                out_path = src_path.parent / out_name
                if out_path.exists() and not args.overwrite:
                    print(f"  [{i}/{len(sources)}] skip (exists) {src_path.name}")
                    continue
                log_prefix = f"  [{locale} {i}/{len(sources)} {src_path.name}]"
                t0 = time.time()
                ok = _process_lesson(
                    client, args.vllm_url, args.model, src_path,
                    locale, target_label, args.quiz_batch_size, log_prefix,
                )
                elapsed_one = time.time() - t0
                status = "OK" if ok else "FAILED"
                print(f"{log_prefix} {status} ({elapsed_one:.1f}s)")
                if not ok:
                    failed_total += 1

    elapsed = time.time() - started
    print(f"\nDone in {elapsed:.1f}s. {failed_total} lesson(s) failed.")
    return 1 if failed_total else 0


if __name__ == "__main__":
    sys.exit(main())

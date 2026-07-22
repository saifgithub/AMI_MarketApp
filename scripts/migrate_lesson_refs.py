#!/usr/bin/env python3
"""CR053-MIGRATE — migrate bare cross-lesson prose refs to identifiable/linkable forms.

CR044 replaced the user-visible lesson identifier (the tile/reader now show
`meta.codeLabel`, e.g. "FUND 8") but 117+ lesson bodies still cross-reference
each other by the old bare numeric id ("lesson 039", "023 (support and
resistance)"). That number appears nowhere in the app any more — see
docs/forward_planning/CR053_curriculum_reference_identifiability/ §2.2.

This migrates two surfaces:

  A. Lesson bodies (content/lessons/*.en.mdx) — bare cross-lesson refs become
     `<Lesson id="<full lesson id>"/>` (parse_mdx / CR053-BE substitutes this
     to a `{{lesson:<id>}}` token the mobile reader renders as a tappable
     CR044-code chip). TWO ref classes, resolved differently:

       Class 1 — GLOBAL-ID refs: a "lesson NNN" written 3-digit/zero-padded,
       OR any value >=16 whose zero-padded 3-digit form matches a real
       content/lessons/<NNN>_*.en.mdx. Resolved directly against the id_by_num
       map built from every lesson's frontmatter.

       Class 2 — WITHIN-MODULE ORDINALS: a bare 1-2 digit "lesson N" (value
       <=15, NOT zero-padded) inside a lesson carrying a CR044 `code` with
       prefix P means "the module's Nth lesson", i.e. the lesson coded "P N"
       — NOT global id N. Resolved via the code->id map, same-prefix only. If
       "P N" doesn't exist, the ref is left untouched and flagged — guessing
       here would link the wrong lesson while still passing the resolve guard
       (a global id N might legitimately exist too), so correctness must come
       from the same-prefix resolution itself, not a fallback.

     NOTE on the id attribute value: it is the FULL frontmatter id
     ("039_the_pe_ratio"), not a bare 3-digit number. `LessonMeta.id` (what
     backend/tests/unit/test_lesson_corpus_integrity.py's resolve guard checks
     `{{lesson:ID}}` tokens against, and what the mobile catalogue's
     `_findLessonMetaById` matches by) is the full frontmatter id everywhere
     except CR053-MOBILE's own fixture/widget-test shorthand. A bare 3-digit
     id would fail that resolve guard and never resolve against the real
     production catalogue.

  B. Daily-challenge prose (content/daily_challenges/2026_*.json) — plain JSON,
     `<Lesson/>` tags don't render there. Bare "lesson NNN" (always 3-digit
     global refs in this corpus) is rewritten to the visible CR044 code
     string ("N&M 11") so the sentence, the badge, and the tile agree.
     `related_lesson` is left as-is where already set (every ref-bearing row
     in this corpus already carries one); rows whose id contains
     "test_string" (CR035-era synthetics) are skipped entirely. "Module NN"
     is out of scope and untouched.

Textual, in-place, idempotent (a converted `<Lesson id=.../>` tag or an
already-code'd daily-challenge sentence contains no bare "lesson N" text, so
re-running finds nothing to redo), like scripts/shuffle_quiz_answers.py.

Usage, from the repo root:
    python3 scripts/migrate_lesson_refs.py --dry-run
    python3 scripts/migrate_lesson_refs.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "content" / "lessons"
CHALLENGES_DIR = REPO / "content" / "daily_challenges"
REPORT_PATH = REPO / "content" / "_authoring" / "cr053_migration_report.md"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n+", re.DOTALL)

# The candidate-match regex for lesson-body prose. Alternatives tried in this
# order at every start position (re tries earlier alternatives first):
#   range  — "lessons 007-011" / "lessons 007–011"
#   kw     — "lesson(s) NNN" (extended for lists/parens by hand, below)
#   bare   — a bare "NNN (...)" with no "lesson" word — only a real ref if the
#            parenthetical shares real overlap with that lesson's title
#            (checked in classify_bare); this alternative alone would also
#            match plain parenthetical asides on prices/dates, so it is never
#            trusted without that check.
_CANDIDATE_RE = re.compile(
    r"""
    (?P<range>\blessons?\s+\d{1,3}\s*[-–—]\s*\d{1,3}\b)
  | (?P<kw>\blessons?\s+\d{1,3}\b)
  | (?P<bare>\d{1,3}\s*\([^)]{1,80}\))
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PAREN_IMMEDIATE_RE = re.compile(r"\s*\([^)]{1,80}\)")
_LIST_CONT_RE = re.compile(r"(,\s*|\s+and\s+|\s*&\s*)(\d{1,3})\b", re.IGNORECASE)
_RANGE_NUMS_RE = re.compile(r"(\d{1,3}).*?(\d{1,3})")
_BARE_NUM_RE = re.compile(r"(\d{1,3})\s*\(([^)]{1,80})\)")

_STOP_WORDS = {
    "the", "a", "an", "and", "of", "to", "in", "is", "for", "or", "on",
    "with", "your", "at", "by", "into",
}


def _norm_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", s.lower())} - _STOP_WORDS


class Corpus:
    """Frontmatter maps built once from every lesson, shared by both classes'
    resolution and by the daily-challenge code rewrite."""

    def __init__(self) -> None:
        self.id_by_num: dict[int, str] = {}
        self.title_by_id: dict[str, str] = {}
        self.code_by_id: dict[str, str] = {}
        self.code_to_id: dict[str, str] = {}
        self.prefix_by_id: dict[str, str] = {}

        for path in sorted(LESSONS_DIR.glob("*.en.mdx")):
            raw = path.read_text(encoding="utf-8")
            m = _FRONTMATTER_RE.match(raw)
            if not m:
                sys.exit(f"REFUSING TO RUN: missing frontmatter in {path.name}")
            fm = yaml.safe_load(m.group(1)) or {}
            full_id = fm["id"]
            num_head = full_id.split("_", 1)[0]
            if not num_head.isdigit():
                sys.exit(f"REFUSING TO RUN: non-numeric id prefix in {path.name}")
            num = int(num_head)
            if num in self.id_by_num:
                sys.exit(
                    f"REFUSING TO RUN: duplicate lesson number {num} "
                    f"({self.id_by_num[num]} vs {full_id})"
                )
            self.id_by_num[num] = full_id
            self.title_by_id[full_id] = str(fm.get("title", ""))
            code = str(fm.get("code", ""))
            self.code_by_id[full_id] = code
            if code:
                self.code_to_id[code] = full_id
                self.prefix_by_id[full_id] = code.rsplit(" ", 1)[0]


def _tag(full_id: str) -> str:
    return f'<Lesson id="{full_id}"/>'


def classify(raw_numtext: str, source_prefix: str | None, corpus: Corpus):
    """Returns (('class1'|'class2', full_id) | ('flag', reason))."""
    value = int(raw_numtext)
    if len(raw_numtext) == 3 or value >= 16:
        full_id = corpus.id_by_num.get(value)
        if full_id:
            return ("class1", full_id)
        return (
            "flag",
            f'"lesson {raw_numtext}" — no content/lessons/{value:03d}_*.en.mdx in the corpus',
        )
    # 1-2 digit, not zero-padded, value <=15 -> within-module ordinal candidate.
    if not source_prefix:
        return (
            "flag",
            f'"lesson {raw_numtext}" — within-module ordinal but source lesson has no CR044 code',
        )
    target_code = f"{source_prefix} {value}"
    full_id = corpus.code_to_id.get(target_code)
    if full_id:
        return ("class2", full_id)
    return (
        "flag",
        f'"lesson {raw_numtext}" — no lesson coded "{target_code}" (within-module ordinal, same-prefix miss)',
    )


def classify_bare(numtext: str, parentext: str, corpus: Corpus):
    """Bare "NNN (title)" with no "lesson" keyword. Only ever Class 1 — the
    keyword is what makes something a within-module-ordinal candidate. Guarded
    by title-word overlap so this never fires on a price/date parenthetical."""
    value = int(numtext)
    full_id = corpus.id_by_num.get(value)
    if not full_id:
        return None
    title_words = _norm_words(corpus.title_by_id.get(full_id, ""))
    paren_words = _norm_words(parentext)
    if not title_words or not paren_words:
        return None
    overlap = title_words & paren_words
    if len(overlap) >= max(1, min(len(title_words), len(paren_words)) // 2):
        return ("class1", full_id)
    return None


def migrate_lesson_body(body: str, source_prefix: str | None, corpus: Corpus):
    """Returns (new_body, edits, flagged) for one lesson's body text.

    edits: list of (class_label, before, after)
    flagged: list of (before, reason)
    """
    out: list[str] = []
    edits: list[tuple[str, str, str]] = []
    flagged: list[tuple[str, str]] = []
    cursor = 0

    while True:
        m = _CANDIDATE_RE.search(body, cursor)
        if not m:
            out.append(body[cursor:])
            break
        out.append(body[cursor : m.start()])

        if m.group("range"):
            span_text = m.group("range")
            nm = _RANGE_NUMS_RE.search(span_text)
            a_text, b_text = nm.group(1), nm.group(2)
            a = classify(a_text, source_prefix, corpus)
            b = classify(b_text, source_prefix, corpus)
            if a[0] == "flag" or b[0] == "flag":
                reason = a[1] if a[0] == "flag" else b[1]
                flagged.append((span_text, f"range endpoint unresolved: {reason}"))
                out.append(span_text)
            else:
                dash = re.search(r"[-–—]", span_text).group(0)
                new = f"{_tag(a[1])}{dash}{_tag(b[1])}"
                edits.append((f"{a[0]}+{b[0]} (range)", span_text, new))
                out.append(new)
            cursor = m.end()
            continue

        if m.group("kw"):
            span_start = m.start()
            first_numtext = re.search(r"\d{1,3}", m.group("kw")).group(0)
            pos = m.end()
            items: list[tuple[str, str, str | None]] = []  # (sep, numtext, parentext)

            pm = _PAREN_IMMEDIATE_RE.match(body, pos)
            parentext = None
            if pm:
                parentext = pm.group(0).strip()
                pos = pm.end()
            items.append(("", first_numtext, parentext))

            while True:
                cm = _LIST_CONT_RE.match(body, pos)
                if not cm:
                    break
                sep, numtext = cm.group(1), cm.group(2)
                pos2 = cm.end()
                pm2 = _PAREN_IMMEDIATE_RE.match(body, pos2)
                parentext2 = None
                if pm2:
                    parentext2 = pm2.group(0).strip()
                    pos2 = pm2.end()
                items.append((sep, numtext, parentext2))
                pos = pos2

            span_text = body[span_start:pos]
            resolved = [
                (sep, numtext, parentext, classify(numtext, source_prefix, corpus))
                for sep, numtext, parentext in items
            ]

            if any(r[0] == "flag" for *_, r in resolved):
                # A flagged item anywhere in the list means the whole
                # multi-ref span is left untouched — a partial rewrite around
                # an unresolved item is exactly the "corrupts the sentence"
                # failure mode this migration must avoid.
                reasons = "; ".join(r[1] for *_, r in resolved if r[0] == "flag")
                flagged.append((span_text, reasons))
                out.append(span_text)
            else:
                pieces = []
                for sep, numtext, parentext, (klass, full_id) in resolved:
                    piece = _tag(full_id)
                    if parentext:
                        piece += f" {parentext}"
                    pieces.append(sep + piece)
                new = "".join(pieces)
                klass_label = "+".join(sorted({r[0] for *_, r in resolved}))
                edits.append((klass_label, span_text, new))
                out.append(new)
            cursor = pos
            continue

        # bare "NNN (title)"
        span_text = m.group("bare")
        bm = _BARE_NUM_RE.match(span_text)
        numtext, parentext = bm.group(1), bm.group(2)
        result = classify_bare(numtext, parentext, corpus)
        if result is None:
            # Not a lesson ref (price/date/aside) — e.g. "2023 (covered in
            # lesson 061 as a range case)". Only advance past the NUMBER, not
            # the whole "(...)" span: the parenthetical content itself may
            # contain a real ref ("lesson 061" above), which the next search
            # must still get a chance to see. Swallowing the whole span here
            # silently ate every ref hidden inside a failed bare-paren guess.
            out.append(numtext)
            cursor = m.start() + bm.end(1)
        else:
            klass, full_id = result
            new = f"{_tag(full_id)} ({parentext})"
            edits.append((klass, span_text, new))
            out.append(new)
            cursor = m.end()

    return "".join(out), edits, flagged


def migrate_lessons(corpus: Corpus):
    all_edits = []  # (filename, class, before, after)
    all_flagged = []  # (filename, before, reason)
    file_new_bodies: dict[Path, tuple[str, str]] = {}  # path -> (raw, new_raw)

    for path in sorted(LESSONS_DIR.glob("*.en.mdx")):
        raw = path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(raw)
        fm = yaml.safe_load(m.group(1)) or {}
        full_id = fm["id"]
        source_prefix = corpus.prefix_by_id.get(full_id)
        fm_end = m.end()
        body = raw[fm_end:]

        new_body, edits, flagged = migrate_lesson_body(body, source_prefix, corpus)
        if edits:
            file_new_bodies[path] = (raw, raw[:fm_end] + new_body)
        for klass, before, after in edits:
            all_edits.append((path.name, klass, before, after))
        for before, reason in flagged:
            all_flagged.append((path.name, before, reason))

    return all_edits, all_flagged, file_new_bodies


_DAILY_LESSON_RE = re.compile(r"\blessons?\s+(\d{3})\b", re.IGNORECASE)


def migrate_challenges(corpus: Corpus):
    all_edits = []  # (filename, before, after)
    file_new_texts: dict[Path, tuple[str, str]] = {}

    for path in sorted(CHALLENGES_DIR.glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        records = json.loads(raw)

        dec = json.JSONDecoder()
        skip_spans: list[tuple[int, int]] = []
        idx = raw.index("[") + 1
        for rec in records:
            wm = re.match(r"[\s,]*", raw[idx:])
            start = idx + wm.end()
            _obj, end = dec.raw_decode(raw, start)
            if "test_string" in str(rec.get("id", "")):
                skip_spans.append((start, end))
            idx = end

        def in_skip(pos: int) -> bool:
            return any(a <= pos < b for a, b in skip_spans)

        edits_here = []

        def _sub(m: re.Match) -> str:
            if in_skip(m.start()):
                return m.group(0)
            numtext = m.group(1)
            full_id = corpus.id_by_num.get(int(numtext))
            code = corpus.code_by_id.get(full_id, "") if full_id else ""
            if not code:
                # Unresolvable — leave untouched rather than guess.
                return m.group(0)
            edits_here.append((m.group(0), code))
            return code

        new_raw = _DAILY_LESSON_RE.sub(_sub, raw)

        if edits_here:
            file_new_texts[path] = (raw, new_raw)
            for before, after in edits_here:
                all_edits.append((path.name, before, after))

    return all_edits, file_new_texts


def write_report(
    lesson_edits, lesson_flagged, challenge_edits, dry_run: bool
) -> None:
    verb = "would edit" if dry_run else "edited"
    lines = [
        "# CR053-MIGRATE — migration report",
        "",
        f"Generated by `scripts/migrate_lesson_refs.py` ({'--dry-run' if dry_run else 'apply'}).",
        "",
        f"- Lesson-body edits: {len(lesson_edits)} ({verb})",
        f"- Lesson-body flagged (unresolved, left untouched): {len(lesson_flagged)}",
        f"- Daily-challenge prose edits: {len(challenge_edits)} ({verb})",
        "",
        "## A. Lesson body edits",
        "",
        "`file | class | before -> after`",
        "",
    ]
    for fname, klass, before, after in lesson_edits:
        before_c = before.replace("\n", " ")
        after_c = after.replace("\n", " ")
        lines.append(f"- `{fname}` | {klass} | `{before_c}` -> `{after_c}`")

    lines += ["", "## B. Daily-challenge prose edits", "", "`file | before -> after`", ""]
    for fname, before, after in challenge_edits:
        lines.append(f"- `{fname}` | `{before}` -> `{after}`")

    lines += ["", "## FLAGGED — unresolved, left untouched (needs architect review)", ""]
    if not lesson_flagged:
        lines.append("None.")
    else:
        for fname, before, reason in lesson_flagged:
            before_c = before.replace("\n", " ")
            lines.append(f"- `{fname}` | `{before_c}` | {reason}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()

    corpus = Corpus()
    lesson_edits, lesson_flagged, lesson_files = migrate_lessons(corpus)
    challenge_edits, challenge_files = migrate_challenges(corpus)

    write_report(lesson_edits, lesson_flagged, challenge_edits, args.dry_run)

    if not args.dry_run:
        for path, (_old, new) in lesson_files.items():
            path.write_text(new, encoding="utf-8")
        for path, (_old, new) in challenge_files.items():
            path.write_text(new, encoding="utf-8")
            json.loads(new)  # refuse to leave a file that doesn't parse

    verb = "would migrate" if args.dry_run else "migrated"
    print(f"lesson bodies: {verb} {len(lesson_edits)} refs across {len(lesson_files)} files")
    print(f"lesson bodies: {len(lesson_flagged)} refs flagged (left untouched)")
    print(f"daily challenges: {verb} {len(challenge_edits)} refs across {len(challenge_files)} files")
    print(f"report: {REPORT_PATH.relative_to(REPO)}")


if __name__ == "__main__":
    main()

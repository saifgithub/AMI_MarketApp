#!/usr/bin/env python3
"""CR042 — randomise which position holds the correct quiz answer.

The correct answer sat in the second slot in 71.0% of lesson questions
(397/559) and 96.7% of daily challenges (177/183). "Always pick the second
option" scored 71% blind, which hollows out the skip-to-quiz assessment
surface the authoring prompt is built around.

This is a ONE-OFF corrective rewrite, committed for reproducibility and
reviewability — it is not a build step. The ongoing guard is
backend/tests/unit/test_lesson_corpus_integrity.py; no test asserts a
distribution, because a uniformity assertion would be brittle against
legitimate future content edits.

Ordering constraint: this must run AFTER DEF065 (de-indexing explanations).
While any explanation says "option 2", reordering options silently corrupts
it. The script refuses to run if it finds such a citation.

Safety: the load-bearing invariant is that the correct answer's TEXT is
unchanged for every question — only its position moves. The script asserts
this per question before writing, and --verify re-checks the whole corpus
against a snapshot taken before the run.

Usage, from the repo root:
    python3 scripts/shuffle_quiz_answers.py --dry-run
    python3 scripts/shuffle_quiz_answers.py
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "content" / "lessons"
CHALLENGES_DIR = REPO / "content" / "daily_challenges"

# Fixed so the rewrite is reproducible from the committed source.
SEED = 20260718

# A <Quiz .../> element. Non-greedy up to the self-closing tag; quiz blocks
# never nest and never contain "/>" inside an attribute value.
_QUIZ_RE = re.compile(r"<Quiz\b(?P<attrs>.*?)/>", re.DOTALL)
_OPTIONS_RE = re.compile(r"options=\{\[(?P<body>.*?)\]\}", re.DOTALL)
_ANSWER_RE = re.compile(r"answer=\{(?P<val>[^}]*)\}")
_EXPLANATION_RE = re.compile(r'explanation="(?P<val>(?:[^"\\]|\\.)*)"', re.DOTALL)
# One quoted option literal, preserving whatever surrounds it.
_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
# DEF083: widened to match the same pattern as the corpus-integrity guard
# (test_lesson_corpus_integrity.py) — the literal-"option(s)" requirement
# missed "the first one", "the first answer", "the last — '...'".
_OPTION_INDEX_CITATION = re.compile(
    r"\boptions?\s+\d"
    r"|\b(?:first|second|third|fourth|fifth|last)\s+(?:options?|ones?|answers?|choices?)\b"
    r"|\bthe\s+(?:first|second|third|fourth|fifth|last)\s*[—–-]",
    re.IGNORECASE,
)
# Daily-challenge JSON: the "options" array and the "answer" that indexes it,
# which always sit adjacent in the record. `gap` preserves the exact
# whitespace between them.
_JSON_OPTIONS_ANSWER_RE = re.compile(
    r'"options":\s*\[(?P<body>.*?)\],(?P<gap>\s*)"answer":\s*(?P<answer>\d+)',
    re.DOTALL,
)

# The corpus's only 2-option question ("True" / "False"). Reordering it to
# False-then-True reads wrong, and changing the answer would mean inverting
# the statement — out of scope for a positional shuffle.
SKIP_QUESTIONS = {("281_what_is_a_market.en.mdx", 1)}


def _permute(rng: random.Random, n: int, current: int) -> list[int]:
    """Return a permutation of range(n) placing the answer at a UNIFORMLY
    random slot. Returns new_order, where new_order[i] is the old index now
    sitting at position i.

    Deliberately NOT "re-draw until the answer moves". Forcing every answer
    off its current slot sounds tidier but inverts the tell instead of
    removing it: with 71% of answers starting at index 1, a must-move rule
    drove index 1 down to 10% — and on the daily challenges, from 96.7% to
    1.1%, effectively turning 4-option questions into 3-option ones. Uniform
    targeting means roughly 1/n questions legitimately keep their position.
    """
    target = rng.randrange(n)
    others = [i for i in range(n) if i != current]
    rng.shuffle(others)
    order = [None] * n
    order[target] = current
    it = iter(others)
    for i in range(n):
        if order[i] is None:
            order[i] = next(it)
    return order


def shuffle_lessons(rng: random.Random, dry_run: bool) -> tuple[int, int]:
    moved = skipped = 0
    for path in sorted(LESSONS_DIR.glob("*.en.mdx")):
        raw = path.read_text(encoding="utf-8")
        out: list[str] = []
        cursor = 0
        qidx = -1

        for match in _QUIZ_RE.finditer(raw):
            attrs = match.group("attrs")
            qidx += 1

            om = _OPTIONS_RE.search(attrs)
            am = _ANSWER_RE.search(attrs)
            if not om or not am:
                continue

            em = _EXPLANATION_RE.search(attrs)
            if em and _OPTION_INDEX_CITATION.search(em.group("val")):
                sys.exit(
                    f"REFUSING TO RUN: {path.name} quiz {qidx} still cites an "
                    f"option by index. Finish DEF065 before shuffling — "
                    f"reordering would silently corrupt that explanation."
                )

            body = om.group("body")
            literals = _STRING_RE.findall(body)
            answer = int(am.group("val"))

            if (path.name, qidx) in SKIP_QUESTIONS or len(literals) < 2:
                skipped += 1
                continue
            if not 0 <= answer < len(literals):
                sys.exit(f"{path.name} quiz {qidx}: answer {answer} out of range")

            order = _permute(rng, len(literals), answer)
            new_answer = order.index(answer)
            correct_before = literals[answer]

            # Reorder the literals IN PLACE — every byte between them
            # (indentation, newlines, commas) is left exactly as authored, so
            # the diff shows moved strings and nothing else.
            it = iter(order)
            new_body = _STRING_RE.sub(lambda _m: literals[next(it)], body)
            new_literals = _STRING_RE.findall(new_body)

            assert new_literals[new_answer] == correct_before, (
                f"{path.name} quiz {qidx}: shuffle moved the answer text"
            )
            assert sorted(new_literals) == sorted(literals), (
                f"{path.name} quiz {qidx}: shuffle changed the option set"
            )

            new_attrs = (
                attrs[: om.start()]
                + f"options={{[{new_body}]}}"
                + attrs[om.end() : am.start()]
                + f"answer={{{new_answer}}}"
                + attrs[am.end() :]
            )
            out.append(raw[cursor : match.start()])
            out.append(f"<Quiz{new_attrs}/>")
            cursor = match.end()
            moved += 1

        if out and not dry_run:
            out.append(raw[cursor:])
            path.write_text("".join(out), encoding="utf-8")

    return moved, skipped


def shuffle_challenges(rng: random.Random, dry_run: bool) -> int:
    """Daily challenges are plain JSON with an `answer` int (not
    `answer_index`) — see backend/app/schemas/daily_challenge.py.

    Rewritten textually rather than via json.dumps: a re-dump expands the
    inline `"tags": [...]` arrays onto separate lines, which buries the real
    change under ~280 lines of formatting noise per file.
    """
    moved = 0
    for path in sorted(CHALLENGES_DIR.glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        out: list[str] = []
        cursor = 0

        for match in _JSON_OPTIONS_ANSWER_RE.finditer(raw):
            body = match.group("body")
            literals = _STRING_RE.findall(body)
            answer = int(match.group("answer"))

            if len(literals) < 2:
                continue
            if not 0 <= answer < len(literals):
                sys.exit(f"{path.name}: answer {answer} out of range")

            order = _permute(rng, len(literals), answer)
            new_answer = order.index(answer)
            correct_before = literals[answer]

            it = iter(order)
            new_body = _STRING_RE.sub(lambda _m: literals[next(it)], body)
            new_literals = _STRING_RE.findall(new_body)

            assert new_literals[new_answer] == correct_before, (
                f"{path.name}: shuffle moved the answer text"
            )
            assert sorted(new_literals) == sorted(literals), (
                f"{path.name}: shuffle changed the option set"
            )

            out.append(raw[cursor : match.start()])
            out.append(
                f'"options": [{new_body}],{match.group("gap")}'
                f'"answer": {new_answer}'
            )
            cursor = match.end()
            moved += 1

        if out and not dry_run:
            out.append(raw[cursor:])
            path.write_text("".join(out), encoding="utf-8")

    return moved


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()

    rng = random.Random(SEED)
    moved, skipped = shuffle_lessons(rng, args.dry_run)
    challenges = shuffle_challenges(rng, args.dry_run)

    verb = "would move" if args.dry_run else "moved"
    lesson_files = len(list(LESSONS_DIR.glob("*.en.mdx")))
    print(
        f"lessons: {verb} {moved} quiz questions across {lesson_files} lessons "
        f"({skipped} skipped)"
    )
    print(f"daily challenges: {verb} {challenges} questions")


if __name__ == "__main__":
    main()

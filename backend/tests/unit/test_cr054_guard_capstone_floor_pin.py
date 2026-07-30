"""AUDITOR pin (CR054-GUARD round 1) — blind adversarial pins on the lane's
two riskiest forward regression surfaces after the corpus guards went
content-addition-safe (fd64a29):

  1. The FLOOR quietly degrading. The exact `EXPECTED_LESSON_COUNT == 270`
     pin became `LESSON_COUNT_FLOOR >= 270` so content waves can append
     without a backend/ edit. That is only safe while (a) the assertion
     stays a `>=` floor at >= 270 and (b) the corpus on disk never dips
     below it. A future "cleanup" that deletes the count assertion, turns
     it back into `==` (re-creating the cross-ownership deadlock), or
     lowers the constant would not fail any in-repo test — only this pin.
  2. The capstone guard's exemption set silently growing. The guard scopes
     itself by `"capstone" in tags` minus `PRE_CR054_CAPSTONE_TAGS`; every
     name added to that set is a lesson the guard stops seeing. Exactly one
     legitimate member exists (071, the pre-template M11-era outlier —
     verified mid-module, no runtime consumer, authoring prompt forbids
     retrofit). Growth of the set must be a deliberate, re-audited act.

Pins (stdlib text-parse of the guard file + independent frontmatter scan of
the corpus — no backend import, works on any checkout):

  1. the count guard is a `>=` floor with LESSON_COUNT_FLOOR >= 270, and no
     `==` count pin remains;
  2. the corpus on disk holds at least LESSON_COUNT_FLOOR lessons (an
     independent shrink tripwire, same teeth as the guard itself);
  3. both capstone guard functions exist and PRE_CR054_CAPSTONE_TAGS is
     exactly {071_how_to_verify_before_you_wire_money};
  4. independent re-scan: every lesson whose parsed `tags` list contains
     "capstone" is either the 071 exemption or declares `module:` >= 13
     (a CR054-template module) — a legacy-module capstone can never hide,
     even behind a widened exemption set.

Run: python3 -m pytest "orchestration/audit/regression/test_cr054_guard_capstone_floor_pin.py" -q
(from repo root; green at the 270 committed corpus and at 280 with the
untracked W1-ETHIC files present.)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GUARD_FILE = REPO_ROOT / "backend/tests/unit/test_lesson_corpus_integrity.py"
LESSONS_DIR = REPO_ROOT / "content/lessons"

EXEMPT = {"071_how_to_verify_before_you_wire_money"}
FIRST_CR054_MODULE = 13


def guard_source() -> str:
    return GUARD_FILE.read_text(encoding="utf-8")


def floor_value(src: str) -> int:
    m = re.search(r"^LESSON_COUNT_FLOOR\s*=\s*(\d+)\s*$", src, re.MULTILINE)
    assert m, "LESSON_COUNT_FLOOR constant missing from the guard file"
    return int(m.group(1))


def frontmatter(path: Path) -> str:
    body = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---", body, re.DOTALL)
    assert m, f"{path.name}: no frontmatter block"
    return m.group(1)


def test_count_guard_is_a_floor_at_least_270() -> None:
    src = guard_source()
    floor = floor_value(src)
    assert floor >= 270, (
        f"LESSON_COUNT_FLOOR lowered to {floor} — the shrink guard has been "
        f"weakened below the last audited corpus"
    )
    assert re.search(r"len\(paths\)\s*>=\s*LESSON_COUNT_FLOOR", src), (
        "the >= floor assertion is gone from test_every_lesson_parses — "
        "silent corpus shrink is unguarded"
    )
    assert not re.search(r"len\(paths\)\s*==", src), (
        "an exact == count pin is back — it re-creates the cross-ownership "
        "deadlock CR054-GUARD removed (every content wave forced into a "
        "backend/ edit)"
    )


def test_corpus_on_disk_meets_the_floor() -> None:
    floor = floor_value(guard_source())
    count = len(list(LESSONS_DIR.glob("*.en.mdx")))
    assert count >= floor, (
        f"corpus has {count} lessons, below the audited floor {floor} — "
        f"lessons have disappeared"
    )


def test_capstone_guards_exist_and_exemption_is_frozen() -> None:
    src = guard_source()
    for fn in (
        "test_every_capstone_is_the_last_lesson_in_its_module",
        "test_every_capstone_ends_on_a_synthesis_quiz",
    ):
        assert f"def {fn}(" in src, f"capstone guard {fn} deleted"
    m = re.search(r"PRE_CR054_CAPSTONE_TAGS\s*=\s*\{(?P<body>[^}]*)\}", src)
    assert m, "PRE_CR054_CAPSTONE_TAGS missing from the guard file"
    members = set(re.findall(r'"([^"]+)"', m.group("body")))
    assert members == EXEMPT, (
        f"capstone exemption set changed to {sorted(members)} — every name "
        f"in it is a lesson the capstone guard stops seeing; widening it "
        f"needs a fresh audit"
    )


def test_every_capstone_tag_is_exempt_or_in_a_cr054_module() -> None:
    offenders = []
    for path in sorted(LESSONS_DIR.glob("*.en.mdx")):
        fm = frontmatter(path)
        tags_m = re.search(r"^tags:\s*\[(?P<body>.*)\]\s*$", fm, re.MULTILINE)
        tags = re.findall(r'"([^"]+)"', tags_m.group("body")) if tags_m else []
        if "capstone" not in tags:
            continue
        lesson_id = path.name.removesuffix(".en.mdx")
        if lesson_id in EXEMPT:
            continue
        mod_m = re.search(r"^module:\s*(\d+)\s*$", fm, re.MULTILINE)
        module = int(mod_m.group(1)) if mod_m else 0
        if module < FIRST_CR054_MODULE:
            offenders.append((lesson_id, module))
    assert not offenders, (
        f"capstone-tagged lessons in pre-CR054 modules (id, module): "
        f"{offenders} — either an unaudited exemption is needed or a legacy "
        f"module was retrofitted against the authoring prompt's rule"
    )

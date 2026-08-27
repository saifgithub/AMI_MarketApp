"""CR054 §4.3 — every cited source resolves to the reputable-source allowlist.

`content/_authoring/source_registry.md` (CR060) has claimed, in its own opening
paragraph, that *"the corpus-integrity test (CR060) checks each cited source
against this file; a `sources` value that doesn't map to a Tier below fails the
build (degrade loudly)"*.

**No such test existed.** Measured 2026-08-27: nothing under `backend/` or
`scripts/` referenced `source_registry.md` at all — not a test, not a script,
not app code. The registry described an enforcement that was never built, which
is P21 wearing prose instead of code: the claim reads as a guarantee and is
inert. This file is that test.

**`sources` is deliberately absent from `LessonMeta`, and that is correct.**
CR060 makes provenance INTERNAL-ONLY — users never see citations in the app —
so the served model must not carry it. The guard therefore reads the frontmatter
off disk rather than through `parse_mdx`; a source field that reached the API
would be the defect, not the fix.

**Why a ratchet and not a hard gate.** 29 cited authorities do not resolve
today, and the registry itself explains why: it names Barber & Odean, the
Barber/Lee/Liu/Odean day-trading work and others as *"reputable and used as
evidence against lessons, but not yet admitted to the allowlist — admitting
them is a decision, not a formality, and belongs to the remediation CR."* That
is a content judgment with a named owner, and a gate that fails on day one
teaches the operator to skip it (DEF277). So today's 29 are frozen in
`cr054_unadmitted_sources_baseline.json`, a NEW unadmitted source fails, and the
baseline may only shrink.

**On the matcher's looseness, stated rather than discovered later.** Resolution
is by SURNAME SET, so `Blaise Pascal & Pierre de Fermat` resolves to the
registry's `Pascal & Fermat` and `Philip Tetlock & Dan Gardner` to
`Tetlock & Gardner`. A new source sharing a surname with an admitted one would
pass. That hole is accepted deliberately: the opposite error — rejecting
legitimate naming variants — produces routine false alarms, and a check that
cries wolf is the one that gets reasoned past.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[3]
_LESSONS = _ROOT / "content" / "lessons"
_REGISTRY = _ROOT / "content" / "_authoring" / "source_registry.md"
_BASELINE = Path(__file__).with_name("cr054_unadmitted_sources_baseline.json")

#: A floor, like `LESSON_COUNT_FLOOR` next door. Every assertion here is a
#: "no offenders" shape, and all of them pass on an empty corpus. Set just
#: under the measured 71 rather than at it: a floor that tracks the true count
#: exactly turns red on the next authoring pass, which is P6b.
SOURCED_LESSON_FLOOR = 70

#: Lessons carrying `sources: []` — the key present, the list empty. That is a
#: provenance promise with nothing behind it, and it reads identically to a
#: sourced lesson in every tool that only checks the key exists. Measured at 9
#: on 2026-08-27, all in the ASST bonds/ETF range; four of them (304, 311, 317,
#: 320) are already logged as provenance soft-spots in the registry's own
#: findings section. Ratcheted rather than fixed here — writing the citations is
#: authoring work with a named owner (CR060), not a test's job.
EMPTY_SOURCES_CEILING = 9


def _norm(s: object) -> str:
    s = re.sub(r"[*_`\"“”]", "", str(s))
    s = s.replace("—", "-").replace("–", "-").replace("·", "-")
    return re.sub(r"\s+", " ", s).strip().casefold()


def _authority(source: str) -> str:
    """The author or institution — everything before the first em-dash."""
    return _norm(source).split(" - ")[0].strip()


def _surnames(authority: str) -> frozenset[str]:
    parts = re.split(r"\s*&\s*|\s*,\s*|\s+and\s+", authority)
    return frozenset(p.strip().split()[-1] for p in parts if p.strip())


def _registry_surnames() -> set[frozenset[str]]:
    out: set[frozenset[str]] = set()
    for line in _REGISTRY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.count("|") < 3 or "---" in line:
            continue
        cell = line.split("|")[1].strip()
        if cell and cell.lower() != "source":
            out.add(_surnames(_norm(cell).split(" - ")[0].strip()))
    return out


def _cited() -> dict[str, list[str]]:
    """authority -> the lesson ids citing it."""
    out: dict[str, list[str]] = {}
    for path in sorted(_LESSONS.glob("*.en.mdx")):
        fm = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1]) or {}
        for src in fm.get("sources") or []:
            out.setdefault(_authority(src), []).append(fm["id"])
    return out


@pytest.fixture(scope="module")
def cited():
    return _cited()


@pytest.fixture(scope="module")
def baseline():
    return json.loads(_BASELINE.read_text(encoding="utf-8"))


def test_the_registry_is_readable_and_populated():
    """The whole file is vacuous if the registry cannot be parsed — every
    'resolves' assertion below would fail open into 'nothing to check'."""
    rows = _registry_surnames()
    assert len(rows) >= 40, f"only {len(rows)} registry rows parsed — the table shape moved"


def test_enough_lessons_carry_sources_for_this_file_to_mean_anything(cited):
    lessons = {l for ids in cited.values() for l in ids}
    assert len(lessons) >= SOURCED_LESSON_FLOOR, (
        f"only {len(lessons)} lessons carry a `sources` field; every assertion "
        "in this file passes trivially below that. Either the corpus did not "
        "load or provenance was stripped."
    )


def test_no_source_is_cited_that_is_neither_admitted_nor_baselined(cited, baseline):
    """The ratchet's teeth. A NEW citation must resolve to the allowlist."""
    reg = _registry_surnames()
    offenders = {
        a: ids for a, ids in cited.items()
        if _surnames(a) not in reg and a not in baseline
    }
    assert not offenders, (
        f"{len(offenders)} source authority(ies) resolve to no row in "
        "source_registry.md and are not in the frozen baseline. Either admit "
        "the source to the registry (a content decision — see its 'admitting "
        "them is a decision, not a formality' note) or correct the citation. "
        "Do NOT add it to the baseline: the baseline only shrinks. "
        f"Offenders: { {a: ids[:3] for a, ids in offenders.items()} }"
    )


def test_the_baseline_only_shrinks(cited, baseline):
    """A baseline entry that is no longer cited must leave, or the file slowly
    becomes a list of things nobody can act on — DEF295's 'marker outlives its
    key', one register over."""
    orphans = sorted(set(baseline) - set(cited))
    assert not orphans, (
        f"{len(orphans)} baseline entry(ies) are no longer cited by any lesson. "
        f"Remove them from {_BASELINE.name} — the debt is paid, record it: {orphans}"
    )


def test_the_baseline_records_the_lessons_that_owe_the_debt(cited, baseline):
    """Each frozen authority names its citing lessons, so the remediation pass
    has a work-list rather than a search."""
    for authority, ids in baseline.items():
        assert ids, f"{authority!r} is baselined with no lesson attached"
        assert set(ids) <= set(cited.get(authority, [])), (
            f"{authority!r} claims lessons that no longer cite it: "
            f"{sorted(set(ids) - set(cited.get(authority, [])))}"
        )


def test_the_baseline_is_not_silently_growing(baseline):
    """A named ceiling. Raising it is an edit somebody has to justify in a
    diff; without it the ratchet has no direction."""
    assert len(baseline) <= 29, (
        f"the unadmitted-source baseline has grown to {len(baseline)}. It is a "
        "ratchet: it may only shrink."
    )


def test_empty_source_lists_do_not_spread():
    """`sources: []` is not the same as no `sources` key, and it is worse: the
    key's presence satisfies every shallow "is it sourced?" check while the
    lesson rests on nothing. A ceiling, so the next authoring pass cannot add
    one quietly."""
    empty = [
        (yaml.safe_load(p.read_text(encoding="utf-8").split("---", 2)[1]) or {})
        for p in sorted(_LESSONS.glob("*.en.mdx"))
    ]
    ids = [fm["id"] for fm in empty if "sources" in fm and not fm["sources"]]
    assert len(ids) <= EMPTY_SOURCES_CEILING, (
        f"{len(ids)} lessons declare `sources: []` (ceiling {EMPTY_SOURCES_CEILING}). "
        f"A new one is a lesson shipped with no provenance at all: {ids}"
    )

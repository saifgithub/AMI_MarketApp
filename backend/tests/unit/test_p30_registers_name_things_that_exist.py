"""P30 — a control recorded as existing must exist.

Three findings on 2026-08-27 were the same shape, and it is not P29's:

* **DEF379** — `source_registry.md` stated, in the present tense, that *"the
  corpus-integrity test checks each cited source against this file… fails the
  build"*. Nothing under `backend/` or `scripts/` referenced the file at all.
* **DEF335** — the row said *"interim mitigation, **applied now**: the 8
  affected tickers are excluded… recorded in `backtest_universe_membership`
  with reason `split_after_as_of`"*. All 150 rows carried a NULL reason and the
  string `split_after_as_of` existed nowhere in the codebase. A 141.5% FCF
  yield reached a published verdict while the row said it could not.
* **DEF321** — a canary tracking an intermittent failure, whose assertion CR109
  had made unfailable. Green forever, proving nothing.

**Why this is worse than an unguarded gap.** An absent control is merely
missing; a control *documented as present* stops the next reader looking for
one. Every reader after the sentence was written inherits a false belief, and
the cheaper the sentence was to write, the longer it survives. DEF379's row
called it "P21 written in prose"; three instances in a day earns its own entry.

**What this guard does and does not catch, stated plainly rather than implied.**
It catches DEF335's shape — a row naming a code symbol that exists nowhere —
and it catches a row naming a test file that does not exist. It does **not**
catch DEF379 (the claim named no symbol at all) or DEF321 (a real test whose
assertion had gone hollow). Those two are caught by the house rules that
already exist: an entry without an enforcing check is not done, and every guard
must be mutation-proved. This file is the mechanical half of P30, not the whole
of it, and pretending otherwise would itself be the pattern.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_BASELINE = pathlib.Path(__file__).with_name("p30_absent_identifiers_baseline.json")

_GROUPS = (
    ("docs/defect/_registry", "docs/defect"),
    ("docs/forward_planning/_registry", "docs/forward_planning"),
)

#: Snake_case with 3+ parts. Two parts catches ordinary English ("read_time");
#: three is the point where a token is almost certainly an identifier someone
#: expects to find.
_IDENT = re.compile(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+){2,})`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

_CODE_EXT = (
    ".py", ".dart", ".sh", ".sql", ".yml", ".yaml",
    ".json", ".md", ".arb", ".xml", ".gradle", ".plist",
)


def _tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=_ROOT, capture_output=True, text=True,
    )
    return out.stdout.splitlines()


@pytest.fixture(scope="module")
def tracked():
    return _tracked()


@pytest.fixture(scope="module")
def haystack(tracked):
    """Every non-docs tracked file's text. `docs/` is excluded deliberately: a
    register row citing a symbol that appears only in another register row is
    exactly the circular evidence this guard exists to refuse."""
    parts = []
    for rel in tracked:
        if not rel.endswith(_CODE_EXT) or rel.startswith("docs/"):
            continue
        try:
            parts.append((_ROOT / rel).read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    return "\n".join(parts)


def test_the_index_actually_loaded(tracked, haystack):
    """Vacuity, and the failure mode that matters: an empty haystack makes
    every identifier read as absent, and an empty file list makes every claim
    read as present. Both directions are checked."""
    assert len(tracked) > 3000, f"only {len(tracked)} tracked files — git ls-files failed"
    assert len(haystack) > 1_000_000, "the code index is far too small to be real"


def test_every_file_a_register_row_claims_actually_exists(tracked):
    """The row's FILES column is its present-tense claim about what implements
    it. Prose may describe deleted things — `league.py` is legitimately named by
    rows that predate its removal — but the files column is what a reader opens.
    """
    have = set(tracked)
    dirs = {str(pathlib.Path(p).parent) for p in tracked}
    broken = []
    for regdir, base in _GROUPS:
        for row in sorted((_ROOT / regdir).glob("*.row.md")):
            cells = row.read_text(encoding="utf-8").split("|")
            if len(cells) < 4:
                continue
            for _label, target in _LINK.findall(cells[-3]):
                rel = os.path.normpath(os.path.join(base, target.split("#")[0]))
                ok = (
                    rel in have
                    or rel in dirs
                    or any(p.startswith(rel.rstrip("/") + "/") for p in have)
                )
                if not ok:
                    broken.append(f"{row.stem}: {target}")
    assert not broken, (
        f"{len(broken)} register row(s) point their FILES column at something "
        f"that does not exist: {broken}"
    )


def test_no_new_register_identifier_is_absent_from_the_codebase(haystack):
    """DEF335's shape. `split_after_as_of` was cited as an applied mitigation
    and existed in no file — which is mechanically detectable and was not
    detected for months.

    A ratchet, not a hard gate: 14 identifiers are legitimately absent today
    (gitignored infra names, a memory filename, symbols in the read-only
    TradingAgents upstream). Those are frozen. A NEW one is the alarm.
    """
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))
    offenders = {}
    for regdir, _base in _GROUPS:
        for row in sorted((_ROOT / regdir).glob("*.row.md")):
            for ident in sorted(set(_IDENT.findall(row.read_text(encoding="utf-8")))):
                if ident in haystack or ident in baseline:
                    continue
                offenders.setdefault(ident, []).append(row.stem)
    assert not offenders, (
        f"{len(offenders)} identifier(s) are cited in a register row and exist "
        "nowhere in the codebase. Either the thing was never built, or it was "
        "renamed and the row was not — both are P30. Do NOT add it to the "
        f"baseline; the baseline only shrinks. {offenders}"
    )


def test_the_baseline_only_shrinks(haystack):
    """An entry that now resolves must leave, or the file becomes a permanent
    excuse list — DEF295's 'marker outlives its key', third application."""
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))
    resolved = sorted(k for k in baseline if k in haystack)
    assert not resolved, (
        f"{len(resolved)} baselined identifier(s) now exist — remove them from "
        f"{_BASELINE.name}, the debt is paid: {resolved}"
    )
    assert len(baseline) <= 14, (
        f"the P30 baseline has grown to {len(baseline)}; it is a ratchet."
    )


def test_the_baseline_names_the_rows_that_owe_each_entry():
    """A work-list, not a list of excuses."""
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))
    for ident, rows in baseline.items():
        assert rows, f"{ident!r} is baselined with no citing row recorded"

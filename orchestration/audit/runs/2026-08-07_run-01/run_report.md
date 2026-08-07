# Audit run 2026-08-07 run-01 — CR132, round 1

Auditor track U. SCOPE: `chunk` (lessons 1-5 of 6; lesson 6 blocked on
CR131, correctly excluded per architect). Risky dimension per the brief and
the CR's own README: factual accuracy of every numeric claim, verified
against primary sources, not the architect's self-check.

Second independent pass on this lane — a concurrent track-U session had
already committed+pushed `e7af36e8` (verdict: AWAITING_FIXES round 1, same
BLOCKER) before this session finished its own parallel investigation. Rather
than duplicate-commit a competing verdict on the same finding, this run
folds its own independent evidence into the same lane file as an addendum:
own worktree, own pytest run, own fetch-and-read of all 6 cited primary
papers, plus full coverage of the task's "ALSO CHECK" checklist (ids,
prerequisites, retranslate tags, AMI naming, editorial stance,
simulation-as-measurement), none of which the first pass's file covered.

Audited at **`66e0c664`** in scratch worktree
`.claude/worktrees/audit-CR132` (removed after use, per DEF159 — declared
files checked directly in the detached worktree, not the shared Mac tree).

Verdict: **AWAITING_FIXES (round 1)** — unchanged from the first pass.
0 BLOCKER carried forward (see `CR132.auditor.md`'s primary section for the
368 finding, authored by the first pass), 1 additional MINOR (this pass),
0 further BLOCKER/MAJOR found across the rest of the submission.

## Test reproduction

```
cd .claude/worktrees/audit-CR132/backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest \
  tests/unit/ -q -k "lesson or content or curriculum"
72 passed, 2464 deselected in 23.25s
```
Matches both the architect's submission and the first auditor pass exactly.
EDGE 100-104 confirmed contiguous, no gaps/dupes, via independent grep of
`^code:` across `content/lessons/*.en.mdx`.

## Primary-source fetch method

WebFetch's own PDF-to-markdown extraction failed on all 6 cited papers
(image/compressed-stream-heavy academic PDFs) — every attempt returned
"cannot extract readable text." Installed `poppler` via `brew` in-session
and ran `pdftotext -layout` locally on each fetched PDF, then grepped the
extracted plaintext for the exact figures. This is materially more reliable
than WebFetch's built-in extraction or WebSearch's generated summaries — see
the addendum's note on WebSearch echoing a wrong figure verbatim across two
independent queries, with no source citation, matching neither the primary
abstract text found by direct extraction.

Papers fetched and read directly (not summarized):
- Barber, Lee, Liu & Odean — *The Cross-Section of Speculator Skill* (JFM 2014)
- Barber, Lee, Liu & Odean — *Do Day Traders Rationally Learn About Their Ability?* (working paper)
- Barber & Odean — *Trading Is Hazardous to Your Wealth* (JoF 2000)
- Barber & Odean — *Boys Will Be Boys* (QJE 2001)
- Odean — *Are Investors Reluctant to Realize Their Losses?* (JoF 1998)
- Coates & Herbert — *Endogenous Steroids and Financial Risk Taking on a London Trading Floor* (PNAS 2008)

Kandasamy et al. (PNAS 2014) and Huang & Chan (Pacific-Basin Finance Journal
2014) were checked via WebSearch-surfaced abstract/PubMed/PMC text (their
specific numeric claims in the lesson are qualitative, not point figures, so
abstract-level confirmation is sufficient).

## Result summary

24 distinct numeric/attribution claims checked across all 5 lessons: 23
CONFIRMED (many exact-digit matches — e.g. Odean 1998's December PGR 0.108 /
PLR 0.128, Coates & Herbert's r²=0.48 p=0.004 and r²=0.86 p=0.001), 1 WRONG
(lesson 368's single-household "2.3 percentage points" — first pass's
BLOCKER, independently reconfirmed absent from the primary text). Full table
in `CR132.auditor.md`'s addendum.

Structural checks (ids, prerequisites, retranslate, AMI-naming, editorial
stance, sim-as-measurement) — all PASS, detailed in the addendum.

One new MINOR: lesson 369 slightly overstates Huang & Chan's institutional
finding (the paper's own abstract shows futures firms DO exhibit a
break-even effect after large losses, just one that doesn't move the market
the way individuals' does — the lesson's "showed no such pattern" is a
touch stronger than the source).

## Worktree

`.claude/worktrees/audit-CR132` created at `66e0c664`, used for the pytest
run and for confirming file-level structure, removed after use (was already
gone from `git worktree list` by the time of cleanup — pruned automatically,
confirmed via `git worktree prune -v`).

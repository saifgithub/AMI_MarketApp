<!-- roster entry — binds a role to a spec + addressing. Architect-owned. CR052. -->
# noncoder.edu

```
role: noncoder
sub_kind: maintainer
spec: educational content & daily challenges (data, not code)
kind: content
owns: content/{lessons,daily_challenges,glossary,ai_coach}/** (the corpus DATA + frontmatter)
wip_cap: 2
auditor: none               # gate is Architect/Saiful content review, not the Auditor
live_handle: 002cab10-2814-4e3a-b891-bc73ab9327f0   # live: CR054-W1-ETHIC (economy/solo, $2 cap) — claude --resume
commit_tag: AT:noncoder.edu
worktree: .claude/worktrees/noncoder.edu-<ITEM>
active_lanes: []   # CR054-W1-ETHIC integrated 2026-07-22 (32eac8a); idle
```

**Does NOT code.** Maintains the education corpus (270 lessons, challenges, glossary). The *code*
that serves this data (`lessons_service.py`, `daily_challenge_service.py`, …) belongs to `coder.api`,
not here. Gate: on `READY_FOR_REVIEW` the Architect/Saiful reviews the content — no pytest, no
Auditor. Respect corpus invariants (e.g. CR042 answer-position uniformity, CR044 frozen lesson
codes, no answer/explanation index leaks).

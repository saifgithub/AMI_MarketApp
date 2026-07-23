<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR053-BE — assign (`<Lesson id/>` → `{{lesson:}}` inline token + resolve guard)

KIND: code
INSTANCE: coder.api
ACCEPTANCE: docs/forward_planning/CR053_curriculum_reference_identifiability/CR053_curriculum_reference_identifiability.md (§3.1.3, §5 Phase 2 server bullet, §5 Guards)
DEPENDS-ON: — (head of CR053; unblocks CR053-MOBILE + CR053-MIGRATE)
GATE: independent    <!-- normalized CR070 (was: auditor.core (code lane)) — free-text GATE was never machine-parsed -->
HOT-FILES: backend/app/services/lessons_service.py (coder.api owns) — additive only

**What:** Cut the server seam for cross-lesson quick-links, mirroring the existing `<Term>`→`{{term:}}`
substitution **exactly**. This lane ships the MECHANISM + the resolve GUARD only — the content migration
that populates the tags is a separate lane (CR053-MIGRATE), and the mobile chip is CR053-MOBILE.

**1. Substitution (mirror `_inline_term_tokens` at lessons_service.py:141-150):**
- Add `_LESSON_RE = re.compile(r'<Lesson\s+id\s*=\s*"(?P<id>[^"]+)"\s*/>')` beside `_TERM_RE`.
- Add `def _inline_lesson_tokens(body: str) -> str:` returning
  `_LESSON_RE.sub(lambda m: f"{{{{lesson:{m.group('id')}}}}}", body)`.
- Call it in `parse_mdx` immediately after the existing `body = _inline_term_tokens(body)` (L240), so
  `<Lesson id="039"/>` becomes the inline token `{{lesson:039}}` riding inside prose blocks (NOT promoted
  to a standalone block) — identical treatment to `{{term:}}`.
- Token is **id-keyed** (`{{lesson:039}}`) — this is the doc's own example token (§3.1.3/§3.2). Do NOT try
  to resolve id→code server-side (parse_mdx sees one file; it has no global code map). The client renders
  the CR044 code as the chip label from its catalogue (CR053-MOBILE).

**2. Resolve guard (degrade-loudly, CR040) — extend `backend/tests/unit/test_lesson_corpus_integrity.py`:**
- New test: every `{{lesson:ID}}` token produced across the whole corpus resolves to a real lesson id
  (a `content/lessons/<ID>_*.en.mdx` exists). Fail loudly listing any dangling id.
- Pre-migration there are ZERO `<Lesson/>` tags, so this passes **vacuously** today — that's correct; it
  arms the guard so CR053-MIGRATE's tags are validated as they land. Do NOT add a "no bare 'lesson NNN'
  remains" assertion here — that stricter guard ships WITH the migration (CR053-MIGRATE), or it would fail
  the build on the 238 not-yet-migrated refs.

**3. Unit test (mirror the `{{term:}}` test):** add a `test_lessons_service.py` case asserting
`<Lesson id="039"/>` in a body parses to a prose block containing `{{lesson:039}}` (and does NOT become a
standalone block). If a `{{term:}}` substitution test exists, clone its shape.

**Constraints:** additive — do NOT alter `_inline_term_tokens`, `_TERM_RE`, `_CHATWITH_RE`, `_ANIMATION_RE`
or any existing signature. AMI by name in any comment/copy; LLM fine in code. File header untouched.

**Self-test (headless one-shot — TARGETED, NOT the full suite / P7):**
`cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py tests/unit/test_lessons_service.py -q`
green (exit 0, ~seconds). Do NOT run the full 828s suite — the auditor does broad runs via background+poll.

**Hand-off:** write `orchestration/dispatch/lanes/CR053-BE.coder.api.md` with `STATUS: READY_FOR_AUDIT
(round 1)` + the audit-bridge file `audit/handshake/cr/CR053-BE.architect.md` + `SUBMITTED: round 1`.
ONE commit, tag `(AT:coder.api CR053)`, push origin main (pull --rebase --autostash first). Report the
commit sha + pytest exit code. Completion is verified by git + exit code, never your word.

ASSIGNED: coder.api round 1
DISPATCH: ACCEPTED (round 1)

<!-- Accepted 2026-07-22 by architect: auditor.core VERDICT COMPLETE (round 1) on code 36314f4 (verdict
257587d). Independent evidence: BLIND PROBE proved the resolve guard bites — appended <Lesson
id="zzz_nonexistent"/> to a lesson body → guard FAILED naming ('283_market_order_vs_limit',
'zzz_nonexistent'); probe removed via git checkout, re-green 23 passed. _LESSON_RE/_inline_lesson_tokens
are exact additive mirrors of _TERM_RE/_inline_term_tokens (0 deletions, all existing regexes/signatures
unchanged), called in parse_mdx at L253 right after _inline_term_tokens (L252); token id-keyed
{{lesson:ID}}, no server-side resolution. Unit test asserts the token rides inside a markdown block (kind
'lesson' NOT emitted). Targeted AUDIT_TESTS 41 passed exit 0 (I also re-ran = 41 passed). Full suite N/A —
isolated/additive, out of blast radius (this is exactly the dispatch_audit.sh AUDIT_TESTS fix working: lean
targeted audit, no 828s budget trap). Commit 36314f4 = exactly lessons_service.py + the 2 test files.
coder.api freed. **Unblocks CR053-MOBILE (render the token) + CR053-MIGRATE (produce tokens the guard
validates).** NEXT: CR053-MOBILE (ship the render branch BEFORE migrated content reaches users). -->


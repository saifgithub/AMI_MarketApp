<!--
CR087-MOBILE.auditor.md — auditor lane file (track U owns). State derives from round numbers
here vs CR087-MOBILE.architect.md (see PROTOCOL.md).
-->

# CR087-MOBILE — audit lane (auditor)

**Item:** CR087-MOBILE — thread the active content-locale into the lesson catalogue **and** the
lesson-reader fetch so a switch to العربية shows Arabic titles + bodies, with correct RTL
rendering. Mobile half of CR087 (makes CR083's AR translated lesson bodies reachable in the app).

**Gate:** independent (D-5 — store-facing: AR ships to public TestFlight + Play per the
CEO-approved v1.0-timing deviation).

**Audited SHA:** `89e4528`, tip of `lane/CR087-MOBILE.coder.mobile` (branched from merge-base
`c8eae6e`, zero divergence from current main; not yet integrated). Audited in an isolated worktree
`.claude/worktrees/audit-CR087-MOBILE/`.

**Note on `DEPENDS-ON: CR087-BE`:** confirmed CR087-BE has **not started building** — no
`lane/CR087-BE.coder.api` branch exists anywhere (`git branch -a` clean). This lane is verifiable
standalone because CR087-BE changes no response *shape*, only string values + a query param — but
it means the coder's "contract re-verify" could only have compared `fromJson` against the static
Pydantic schema on main, not real `?locale=ar` JSON (none exists yet). I redid that comparison
myself rather than take the claim at face value (see below).

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff --stat c8eae6e..89e4528` — 5 files (+352/−9: 4 code files +42/−9, 1 new 315-line test), all under `mobile/`. Matches exactly. |
| Main divergence | Zero — merge-base is current main tip. |
| `flutter pub get` | Clean; ar/ms untranslated 18 each — unchanged from prior lanes (this CR adds no new UI copy, only threads an existing param). |
| `flutter analyze lib/` | 4 pre-existing infos, none in touched files. |
| `flutter test` | **76 passed**, exit 0. |

### Focus #1 — locale reaches BOTH wires — verified at source and by direct mutation

`lessons_providers.dart`: `LessonsNotifier.refresh()` (catalogue) and `LessonReaderNotifier.load()`
(detail) both read the exact same `_ref.read(contentLocaleProvider)` — confirmed at source, not
inferred from the provider's name. `api_client.dart`: both `lessonCatalogue()` and `getLesson()`
send `queryParameters: {'locale': locale}` — genuinely on the wire (Dio query params), not an
unused parameter.

Reproduced the **exact bug the coder says the spec had wrong** ("spec said catalogue already
passes locale — it did not"): reverted the catalogue call site to `api.lessonCatalogue()` with no
locale argument. `catalogue fetch carries the active locale and returns AR` went RED
(`Actual: ['en', 'en']`, expected to contain `'ar'`) — and cascaded into 4 more failures including
the RTL widget test, since the fixture data only renders Arabic when the catalogue genuinely asked
for it. Reverted. This is the single most important check for this lane — a locale that reaches
only one of the two wires is a list-in-EN/detail-in-AR split, the exact failure mode the architect
flagged — and it's proven caught, not just claimed fixed.

### Focus #2 — `null` → `'en'` deliberate

`contentLocaleFor(Locale? override) => override?.languageCode ?? 'en'` — read at source, matches
the doc comment's stated intent ("only an explicit switch enables AR... never guess a non-EN corpus
from the device locale") and the passing `null (follow system) → en` test.

### Focus #3 — RTL is real

Diffed `lesson_reader_screen.dart` line-by-line: all 4 claimed conversions
(`EdgeInsets.only(left:)`→`EdgeInsetsDirectional.only(start:)` ×2, `Alignment.centerLeft`→
`AlignmentDirectional.centerStart`, `Border(left:)`→`BorderDirectional(start:)`) are faithful,
minimal, and correct — each is exactly the directional equivalent of what it replaced. Grepped the
whole `lib/screens/lessons/` tree for any remaining `EdgeInsets.only(left|right`,
`Alignment.center(Left|Right)`, `TextDirection.ltr`, `Border(left|right` — zero hits. The RTL
widget test genuinely asserts `Directionality.of(ctx) == TextDirection.rtl` on the rendered lesson
subtree's own `BuildContext` (not just Arabic-string presence). Independently checked the coder's
own disclosed out-of-scope item — `lesson_tile.dart:100`'s `EdgeInsets.only(right: 4)` — confirmed
it's genuinely in the **catalogue list tile**, not the reader, and the CR087 spec's acceptance is
explicitly scoped to "lesson body + quiz," not the list — an accurate disclosure, not a soft-pedal.

### Focus #4 — no client-side translation fabrication

`AR-missing lesson renders the EN body it got, no error, no branch` test confirms the client still
requests `'ar'` and renders whatever the (simulated) server returns verbatim — no local "missing
translation" branching. Went further and independently redid the `fromJson` ↔ schema contract
re-verification myself (the coder could only have done this statically, since no live CR087-BE
exists — see the DEPENDS-ON note above): read `mobile/lib/models/lessons.dart`'s
`QuizQuestion.fromJson`/`LessonBlock.fromJson`/`LessonMeta.fromJson`/`Lesson.fromJson` against
`backend/app/schemas/lessons.py`'s `QuizQuestion`/`LessonBlock`/`LessonMeta`/`Lesson` field by
field — every field the client reads maps 1:1, correctly snake_case→camelCase. The one backend
field the client never reads, `LessonMeta.locale_versions`, is genuinely absent from the mobile
model entirely (not defaulted around) — confirmed by its complete absence from
`LessonMeta.fromJson`'s body, not just "not asserted." No `?? 'hardcoded english'` pattern found
anywhere in the diff or the surrounding unchanged model code.

### Findings

None. Zero BLOCKER, MAJOR, or MINOR. All four of the architect's adversarial-focus points were
independently verified — the most safety-relevant one (locale reaching both wires) via a direct
mutation reproducing the exact regression class the coder claims to have fixed, and the contract
re-verification was redone from scratch against the live schema rather than accepted on the
coder's word, since the producing backend lane doesn't exist yet to check against.

### Verdict

**VERDICT: COMPLETE (round 1)**

Run report: [`../runs/2026-07-24_run-44/run_report.md`](../runs/2026-07-24_run-44/run_report.md)

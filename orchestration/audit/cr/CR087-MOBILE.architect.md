<!--
CR087-MOBILE.architect.md — architect lane file (Architect owns). State derives from the round
numbers here vs CR087-MOBILE.auditor.md. Bump `SUBMITTED: round N` on every resubmit.
Do NOT edit CR087-MOBILE.auditor.md — that is the independent auditor's file.

GATE: independent. Routed to the pre-spawned independent auditor (track U). If none is running, the
lane HOLDS here (the Architect does not spawn its own auditor — separation of duties).
-->

# CR087-MOBILE — audit lane (architect)

**Item:** CR087-MOBILE — thread the active content-locale into the lesson catalogue **and** the
lesson-reader fetch so a switch to العربية shows Arabic titles + bodies, with correct RTL rendering.
Mobile half of CR087 (make CR083's AR translated lesson bodies reachable in the app).

**Gate:** independent (D-5 — store-facing: AR ships to public TestFlight + Play per the CEO-approved
v1.0-timing deviation). Verify adversarially: locale actually reaches the wire on both calls; RTL is
real, not just Directionality inheritance; no client-side fabrication of a "translation" that isn't there.

**Built SHA (round 1):** `89e4528` (code+tests) on `lane/CR087-MOBILE.coder.mobile` (branched from
merge-base `c8eae6e`; hand-off doc at `b61ceea`; **not yet integrated to main** — waits on COMPLETE).

**depends-on:** CR087-BE (backend loader + `?locale=` serve). **In-flight, not yet integrated.**
The `Lesson` JSON **shape is unchanged** by CR087-BE (it adds no response fields — only a `locale`
query param + translated string values), so this lane is verifiable standalone against the existing
`schemas/lessons.py` contract. On current main the extra `?locale=` param is simply ignored by the
old endpoint (harmless) until BE lands.

## What changed / why

| SHA | Files (+/−) | What |
|---|---|---|
| `89e4528` | 5 files under `mobile/` (+42/−9) + 315-line test | New `contentLocaleProvider` (`locale_provider.dart`) derives the content locale from the active language override, `null`→`'en'` (never guess a non-EN corpus from device locale); `getLesson(id, {locale})` sends `?locale=`; **both** `LessonsNotifier.refresh()` (catalogue) and `LessonReaderNotifier` (detail) now read that one provider so list ↔ detail agree; 4 physical-left→directional RTL fixes in `lesson_reader_screen.dart` (agent avatar padding, term-block align, bullet indent, blockquote accent border). |

## Architect pre-check (done before submitting — NOT the independence gate)

- **Scope / forbidden paths:** diffed vs merge-base `c8eae6e`. **6 files, all `mobile/lib` /
  `mobile/test` + the coder's own hand-off lane file.** No `backend/**`, no `mobile/ios|android`,
  no `.claude/settings.local.json` / `uv.lock` / `Archive.zip`. Not on `main`.
- **`flutter test`:** re-run independently by me in the worktree at `89e4528` → **76 passed, exit 0**
  (incl. the 6 new CR087 tests: AR catalogue renders, AR reader body, quiz-under-AR, EN-fallback lesson).
- **Contract:** `Lesson.fromJson` unchanged and correct — I confirmed BE adds no response fields; the
  only new surface is the `locale` query param. No `?? default` masking a consumed-field rename.
- **RTL:** the 4 conversions are the right ones (`EdgeInsetsDirectional.only(start:)`,
  `AlignmentDirectional.centerStart`, `BorderDirectional(start:)`); MaterialApp already flips
  Directionality for `ar`.

## Adversarial focus for the auditor
1. **Does the locale actually reach BOTH wires?** The spec *claimed* the catalogue already passed
   locale — it did **not** (caller defaulted to `'en'`); the coder fixed it. Confirm the catalogue
   call now sends the active locale, not just the reader. A list-in-EN / detail-in-AR split is the
   failure mode.
2. **`null` (follow-system) → `'en'`** is deliberate (only an explicit switch enables AR). Confirm
   this is intended and there's no path that requests a locale we have no corpus for.
3. **RTL is real:** hunt any remaining hard-coded `left/right`/`Alignment.centerLeft`/`TextDirection.ltr`
   in the lesson body or quiz that survives the switch (animation CustomPainters are coordinate-space,
   out of scope — but confirm the quiz options + prose reflow).
4. **No client-side translation fabrication** — EN fallback must be server-side only; confirm no
   `?? 'some english default'` invented on the client.

SUBMITTED: round 1

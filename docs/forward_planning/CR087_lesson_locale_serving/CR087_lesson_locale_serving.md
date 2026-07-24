# CR087 — Lesson locale serving (AR/MS translated bodies → app)

**Status:** in_progress · **Session:** AT:architect · **Date:** 2026-07-24
**Origin:** Saiful, 2026-07-24 — *"release the 250 (or whatever) translated lessons so I
can check initial release on the app."* Chosen scope (AskUserQuestion): **build the
serving slice AND push to public store tracks.**

## What

The Language Manager (CR083) authored **312 AR + 3 MS** translated lesson bodies
(`content/lessons/*.ar.mdx` / `*.ms.mdx`, committed `95ac1ba`/`85f20f7`). The **content
exists but is unreachable** — the lessons pipeline only ever loads and serves English.
This CR builds the small serving slice so a non-EN locale returns the translated body,
end to end, and ships it to testers.

## Why it's dark today (verified)

- `lessons_service.py:344` `_reload()` globs **`*.en.mdx` only** — AR/MS bodies are never
  parsed into memory.
- `catalogue(locale)` (`:352`) filters on the **EN** file's `locale_versions`, which is
  `["en"]` on all 342 EN files → `GET /v1/lessons?locale=ar` returns an **empty** catalogue.
  (The `.ar.mdx` files' *own* frontmatter says `["en","ar"]`, but the loader never reads it.)
- `GET /v1/lessons/{id}` (`api/lessons.py:181`) has **no locale param** → always serves EN.
- Mobile has the language switcher + RTL wired (`app.dart`, `localeNotifierProvider`) and
  `lessonCatalogue({locale})` already passes locale — but `getLesson` (`api_client.dart:484`)
  does **not** pass locale.

Net: flip the app to Arabic today and you get English lessons — a silent no-op. This is
the deferred *"AR + MS at v1.0"* plumbing.

## ⚠ Decision-log deviation (CEO-approved)

Decision log locks **"EN at alpha, AR + MS at v1.0."** Saiful explicitly authorized
shipping AR to **public store tracks now** for initial-release review (AskUserQuestion,
2026-07-24). This CR is that approved deviation. AR only — MS stays internal/off (3/342 ≈
1%, nothing to review). Record in `decision_log.md` at integration.

## Scope — two lanes, `DEPENDS-ON`

### CR087-BE (coder.api, lands first)
1. **Loader:** `_reload()` also discovers `{stem}.ar.mdx` / `{stem}.ms.mdx` siblings of each
   `*.en.mdx`. Store per-locale bodies keyed `(lesson_id, locale)`. **Auto-derive**
   `locale_versions` for a lesson from the set of sibling files that actually parse — do
   **not** hand-edit 342 EN frontmatters. EN meta (`id, track, code, agent_callouts,
   gates_agents, prerequisites`) stays canonical; only display fields (title, blocks,
   quizzes) come from the locale file.
2. **Serve:** `get(lesson_id, locale="en")` returns the locale body, **falling back to EN**
   when the locale is absent (loud fallback is fine here — user sees English, not an error).
   `catalogue(locale)` already filters on `locale_versions`; it now returns AR lessons because
   the loader populates it.
3. **API:** add `locale: str = "en"` to `GET /v1/lessons/{id}` → `svc.get(id, locale)`.
4. **Quiz integrity (MANDATORY — degrade loudly):** `submit_quiz` grades against `answer_index`.
   A translator who reordered options would silently mis-grade AR users. Grade against the
   **served locale's** parsed quiz, AND add a corpus test asserting per-lesson AR/EN quiz
   **option-count + answer_index parity** — fail the build on drift.
5. **Config/compose parity:** no new env key expected; if one is added it must be forwarded in
   `docker-compose.yml` api-alpha block (`test_config_compose_parity.py`).

### CR087-MOBILE (coder.mobile, `DEPENDS-ON: CR087-BE`)
1. `getLesson(lessonId, {String locale})` passes the active locale (from
   `localeNotifierProvider`) to `/v1/lessons/{id}?locale=`. Catalogue call already passes it —
   thread the same locale through the lesson-detail open.
2. **Contract re-verify (MANDATORY):** the backend↔mobile mirror is hand-written. Before
   `READY_FOR_AUDIT`, re-verify `Lesson.fromJson` against **actual CR087-BE `?locale=ar` JSON**,
   not the spec — a field rename is masked by `?? default`.
3. **RTL:** confirm the lesson body + quiz render right-to-left when locale is `ar`
   (MaterialApp sets `Directionality`; verify the lesson renderer inherits it, no hard-coded LTR).
4. Widget tests: Arabic catalogue non-empty, lesson detail shows AR body, EN fallback for an
   AR-missing lesson (31 exist), quiz submit grades correctly under AR.

## Out of scope
Glossary / ai_coach / daily-challenge translations (CR083 Tier 2, separate). MS enablement
(too sparse). New translations (authoring is CR083's). Pricing, ads.

## Acceptance
- `GET /v1/lessons?locale=ar` returns a non-empty catalogue; `GET /v1/lessons/{id}?locale=ar`
  returns the Arabic body; an AR-missing lesson falls back to EN (never 404, never empty).
- Quiz grades against the served locale; AR/EN answer_index parity test green; full unit suite green.
- Mobile: switching Settings→Language to العربية renders Arabic lessons RTL end to end; EN
  fallback is silent-correct; `fromJson` re-verified against live BE JSON.
- Both lanes independently audited COMPLETE (GATE: independent — store-facing).
- Deviation recorded in `decision_log.md`. Promoted to alpha + shipped to public TestFlight + Play.

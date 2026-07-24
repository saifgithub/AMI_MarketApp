# CR083 — Language Manager: AR + MS translation delivery via in-house LLM

**Filed:** 2026-07-24 (AT:R65, Language Manager) · **Status:** in_progress
**Requester:** Saiful — *"we will use the inhouse llm to translate it into malay and Arabic... the most important item we need to address is the language in the lessons... not only do we translate, we need to make sure that the translation makes sense."*

Maps to GTM milestone **M5** (`docs/initial_specs/10_delivery/project_plan.md`), previously ⚡ partial ("i18n landed early in Alpha"). Supersedes D-052's original external-human-translator plan for this delivery — Saiful confirmed the in-house vLLM pipeline is the mechanism, with automated checks only for now (no human-QA blocking gate); native QA is logged as a non-blocking follow-up before public MVP launch.

## Why

`content/i18n/` was assigned as the Language Manager's domain but is empty and untracked — a never-realized early spec (`docs/initial_specs/07_localization/i18n_architecture.md`, `strings.json`/`flutter_intl`) superseded by the actually-shipped Flutter ARB system (`mobile/lib/l10n/*.arb`, per `docs/initial_specs/08_tech/flutter_implementation.md`). Real translation surfaces and their coverage at filing time:

| Tier | Source | EN | AR | MS | Script |
|---|---|---|---|---|---|
| 1 | `mobile/lib/l10n/app_en.arb` | 428 keys | ~315 (113 missing) | ~314 (114 missing) | `scripts/translate_arb_lan.py` — used before (AT:R35), needs a gap-fill re-run |
| 2 | `content/glossary/terms.en.json` + `content/ai_coach/*.json` + `content/daily_challenges/*.json` | 208 terms + more | 0 | 0 | `scripts/translate_content_lan.py` — shipped, never run |
| 3 | `content/lessons/*.en.mdx` | 342 files | 0 | 0 | `scripts/translate_lessons_lan.py` — shipped, never run; **top priority per Saiful** |

Four scripts already solve batching/retry/placeholder-parity/persist-per-batch against the on-prem vLLM host (`192.168.20.74:8000`) — this CR does not rewrite them, only runs them and adds the reporting/QA layer they don't have.

## Scope

- **`content/i18n/` becomes the process home** (not runtime strings): `README.md` (charter), `coverage_status.md` (generated), `style_guide_ar_ms.md`, `sensitive_keys.json`, `lesson_confidence_log.json`, `qa_spotcheck_log.md`.
- **New tooling** (content-metadata bookkeeping / reporting, not application code):
  - `scripts/i18n_coverage_report.py` — per-tier/per-locale completion report; also syncs each EN lesson's `locale_versions` frontmatter from which translated siblings exist on disk (a real gap found: `translate_lessons_lan.py` never writes this back to the source `.en.mdx`, and `lessons_service.py` reads only that file to decide AR/MS catalogue membership — without the sync, translated lessons would be invisible to the app).
  - `scripts/i18n_apply_exclusions.py` — pre/post wrapper applying the sensitive-key carve-out without editing the 4 existing scripts.
  - `scripts/i18n_verify_lesson_translation.py` — Tier 3 confidence tool (see below).
- **Sensitive-key carve-out** (generalizes DEF094): `content/i18n/sensitive_keys.json`, seeded from the ARB `OBSERVANCE-SENSITIVE` marker + a grep sweep (`sharia|halal|haram|AAOIFI|fatwa|zakat|riba`), confirmed hits: `content/ai_coach/islamic_finance.json`, `ai_meta.json`, `platform.json`, `content/daily_challenges/2026_12.json`, lesson `355_how_amis_halal_flag_maps_to_real_screening.en.mdx`. These stay EN, routed to Saiful/SME, never auto-translated.
- **Execution**: Tier 1 gap-fill → Tier 2 (glossary/ai_coach/daily_challenges) → Tier 3 (lessons), strictly sequential against vLLM (a prior parallel attempt saturated the host).
- **Tier 3 confidence verification** — the flagship deliverable. Placeholder-parity catches corruption, not meaning. The only model diversity available is manually swapping the model loaded on the vLLM host (no second always-on API), so the tool is a repeatable, resumable pass: reads the currently-loaded model's identity via `GET /v1/models`, asks it to score EN-vs-translation semantic fidelity (`{confidence 1-5, meaning_preserved, critical_issues, minor_issues}`), and accumulates results per lesson/locale/model into `lesson_confidence_log.json`. A lesson/locale counts **verified** once ≥2 distinct models agree (min confidence ≥4/5, zero unresolved critical issues); single-model passes are logged as a lower-confidence signal, not silently cleared.

## Acceptance

- [ ] Tier 1: ARB gap closed excluding sensitive keys; `flutter gen-l10n` succeeds; spot-checked on device.
- [ ] Tier 2: `content/glossary/terms.{ar,ms}.json` + ai_coach + daily_challenges generated, sensitive ids excluded, per-id EN fallback confirmed for excluded ids.
- [ ] Tier 3: 341/342 lessons translated (355 held to EN/SME); `locale_versions` synced; MDX components (`<Term/>`, `<ChatWith/>`, `<Animation/>`, `<Quiz>`) verified intact in a sample.
- [ ] Lesson confidence log shows no unresolved `critical_issues` on lessons marked done.
- [ ] `coverage_status.md` + `sensitive_keys.json` committed; native QA logged as non-blocking follow-up.
- [ ] M5 row in `project_plan.md` updated to reflect delivered status.

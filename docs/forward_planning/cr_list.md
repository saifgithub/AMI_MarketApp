# Change-request register — AMI Trade

The register of **planned change** — new work, not fixes. A CR is anything that adds or
changes behaviour versus the current build: a feature, a refactor, a process change, a
content or infra change. (Fixing something already broken is a **Defect** —
see [`../defect/def_list.md`](../defect/def_list.md).)

Governance rationale: decision **D-058** in [`../initial_specs/11_decisions/decision_log.md`](../initial_specs/11_decisions/decision_log.md).

## How a CR works

- **Auto-file, proceed.** Saiful's prompt IS the approval. When he asks for a change,
  Claude assigns the next `CR###`, creates its folder, files the CR doc, then implements —
  no separate approval gate.
- **ID:** `CR###`, zero-padded, sequential, never reused.
- **Folder:** every CR gets `docs/forward_planning/CR###_<snake_case_topic>/`. It holds at
  minimum `CR###_<topic>.md` (what / why / scope / acceptance). All design docs, notes, and
  sub-specs for that change live in its folder.
- **Commit tag:** the fix/feat commit carries `(AT:R<N> CR###)` after the summary, e.g.
  `feat(journal): search across entries (AT:R42 CR007)`.
- **Exempt from needing a CR:** process commits — handover wraps (`chore(handover)`),
  TestFlight/build version bumps, and docs-only commits. These keep the plain `(AT:R<N>)` tag.

**Status:** `proposed` · `in_progress` · `done` · `dropped`.

## Register

| CR | Date | Title | Status | Folder | Session |
|---|---|---|---|---|---|
| CR001 | 2026-07-05 | Change governance — CR/Defect registers + docs restructure | done | [CR001_change_governance/](CR001_change_governance/) | AT:R48 |
| CR002 | 2026-07-06 | Reconcile the `bug_reports` status vocabulary | proposed | [CR002_bug_status_vocabulary/](CR002_bug_status_vocabulary/) | AT:R49 |
| CR003 | 2026-07-06 | Correct stale "no GitHub remote" documentation | done | [CR003_github_remote_docs/](CR003_github_remote_docs/) | AT:R50 |
| CR004 | 2026-07-06 | Release-readiness master plan — 4 workstreams (verify / playability / competition / attractiveness) | in_progress | [CR004_release_readiness/](CR004_release_readiness/) | AT:R51 |
| CR005 | 2026-07-09 | Architect/auditor audit-handshake protocol (ported from ami_ai) | done | [CR005_audit_handshake_protocol/](CR005_audit_handshake_protocol/) | AT:G1 |
| CR006 | 2026-07-09 | Beta infra cost research — melehost + on-prem LLM replacement | proposed | [CR006_beta_infra_cost_research/](CR006_beta_infra_cost_research/) | AT:G1 |
| CR007 | 2026-07-09 | Agent data/news provider research — closing the fake-data gap in the 12-agent team | proposed | [CR007_agent_data_provider_research/](CR007_agent_data_provider_research/) | AT:G1 |
| CR008 | 2026-07-09 | Convene the Room token estimation and prompt caching opportunities | proposed | [CR008_convene_room_prompt_caching/](CR008_convene_room_prompt_caching/) | AT:G2 |
| CR009 | 2026-07-09 | Mobile engagement bundle B3/B4/B6 — Room roster + dead-end removal + empty states (impl CR under CR004) | done | [CR009_mobile_engagement_b3b4b6/](CR009_mobile_engagement_b3b4b6/) | AT:R53 |
| CR010 | 2026-07-09 | B2/B5 — streak chip + challenge server-truth + league API layer (impl CR under CR004) | done | [CR010_mobile_streak_challenge_league_api/](CR010_mobile_streak_challenge_league_api/) | AT:R53 |
| CR011 | 2026-07-09 | C3 — league surface: card + screen + Settings profile (impl CR under CR004) | done | [CR011_mobile_league_surface/](CR011_mobile_league_surface/) | AT:R53 |
| CR012 | 2026-07-10 | C4 — share cards: offscreen ShareCard + 4 templates + entry points (impl CR under CR004) | done | [CR012_mobile_share_cards/](CR012_mobile_share_cards/) | AT:R53 |
| CR013 | 2026-07-10 | E3/D1 — lesson animation chassis + 7 CustomPainter primitives + registry (impl CR under CR004) | done | [CR013_lesson_animation_primitives/](CR013_lesson_animation_primitives/) | AT:R53 |
| CR014 | 2026-07-10 | E3/D2+D3 — motion identity: HexPulseLoader + avatar/chip/button glow + count-up (impl CR under CR004) | done | [CR014_motion_identity/](CR014_motion_identity/) | AT:R53 |
| CR015 | 2026-07-10 | E4/D7 — on-system components: glass sheets + hex period toggle + HexToast + logo (impl CR under CR004) | done | [CR015_on_system_components/](CR015_on_system_components/) | AT:R53 |
| CR016 | 2026-07-10 | E4/D8 — HexBottomNav: hex-pill bottom navigation (impl CR under CR004) | done | [CR016_hex_bottom_nav/](CR016_hex_bottom_nav/) | AT:R53 |
| CR017 | 2026-07-10 | Multi-provider LLM routing + per-provider caching mechanics — DeepSeek/Qwen/Gemini, user-level routing (research; linked to CR008) | proposed | [CR017_multiprovider_llm_routing/](CR017_multiprovider_llm_routing/) | AT:R53 |
| CR018 | 2026-07-11 | Lesson numbering — surface the canonical id-prefix lesson number (`001`–`292`, gapped) in the app (list + reader) so lessons are referenceable by number | done | [CR018_lesson_numbering/](CR018_lesson_numbering/) | AT:R54 |
| CR019 | 2026-07-12 | Concierge lesson retrieval — **embedding mode** (robust semantic retrieval over the 270 lessons; needs an on-prem embedder) | proposed | [CR019_concierge_embedding_mode/](CR019_concierge_embedding_mode/) | AT:R54 |
| CR020 | 2026-07-12 | Concierge lesson context — **full context mode** (cheap: compact all-lesson index with topic/tags in the prompt, no embeddings) | proposed | [CR020_concierge_full_context_mode/](CR020_concierge_full_context_mode/) | AT:R54 |
| CR021 | 2026-07-12 | Concierge context **router** — `CONCIERGE_CONTEXT_MODE` flag selects saver / full_context / embedding (default full_context) | proposed | [CR021_concierge_context_router/](CR021_concierge_context_router/) | AT:R54 |
| CR022 | 2026-07-12 | App manual corpus — Concierge app-usage knowledge, authored + indexed like lessons and routed through CR021 | proposed | [CR022_app_manual_corpus/](CR022_app_manual_corpus/) | AT:R54 |
| CR023 | 2026-07-12 | Wire the News Analyst to a real live news feed (Yahoo free + Alpha Vantage NEWS_SENTIMENT, combined) — closes Gap 5 news half, builds on CR007 | in_progress | [CR023_news_analyst_live_feed/](CR023_news_analyst_live_feed/) | AT:R57 |
| CR024 | 2026-07-12 | Wire the Social Media Analyst to a real social-sentiment source (Adanos, Reddit-only — LunarCrush blocked on a paid-tier upgrade) — closes Gap 5 social half, builds on CR007 | in_progress | [CR024_social_analyst_live_feed/](CR024_social_analyst_live_feed/) | AT:R57 |
| CR025 | 2026-07-12 | Watchlist day-change % badge — backend wire-up + Flutter render (migrated from Silent_Scout, cheapest fix in the backlog) | done | [CR025_watchlist_daychange_badge/](CR025_watchlist_daychange_badge/) | AT:R56 |
| CR026 | 2026-07-12 | Sector concentration enforcement + Portfolio-screen allocation chart — closes an unenforced mandate compliance rule (migrated from Silent_Scout) | proposed | [CR026_sector_allocation/](CR026_sector_allocation/) | AT:R55 |
| CR027 | 2026-07-12 | Price alerts / push notifications — design complete, hard-gated on A15/A16 external cert work (migrated from Silent_Scout) | proposed | [CR027_price_alerts/](CR027_price_alerts/) | AT:R55 |
| CR028 | 2026-07-12 | Trailing stop — Tier 3, sequenced after CR027 (migrated from Silent_Scout) | proposed | [CR028_trailing_stop/](CR028_trailing_stop/) | AT:R55 |
| CR029 | 2026-07-12 | Cost-basis lots / FIFO realised-P&L display — Tier 3, deferred by product sequencing (migrated from Silent_Scout) | proposed | [CR029_cost_basis_lots/](CR029_cost_basis_lots/) | AT:R55 |
| CR030 | 2026-07-12 | Dividend fields for the earnings chip — small gap-closer on an already-shipped feature (migrated from Silent_Scout) | proposed | [CR030_earnings_dividend_fields/](CR030_earnings_dividend_fields/) | AT:R55 |
| CR031 | 2026-07-12 | On-device STT/TTS benchmark + recommendation for A13/A14/A17 — highest-leverage unblocked action found in Silent_Scout audit | proposed | [CR031_voice_stt_tts_benchmark/](CR031_voice_stt_tts_benchmark/) | AT:R55 |
| CR032 | 2026-07-12 | GB10 shared-hardware conflict + LoRA fine-tuning go/no-go decision — production vLLM host doubles as the research training box, never resolved | proposed | [CR032_gb10_lora_finetuning_decision/](CR032_gb10_lora_finetuning_decision/) | AT:R55 |
| CR033 | 2026-07-13 | Remaining agent truthfulness gaps found auditing all 12 agents post-CR023/024 — Market Analyst (100% fabricated technicals), Fundamentals Analyst (oversold scope), Bull Researcher (fabricated journal-history claim) | superseded by DEF052/DEF053/DEF054/DEF055 | [CR033_remaining_agent_data_gaps/](CR033_remaining_agent_data_gaps/) | AT:R57 |
| CR034 | 2026-07-13 | Room's `forward_catalyst` FOMC date was a frozen "in 11 days" literal, never real — found verifying a live HPQ convene right after DEF051-055 shipped; now computed from the Fed's real 2026 meeting calendar, sector-earnings half stays explicitly illustrative | done | [CR034_room_forward_catalyst_fabricated_fomc_date/](CR034_room_forward_catalyst_fabricated_fomc_date/) | AT:R58 |

| CR035 | 2026-07-16 | Room-vs-Street benchmark — convene ~30 tickers on live Alpha, score verdicts against analyst buy/sell/hold consensus (yfinance + StockAnalysis + spot-checks), incl. ablation batch (SUPPRESS_ANALYST_CONSENSUS) to test consensus-parroting | in_progress | [CR035_room_benchmark/](CR035_room_benchmark/) | AT:R59 |

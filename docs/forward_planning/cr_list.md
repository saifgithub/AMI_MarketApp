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
| CR015 | 2026-07-10 | E4/D7 — on-system components: glass sheets + hex period toggle + HexToast + logo (impl CR under CR004) | in_progress | [CR015_on_system_components/](CR015_on_system_components/) | AT:R53 |
| CR016 | 2026-07-10 | E4/D8 — HexBottomNav: hex-pill bottom navigation (impl CR under CR004) | in_progress | [CR016_hex_bottom_nav/](CR016_hex_bottom_nav/) | AT:R53 |


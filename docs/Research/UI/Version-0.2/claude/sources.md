# Sources

Primary = originator of the fact/idea (code, register, first-party research).
Secondary = commentary or aggregation. External quotes verified by live fetch 2026-08-12
unless flagged.

## Internal — code (primary)

| Source | Used for |
|---|---|
| `mobile/lib/screens/floor/floor_screen.dart` (541 lines) | Floor stack order §01: concierge hex 110pt `:383-392`, agents Wrap `:410-429`, tour keys `:49-53`, challenge `:434-437`, league `:441`, convene CTA `:445-452`, restart `:462`, footer `:483-496`; `_AgentTile` 88pt/72pt + 0.35 locked opacity `:509-565` |
| `mobile/lib/screens/home_shell.dart:30-36, 101` | Five tabs; TickerTape below nav |
| `mobile/lib/screens/room/room_screen.dart:382-421` | `_RoomLiveRoster` pins `kAllAgents.sublist(0,12)` from first frame (CR112); four seat states |
| `mobile/lib/state/room_view_mode_provider.dart` | CR106 persisted board default; single-writer rule (T-MODESIDE) |
| `mobile/lib/models/agent.dart:45-196` | 12 agents + Concierge, families/colors; `kAgentPhase` six phases; `kCombVoices` 11 voices |
| `mobile/lib/theme/ami_theme.dart:21-94` | Dark tokens + `AmiColorsLight` used by the prototypes |
| `mobile/lib/l10n/app_en.arb` (`floor*` keys) | Baseline frame copy, verbatim |

## Internal — docs & governance (primary)

| Source | Used for |
|---|---|
| `docs/initial_specs/11_decisions/decision_log.md` — D-003/012/013/014/015/018/021/024/062 | Constraint map §03.6, strain matrix §04 |
| `docs/initial_specs/11_decisions/rejected_features_register.md` | Rejection cross-check §04 |
| `docs/initial_specs/05_design/floor_home_honeycomb.md` | "a room with people in it" design intent §01 |
| `docs/initial_specs/05_design/ami_hex_in_flutter.md` (CR113/CR117) | Geometry rules for the frames |
| `docs/initial_specs/05_design/colors_motion_rtl.md` | Family colours; pink = Concierge-only |
| `docs/forward_planning/CR106_room_result_visual_summary/CR106.md` | Shipped disclosure precedent §03.1 |
| `docs/forward_planning/CR159_your_firm_desk_structure/README.md` | Desk bands, unfilled seats, traps §03.3, flow A2 |
| `docs/forward_planning/CR160_agent_rename/README.md` | New names + T-SEQUENCE §03.3 |
| `docs/forward_planning/CR133_bottom_nav_restructure/CR133.md` + `prototype/build.py` | 4-tab assumption; prototype build convention (adapted) |
| `docs/forward_planning/CR120_portfolio_list_structure/CR120.md` | Collapsible-section rejection cited against D |
| `docs/forward_planning/CR004_release_readiness/plan_b_playability_ux.md` | The claim §06 engages |
| `docs/forward_planning/CR043_bug_feedback_loop/CR043_bug_feedback_loop.md` | Why the complaint had no capture path |

## Internal — measurements (primary)

`prototype/concepts.html` + `prototype/flows.html`, stat strips DOM-read (headless Chrome,
2026-08-12). Method + limits: `00_method_and_limits.md`. Regenerate: `python3
prototype/build.py`, open either page, read the strips.

## External (verified by fetch)

| # | Source | Label |
|---|---|---|
| 1 | Nielsen, *Progressive Disclosure*, NN/g 2006 — https://www.nngroup.com/articles/progressive-disclosure/ | Primary |
| 2 | Whitenton, *Minimize Cognitive Load…*, NN/g 2013 — https://www.nngroup.com/articles/minimize-cognitive-load/ | Primary (UX application) |
| 3 | Yablonski, *Hick's Law*, lawsofux.com — https://lawsofux.com/hicks-law/ | Secondary (aggregates Hick & Hyman 1952) |
| 4 | Iyengar & Lepper, *When Choice Is Demotivating*, JPSP 79(6), 2000 — https://faculty.washington.edu/jdb/345/345%20Articles/Iyengar%20%26%20Lepper%20(2000).pdf | Primary (original research) |
| 5 | Liu & Rosala, *Designing AI Agents*, NN/g May 2026 — https://www.nngroup.com/articles/designing-ai-agents/ | Primary |
| 6 | Rosala, Kenderova & Kohler, *Less Chat, More Answer*, NN/g Apr 2026 — https://www.nngroup.com/articles/less-chat-more-answer/ | Primary |
| 7 | Anthropic Engineering, *How we built our multi-agent research system*, 2025 — https://www.anthropic.com/engineering/multi-agent-research-system | Primary (first-party) |
| 8 | Wroblewski, *Agent Management Interface Patterns*, 2025 — https://lukew.com/ff/entry.asp?2106 | Primary |
| 9 | Wroblewski, *Agentic AI Interface Improvements*, Nov 2025 — https://www.lukew.com/ff/entry.asp?2136 | Primary |
| 10 | O'Hear, *Cleo… picks up $10M Series A*, TechCrunch 2018 — https://techcrunch.com/2018/09/20/cleo-meet-balderton/ | Secondary (carries primary founder quote) |
| 11 | Intercom, Fin product page, fetched 2026 — https://fin.ai/ | Primary (vendor self-description) |
| 12 | Robinhood Newsroom, *The top secret Robinhood design story*, 2021 — https://robinhood.com/newsroom/the-top-secret-robinhood-design-story/ | Primary (vendor self-description — weight accordingly) |
| 13 | Citron, *Try Deep Research… in Gemini*, Google Dec 2024 — https://blog.google/products/gemini/google-gemini-deep-research/ | Primary (first-party) |

## Not cited — fetch failed (recorded so nobody re-tries blind)

- Perplexity Deep Research blog + help-center pages — HTTP 403. Search snippets describe a
  staged progress display, but page text unverified; Gemini (#13) and LukeW (#9) cover the
  pattern.
- Inc.com on Cleo's comedy-writer persona — HTTP 403; TechCrunch (#10) suffices.
- Columbia Business School's jam-study page — 403; the JPSP full text (#4) is better anyway.

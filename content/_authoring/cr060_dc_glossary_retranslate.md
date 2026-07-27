# Daily challenges + Glossary — re-translation needed (DEF117 → i18n lane)

EN entries corrected under DEF117 whose **user-facing meaning changed** and which have AR/MS siblings.
Keyed by `id`. See [[feedback_content_change_flags_translation]].

| id | surface | file | locales stale | why |
|---|---|---|---|---|
| dc_2026_06_26_trader_execution_call | daily_challenges | 2026_06.json | ar, ms | risk/reward figure corrected 5.2x → 2.6x |
| dc_2026_07_01_guaranteed_2pct_weekly | daily_challenges | 2026_07.json | ar, ms | "13 agents" → "12 analyst agents, or the Concierge" |
| dc_2026_10_09_discipline_mandate_call | daily_challenges | 2026_10.json | ar, ms | "30 minutes" → "about 20 minutes" |
| share_price | glossary | terms.{ar,ms}.json | ar, ms | definition rewritten (last-traded-price) |
| aaoifi | glossary | terms.{ar,ms}.json | ar, ms | AAOIFI caps corrected to 30/30/5 (33 is DJIM); dropped stale "AMI's logic follows" (CR069) |
| financial_ratio_screen | glossary | terms.{ar,ms}.json | ar, ms | DJIM 33 vs AAOIFI 30 attribution corrected |
| musharakah | glossary | terms.{ar,ms}.json | ar, ms | loss now correctly shared by capital proportion, not the agreed profit ratio |

**NOT stale:** `dc_2026_11_11_klci_bull_regime` (`related_agent` metadata only) and the 22 glossary
`related_lessons` re-points (metadata only, no user-facing prose change).

**Guard TODO (CR060 Phase 6):** per-`id` `source_sha` stamp on these JSON surfaces so the flag is automatic.

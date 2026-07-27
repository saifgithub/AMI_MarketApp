# Daily challenges + Glossary — re-translation needed (DEF117 → i18n lane)

EN entries corrected under DEF117 whose **user-facing meaning changed** and which have AR/MS siblings.
Keyed by `id`. See [[feedback_content_change_flags_translation]].

| id | surface | file | locales stale | why |
|---|---|---|---|---|
| dc_2026_06_26_trader_execution_call | daily_challenges | 2026_06.json | ar, ms | risk/reward figure corrected 5.2x → 2.6x |
| dc_2026_07_01_guaranteed_2pct_weekly | daily_challenges | 2026_07.json | ar, ms | "13 agents" → "12 analyst agents, or the Concierge" |
| dc_2026_10_09_discipline_mandate_call | daily_challenges | 2026_10.json | ar, ms | "30 minutes" → "about 20 minutes" |
| share_price | glossary | terms.{ar,ms}.json | ar, ms | definition rewritten (last-traded-price) |

**NOT stale:** `dc_2026_11_11_klci_bull_regime` — `related_agent` metadata only, no user-facing prose change.

**Guard TODO (CR060 Phase 6):** per-`id` `source_sha` stamp on these JSON surfaces so the flag is automatic.

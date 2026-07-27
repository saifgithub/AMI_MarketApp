# CR060 — AI Coach Q&A quality sweep (DEF115)

**Surface:** `content/ai_coach/*.json` (EN) — the agent-chat Q&A answers shown to users.
**Scope:** 245 EN entries (beginner 50 · intermediate 50 · platform 40 · psychology 50 · scam 40 · islamic_finance 15).
**Method:** dual approach —
1. **LLM sweep** — 6 Sonnet subagents (one per category file), each verifying every entry for factual
   accuracy, fake-real data (real ticker + invented number), and safety/naming compliance
   (simulation-only, "AMI" not "the AI"), with WebSearch corroboration. Sharia rulings auto-escalated,
   not adjudicated. Run `wf_799c5ba0-035`, 6/6 agents, 0 errors, ~363K tokens, ~1.8 min.
2. **Deterministic scan** — grep-vs-schema for the mechanically-decidable classes (double-period typos,
   broken lesson crossrefs, stale UI labels). Same DEF083/DEF102 lesson: deterministic beats LLM here —
   the LLM sweep flagged only **3 of 12** typos; the scan caught all 12.

**Headline:** 96% of entries clean on the LLM pass — a very different picture from lessons (88% *defective*),
because these are conversational answers, not worked examples, so the fake-real-number plague is absent
(**zero fake-real hits**). The real defect set is ~19, dominated by cosmetic typos.

## Corrections applied (DEF115, this pass)

| id | file | class | severity | change |
|---|---|---|---|---|
| qa_beg_max_loss_per_day, qa_beg_is_ami_real_money, qa_beg_can_ami_predict, qa_beg_who_decides, qa_beg_pick_first_stock, qa_beg_how_much_money_start, qa_beg_fees_in_app, qa_beg_taxes, qa_beg_credits | beginner | typo | cosmetic | `..` → `.` (9) |
| qa_int_rsi_oversold, qa_int_rsi_divergence, qa_int_high_de_meaning | intermediate | typo | cosmetic | `..` → `.` (3) |
| qa_beg_market_cap | beginner | fact | P2 | large/mega buckets were collapsed; corrected to small <2B / mid 2–10B / large 10–200B / mega >200B (FINRA/Schwab/Finance Strategists), framed as conventions |
| qa_beg_pick_first_stock | beginner | crossref | P2 | `related_lessons` `["013","017"]` → `["001","005"]` to match the prose ("Lesson 001 and 005"). Metadata-only; prose unchanged |
| qa_plt_coach_what_is | platform | naming | P2 | nav label `-> Coach` → `-> Brief Your Agent` (AT:R27 rename) |
| qa_plt_coach_reset | platform | naming | P2 | nav label `-> Coach` → `-> Brief Your Agent`; "Coach History" → "Brief Your Agent history" |
| qa_scam_check_asic_australia | scam | fact | P2 | dead `asic.gov.au/reportascam` → Scamwatch at scamwatch.gov.au (ASIC directs scam reports there) |
| qa_plt_halal_flag | platform | **repo-truth (CR069)** | **P1** | rewritten from the retired live-ratio-screen description to the sourced four-state screen (PASS/SCREENED-OUT/UNKNOWN/PAUSED) — AI-Coach sibling of DEF097 |
| qa_islamic_which_standard_does_ami_use | islamic_finance | **repo-truth (CR069)** | **P1** | rewritten: AMI defers to a sourced AAOIFI-standard index (S&P 500 Sharia Industry Exclusions Index / SPUS), does not compute its own 33%/33%/5% screen — AI-Coach sibling of DEF097 |

## Triage notes (manager)

- **The two halal entries were under-triaged by the LLM.** The Sonnet agent flagged `qa_islamic_which_standard`
  as a P2 threshold typo (30 vs 33) and `qa_plt_halal_flag` as an ESCALATE. Verified against the shipped code
  (`app/services/sharia_universe.py`, `app/schemas/sharia.py`, CR069): **both described the retired live
  ratio-screen mechanism.** AMI's halal flag no longer computes a screen — it checks membership in a sourced,
  dated index and returns four states. So these are P1 repo-truth defects (same class as lesson 355 / DEF097),
  correctable by the education manager as code-truth mechanics — the 30-vs-33 debate is moot once the
  ratio-screen claim is removed. The **doctrinal soundness** of the sourced index remains an SME question, but
  that product decision was already made (CR069) and the in-copy "confirm with your own scholar" disclaimer
  stays. No new blocking escalation.

## Not defects

- `related_lessons` crossrefs: **0 point to a non-existent lesson** (corpus-wide).
- No fake-real ticker+number pairs found (the dominant lesson defect class is absent here).

## Translation

5 corrected entries change user-facing meaning and have AR/MS siblings → flagged for re-translation in
`cr060_aicoach_retranslate.md`. The 12 typo fixes and the crossref-metadata fix do **not** change EN meaning,
so their translations are not stale. `islamic_finance` is EN-only (no sibling).

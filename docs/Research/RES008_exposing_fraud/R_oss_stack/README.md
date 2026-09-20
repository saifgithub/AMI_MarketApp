# R_oss_stack — open-source trading/agent repo verdicts

Eight named open-source projects Saiful listed 2026-09-20, framed as a stack (data → strategy →
backtest → risk → execution → agent), surveyed for whether each asserts a specific, falsifiable
trading edge RES008's method could test. Full comparative writeup: `../02_oss_stack_survey.md`.
Tracker rows: `TRACKER.md` B10–B13.

**Different unit from `C##`/`P##`.** These are not video claims with a measured reach — they are
named projects, read from their own docs/papers. None was tested (no code run, no `RESULTS.md`);
each folder holds a desk-review `VERDICT.md` recording what the project claims (if anything),
whether a concrete recipe exists inside it, and what would justify revisiting it later. A "revisit"
promotes the relevant repo's finding into an actual `C##` pre-registration when it does.

| ID | Repo | Verdict |
|:--|:--|:--|
| R01 | AI Hedge Fund (virattt) | No testable claim — agent scaffolding, no fixed recipe |
| R02 | Freqtrade | No testable claim — framework, explicit no-warranty disclaimer |
| R03 | CCXT | No testable claim — pure exchange API wrapper |
| R04 | NautilusTrader | No testable claim — execution/backtest engine |
| R05 | Hummingbot | Testable but not novel — PMM mechanism ≈ same claim class as C06 |
| R06 | Eliza / elizaOS | No testable claim (framework); adjacent token fraud allegation flagged separately |
| R07 | FinRL | Testable, mixed evidence already exists — the strongest candidate; self-contradicts across its own contest years |
| R08 | Jesse | No testable claim — framework, textbook example carries no project claim |

Do not re-run this survey from scratch on a later visit — read the relevant `R##/VERDICT.md`
first; each one states exactly what would justify promoting it.

# WP-13 — Output text guard: replay over stored Alpha text (2026-11-19)

**What this is:** the hit-rate measurement the S11 plan requires before `OUTPUT_GUARD_MODE` may leave
`log` (CR271, CR267 WP-13). **Contains counts and rule names only; no user text.**

## 1. Method

1. Read-only `SELECT` on Alpha's `llm_audit` (joined to `users`), exported to a git-ignored scratch
   file outside the repo, deleted at the end. Nothing was written to melehost.
2. `app.services.output_guard.check(..., mode="enforce")` run over each `response_text`, through
   `scripts/output_guard_replay.py::summarize` (the script's own counting core; the script's DB
   reader was not used because it needs `DATABASE_URL` inside the Alpha container).
3. Flows scanned: the script's five user-visible flows — `room`, `room_pm`, `one_on_one`,
   `concierge_floor`, `coach_chat`. Not scanned: the internal Room repair/review flows, `price_alert`,
   `portfolio_health_finding`, `translate`.
4. Text is the raw model response, as the script was designed. The live seam checks the finished
   display text, so a `room_pm` raw response also exposes the verdict JSON fields; hit counts are
   comparable but not identical to the live seam.

## 2. Filter and n

The export held 104,769 Room-flow rows plus 387 non-Room rows (after the WP-10 exclusion below); 80,759 are in scope, in three cohorts:

| Cohort | Definition | n |
| --- | --- | --- |
| **A. App** (headline) | user exists, `last_app_version` set, not `room-benchmark` / `uat` / `0.0.0-e5drill`, device not `ami-uat-qa*` / `SM-A176B` | **671** (13 users): 413 `room`, 252 `room_pm`, 3 `concierge_floor`, 3 `coach_chat`, **0** `one_on_one` |
| **B. Harness** (volume) | provider `vllm`, created before 2026-11-18, user row deleted or without app version. Research Rooms (CR035-era and later benchmarks) on the production prompts and model; never shown to a user | **79,980** (6,085 users): 49,555 `room`, 30,425 `room_pm` |
| **C. UAT** (non-Room only) | the `uat` / `ami-uat-qa` / Galaxy-rig users, flows other than Room | **108**: 36 `one_on_one`, 37 `concierge_floor`, 35 `coach_chat` |

1. **Excluded:** the CR035 `room-benchmark` users; the WP-10 harness rooms — all DeepInfra rows
   and all `ling…fin` rows (2026-11-18); everything created on or after 2026-11-18 in cohort B;
   earlier non-`vllm` providers (kimi, deepinfra, anthropic) in cohort B; Room rows of the UAT
   users (the nightly UAT rooms); rows with null `response_text`.
2. **No user-text coverage of the thin surfaces.** Alpha has almost no organic traffic: cohort A has
   no 1-on-1 and 3 each of Concierge and Brief. Those surfaces are covered only by 108 scripted UAT
   replies. The replay measures false positives on cooperative traffic; it cannot measure how well
   the guard stops a user who tries to extract advice.
3. Cohort A includes the founder's own test devices.

## 3. Hit rates (guard as shipped at `c199e6d6`)

| Rule | A: App (n=671) | B: Harness (n=79,980) | C: UAT non-Room (n=108) |
| --- | --- | --- | --- |
| advice (enforcing) | 0 (0.00%) | 13 rows (0.0163%): 9 `room`, 4 `room_pm` | 0 |
| abuse (enforcing) | 0 | 0 | 0 |
| off_topic (log only) | 0 | 11 rows (0.0138%), all `room` | 0 |
| **Would be withheld in enforce** | **0 / 671** | **13 / 79,980 (0.0163%)** | **0 / 108** |

## 4. Read of every hit (all 13 advice, all 11 off_topic)

1. **advice: 3 true, 10 false.** Precision 23%.
   1. True (3): two "you should / shouldn't buy" addressed to the reader (one CIO narration, one
      bear researcher), and one "this guaranteed return" used to argue for a larger position.
   2. False, "can't / cannot lose" (6): a price level the uptrend "cannot lose", or "the stock can't
      lose that ground". Five different desk roles, same trigger — the 200-day-average idiom.
   3. False, "guaranteed return" (4): the regulated-utility term of art ("guaranteed return on
      rate base"), once in the past tense ("pricing power that once guaranteed returns"), once quoted.
2. **abuse: 0 hits** in 80,759 + 108 rows. Not exercised by cooperative traffic.
3. **off_topic: 11 of 11 are not off-topic.** Each is an analyst note (market, news, fundamentals,
   social) of 1,155–15,556 words; a normal note is a few hundred. They are runaway or looping
   generations that dilute the market-term density below the threshold. The rule is log-only and
   is doing something else: it is a length alarm by accident. S11 WP-13 item 1.3 already proposes
   dropping it.

## 5. Misses

1. **Sample of 50 non-hits** (25 CIO — 24 harness, 1 app — and 25 Concierge — 24 UAT, 1 app), read
   as every sentence containing a second-person word or a recommend / advise / suggest verb: **0
   misses.** The 25 CIO narrations contained no second-person sentence at all. The Concierge
   replies refuse advice in 12 of 25 ("I don't give trading advice", "I won't tell you to buy …");
   those correctly pass.
2. **Looser probe over all 80,746 non-hit rows** (patterns broader than the guard: "you … buy",
   "I'd buy", "consider buying", imperative "Buy now", "I recommend holding", "strong buy", "easy
   money", "your money should"). Reading the samples of each:
   1. No second-person personalised advice found. The "you … buy" family (about 100 rows) is the
      Street/desk voice: "the setup asks you to buy a re-rating", "the Street is not telling you to buy".
   2. About 1,700 CIO rows contain "I would buy X if …" inside the `kill_criterion` field. That is
      the CIO's falsifier, not advice to the user.
   3. **Policy question, not a bug:** about 40 Room debater turns (0.05%) open with an imperative
      ("Buy now to capture …", from the aggressive and neutral debaters). It is the debate voice and
      the design lets "the desk should buy" pass, so the guard does not hit it. Saiful should decide
      whether a bare imperative in a Room turn is acceptable on screen.
   4. Single "consider buying on the pullback" in one CIO narration: soft, borderline.

## 6. Tuning made (CR271)

Both from the false positives above, minimal and deterministic, in
`backend/app/services/output_guard.py`:

1. **"can't / cannot lose"** now needs a promise-shaped subject (you / it / this / that / trade /
   bet / position / investment / stock / setup / play / name) and must end the clause or name money.
   Removes all 6 false hits. Unchanged: "Trust me, you can't lose.", "This trade can't lose money.".
2. **"guaranteed return/profit/gain"**: (a) not after "once / formerly / previously"; (b) skipped
   when rate-base vocabulary (`rate base`, `allowed ROE/return`, `regulated utility/asset/return`)
   is in the same sentence. A promise in a later sentence still hits (tested). Removes 4 false hits.
3. Eleven new cases in `tests/unit/test_cr271_output_guard.py`: 6 false positives as negatives, 5
   guards that the tuning did not loosen (positives).

## 7. After tuning

| Rule | B: Harness (n=79,980) before | after |
| --- | --- | --- |
| advice rows | 13 (0.0163%) | **3 (0.0038%)** — all true |
| abuse rows | 0 | 0 |
| off_topic rows (log only) | 11 | 11 |
| would be withheld | 13 | **3** |

Cohorts A and C: 0 before, 0 after.

## 8. Recommendation

1. **Enforce advice and abuse: yes, once the tuning merges.** After tuning, the guard hits 3 of
   80,759 in-scope rows (0.004%), all true; 0 of the 671 rows that reached app users. A false
   withhold costs a labelled scripted turn, not a verdict.
2. **Caveat Saiful should weigh:** the measurement proves the guard does not fire on normal
   analyst traffic. It does not prove it catches a user who pushes the Concierge or 1-on-1 into
   giving advice — there is no organic 1-on-1 traffic to replay. Before go-live (WP-54) run an
   adversarial pass: 30–50 scripted advice-eliciting prompts through 1-on-1, Concierge and Brief on
   Alpha, in `log` mode, and count the hits.
3. **Leave `off_topic` log-only, or drop it** as S11 proposes. Its 11 hits are runaway-length notes.
   A length sanity cap on analyst notes would be the honest rule; that is a separate item.
4. Decide the bare-imperative policy in §5.2.3 before enforcing, since it changes what the rule
   is meant to catch.

# WP-13 — Enforce replay over all stored Alpha agent text (2026-11-20)

**What this is:** the hit-rate measurement that lets `OUTPUT_GUARD_MODE` become `enforce` on Beta (CR271, CR267 WP-13).
It follows `wp13_guard_replay_2026-11-19.md` (80k rows, advice/abuse/off_topic) and `wp13b_advice_probe_2026-11-19.md`
(40-prompt probe, tuned rules). **Counts, rule names and abstract descriptions only; no stored or model text** (the repo is public).

## 1. Method

1. Read-only. The current `output_guard.py` was copied into `ami_api_alpha` and run against rows streamed from `llm_audit`
   over a connection opened with `default_transaction_read_only=on`; only counts and a local sample file left the container
   (the sample was read, then deleted). Nothing was written to Alpha's database.
2. **Every stored row on the six user-visible flows with a response**: `room`, `room_risk_officer`, `room_pm`, `one_on_one`,
   `concierge_floor`, `coach_chat`. Not scanned: the internal repair/review flows, `price_alert`, `portfolio_health_finding`,
   `translate`, null-flow rows.
3. Surfaces as the live seams use them: `room`/`room_risk_officer` -> `room_turn`, `room_pm` -> `room_verdict`,
   `one_on_one` -> `one_on_one`, `concierge_floor` -> `concierge`, `coach_chat` -> `brief`. On the three direct flows the
   user's own last message is paired with the reply, so `personal_advice` runs as it does live.
4. Mode `enforce`. Raw model response, not the display text (a `room_pm` response also carries the verdict JSON fields), so
   counts are comparable to, not identical with, the live seam.
5. The committed `backend/scripts/output_guard_replay.py` now does the same pairing and includes `room_risk_officer`.

## 2. n

**121,116 rows**, three cohorts (same definitions as the 2026-11-19 replay, applied by SQL):

| Cohort | Definition | n |
| --- | --- | --- |
| A. App | real build, real device, not benchmark/UAT/rig | **907** (512 `room`, 318 `room_pm`, 67 `room_risk_officer`, 5 `coach_chat`, 4 `concierge_floor`, 1 `one_on_one`) |
| H. Harness | user row deleted or no app version: research Rooms on the production prompts, never shown to a user | **108,377** (Room flows only) |
| U. UAT / rig | UAT and Galaxy-rig users, incl. the 40 advice-eliciting probe prompts of WP-13b | **11,832** (164 on the direct flows: 53 `one_on_one`, 54 `concierge_floor`, 57 `coach_chat`) |

Alpha still has almost no organic traffic on the direct surfaces: 10 rows from real app users across all three.

## 3. Hits per rule (after this tuning)

| Rule | A: App (907) | H: Harness (108,377) | U: UAT/rig (11,832) | Total rows |
| --- | --- | --- | --- | --- |
| advice (enforcing) | 0 | 3 (2 `room`, 1 `room_pm`) | 4 (3 `one_on_one`, 1 `coach_chat`) | **7** |
| personal_advice (enforcing) | 0 | 0 | 5 (`one_on_one`) | **5** |
| abuse (enforcing) | 0 | 0 | 0 | **0** |
| runaway_length (trim, not a withhold) | 0 | 59 (56 `room`, 3 `room_pm`) | 0 | **59** |
| **Rows withheld in enforce** | **0 / 907** | **3 / 108,377** (0.0028%) | **7 / 11,832** (all dated the 13b probe day) | **10 / 121,116** (0.0083%) |

Before this tuning (the rules as merged at the start of the day) the same replay withheld **18** rows: advice 10,
personal_advice 9, abuse 1. The 8 removed rows are all false positives, below.

## 4. Hand-check of every enforcing hit

The hit set is small, so this is a census of all 12 hit instances after tuning, not a sample.

1. **True (10).** `advice` 6: second-person "you should / shouldn't" aimed at the reader (1 CIO narration, 1 Brief reply); bare verdicts
   answering a user's question (a "Yes, buy", a lone "Hold.", a YES over a BUY ticket); a "guaranteed return" used to argue for a larger
   position (1 Room desk). `personal_advice` 4: a stance or share-count ticket answering a "should I buy X" question (all `one_on_one`).
2. **Borderline, kept (2).** A `WAIT` ticket sized 0% answering "tell me whether to go long" (a directive on the user's own
   decision, but a refusal to trade); a bear-case parenthetical "(i.e., you should buy)" naming the condition that would
   flip the thesis (generic "you" in a hypothetical, one Room turn).
3. **Clear false positives after tuning: 0 of 12** (10 true, 2 borderline). FP rate on the census: 0 clear, 2 borderline.
4. **The 8 false positives removed today** (found by reading the 18 before-tuning hits):
   1. "not a guaranteed return" / "isn't a guaranteed gain" (a negation; 1 CIO verdict reason).
   2. A refusal quoting the user's own phrase with the comma inside the closing quote (`"guaranteed returns,"`; 1 Brief refusal).
   3. "if you must buy before confirmation, do it at 2.5%" (a conditional, 1 Room debater).
   4. "retard" used as a verb ("accelerate or retard the thesis", 1 News Analyst note): the abuse rule's only hit anywhere.
   5. A ticket cue on "30% portfolio drawdown" in a mandate-cap sentence (1 `one_on_one`).
   6. A ticket cue on a caps `APPROVE` inside "either APPROVE or PASS", in an Arabic refusal (1 `coach_chat`).
   7. A ticket cue on a caps `BELI` inside a quoted example of what the user could type (1 Malay `coach_chat`).
   8. A ticket cue on "BUY atau HOLD/WAIT" listing options (1 Malay `coach_chat`).

## 5. Misses

1. **Personal-ask rows with no hit.** On the 164 direct-flow rows, 35 have a user message that reads as a personal-advice ask
   and no hit. Read in full: **0 are clear advice.** 25 are refusals, "open the Room" deflections or requests for missing
   inputs. 3 are compliance preambles to a jailbreak ("Understood, I will move to advising your real-money portfolio",
   "I will always name the stock that can't lose") that then ask for inputs and give no directive.
2. **Known limit, unchanged:** a reply that steers without a ticket shape or a second-person verb ("the safer move is the
   index fund") passes. The guard is a floor, not a classifier; the 13b probe found 3 such 1-on-1 replies and they remain.
3. **Policy question from 2026-11-19 stays open:** about 40 Room debater turns open with a bare imperative ("Buy now to capture ...").
   The guard does not hit them by design (Saiful, 2026-11-19: the debate voice).

## 6. Rule changes (all in `backend/app/services/output_guard.py`, each with a negative and a still-fires test)

1. `guaranteed return/profit/gain`: not after "not a / not an / not the / not any / isn't a / n't an".
2. "you should / must / need to ...": not after "if / unless / whether / when".
3. Quoted-mention check: the closing quote may follow a `, . ; : ! ?`.
4. Abuse: "retard" no longer matches as a verb or in "retarded by". Still hits "retarded take", "a / such a / utter retard", "you retard.".
5. Ticket cue (`personal_advice`): a caps stance word that is one option of a list (`BUY or HOLD`, `either APPROVE or PASS`, `BUY atau HOLD/WAIT`)
   or sits inside a double-quoted example is not a ticket; "N% portfolio drawdown / loss / decline / volatility" is not an allocation.
6. Tests: `backend/tests/unit/test_cr271_enforce_replay_fixes.py` (synthetic strings; paraphrases only).

## 7. `runaway_length` cap

1. Words per turn, p50 / p95 / p99 / p99.9 / max (all stored rows):

   | Flow, cohort | n | p50 | p95 | p99 | p99.9 | max |
   | --- | --- | --- | --- | --- | --- | --- |
   | `room`, App | 512 | 151 | 278 | 353 | 669 | 669 |
   | `room`, Harness | 63,545 | 192 | 432 | 570 | 1,488 | 18,369 |
   | `room`, UAT | 8,555 | 152 | 321 | 400 | 569 | 1,473 |
   | `room_pm`, App / Harness | 318 / 38,239 | 154 / 185 | 258 / 295 | 307 / 365 | 323 / 577 | 323 / 3,556 |
   | `room_risk_officer`, Harness | 6,572 | 239 | 384 | 437 | 549 | 708 |
   | one_on_one / concierge / coach_chat (all cohorts) | 164 | 39 / 58 / 99 | 274 / 84 / 232 | 359 / 131 / 270 | | 359 / 131 / 270 |

2. Turns over a cap (all Room flows): over 560 words 764; over 1,000 about 103; over 1,500 66; over 1,680 **59**; over 2,000 55. No natural gap.
3. Looping check on the 220 turns over 700 words (share of unique 6-word runs under 0.5): between 700 and 2,000 words only 7 of 165
   are loops; over 2,000, 35 of 55 are. Everything the app cohort ever produced is under 700.
4. **Cap stays 1,680** (about 3x the Room p99 of 570 and above the p99.9 of 1,488). It trims 59 of 121,116 turns (0.049%), none in
   the app cohort, none in the direct surfaces; about 36 of the 59 are loops and the rest are long, unique notes that lose only a tail
   and gain a visible "[AMI trimmed an overlong note]". A tighter cap would start cutting normal long debate turns (97 turns over 1,000).
   Revisit once Beta's model (DeepSeek-V4-Flash) has its own length distribution.

## 8. Enforcement, as built

1. **Setting:** `OUTPUT_GUARD_MODE` (`off | log | enforce`), forwarded in compose (`${OUTPUT_GUARD_MODE:-log}`), listed `[REQUIRED]` in
   `infra/beta.env.example`, now `enforce` there. **Beta boot refuses any other value** (`beta_boot_problems`). Alpha stays `log` until the deploy flips it.
2. **What a hit does, per surface** (every hit logs one `output_guard_hit` event with surface, rule, agent, run id and an 80-character span, never the text):
   1. Room desk turn: replaced by the scripted standing-guidance turn, recorded in `scripted_turns`, which DEF507 marks as scripted on the stream, the stored
      transcript and the replays. It is never shown as that desk's own call.
   2. CIO narration and verdict reason: replaced by "AMI withheld this explanation because ..."; the deterministic action and sizing are untouched.
   3. 1-on-1 and Concierge: the endpoint buffers the whole reply; the SSE frame, the stored message and the Journal entry all carry "AMI withheld this reply ...".
   4. **Brief (changed in this WP):** in `enforce` mode the reply is now held until the guard has judged it, then sent once, either as the text or as the
      "AMI withheld this reply ..." sentinel. Before, Brief streamed live and could only append a retraction line after the advice was on screen
      (the old `retraction_notice` is deleted). `log` and `off` still stream live.
3. Sentinels name AMI, never "the AI". Cost: Brief shows its reply in one piece instead of token by token while `enforce` is on.

## 9. DEF511 (same lane)

`ANDROID_PLAY_STORE_URL` (default = today's personal Play URL, so Alpha is unchanged) replaces the hard-coded constant behind the forced-update screen.
Forwarded in compose, `[REQUIRED]` in `infra/beta.env.example` (example value = the WP-49 proposed package `ai.agenticmarketintel.trade`, confirm when the listing
exists), and Beta boot refuses it empty or naming the personal package.

## 10. Recommendation

1. Enforce on Beta: yes. 10 of 121,116 rows would be withheld, all of them either true or borderline, none from a real app user.
2. Flip Alpha to `enforce` at the next deploy: same rules, but Alpha's direct surfaces have 10 organic rows, so the measurement says "no false positives on cooperative
   traffic", not "catches a determined user".
3. After 2-3 weeks of Beta, replay Beta's own `llm_audit` (the script is ready) before trusting the rules on a new model.

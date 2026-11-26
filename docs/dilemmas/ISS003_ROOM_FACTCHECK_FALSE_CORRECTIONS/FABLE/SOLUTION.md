# ISS003 — FABLE (claude-fable-5-2) solution

**Independence:** no other contributor folder existed when I worked (the ISS003 folder held only the brief, the invite and the state file). I read none.

**One thing outside the invite's letter:** the invite says this machine cannot run the app. I did not run it, but I did read Alpha: one read-only `SELECT` over `room_runs`, `room_fact_sheets` and `mandates` via `ssh melehost`, exported to a scratch folder outside the repo. No writes. Every population number below comes from replaying that export offline. The export is not committed (real Room text, public repo); the query is in `prototype/replay.py`.

---

## 0. The short version

1. **The brief's framing is wrong in one place, and it matters.** The check was built to stop desks altering sheet figures. Measured on 369 stored Rooms, desks almost never do that: 94–97% of the figures in desk prose are figures the sheet shows. What the checker actually fires on is correct figures that sit near a label for a different field.
2. **Today's checker is wrong about 99% of the time, not occasionally.** 625 firings across 369 Rooms; 2 are real misquotes (both dropped minus signs, in one turn). 581 of the 625 (93%) "correct" a figure that is itself on the fact sheet.
3. **Proposal: stop asking "which field did the desk mean, and is it wrong?" Ask "is this a number the desk was shown?"** The second question needs no reading of meaning. AMI then says one kind of sentence only: *these figures are not on the fact sheet; they are the desk's own calculation or estimate.* It never says what a figure "should" be.
4. **A false correction becomes impossible, not rarer**: no code path produces a sentence of the form "the sheet says Y, not X".
5. **The price:** an altered figure is exposed about 79% of the time, not 100%, and two kinds of error are not caught at all (a dropped minus sign; the right number under the wrong label). Section 6 has the numbers.

---

## 1. What I measured first (nobody had)

The brief says no population measurement exists. It does now. Corpus: every completed Room on Alpha with a stored frozen sheet, 2026-11-20 to 2026-11-26.

| | US | Bursa | Total |
|---|---|---|---|
| Rooms | 139 (12 tickers; MSFT 50, AAPL 48, KO 24) | 230 (206 tickers) | 369 |
| Desk turns | 1,667 | 2,759 | 4,426 |
| **Today's checker (post fix 2), replayed** | | | |
| Firings | 370 | 255 | 625 |
| Rooms with at least one firing | 128 (92%) | 151 (66%) | 279 (76%) |
| Firings where the "wrong" figure is itself on the sheet | 350 | 231 | 581 (93%) |
| Notes users were actually shown (stored in transcripts) | 555 | 1,082 | 1,637 |
| Risk Officer "[AMI: unverifiable]" tags stored | 220 | 402 | 622 |
| ...of which every figure in the tagged quote is on the sheet | 209 | 388 | 597 (96%) |

Hand adjudication of the 625 firings (one adjudicator, me, not blind): I read about 120 of them — all 50 whose figure was not on the sheet, all 35 that differed from the bound field only in sign or scale, and 45 at random.

1. Real misquotes: **2** — "TTM free cash flow is RM9M" and "1% TTM revenue growth" where the sheet has −9 and −1 (0388.KL, CIO turn, same paragraph).
2. Unresolved: 1 (a GOOGL 52-week low, context cut off).
3. Everything else read was a correct figure. The classes, by size: another sheet field's value next to this field's label (EV/EBITDA beside "P/E", SBC-adjusted FCF, capex, net cash, peer median); sign given in words ("RM148M negative", "FCF burn"); truncation rather than rounding ("$59.9B" for 59,957M — 18 firings on MSFT alone); the desk's own arithmetic ("29% premium", "1.7x the ATR"); a bullet dash read as a minus.
4. From the random 45: 1 true. So precision is about 0.5% by count, and under 12% at 95% confidence from the random sample alone.

Two consequences for the framing:

1. **CR038 did not measure this.** CR038 measured desks asserting *synthetic inputs* (macro/Fed scaffolding) as real, 70% unhedged. That is a problem of inputs that should not have been on the sheet. The prose checker came from an audit gap (CR219 R59-F1, "nothing checks restated figures"), with no measured rate of misquotes behind it. The measured rate, in the 14 fields the checker covers, is 2 misquotes in 369 Rooms, both in one Room.
2. **A checker that fires in 76% of Rooms is announcing its own fault.** No plausible error rate for the desks is that high. Firing rate per Room is a free canary and was never watched.

So three rounds of fixes were tuning a detector whose target is roughly 300 times rarer than its false alarms. No rule set closes that gap; the next fix would have been round 4 of the same thing.

---

## 2. The proposal

### 2.1 Mechanism

1. **Ledger.** For each desk turn, collect every numeral in the text the code itself gave that desk: the rendered sheet block, the mandate and portfolio blocks, the news/social feed block, coded sizing lines. Build it from the assembled prompt in `room_prompts.build_room_messages` / `build_risk_officer_messages` (everything except the transcript-so-far and the static instructions), so a block cannot be forgotten. Earlier turns go in as a separate source ("from the debate").
2. **Same extractor on both sides.** The function that reads numerals out of desk prose is the one that reads them out of the ledger text. A quirk in it (how "11.5x" or "RM15,433M" parses) lands on both sides and cancels. Today's checker compares prose text against raw profile values through 14 hand-written field specs; that asymmetry is where rounds 1 and 2 came from.
3. **Match by value only.** A prose figure is a *figure of record* if some ledger figure equals it at the prose figure's own precision, by rounding or truncation, ignoring sign, with one unit rule: a percentage never matches an amount. No labels, no windows, no field specs.
4. **Three outcomes per figure:** `record` (in the ledger), `derived` (a one-step calculation from two figures in the same sentence: ratio, premium, difference, percentage-of), `own` (neither). Years, periods, "ATR(14)", "52-week", list markers and bare small integers are not figures. Figures on the Execution Desk's Entry/Stop/Target lines are decisions, not claims.
5. **One user-visible sentence**, appended to a turn that has `own` figures:

   > [AMI: not on the fact sheet — 29%, 2.4x. These are this desk's own calculation or estimate, not figures of record.]

   It lists the desk's own text. It never contains a sheet value. A turn with none gets no note.
6. **Structured surfaces** use the same function:
   1. Risk Officer `key_number` / `decisive_number`: verified if every figure in it is `record`. If not, it is not promoted to the headline (today's demotion, kept) and carries the note above instead of "[AMI: unverifiable]".
   2. Stance headline: nulled if it carries an `own` figure (today it is nulled on a label mismatch).
   3. CIO kill criterion: same note.
7. **Phase 2 (mobile, optional, where the teaching value is):** the server already has a span and a ledger label for every figure. Send them with the turn; the app underlines figures of record and shows the sheet line on tap ("Fact sheet: FCF −RM15,433M (TTM)"). The learner sees where each number came from, which is the habit the product is trying to teach. Phase 1 needs no client change.

Prototype: [`prototype/grounding.py`](prototype/grounding.py), 269 lines, stdlib only, no new dependency.

### 2.2 Prevent, detect, or make impossible?

1. *A correct figure called wrong:* **impossible.** The sentence type is gone. `test_no_sentence_ever_states_a_sheet_value` pins it.
2. *A figure of record called "not on the fact sheet":* **possible, prevented by construction where it can be, detected otherwise.** It happens if the ledger misses a block (prevented: built from the real prompt) or a number is written in a form the extractor does not read ("fifteen billion"). This is the new failure mode. It is milder than the old one — AMI points at a number, it does not supply a wrong replacement — but it is still a false statement, and section 2.3 gives it a budget.

### 2.3 The rate I would accept, and how it is measured

1. **"Correct figure is wrong":** zero, structurally. Not a rate.
2. **"Figure of record listed as not on the sheet":** at most 1 in 100 listed figures, and at most 1 Room in 50 containing one.
3. **Gate before any market is switched on:** replay at least 300 Rooms for that market, adjudicate 300 listed figures drawn at random, pass on 0 or 1 false (95% upper bound 1.0% / 1.6%). US and Bursa gated separately, each with its own switch.
4. **Who adjudicates:** a person or an agent reads each listed figure against that turn's stored prompt. The question is mechanical ("is this number in the prompt?"), which is why one pass is enough; "what did the desk mean?" never comes up.
5. **Where this stands today:** in my replay the prototype lists 897 figures over 369 Rooms (US median 3 per Room, p90 7; Bursa median 2, p90 4). I read 120 at random:

   | Class | n of 120 |
   |---|---|
   | Desk's own arithmetic ("79% above the median", "0.11% drawdown contribution") | 42 |
   | Mandate / portfolio figures ("3.0% cap ($300)", "RM50,000 cash", "30% drawdown") | 30 |
   | Desk-specific sheet lines I could not rebuild offline (daily dollar volume, float %) | 14 |
   | Thresholds and falsifiers ("if FCF conversion recovers above 60%") | 11 |
   | News feed figures ("$3M salary", "$55M equity target") | 11 |
   | Desk's own levels (a stop, a target) | 8 |
   | Parse artefacts ("FY2023/22", "Oct 26–28") | 2 |
   | Nonsense ("$300k in a $10k portfolio") | 2 |

   55 of the 120 (mandate, feed, desk-specific lines) are figures the desk was shown but my offline ledger lacked: I had the frozen sheet, not the stored prompt. **So the gate is not passed yet, and I am not claiming it is.** With the ledger built from the real prompt those 55 should become `record`, leaving about 1.3 listed figures per Room. That is the first thing the implementation CR must replay, on melehost where the prompt can be rebuilt.
6. Of the 65 that would remain, none was a sheet figure in an unread form; 2 were parse noise (true but silly to list). 0 of 65 gives a 95% upper bound of 4.6%, which is not yet inside the 1% budget. The sample has to be bigger; that is what the 300 is for.

---

## 3. What happens to a fabricated or altered figure

1. **Invented figure** (not on the sheet, not derivable): listed in the note, in whatever desk, about whatever field. Today's checker sees it only if it sits beside one of 14 labels.
2. **Altered figure:** listed unless the altered value happens to equal some other ledger figure. I measured that directly: take a figure a desk quoted correctly, change it by 3–60% at the same precision, test it against its own Room's sheet (19,384 trials).

   | Figure type | Still matches by chance |
   |---|---|
   | All | 21% |
   | Whole-number percentage ("25%") | 54% |
   | One-decimal percentage ("12.4%") | 22% |
   | One-decimal multiple ("11.5x") | 9% |
   | Amount, two decimals ("$18.22") | 7% |
   | Amount, whole units ("RM15,433M") | 15% |

   A sheet carries a median of 121 distinct figures, so round numbers collide. **Protection is about 79% overall and poor for whole-number percentages.** The phase 2 tap-through softens this (the tap shows what the number matched), but I am not counting that as a control.
3. **Compared with today:** the old checker's measured yield is 2 real catches in 369 Rooms at a cost of 623 false corrections, and its two catches are both of a kind (dropped sign) that my design misses. On misquotes inside those 14 fields I am weaker by exactly that: roughly 1 real catch per 180 Rooms given up. On everything else — invented figures, figures from the rest of the sheet, the Risk Officer's quoted numbers — coverage goes from none to about 79%.
4. **What stays untouched:** the deterministic CIO compliance check, the trade-geometry check and the R:R recompute. Those compute from structured values and are not part of this problem.
5. **The CR038 class proper** (inputs that should not be asserted as real) is still solved at source, as CR038 itself concluded: do not put it on the sheet.

---

## 4. Fewer sheet fields, and figures that are not sheet figures

1. **Bursa.** Nothing is per-field, so nothing changes. A thinner sheet means a smaller ledger, which means fewer chance matches and more arithmetic listed. Measured: Bursa 96.5% of figures are figures of record, US 94.3%. Today's failure on thin sheets (a label binding to the only nearby field) cannot occur because labels are not read.
2. **Mandate cap** (round 3, case 1): in the ledger as a mandate figure. `record`, source `mandate`.
3. **Multiple of a sheet figure** ("1.0x ATR(14) (RM0.145)"): RM0.145 is `record`. "1.0x" is the desk's own multiplier and is listed as such — true, slightly noisy. It is never "corrected" to 0.145.
4. **Sign in words** ("RM15,433M negative"): `record`. Sign is not compared.
5. **Average of the sheet's own history** ("RM5,273M"): listed as the desk's own calculation. True. Better still, add the line to the sheet (next point).
6. **Figure from the debate:** matched against earlier turns, source `debate`, not re-listed. An invented figure is listed once, where it first appears.
7. **New sheet field:** zero checker work. Add a line to the renderer and it is in the ledger. This is also the cheap way to shrink the `own` set: the commonest desk arithmetic in the sample (premium to historical median, distance to the 52-week low, net debt over market cap, position value at the cap) can be precomputed on the sheet, and each line added turns a class of `own` into `record`.

---

## 5. Verification

### 5.1 What a reviewer can run now

1. `python3 -m pytest docs/dilemmas/ISS003_ROOM_FACTCHECK_FALSE_CORRECTIONS/FABLE/prototype/test_brief_cases.py -q` — 16 tests, under a second, no app imports. Every false correction from rounds 1–3 is there, plus invented and altered figures, plus three tests named `test_MISS_*` that pin what the design does not catch.
2. `prototype/replay.py` — export with the query in its docstring, run from `backend/`. Prints every number in sections 1–3 for both the old checker and the prototype, and writes the findings for adjudication. 12 seconds for 369 Rooms.
3. Not reproducible by a reviewer without redoing it: my hand adjudication. The files it was done on (`old_findings.json`, `own_figures.json`) are regenerated by the replay; the sample seeds are not in the script.

### 5.2 How the next unseen phrasing is caught before users

Honest answer: not always, but the design changes what "unseen phrasing" can do.

1. **Phrasing about meaning cannot break it.** Sign words, forward vs trailing, averages, multiples-of, mandate figures — every round 1–3 class was a misreading of what a number referred to. That reading is no longer done.
2. **Phrasing of the number itself can.** "15.4 billion", "RM15.4bil", "15,4 bilion" are read; "fifteen billion", Arabic-Indic digits and "1.2 lakh" are not. Consequence: a figure of record gets listed. Guards:
   1. *Golden diff on the corpus.* The replay output (run, turn, listed figure) is stored as an adjudicated golden file. A change to the extractor, the prompt blocks or the sheet renderer re-runs it; any newly listed figure fails the check until someone adjudicates it. The corpus grows every night, so the phrasing desks actually use reaches the gate before a deploy does.
   2. *Round-trip test.* For every ledger figure on every corpus sheet, render it in each supported surface form inside a carrier sentence and assert it matches. Catches extractor regressions; does not discover new forms.
   3. *Shadow first.* `ROOM_FACTCHECK_NOTES` gains a third value. A market runs log-only until its gate (2.3) passes. AR and MS locales are separate gates; do not switch them on off the EN result.
3. **Per-turn breaker.** More than 6 listed figures in one turn is not a desk doing arithmetic, it is the extractor or the ledger failing. The note is replaced by "[AMI: figure check unavailable for this turn.]" and `room_provenance_breaker` is logged at error level. In the replay the worst whole Room had 11 listed figures across all its turns, so 6 in one turn is far outside normal.

### 5.3 Regression in production

1. One log event per turn (`room_figure_provenance`): counts by outcome, the listed figures, ledger size, breaker state.
2. Nightly replay of the last 24 hours on melehost, compared with bands taken from this corpus: share of figures of record below 90%, or median listed figures per Room above twice baseline, files a Defect through the existing bug-monitor path.
3. Firing rate per Room is on the same report. Had it existed, "76% of Rooms" would have been visible on day one.
4. A user can already report a turn; a note the user disputes arrives through `bug_reports` as today.

---

## 6. What this misses

1. **Dropped or flipped sign.** "FCF yield is 12.6%" for −12.6% passes. This is the only real error today's checker demonstrably caught (2 in 369 Rooms). I looked at catching it without inference and could not: on this corpus, of the 35 firings that differed from the sheet only in sign or scale, 33 were correct figures (sign given in words, truncation, or a bullet dash read as a minus). A "sign candidate" signal can be logged and put through the same gate later; it should not be shown on my say-so.
2. **Right number, wrong label.** "Trailing P/E is 11.1x" when 11.1x is the forward multiple passes. In the random sample of the old checker's firings — which is exactly the population where this would show — I found none in 38, so it is under about 8% of those firings; I cannot bound it tighter.
3. **Chance matches.** 21% of altered figures, 54% of whole-number percentages (section 3).
4. **Wrong arithmetic.** "A 410% premium" for 39.4x against 9.6x (it is 310%) is listed as the desk's own calculation, not flagged as wrong. Checking it means deciding which two figures the desk combined — the inference this proposal removes.
5. **Claims without numbers.** "Margins are expanding" when they are not. Never in scope, still not.
6. **Numbers written in words or other scripts**, until the extractor learns them. These fail the other way (a real sheet figure listed).
7. **Things that look like figures.** "Next 12M" (twelve months) is read as 12 million and listed. True, pointless.
8. **My measurement itself.** One adjudicator, not blind. One week of Rooms. US is three tickers for 88% of its Rooms. The ledger in the replay is an approximation, and half the prototype's listed figures trace to that. The 1% budget is a target with a test attached, not a result.

---

## 7. Cost, and what happens when it is wrong

1. **Latency:** under 3 ms per turn (12 s for 4,426 turns including the old checker and the sheet render). **Model calls:** none. **Dependencies:** none.
2. **Build:** backend only for phase 1. Ledger hook in `build_room_messages` and `build_risk_officer_messages`; swap the `annotate_sheet_mismatches` call in `room_runner._compute_agent_text` and the kill-criterion call; swap `risk_officer._quotation_check`; setting plus compose forwarding (the parity test enforces it); log event; replay script and golden file on melehost. About two days for one worker plus the adjudication pass. Phase 2 is a mobile CR of its own.
3. **Per new sheet field:** nothing.
4. **Code removed:** `_FIELD_SPECS`, the label windows, qualifier and exclusion patterns and sign rescue in `numeric_quotation.py` — roughly 700 of its 1,162 lines — after a month of running the old checker log-only beside the new one for comparison.
5. **When the control is wrong:**
   1. Ledger cannot be built, or the breaker trips: the user sees "[AMI: figure check unavailable for this turn.]" and an error is logged. Loud both ways.
   2. Extractor misses a surface form: a figure of record is listed. Visible to the user, mild, caught by the nightly band if it is systematic, by the golden diff if it is in the corpus.
   3. Chance match: an altered figure is not listed. **Silent.** This is the residual I cannot make loud, and it is quantified in section 3.
6. **House rules:** nothing depends on a prompt instruction. The note is in AMI's name. No model is involved, so the on-prem rule is moot.

---

## 8. What I rejected

1. **More rules on the current matcher.** Three rounds, 0.5% precision, 14 fields out of a sheet that carries a median of 121 distinct figures. The space of ways to say what a number refers to is open; the space of ways to write the number is small.
2. **A model as judge of each finding.** Prompt-shaped, on a refusal-stripped model, one more call per finding on a pipeline that already runs minutes. Usable only as a suppressor, and what it would suppress is 99% of the input.
3. **Desks cite sheet fields by token and the code prints the number.** The only design that makes misquotation itself impossible. Rejected for now on the evidence: desks already copy faithfully 94–97% of the time, compliance with a citation syntax cannot be measured from here, and it changes streaming and every desk prompt. Worth revisiting only if a later measurement shows misquotes matter.
4. **Delete the check and show nothing.** Defensible on the numbers (2 real misquotes in 369 Rooms). Provenance costs 3 ms, covers invented figures the old check never saw, and its phase 2 is a teaching feature in its own right, so I would keep it.
5. **Soften the wording of today's note** ("for reference, the sheet shows..."). Still fires in 76% of Rooms on the same wrong pairings; the learner still reads it as a correction.

---

## 9. One recommendation that does not depend on choosing this proposal

Whatever wins, adopt the gate: **no sentence in AMI's voice that judges a desk's figure ships until it has been replayed over at least 300 stored Rooms per market and a sample of its firings adjudicated.** The export and replay took under an hour and would have stopped this at round 0.

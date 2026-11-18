# CR267 — Questions for the plan's author (pre-execution read)

**What this is:** questions from the executing agent (Opus) to the Fable session that wrote
`CR267_beta_programme.md`, raised on a read-through for execution, starting at WP-00. Nothing has
been executed. **Why:** some steps contradict the repo as it stands on 2026-11-18, and some leave
out values an executor would otherwise have to invent. Each question cites what was checked.

Legend: **[B]** blocks the WP as written · **[C]** clarification; the executor will take the stated
default if no answer comes.

---

## A. Programme-level

1. **[B] Does WP-54 go ahead if WP-26 fails?** WP-26's acceptance is "a file with a single PASS or
   FAIL", so a FAIL still counts as `done` and satisfies WP-54's dependency. But WP-53 line 3 ("WP-26
   gates still hold") would then be red for the whole Beta, and the Beta could never meet its exit
   criteria. Is the intent "ship Beta with the Room labelled experimental", or "Beta waits for Room
   Lite to pass"?
2. **[B] Room Lite needs "Saiful's go" but is not a gate in §4.** Add it as S10, or is it covered
   by an existing gate?
3. **[C] WP-54's dependency list leaves out WP-12 (budget cap), WP-13 (output guard), WP-28,
   WP-29, WP-45 (Beta URL in builds) and WP-51.** WP-12 and WP-13 look like hard prerequisites for
   external testers, and WP-45 is needed for any Beta build to reach the Beta host at all. Is leaving
   them out deliberate? Default: add WP-12, WP-13 and WP-45 to WP-54.
4. **[C] Commit tag.** The plan's own commit uses `(AT:R CR267)` with no round number. What
   `AT:<track><N>` should the executing session use: a new track letter for this programme, or R
   with a number?
5. **[C] Session-start routines vs S0/S1.** CLAUDE.md step 2 runs `/daily-cr-def-review` (last run
   2026-10-27) and step 2b runs `/bug-monitor` (last cycle 2026-10-20) at the start of any session.
   The first executing session will therefore run both before WP-00. Does that session-start review
   count as WP-01/S1, or should the executor skip it until WP-00 has fixed the registers?
6. **[C] Is track K (Kimi) still active?** The last commits before CR267 are `AT:K4 CR266`
   (2026-10-30), with a 60-room matrix left running. WP-00 marks CR266 as superseded and treats K's
   untracked files as leftovers. Is K closed, or does someone need to tell it?

## B. WP-00 Re-entry

7. **[B] Where does the CR266 run's output live?** Step 1 says the harness output folder is "named
   in `CR266_decision_reliability/progress.md`". It isn't. The file names only `~/cr266_smoke/ling/`
   and the Claude background-task IDs `bash-8x2ggogr` / `bash-uf7qb557` ("corrected 60-room matrix
   now running"), which are not paths on melehost. Do you know the melehost path or the harness
   output root?
8. **[B] Which CR253?** Two folders carry the ID: `CR253_risk_disposition_communication/` (the one
   the row points to) and `CR253_data_lane_completeness/` (no row). The deleted file
   `CR253_tm_all_salvage_conversion/…md` is the pre-re-mint copy of CR254, whose row says "re-minted
   from CR253". The deletion therefore looks intentional, not accidental. Do you agree it should be
   committed as a deletion? And should `CR253_data_lane_completeness` get a fresh ID now?
9. **[B] Status vocabulary.** `gen_registers.py` allows only
   `proposed | in_progress | done | dropped | standing` for CRs. There is no `superseded`. Should
   "superseded by CR267" be written as `dropped` with the reason in the row text?
10. **[C] The "six stale rows" list does not match the registry.** Current statuses: CR252, CR253,
    CR255, CR256, CR257 and CR259 are `proposed`; CR251, CR254, CR260, CR265 and CR266 are
    `in_progress`. Specifically:
    1. CR256 shipped code behind a flag (`room_evidence_gate_thresholds_json` is in `config.py`).
       Is that `done`, or `dropped` because WP-23 replaces it?
    2. CR254 (tm-all salvage, "mandates are data") is not an approval-curve CR. Why is it on the
       superseded list?
    3. CR260 is re-scoped by WP-21. Should WP-00 rewrite its row to the new scope, or leave that to
       WP-21?
    4. CR258 (company account migration) is `proposed`, yet D-073's 2026-10-13 update says
       "executing now". Should WP-00 fix that row too?
11. **[B] Should the untracked memos be committed to a public repo?** `origin` is PUBLIC (checked
    with `gh`). Step 5 says "commit what is real", which includes 7 track-K checkpoint memos and 1
    auto-snapshot. A pattern scan found no keys in them. But DEF178 started exactly this way (a live
    key in a committed memo), and RES008 policy is to scrub before every commit. Commit them after a
    manual scrub, or move them somewhere git-ignored?
12. **[C] Decision log scope.** The next free number is D-076. Step 3 reopens D-066/D-067 and
    closes D-068, but it misses two more:
    1. **D-072** says Beta launches "on the current melehost Alpha stack". Decision 1 (a newly
       allocated Beta host) reverses that.
    2. **D-073** (company accounts "at the end") — decision 1 is consistent with it, but the plan
       has no WP for the CR258 migration itself (see Q38).
    Should D-072 be marked amended as well?
13. **[C] The acceptance line "`git status --short` is empty" can't be guaranteed on a shared
    checkout.** Another track can dirty the tree at any time (a new untracked memo,
    `20261118T111900Z_f2ac2318…md`, appeared during this read). Default: scope the check to paths
    WP-00 owns, and list anything else that is dirty.

## C. Phase 1 — Hosted LLM

14. **[B] Where is the DeepInfra key, and who places it?** The executor needs it on melehost (for
    the harness and Alpha) and must not paste it into a public commit. Is it already in melehost's
    `.env`, or does Saiful hand it over? Is there a spending limit on the DeepInfra account for the
    WP-10/WP-20/WP-26 runs? Rough arithmetic, not measured: 360 rooms for WP-10, 300 for WP-20 and
    300 for WP-26, at 5¢ a room, comes to about $50.
15. **[B] Which temperature?** WP-10 says "temperature pinned" and WP-11 pins production, but
    neither gives a value. WP-22 uses 0 for the judge. What should the desks use, and should WP-10
    test more than one value?
16. **[C] Does the V2 harness pass `VLLM_API_KEY`?** The gateway does (`llm_gateway.py:1007`), but
    the harness has its own config. If the harness drops the key, the "config only" claim is false
    for the harness.
17. **[B] The on-prem fallback conflicts with two other decisions.**
    1. The gateway has one `vllm` slot. Keeping DeepInfra *and* on-prem means a second
       OpenAI-compatible slot, which is a code change. Decision 3 says configuration only.
    2. The on-prem serve is the **abliterated** Qwen3.8 build, and WP-10 deliberately shortlists only
       non-abliterated models. Should a refusal-stripped model be the fallback for user-facing
       Rooms?
    3. Degrade loudly: is a labelled fallback to a different model acceptable, or should a hosted
       outage end the Room in "unavailable", as WP-23 does for the grader?
18. **[C] WP-24's room key doesn't include the model.** A Room produced by the fallback model would
    be banked and replayed as if it came from the hosted model. Should the key include the model
    `root`?
19. **[B] What is the daily spend ceiling in WP-12?** No figure is given. Also, DEF186 is `fixed`,
    so what exactly is "left over" from it: only the one-Room-in-flight limit?
20. **[C] Does WP-13's week of Alpha traffic mean calendar time?** If so, the enforcement switch
    waits at least 7 days after deploy, and WP-13 sits on the launch path (see Q3). Is there enough
    Alpha traffic to measure a hit rate at all? Default: also replay the stored agent text from
    `llm_audit`.
21. **[C] WP-02 is not "a handful of files".** `alpha-2026-10-19-1..HEAD` changes 6 files in
    `backend/app`, about 1,150 lines added, including `room_runner.py` +547. That is CR266's
    structural work. Promoting ships it to Alpha before WP-00 decides CR266's fate. Is all of it
    flag-guarded and off by default? Is promoting it intended?

## D. Phase 2 — The Room

22. **[B] Does WP-20 run blind?** WP-22 scores graders against consensus on WP-20 rooms. But WP-20
    runs before WP-21 removes consensus from the fact sheet, so the desks in those rooms *saw* the
    Street rating. Consensus agreement measured on those rooms is contaminated. Should WP-20 wait
    for WP-21, or run with consensus stripped in the harness?
23. **[B] Which universe for consensus scoring?** WP-22.3.1 uses `tickers_150.txt` (CR035) and
    `room_benchmark.py`, but the WP-20 rooms are the 30-ticker CR228 universe. Should the consensus
    metrics be computed on the 30 tickers only, or does WP-20 also need a 150-ticker run?
24. **[B] Are cards on in WP-20?** "Production settings" means cards OFF, but the plain-code grader
    in WP-22 runs over CR266 typed cards. CR266's control had complete cards in only 43 of 60 rooms.
    Should WP-20 run with cards ON, and how should the code grader handle rooms with missing cells?
25. **[C] Does DeepInfra return token probabilities?** WP-22 assumes the hosted judge returns
    logprobs. If the chosen model doesn't, is a constrained answer without probabilities acceptable?
26. **[B] Doesn't fitting on consensus make WP-26 circular?** WP-23 fits the rule's weights and
    bands on WP-20 rooms. If the fitting target is consensus agreement, then WP-26's gate
    ("consensus scores ≥ CIO baseline") is close to circular, even on fresh rooms. What is the
    fitting target, and is consensus held out from it?
27. **[B] Can testers see the Street rating?** WP-21 step 3 puts the Street comparison on the
    verdict card. Step 4 says consensus is "labelled internal-evaluation-only until a licensed source
    exists" (yfinance; licensed data is backlog item CR007). Do Beta testers see it or not?
28. **[C] Is the banked room per user or shared?** WP-24 keys on (ticker, mandate snapshot,
    fact-sheet hash, policy version). Two users with identical mandates would hit the same key. Can
    one user be served a room another user paid for? Default: include `user_id` in the key.
29. **[C] What does "consistency" add on a new day?** Each trading day gives a new fact-sheet hash,
    so a new room, so the fresh-run flip rate shows up as day-to-day flips with an explainer citing
    "price changed". Is that the intended reading of decision 5, or should small input changes reuse
    the banked room?
30. **[C] WP-25 needs typed claims.** "Which desk claims changed" requires CR266 typed claims to be
    on. Should cards be ON in production after WP-26, or does the explainer work without them?
31. **[C] What counts as a holdout approval?** WP-26 says "zero holdout approvals (the RIOT / APD /
    BA shapes from CR257)". Is there a computable definition in CR257 §7–8, and are those tickers
    inside the 30-ticker universe or run separately?

## E. Phase 3 — App fixes

32. **[B] Does S6 contradict §7?** S6 needs counsel's ruling before WP-30 reaches testers, and
    WP-54 depends on WP-30. But §7 lists "counsel review of the legal documents" as backlog. Is a
    narrow counsel question (archive vs delete only) in scope for Beta, and who books it?
33. **[B] Will closure-with-archive pass store review?** Apple's guideline 5.1.1(v) requires
    in-app account *deletion*, and Play's Data Safety form requires a deletion path. Has
    "close + archive" been checked against either for Beta App Review and Play closed testing? This
    could fail WP-50 regardless of counsel.
34. **[C] Do current Alpha users need the 18+ confirmation?** WP-31 adds it to onboarding. Default:
    no; Beta starts with an empty database (WP-41).
35. **[C] Open defects outside every batch.** There are 44 open defects; the WP-27/33/34/35 batches
    name about 25. Unassigned ones include DEF469 (a real tester report, Android), DEF470, DEF481,
    DEF482 and DEF485. Default: WP-01 decides each one.
36. **[C] Is there a free-credits mode and a locale lock?** WP-36 assumes both can be switched
    per build or per environment. Do they exist, or is each a new setting? New settings fall under
    the compose-parity test.

## F. Phase 4–5 — Infra and launch

37. **[C] How big is the cohort for load testing?** WP-46 loads at "invited-cohort size", and the
    cohort is 20–200. Default: 200 testers with 10 concurrent Rooms. That also needs DeepInfra's
    rate limits checked.
38. **[B] Where is the company-account migration?** WP-50 assumes app records exist under the
    company accounts, but CR258 is `proposed` and no WP covers it: bundle IDs, signing, Sign in with
    Apple keys, OneSignal, RevenueCat. Is it a hidden WP, or part of S7?
39. **[B] Where do WP-53's numbers come from?**
    1. Crash-free sessions: is that Sentry release health? `sentry_flutter` is in `pubspec.yaml`,
       but is a DSN set for release builds?
    2. Day-7 retention: there is no analytics SDK, and §7 lists analytics as backlog. Should
       retention be computed from backend session rows instead?
40. **[C] Does Play's 12-testers rule apply?** WP-54's "12 testers for 14 days" applies to *new
    personal* developer accounts. If the company Play account is an organisation account, the rule
    may not apply. Is it still wanted as a soft target?
41. **[C] Does Singapore hosting need PDPA wording before launch?** The planning record (item 11)
    flags Singapore hosting as a cross-border transfer under Malaysia's PDPA, for the privacy policy
    and counsel's list. No WP carries it. Default: add the wording to the WP-30 policy edits.

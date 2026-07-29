# Daily CR/Defect open-items review log

Append-only ledger written by `/daily-cr-def-review` (CR085). One writer only — the
daily routine — so this is a plain running file, not one-per-item like the CR/Defect
registers (that split exists to avoid concurrent-write sweeps; a single writer has no
sweep risk, see CR081).

One `## YYYY-MM-DD` section per day. Within a section, one line per item asked:

```
- **CR014** (proposed since 2026-07-10) — asked: "Start now / keep deferring / drop it?"
  → Saiful: "start it, assign to coder.mobile"
```

Follow-up context (checked at the *start* of the next run, before re-asking) is appended
to that day's section as a second line under the same item, not as an edit to history:

```
- **CR014** — follow-up: still `proposed`, no commit tagged CR014 since 07-25 → re-asked
```

Nothing here changes a CR/Defect's actual status — that only happens through the normal
governance flow (a domain owner's row-file edit + `gen_registers.py`). This log records
what Saiful said and whether it happened; it is not itself a source of truth for status.

---

## 2026-07-24

First run — no prior entries to follow up on. All 23 proposed CRs + 4 open Defects
asked live in-conversation (not via the `/schedule` cloud routine — see note at bottom).

- **CR002** (proposed since 2026-07-06, reconcile `bug_reports` status vocabulary) — asked: "Start now / keep deferring / drop it?" → Saiful: "Keep deferring"
- **CR006** (proposed since 2026-07-09, Beta infra cost research) — asked: same → Saiful: "Keep deferring"
- **CR007** (proposed since 2026-07-09, agent data/news provider research) — asked: same → Saiful: "Closed. This is down" (read as: already done)
- **CR008** (proposed since 2026-07-09, Room token estimation + prompt caching) — asked: same → Saiful: "Closed. Done"
- **CR017** (proposed since 2026-07-10, multi-provider LLM routing + caching) — asked: same → Saiful: "Keep deferring"
- **CR019** (proposed since 2026-07-12, Concierge lesson retrieval — embedding mode) — asked: same → Saiful: "Closed. Done"
- **CR020** (proposed since 2026-07-12, Concierge lesson context — full context mode) — asked: same → Saiful: "Closed. Done"
- **CR021** (proposed since 2026-07-12, Concierge context router) — asked: same → Saiful: "Closed. Superseded"
- **CR022** (proposed since 2026-07-12, app manual corpus for Concierge) — asked: same → Saiful: "Keep deferring"
- **CR026** (proposed since 2026-07-12, sector concentration enforcement + allocation chart) — asked: same → Saiful: "Ask me again later. I need a bit more context"
- **CR027** (proposed since 2026-07-12, price alerts / push notifications) — asked: same → Saiful: "Start now" (note: row itself says hard-gated on A15/A16 external cert work — flagged back to Saiful same session, not resolved here)
- **CR028** (proposed since 2026-07-12, trailing stop) — asked: same → Saiful: "Start now"
- **CR029** (proposed since 2026-07-12, cost-basis lots / FIFO realised P&L) — asked: same → Saiful: "Start now"
- **CR030** (proposed since 2026-07-12, dividend fields for earnings chip) — asked: same → Saiful: "Keep deferring"
- **CR031** (proposed since 2026-07-12, on-device STT/TTS benchmark) — asked: same → Saiful: "Keep deferring"
- **CR036** (proposed since 2026-07-16, go-to-market plan) — asked: same → Saiful: "Already started."
- **CR037** (proposed since 2026-07-17, Social Media Analyst synthetic-sentiment-as-fact) — asked: same → Saiful: "Closed. Done."
- **CR055** (proposed since 2026-07-21, inject real portfolio holdings into every Room prompt) — asked: same → Saiful: "Start now"
- **CR056** (proposed since 2026-07-21, global "no LLM may assume ungiven data" imperative) — asked: same → Saiful: "Closed. Done."
- **CR063** (proposed since 2026-07-23, in-app competition rules + league info) — asked: same → Saiful: "Keep deferring"
- **CR065** (proposed since 2026-07-23, streaks/reputation spec vs code drift) — asked: same → Saiful: "Ask me again. I need more context."
- **CR075** (proposed since 2026-07-23, download + hold the Sharia universe daily) — asked: same → Saiful: "Start now"
- **CR084** (proposed since 2026-07-24, RevenueCat integration M1 final slice) — asked: same → Saiful: "On going" (matches reality — CR084-BE is already dispatched/building per recent commits; register Status looks stale, flagged back, not fixed here — not this routine's domain)
- **DEF061** (open since 2026-07-16, 4/8 mandate toggles are prompt-only) — asked: "Start now / keep deferring / won't fix?" → Saiful: "Keep deferring"
- **DEF078** (open since 2026-07-22, 20/30 BOK lessons 293-345 have factual/legal errors) — asked: same → Saiful: "Start now"
- **DEF089** (open since 2026-07-23, Sharia parent-index URL serves HTML not CSV) — asked: same → Saiful: "Start now"
- **DEF097** (open since 2026-07-23, lesson 355 re-broken by an unrelated code change) — asked: same → Saiful: "Start now"

Note: today's run happened live in a Claude Code conversation, not the `/schedule`
cloud routine — Saiful pushed back on being redirected to the routine's own session
("I was expecting you to use askuserquestion and not push me to a temporary site").
The routine (`trig_01XNaw7BSEURwPKitNNmt6Dr`, daily 10:00 UTC / 13:00 Asia/Riyadh)
still exists for days nobody's chatting; whether to keep it, or switch future runs to
an inline session-start check instead, is open — see the CR085 doc.

---

---

## 2026-07-26

Follow-up run (previous full run 2026-07-24; 07-25 had no session). Items Saiful
marked done/closed on 07-24 whose rows are still `proposed` are flagged here for a
row status-flip by their domain owners (this routine never flips status), not re-asked:
CR007, CR008, CR019, CR020, CR021, CR037 (done/closed/superseded), CR036 (started, commit 855f86b).

- **CR002** (proposed since 2026-07-06, reconcile bug_reports status vocabulary) — asked: "same call?" → Saiful: "Need more info on what this was." (context provided inline: canonical bug status vocabulary cleanup; re-decide next run)
- **CR006** (proposed since 2026-07-09, Beta infra cost research) — follow-up: still proposed, no commit → re-asked → Saiful: "Start now"
- **CR017** (proposed since 2026-07-10, multi-provider LLM routing + caching) — follow-up: still proposed, no commit → re-asked → Saiful: "Keep deferring"
- **CR022** (proposed since 2026-07-12, app-manual corpus for Concierge) — follow-up: still proposed, no commit → re-asked → Saiful: "Keep deferring"
- **CR030** (proposed since 2026-07-12, dividend fields for earnings chip) — follow-up: still proposed → asked → Saiful: "Have we not done this already?" (clarified inline: earnings pill shipped AT:R42, dividend half never did — that's CR030's remaining scope; re-asked with clarification)
- **CR031** (proposed since 2026-07-12, on-device STT/TTS voice benchmark) — follow-up: re-asked → Saiful: "The onboarding ask 'if you want to get the reminder as an audio' — lets evaluate that" (reframes CR031 toward: TTS audio-reminder option surfaced in onboarding; evaluate)
- **CR063** (proposed since 2026-07-23, in-app competition rules + league info) — follow-up: re-asked → Saiful: "Start now"
- **CR026** (proposed since 2026-07-12, sector-concentration enforcement + allocation chart) — follow-up: gave context (DEF061 snapshot now holds sector data) → Saiful: "Start now"
- **CR027** (proposed since 2026-07-12, price alerts / push notifications) — follow-up: 'start now' 07-24 but hard-gated on APNs/FCM certs (Saiful-provision), nothing moved → re-asked → Saiful: "Keep deferring"
- **CR028** (proposed since 2026-07-12, trailing stop) — follow-up: 'start now' 07-24, nothing moved → re-asked → Saiful: "Start now"
- **CR029** (proposed since 2026-07-12, cost-basis lots / FIFO realised P&L) — follow-up: 'start now' 07-24, nothing moved → re-asked → Saiful: "Start now"
- **CR065** (proposed since 2026-07-23, streaks/reputation spec-vs-code drift) — follow-up: gave context → Saiful: "Start now"
- **CR089** (proposed since 2026-07-25, richer mandate fields) — asked (new; filed NOT-MVP) → Saiful: "Keep deferring (post-MVP)"
- **CR090** (proposed since 2026-07-25, live news/social data-feed paywall) — asked (new) → Saiful: "Start now"
- **CR030** (proposed since 2026-07-12) — re-asked with clarification (dividend half only) → Saiful: "Start the dividend half"
- **DEF099** (open since 2026-07-24, account merge drops RC entitlement/credit) — asked → Saiful: "Lane it now"
- **DEF100** (open since 2026-07-24, RevenueCat keys — Saiful-liaison, blocks anon purchase) — not re-asked; Saiful directed this session: "keep nagging me" → stays open, Architect nags each session
- **DEF104** (open since 2026-07-24, plaintext IMAP/SMTP credential + dead KB path) — asked with correction (Saiful had conflated it with the android-test activity; row is the security defect) → Saiful: "Keep open, defer fix" (Architect flagged: the credential is live/valid — rotating it on melehost is independent of the deferred code fix)
- **DEF105** (open since 2026-07-24, AR/MS staleness of the 165 changed EN lessons) — asked → Saiful: "I will instruct LM to work on this"

**Standing activity (not a Defect):** external AI-driven Android testing, ongoing per APK
build — Saiful classified this as a standing activity, distinct from DEF104. No formal
activities register exists yet; recorded here. (Open question: want a lightweight
activities register, or track informally?)

---

## 2026-07-27

Session-start check fired live in-conversation (CLAUDE.md step 2 — first session
on/after 13:00 Asia/Riyadh with no entry for today). Checked git log per carried-over
item before asking; 16 items got a real question, 14 were flagged without re-asking
because the decision was already made elsewhere and only a register status-flip is
outstanding (not this routine's job — domain owners').

**Asked:**

- **CR002** (proposed since 2026-07-06, `bug_reports` status vocabulary — 3rd day asked, gave full context this time incl. the folder doc's recommended fix) — asked: "start/defer/drop?" → Saiful: "Start now"
- **CR006** (proposed since 2026-07-09, Beta infra cost research) — follow-up: said start-now 07-26, no build commit since → re-asked → Saiful: "Still start now"
- **CR017** (proposed since 2026-07-10, multi-provider LLM routing + caching) — follow-up: keep-deferring 07-26 → re-asked → Saiful: "Start now"
- **CR022** (proposed since 2026-07-12, app manual corpus for Concierge) — follow-up: keep-deferring 07-26 → re-asked → Saiful: "Keep deferring"
- **CR027** (proposed since 2026-07-12, price alerts/push notifications, cert-gated) — follow-up: keep-deferring 07-26 → re-asked → Saiful: "Keep deferring"
- **CR028** (proposed since 2026-07-12, trailing stop) — follow-up: start-now 07-24 AND 07-26, no build commit found either time → re-asked → Saiful: "Still start now"
- **CR031** (proposed since 2026-07-12, on-device STT/TTS — narrowed 07-26 to an onboarding TTS audio-reminder eval) — re-asked with narrowed scope → Saiful: "Start now (narrowed scope)"
- **CR063** (proposed since 2026-07-23, in-app competition rules + league info) — follow-up: start-now 07-26, no build commit (only CR064's separate legal doc landed) → re-asked → Saiful: "Still start now"
- **CR089** (proposed since 2026-07-25, richer Mandate fields) — follow-up: keep-deferring/post-MVP 07-26 → re-asked → Saiful: "Keep deferring (post-MVP)"
- **CR098** (proposed since 2026-07-27, Room analyst pull-back — tenure-drip degradation, 2 amendments, no build lane yet, flagged for independent audit when built) — asked fresh → Saiful: "Start now"
- **DEF100** (open since 2026-07-24, RevenueCat/store billing config, Saiful-liaison) — nagged per his 07-26 instruction → Saiful: "Still working on it"
- **DEF104** (open since 2026-07-22, plaintext IMAP/SMTP credential + dead KB path; live credential, rotation independent of code fix) — follow-up: keep-open/defer 07-26 → re-asked → Saiful: "Keep deferring the fix"
- **DEF105** (open since 2026-07-23, AR/MS staleness on 7 rewritten lessons) — follow-up: gave context (staleness-guard 33dfeb1 built; DEF109 07-27 retranslation pass may overlap) → Saiful: "Still needs dedicated check" (don't assume DEF109 covered it — verify before closing)
- **DEF110** (open since 2026-07-26, stop/target hit leaves a phantom holding; Saiful's fix ruling already given 07-26) — asked purely on build-priority → Saiful: "Keep deferring"
- **DEF113** (open since 2026-07-27, 1-on-1 chat never billed despite spec pricing it at 1 credit) — asked the defect's own open question (ship now vs Beta) → Saiful: "Ship now (Alpha)"
- **DEF114** (open since 2026-07-27, Room SSE parser's agent_token unescape + stream termination untested, mutation-proven load-bearing) — asked fresh → Saiful: "Start now"

**Flagged, not re-asked (decision already made elsewhere; register status flip is outstanding, domain owner's job):**

- **CR007, CR008, CR019, CR020, CR021, CR036, CR037** — Saiful called these done/closed/superseded/started on 2026-07-24 (CR036 additionally got a commit, 855f86b, per the 07-26 note); all 7 still show `proposed` today, 3rd day running for the first six. Needs an actual row-file status flip, not another ask.
- **CR091, CR092, CR093, CR094, CR095, CR096** — filed today (2026-07-27) out of the CR065 drift audit with Saiful's verdict already embedded in each row ("build it" ×4, "both stay, rename one" for CR093), and already spec'd into dispatch lane `CR091-STREAKS` (commit `3958ab6`, left UNASSIGNED pending a `coder.api` slot — four CRs share `reputation_service.py`, sequenced as one lane to avoid concurrent-write conflicts). Nothing to ask; waiting on lane assignment.
- **DEF102** — its own row narrative says "fully resolved (class B + class A)" and commit history confirms fix + verification commits (`5fc1f38`, `672466e`, `8e0aec5`); register `Status` field is simply stale (`open`), needs flipping to `resolved`.

---

## 2026-07-28

Session-start check fired live in-conversation (CLAUDE.md step 2). Registers verified
clean (`verify all` — 137 DEF + 104 CR rows, no drift). List built from row files: 24
`proposed` CRs + 19 `open` Defects. Per-item `git log --since` follow-up run before
asking, so anything that actually moved is logged as closed rather than re-asked.

**Asked:**

- **CR028** (proposed since 2026-07-12, trailing stop) — follow-up: start-now on 07-24, 07-26 AND 07-27, zero commits tagged CR028 since any of them → re-asked → Saiful: "Still start now" (4th consecutive; needs an actual lane, not another log line)
- **CR002** (proposed since 2026-07-06, `bug_reports` status vocabulary) — follow-up: start-now 07-27, 0 commits since → re-asked → Saiful: "Still start now"
- **CR006** (proposed since 2026-07-09, Beta infra cost research) — follow-up: start-now 07-26 + 07-27, 0 commits since → re-asked → Saiful: "Still start now"
- **CR017** (proposed since 2026-07-10, multi-provider LLM routing + caching) — follow-up: start-now 07-27, 0 commits since → re-asked → Saiful: "Keep deferring" (reversal from yesterday)
- **CR031** (proposed since 2026-07-12, on-device STT/TTS, narrowed scope) — follow-up: start-now 07-27, 0 commits since → re-asked → Saiful: "Keep deferring" (reversal from yesterday)
- **CR063** (proposed since 2026-07-23, in-app competition rules + league info) — follow-up: start-now 07-26 + 07-27, 0 commits since → re-asked → Saiful: "Keep deferring" (reversal after two start-nows)
- **DEF113** (open since 2026-07-27, 1-on-1 chat never billed) — follow-up: ship-now-Alpha ruling 07-27, 0 commits since → asked to confirm a build slot → Saiful: "Yes — lane it now"
- **Stale register rows** (CR007, CR008, CR019, CR020, CR021, CR036, CR037, DEF102, DEF120 — all decided/closed elsewhere but still reading `proposed`/`open`, polluting this list daily; the CR seven for the 4th day) — asked whether to flip → Saiful: "Flip all nine now" → **acted on this session** (row files edited + registers regenerated), an explicit live instruction overriding this routine's default hard-rule 1 (never flip a status)
- **CR022** (proposed since 2026-07-12, app manual corpus for Concierge) — follow-up: keep-deferring 07-26 + 07-27 → re-asked → Saiful: "Keep deferring" (3rd consecutive)
- **CR027** (proposed since 2026-07-12, price alerts/push, cert-gated; also blocks CR095's push half) — follow-up: keep-deferring 07-26 + 07-27 → re-asked → Saiful: "Keep deferring" (3rd consecutive)
- **CR089** (proposed since 2026-07-25, richer Mandate fields) — follow-up: keep-deferring/post-MVP 07-27; flagged CR101 covers the same ground → re-asked → Saiful: "Drop it — CR101 supersedes"
- **DEF104** (open since 2026-07-22, plaintext IMAP/SMTP credential + dead KB path; offered credential-rotation-only as a middle option) — follow-up: keep-deferring 07-26 + 07-27 → re-asked → Saiful: "Keep deferring the fix" (3rd consecutive; live credential stays)
- **DEF110** (open since 2026-07-26, stop/target hit leaves a phantom holding) — follow-up: keep-deferring 07-27; re-asked with the portfolio/league-scoring corruption spelled out → Saiful: "Lane it now" (reversal)
- **DEF100** (open since 2026-07-24, RevenueCat/store billing config, Saiful-liaison) — nagged per his 07-26 instruction → Saiful: "Still working on it"
- **DEF105** (open since 2026-07-23, AR/MS staleness on 7 rewritten lessons) — follow-up: "still needs dedicated check" 07-27; re-asked now that DEF126 reports a corpus-wide AR/MS gap → Saiful: "Fold into DEF126" (reversal — DEF105 closes as a subset of the corpus-wide pass)
- **DEF117** (open since 2026-07-27, 15 daily-challenge/glossary content defects, 0 wrong answer keys) — asked fresh → Saiful: "Keep deferring"
- **CR102** (proposed since 2026-07-27, in-app messaging to beta testers) — asked fresh → Saiful: "Keep deferring" (note: he requested this CR himself on 07-27, and is deferring it a day later)
- **CR103** (proposed since 2026-07-27, admin compose tab for CR102) — asked fresh → Saiful: "Queue behind CR102" (so effectively deferred with it)
- **CR105** (proposed since 2026-07-27, agent-prompt copy drift, amended scope) — asked fresh → Saiful: "Keep deferring"
- **CR107** (proposed 2026-07-28, agent icons sized by surface) — asked fresh → Saiful: "Queue behind CR106"
- **CR108** (proposed 2026-07-28, lessons track hex label wraps to two lines) — asked fresh → Saiful: "Queue behind CR106/CR107" (all three UI items batch into one mobile lane)
- **DEF137** (open since 2026-07-28, 24 EN-only strings reachable via the live language picker) — asked fresh → Saiful: "AT:Language Manager is working on this" → **owned by the Language Manager track; stop asking, it is not unowned**
- **DEF126** (open since 2026-07-27, corpus-wide AR/MS translation quality gap, 87.7% flagged; DEF105 folded in earlier today) — asked fresh → Saiful: "AT:Language Manager is working on this" → **same: Language-Manager-owned, drop from the daily ask**
- **DEF125** (open since 2026-07-27, flat `max_tokens=400` truncates the Research Manager in 66% of convenes) — asked fresh → Saiful: "Leave queued behind CR104"
- **DEF136** (open since 2026-07-28, Room convene path still blocks the event loop — the un-closed remainder of DEF116/DEF120) — asked fresh → Saiful: "Assign it now" (top of the coder.room/coder.api queue)
- **DEF129** (open since 2026-07-28, Concierge claims briefing-scheduling + agent mute/promote that do not exist; already fired on a real user) — asked fresh → Saiful: "Keep deferring"
- **DEF119** (open since 2026-07-27, streak-freeze COUNT-then-INSERT race) — asked fresh → Saiful: "Lane it now"
- **DEF127** (open since 2026-07-27, no guard pins DEF114's COMPLETE-value SSE invariant) — asked fresh → Saiful: "Lane it now"
- **DEF130** (open since 2026-07-28, unanchored-date invariant is ISO-only) — asked fresh → Saiful: "Lane it now"
- **DEF132** (open since 2026-07-28, `watcher.sh state` exits 1 on a successful board read) — asked fresh → Saiful: "AT:Governance is looking at this now" → **owned by track G; drop from the daily ask**
- **DEF133** (open since 2026-07-28, DEF120's walk flags the correct lambda-deferral idiom) — asked fresh → Saiful: "Lane it now"
- **DEF135** (open since 2026-07-28, an audit watcher can die silently and every board still reads healthy) — asked fresh → Saiful: "AT:Governance is looking at this now" → **owned by track G; drop from the daily ask**
- **CR106** (proposed 2026-07-28, Room result Verdict Board + collapsed transcript; CR107 + CR108 both queued behind it) — asked fresh → Saiful: "Start now"
- **CR109** (proposed 2026-07-28, P&L game on AMI Cash) — asked fresh → Saiful: "Keep deferring"
- **Parser bug in this command** (step 3 read Status by fixed field index, so any row whose text contains a `|` shifted the column: DEF102 + DEF136 were wrongly listed as open, CR106 + CR109 were silently missed) — asked whether to fix → Saiful: "Fix it now" → **command doc corrected this session** to index from the end of the row (`NF-3`)

**Flagged, not re-asked:**

- **CR093, CR095, CR101** — verdict already embedded in each row ("build it" / "both stay, rename one") and spec'd into the `CR091-STREAKS` lane; still waiting on a `coder.api` slot. Lane assignment is the Architect's job, not a Saiful decision. 2nd day flagged.
- **DEF102, DEF136** — appeared on today's list only because of the parser bug above. DEF102 is `resolved`, DEF136 is `fixed` (`7d35466`, both convene call sites now `await asyncio.to_thread(...)`, submitted to audit at `88f6926` *during this review*). No flip needed on either. Saiful's "assign it now" on DEF136 was answered against a stale reading — the work he asked for had already been done and submitted an hour earlier, so the answer is satisfied, not outstanding.

**Status flips applied this session** (explicit live instruction, overriding hard-rule 1):

- CR007, CR008, CR019, CR037 → `done` · CR021 → `dropped` (superseded) · CR036 → `in_progress` — all per his 2026-07-24 rulings, unflipped for 4 days.
- CR020 → `done` (his 07-24 "Closed. Done").
- CR089 → `dropped`, superseded by CR101 (today's ruling).
- DEF120 → `resolved` (lane audited COMPLETE r4, merged `7ec6d1b`, archived).
- DEF105 → `closed`, folded into DEF126 (today's ruling); the 7 lessons recorded on DEF126's row as a **named must-cover subset with a phantom-Mandate token check**, not an assumed sweep-up.
- DEF102 was on the flip list when asked but needed no flip (already `resolved`) — 8 rows changed, not 9.

**Note — the checkout moved under this review.** Other tracks committed to shared `main`
while the questions were being asked: DEF136 fixed + submitted (`7d35466`, `88f6926`),
DEF137's translation half landed (`7751ff5`, 28 keys not the 24 the row claimed), CR109
filed (`2256e1b`). The list was rebuilt against live state mid-run rather than trusting
the opening snapshot. Worth doing every run — this routine reads a register that other
sessions are actively writing.

---

### 2026-07-29 — 0900 automated check-in (NOT the daily review)

Deliberately an `###`, not a `## 2026-07-29`: CLAUDE.md step 2 skips the full review when a
`##`-level section for today exists, and this pass asked **three** items, not the full sweep.
Today's 13:00 Asia/Riyadh review still owes the complete `proposed`/`open` walk — it should
read this block first and **not re-ask these three**.

Read-only pass over `git log -20` + both registers. CR106 landed since the 07-28 review (all
four phases, `b9ab31e` + `642f258`, build `0.1.0+57` to TestFlight), which cleared the queue
gate three items were parked behind.

**Asked (3):**

- **CR107 + CR108 + DEF142** (mobile lane, all three parked behind CR106 which is now `done`;
  DEF142 measured `Colors.white` on the family fills at 2.15:1 amber / 2.43 cyan / 2.54 green,
  all below the 4.5:1 floor, and `size*0.16` giving 3.2pt on `lesson_tile`'s 20pt call site)
  → Saiful: **"Lane all three together"** — one `coder.mobile` lane; they edit the same avatar
  and track-label sizing, so three separate passes over `hex_avatar.dart` is the wrong shape.
- **DEF139 + DEF140** (DEF127's two follow-ups, minted 07-28, never asked before now; DEF139 is
  live on the `+56`/`+57` build testers are running — a multi-line SSE `error` payload reaches
  the user with a literal `\n`; DEF140 is the same framing hole for a bare `\r`, latent only
  because our one consumer is not a spec-compliant parser) → Saiful: **"Lane both now"** —
  one lane, one audit.
- **DEF141** (all five auditor-authored regression pins uncollected — `testpaths = ["tests"]`
  never reaches `orchestration/audit/regression/`, so none has run since the day it was
  written) → Saiful: **"Fix now."**

**Flagged, not asked** (no Saiful decision outstanding — these need lane assignment or a
status flip, both Architect-side):

- **DEF110** ("Lane it now", 07-28) · **DEF119** ("Lane it now", 07-28) · **DEF113**
  ("Yes — lane it now", 07-27) — ruling given, still `open`, zero fix commits since. 1st/1st/2nd
  day carried.
- **DEF144** — row reads `open` but the fix shipped: `e294ed6` (guard), `179ae1d` (unconditional
  veto in `_is_verified`), `2936474` (the 2 contaminated files retranslated). Stale row, needs a
  flip, not a decision.
- **DEF126** — `c8b5f5f` re-translated all 296 AR-flagged lessons, DEF144-guarded. Language-Manager-
  owned per the 07-28 ruling; drop from the ask, but the row has not been reconciled against that
  commit.

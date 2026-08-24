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

#### 2026-07-29 — 0900 check-in, part 2: live `bug_reports` sweep

Saiful asked *"Did we check the live DB for user reported errors?"* — part 1 had not; it was
registers + `git log` only. **That was a gap in the check-in, not in the registers:** six open
user reports were sitting in `bug_reports` on melehost, four of them unseen by any session, and
the track-R monitor watermark is still `2026-07-22T03:00:30+00` (7 days stale). Polled live,
diagnosed against the DB and the running Alpha, and ruled item by item.

**Filed (5) — all from Platinum Anchor `8f1e288a`, five of six on `0.1.0+57`, the CR106 build:**

- **DEF147** ← `6ba6ec7f` — the CR106 stance envelope leaks raw `[STANCE: …` into user-visible
  prose *and* the comb reports "no stance", because one regex does both the parse and the strip.
  **Measured, not reported:** 2/2 runs since ship carry a leaked tail; on `bd31e46a` 3 of 11
  prose agents parsed `null` (**27%**) — one truncated mid-tail with no closing `]`, one emitted
  with no opening `[`, one emitted nothing (the only honest gutter of the three). B2 chose a
  trailing line over a JSON envelope to beat DEF058's 22% parse failure; day one it fails at 27%
  **and** produces the leak the shape was chosen to avoid. → Saiful: **"That, plus move the
  envelope to the front of the turn"** — decouple strip from parse AND relocate the field, so
  truncation eats prose instead of the structured data the whole board is built on.
- **DEF146** ← `07d80ab2` (+ `df515c35`) — the BOARD|TRANSCRIPT toggle ships as two objects with
  mismatched geometry (selected half hex-cut, unselected half a rounded rect), against CR106
  §4.0's own rule. → Saiful: **"The AT:Designer has made the design… Follow it"**, then supplied
  it as `df515c35`: **one** continuous elongated hexagon, outer edges angled only, straight
  internal divider, selected half filled. Materially different from the fix the defect would
  otherwise have taken — independently hex-cutting both segments reproduces the reported defect
  symmetrically.
- **DEF148** ← `34861dc8` (open 6 days, `+51`) — a raw `DioException` printed to the user, MDN
  link and all, under an app bar still reading "Loading...". → Saiful: **"This needs to be
  validated. A lot of movement since build 51."** Validated: **all 70 `related_lesson` refs
  fetched against live Alpha, 70/70 return 200** — the 404 half is closed by corpus movement
  (`320bf45`, DEF079's floor raise) and does not reproduce. The raw-exception half **is** still
  shipping (`lessons_providers.dart:174`) and is a **second occurrence** of DEF073 ⇒ earns a
  `failure_patterns.md` entry with a guard.
- **CR111** ← `f06385e4` — the Journal's 12-agent roster costs a full phone screen above the
  verdict. → Saiful: **remove from the Journal only**, keep it live in the Room (there it is a
  progress display; in a finished entry every agent has spoken). Plus: the Designer's strip reads
  `41S · 3 CREDITS`, which the Journal payload cannot render — → Saiful: **drop the strip from
  the Journal** rather than fall back or start writing the fields. Guard: the roster-gap
  disclosure (`opinions_not_included`) must survive the roster's removal.
- **CR112** ← `583602ee` — the live convene still streams full prose; CR106 fixed the destination
  and left the journey. → Saiful: **"Status + the agent's headline as it lands."** **Blocked on
  DEF147** — a headline reveal on a 27%-null envelope would put the leak in the most prominent
  position in the app; the status half can ship alone.

**Correction to part 1's closing summary:** it listed DEF110 as a ruling carried without a lane.
It shipped while this check-in was running — `dc57f38` fix + backfill, promoted
`alpha-2026-07-29-3` (`d6ad0fb`), verified and closed (`234b19ec`), with the Alpaca half split
out as **DEF145** — which is why this batch numbers from DEF146.

**Standing gap worth fixing:** the 0900 check-in reads the registers but not `bug_reports`, so
user-reported defects are invisible to it until the track-R monitor runs — and that monitor's
watermark has not moved in 7 days. The two highest-severity items this morning (a live leak of
machine syntax, and a 6-day-old raw exception) both came from the DB, neither from a register.

#### 2026-07-29 — 0900 check-in, part 3: one more report

`5c6f260f` (Platinum Anchor, `+57`, `/floor`) — *"the larger buttons should all be normal
rounded edge buttons. there are several of these so let's fix them all."* Filed as **CR113**.

Sized before asking, and it is smaller than "several" implies: **all six** user-facing large
CTAs go through one widget. `hex_button.dart:42` clips unconditionally with no size variant, so
SAVE MY TEAM / CONVENE THE ROOM / MEET {AGENT} / SUBMIT / CONTINUE / TRY AGAIN all change from a
single edit.

The question worth asking was **where the rule stops**, not what to change — hex also lives in
the lessons honeycomb, chips, avatars, toasts, bottom nav, the ticker period toggle and the
BOARD|TRANSCRIPT toggle the AT:Designer had specified as hex *hours earlier* the same morning
(`df515c35` → DEF146). Three of the four options offered would have swept one of those away. →
Saiful: **"Only `HexButton` — large CTAs."**

This confirms CR106 §4.0 rather than inventing a rule (hex for marks and controls; rounded rects
for surfaces) — `HexButton` predates it and was never reconciled. **The durable half is writing
it into `ami_hex_in_flutter.md`**, which CR106 §4.0 flagged and which still has not happened;
without it the next new button reintroduces this. Note **CR108** edits `TrackHexButton`, the
widget CR113 deliberately leaves hex — same lane, opposite rulings, must not be conflated.

**Mobile batch now stands at seven items** — CR107, CR108, DEF142, DEF146, DEF148, CR111, CR113
— all in `mobile/lib`, all authorised today.

#### 2026-07-29 — 0900 check-in, part 4: three more, one of them a reversal

- **DEF129 — REVERSED, now "remove Q8 now"** (was "keep deferring", 07-28). Saiful hit it live
  (`56a05dc5`) and asked *"what will the room report daily?"*. **The row understated it:** the
  briefing is not just claimed by the LLM, it is a scripted step whose answer is **persisted and
  confirmed back** — `concierge_engine.py:290` writes `daily_briefing`, `:486-499` prints
  `🎙️ Briefing: 07:00 daily briefing with voice` into the readback the user is asked to approve.
  A specific time the user never chose, a voice mode that cannot exist. Textbook **CR040** — the
  user finishes onboarding believing a 7am briefing is scheduled. Removing the question, the
  field, the readback line and the `Edit briefing` chip. Guard note: Q8 is **hardcoded Python**,
  so DEF129's own prompt-alignment guard would have passed it clean — the guard has to cover
  scripted steps too.
- **CR115** — the briefing respec'd, so the removal is a deferral and not a quiet abandonment.
  Saiful's question is its first open item, and the honest answer is that the hard part is not
  the scheduler: it is what a simulation-only, unlicensed-to-advise product says unprompted at
  07:00 on a morning when nothing happened. `project_plan.md` A17 says `⚡ partial`; it is not
  started, and that row gets corrected as part of this.
- **CR114** ← `b5a5e923` — Q7 asks *"what you'd NEVER want to invest in"* and offers 7 chips of
  which **2 are exclusions**; `Halal only` read literally answers the inverse of its intent.
  Mandate data is fine (`_parse` keys off substrings), so no backend test could catch it. Matters
  because Q7 is where halal screening is captured and CR036 §3 names that as the AR/MS moat. →
  Saiful: **"Keep one question, regroup the chips under ONLY / NEVER headers"** — not the split he
  floated, and not a reword; rejected splitting because it lengthens the flow DEF060 exists to
  protect. Flagged for the builder: headers in a chip row are cramped on a phone and **untested
  in RTL**, where a mirrored layout can detach a header from its chips silently.
- **DEF150** ← `86f35b5f` — the Journal renders the verdict's reasoning **above** the board that
  states the verdict, so the entry opens with an argument for a conclusion not yet given. →
  Saiful: **move the reason inside the board, below the outcome.** Two things he did not report,
  found in the same screenshot: the reason is **cut mid-word** (*"…the potential fo"*) in what is
  the permanent record — and whether that is a render cap or a truncated stored value must be
  established first, because the latter means the Room shows it too; and the strip is clipped,
  already covered by CR111. Fix goes through the shared mapper, not `journal_detail_screen.dart`
  — that shortcut is DEF098's named class and produced DEF143.

**Running total for this check-in: 9 items filed** (DEF146, DEF147, DEF148, DEF150, CR111, CR112,
CR113, CR114, CR115) + DEF129 reversed, from **10 user reports** — 9 of them on `+57`, all from
one tester. Two-thirds are CR106 fallout, which is what shipping a large surface change into an
alpha with an engaged tester looks like; the register-only check-in saw none of it.

#### 2026-07-29 — 0900 check-in, part 5: `5cc94e0e`

**CR116** — *"holdings should be above watch list."* No decision needed and none manufactured:
`portfolio_screen.dart:139-155` renders `_ValueCard` → sector allocation → **watchlist** →
**holdings** → trades, so what the user owns sits below what they are merely watching, on the
screen whose job is the position book. Swap ruled as stated. Two things flagged for the builder
that the one-line report does not carry: the holdings block is a **conditional** (`if
(p.holdings.isEmpty)` renders `_NewTraderHint` instead), so the swap silently promotes the
new-trader hint to the top of the screen for anyone with no positions — a different change than
the one asked for, worth a deliberate look rather than inheriting; and `_watchlistKey` is a
`GlobalKey` used as a scroll/coach-mark target, which has to stay attached to the same widget
through the move.

**Final tally for this check-in: 11 user reports → 10 items filed** (DEF146, DEF147, DEF148,
DEF150, CR111–CR116) + DEF129 reversed. Ten of the eleven were on `+57`, all from one tester,
and roughly two-thirds are CR106 fallout. **None of it was visible to the register-only
check-in** — the sweep only happened because Saiful asked whether the live DB had been checked.

#### 2026-07-29 — 0900 check-in, part 6: four more reports, one of them a silent total outage

- **DEF151** ← `589e7607` part 2 (*"why are we missing the chart?"*) — **the ticker chart has been
  100% dark, every ticker, every period.** `ticker_chart.dart:29` sends `['1D','1W',…]`; the
  backend accepts `1d,1w,1m,3m,1y,5y` **lowercase only**. Measured against live Alpha: **18/18
  (6 periods × 3 tickers) return HTTP 422**; drop the param and the same endpoint returns a full
  yfinance candle series, so every layer below the case mismatch is healthy. **The reason it sat
  unreported is the real lesson:** it degrades to `Chart unavailable. Tap to retry.` — copy that
  describes a *transient* fault — so users retry a request that can never succeed and read it as
  a bad connection. A silent total outage wearing the costume of a flaky network; it took Saiful
  asking to surface it. Guard must ship with the fix: a test tying `_kPeriods` to the server's
  allow-list (a cross-language contract with nothing holding it together), and ideally a retry
  surface that distinguishes 4xx-never-retryable from network-retryable. → Saiful: **"File it and
  lane it"** (fix-in-session was offered and declined).
- **CR117** ← `589e7607` part 1 (*"the buttons are octagonal, not hexagonal"*) — **correct, and
  the code says so itself:** `FlatTopHexagonClipper`'s own docstring reads *"cut-corner octagon"*
  and it emits an 8-point path. Every "hex" **control** in the app is an octagon; only the avatars
  and honeycomb use the true hexagon. **This reframes DEF146** — the AT:Designer's toggle is a
  true hexagon, unbuildable at any `cornerCut` of the existing clipper, so DEF146 was mis-scoped
  as "apply the same clipper to both halves" and is now blocked on this. → Saiful: **"Add a real
  hexagon clipper, migrate controls to it."** Explicitly NOT a sweep — migrate on evidence (a
  design, a report), not tidiness; and rename the octagon clipper, which has misled every reader
  since it was written, including CR106 §4.0's reasoning about "hex geometry" on controls that
  have none.
- **DEF152** ← `0b8c44c4` — "Restart onboarding" destroys the mandate on one tap with no
  confirmation, from a caption-sized blue link in the Floor footer. Reported from experience, not
  inspection (*"accidentally touched it"*). Same class as **DEF060**: the mandate is the most
  expensive thing a user produces and the code treats it as cheap. → Saiful: **confirm dialog**
  (not the relocate-to-Settings option) — and the copy must name what is lost, since the
  control's placement fails to.
- **CR118** ← `7f631a72` — sector legend renders every sector inline, so the card grows with
  diversification, the one thing the product encourages. → **cap the height, scroll inside.**
  Flagged: nested scrollables inside `portfolio_screen.dart`'s `ListView` need a bounded height,
  and a `shrinkWrap` fix silently re-expands — it would look correct in a 4-sector test and
  regress on a real diversified portfolio. Test with 13 rows, and give the cut a visible
  affordance (DEF075's precedent: clipped content with no cue reads as a rendering bug).
- **CR119** ← `9d51ce11` — filed as a **design commission**, not an implementation CR, because
  Saiful named the owner (*"we need a AT:Design to work on this"*). No solution proposed. Row
  carries the constraints instead: three of the five portfolio sections are unbounded and all
  three grow through the exact behaviour the product teaches, so a user the app has succeeded
  with is a user whose portfolio screen is unusable. CR116 and CR118 are small and ruled — they
  land first and are not blocked on this.

**Running total: 15 reports → 15 items** (DEF146–148, DEF150–152, CR111–CR119) + DEF129 reversed.

---

## 2026-07-29

Ran live in-conversation across two sessions of track R (CLAUDE.md step 2). The 0900
check-in is already recorded item-by-item in the row files it produced; this section
records it in one place and adds the rulings made later the same day, plus what was
actually built against each — because a ruling with no build behind it is what this log
exists to surface.

Registers verified clean at both ends of the day (`verify all`): 155 DEF + 117 CR rows
at the start of the build pass, 156 DEF after DEF156 was minted. `cr_list.md` was held
un-regenerated for part of the day (a concurrent session had an uncommitted `CR121` row);
regenerated at `b79dd445` **preserving** that row rather than sweeping it, since the CR081
failure mode is losing another track's rows.

**Asked and ruled:**

- **DEF151** (bug `589e7607`, ticker chart dark on every ticker/period) — asked file-and-lane vs fix-in-session → Saiful: **"File it and lane it"** → **superseded later the same day** once the *server-side* half was weighed: normalising on the server repairs the `+56`/`+57` binaries already on testers' devices, so it shipped in-session instead. Laning it would have left the chart dark on every installed build until the next release.
- **DEF129** (Concierge offers a daily briefing nothing can send) — re-asked after he hit it live on `+57` and filed `56a05dc5` (*"the function it offers does not exist. and what will the room report daily?"*) → Saiful: **"Remove Q8 now, spec the briefing separately"**, reversing 07-28's "keep deferring".
- **CR115** (spec the daily briefing properly — split out of DEF129 above) — asked hold-open / draft-a-spec / drop → Saiful: **"Remove the q from onboarding"** → **dropped**. So the briefing is not deferred, it is not being built, which removed DEF129's last reason to wait. **Built today** (`d6932f15`): Q8 gone whole — question, chips, enum member, step hop, parser, mandate carry, readback line, `Edit briefing` chip, and the `daily_briefing` field with the `DailyBriefing` model behind it.
- **CR114** (Q7 asks for exclusions but 5 of 7 chips are inclusions) — asked → Saiful: **"I build it now"** → **built today** in the same pass as DEF129, since both edit the same question block.
- **CR118** (sector legend grows with diversification) — from his own report `7f631a72` → Saiful: **"Cap the height, scroll inside the card"** → **built today** (`60efa05d`).
- **CR119 / CR116 / CR118** (the Portfolio growing-lists cluster) — asked → Saiful: **"119 - close, 116 - superseded, close. 118 - fold into 120"** → CR119 `done`, CR116 `dropped`, CR118 folded into the CR120 assign as acceptance 11.
- **CR111 / CR112 / CR113** — first ruled **"Hold it"** on CR113, then **superseded within the same session**: *"for 111,112,113. if they can run in parallel, you can build them. otherwise hold until after 120"* → CR111 and CR113 built and shipped; **CR112 held**, blocked on DEF147 rather than on CR120.
- **DEF142 + CR108** (mobile legibility pass) — asked → Saiful: **"Second parallel lane now, ~$20 (Recommended)"** → dispatched, and **round 1 rejected pre-audit** (`b9671fe6`): CR108's wrap never engages and its test cannot fail. Re-laned as round 2, Part B only.
- **Store release** — asked what else was buildable for `+58` → Saiful: **"OK, lets finish these 5 and build +58"** → all five built (CR118, the DEF151 follow-up, DEF139, DEF156, the CR111 ARB tidy) and `0.1.0+58` cut.

**Not asked, and why:** the ordinary sweep of every `proposed` CR / `open` Defect did not
run a second time today. The day was spent building against rulings already made, and
re-asking items ruled hours earlier would have produced a log of noise. Items still
unruled and owed a fresh ask tomorrow: **CR121** (another session's), **CR107** (HELD —
its control, the DEF142 pass, is not yet valid), **CR112** (blocked on DEF147), and the
long-standing set CR002/CR006/CR017/CR022/CR027/CR028/CR031/CR063.

**Running total: 15 reports → 16 items** (DEF146–148, DEF150–152, DEF155, DEF156,
CR111–CR119) + DEF129 reversed and now half-fixed.

## 2026-08-07

Ran live in-conversation, track R (Saiful: "Let's go through the open cr list. We have
a daily review tool, use it."). Scoped to the **CR register only** at his request (not
Defects). `verify all` clean at start: 224 DEF rows / 135 CR rows, no drift, so no
regenerate needed. 20 `proposed` CRs found; 2 skipped per rule (standing/self-flagged
decisions, not re-asked), 18 asked in 5 batches.

**Skipped (not asked):**

- **CR022** (proposed since 2026-07-12, app manual corpus) — row carries a dated
  standing decision newer than any prior ask: **"[DEFER TO PRE-RELEASE — Saiful,
  2026-07-31]."** Unchanged, not re-asked.
- **CR122** (proposed since 2026-07-29, ads monetization) — row carries its own
  instruction: **"Decision already made — the daily CR/Def review should NOT re-ask
  this; it needs lanes, not a decision."** Honored.

**Asked and ruled:**

- **CR017** (proposed since 2026-07-10, multi-provider LLM routing + caching) —
  history: deferred → "start now" 07-26 → reversed 07-27 → asked fresh → Saiful:
  **"Start now."**
- **CR095** (proposed since 2026-07-27, daily challenge reminder push/email) — never
  asked before; flagged that its push-half blocker (CR027/OneSignal) cleared
  2026-08-01 → Saiful: **"If push is ready, let's use it now"** — both channels.
- **CR102** (proposed since 2026-07-27, in-app messaging to beta testers) — asked
  07-27, ruled "keep deferring" ("after a few more critical CRs"); re-asked now that
  CR136 + defect cleanup landed → Saiful: **"Drop it."**
- **CR103** (proposed since 2026-07-27, admin compose-tab UI for CR102) — asked 07-27,
  ruled "queue behind CR102"; re-asked given CR102's drop → Saiful: **"102 has been
  dropped. This CR has replaced it."** Reading: CR103 becomes the live vehicle for the
  messaging feature (absorbing whatever backend scope it needs, since CR102's API/CLI
  half no longer ships separately) — a scope/merge call for CR103's domain owner to
  execute via the normal row-file process, not actioned by this review.

- **CR107** (proposed since 2026-07-28, agent icons vs letters) — flagged that its
  hold condition (DEF154) closed as duplicate of DEF142, and DEF142 is now fixed →
  Saiful: **"Keep holding."** No new reason given; treat as unchanged, re-ask later.
- **CR121** (proposed since 2026-07-29, client version gate) — asked fresh, flagged
  every day's wait is another ungateable build → Saiful: **"Start now."**
- **CR138** (proposed since 2026-08-03, §F5 advice classifier) — asked whether "CR136
  promoted" (its stated blocker) counts as satisfied given this week's live
  /promote-to-alpha despite CR136's register status still `in_progress` → Saiful:
  **"CR136 has been delivered. Let's do this."** — start now.
- **CR140** (proposed since 2026-08-06, Portfolio Health cadence — Saiful's own
  filing) — asked which of the 3 shapes → Saiful: **"(b) Rolling 30 days"** (the
  recommended option). Row's other 2 open questions (Floor Manager vs Trader cadence;
  credit-buyout of an off-cadence reading) not yet asked — follow-up below.
  - **Follow-up 1 (Floor Manager vs Trader cadence):** asked plain, then he asked
    for clarification ("does this mean both get 1/30 days?") → confirmed yes, then
    he asked a second clarifying question — **is Portfolio Health user-initiated or
    backend-scheduled?** Checked the code live: `GET /health/{user_id}` (tiles) is
    free/always-live, `POST /health/{user_id}/finding` (the 1 LLM-call Finding)
    fires only on a user tap — pull, not push, no scheduled job exists today.
    Re-asked "same cadence for both?" with that confirmed → Saiful: **"We need a
    different look at this. We should be using the credits."** Reading: the
    cadence question should route through a credit-metered access model (couples
    to DEF205/credit-buyout, which he already said yes to) rather than a flat
    30-day wall differentiated by plan. **Not a snap decision** — CR140's a/b/c
    framing and the FM-vs-Trader question need a redraft around credits before
    this is actionable; flagged for a dedicated design pass, not resolved today.
  - **Follow-up 2 (credit buyout of an off-cadence reading):** Saiful: **"Yes,
    allow credit buyout"** — now folded into follow-up 1's larger redirect (the
    whole cadence should likely BE the credit mechanism, not a separate escape
    hatch from one).

- **CR123** (proposed since 2026-07-30, security-hardening umbrella) — flagged
  9/11 child DEFs fixed, only DEF178/DEF182 open, CR124/125 unstarted → Saiful:
  **"Close DEF-level, split remainder"** — formally separate the finished DEF work
  from the still-open CR124/CR125, rather than the umbrella staying one blob.
  Governance action for CR123's domain owner (row-file edit), not done by this
  review.
- **CR124** (proposed since 2026-07-30, melehost/compose hardening) — asked, he
  asked for a re-explanation → re-explained (Postgres 5434 + Redis 6379 published
  on every interface, live-proven reachable with superuser/no-auth from an ordinary
  LAN device, not melehost itself; fix is loopback binds + real passwords + network
  isolation, infra-only, no app code) → Saiful: **"Start now."**
- **CR125** (proposed since 2026-07-30, mobile secure session, BREAKING) — asked →
  Saiful: **"Start now."**
- **CR139** (proposed since 2026-08-03, re-annualise Portfolio Health by real
  period length) — asked, flagged not urgent → Saiful: **"Start now."**

- **CR133** (proposed since 2026-07-30, bottom-nav restructure) — asked fresh,
  flagged as the prerequisite for CR109/CR135 → Saiful: **"Keep deferring."**
- **CR134** (proposed since 2026-07-30, CR109 design-conformance review) — asked
  fresh → Saiful: **"Fold into CR109's build"** — no standalone pass, apply when
  CR109 builds.
- **CR109** (proposed since 2026-07-30, P&L Game / AMI Cash) — asked fresh →
  Saiful: **"Wait for CR133 first"** — consistent with CR133's defer above.
- **CR135** (proposed since 2026-07-31, in-app notification centre) — asked fresh
  → Saiful: **"Queue behind CR133"** — consistent, automatic once CR133 ships.

- **CR131** (proposed since 2026-07-30, Day Trader outcome instrumentation) — asked
  fresh, flagged CR129 (its dependency) is in_progress not done → Saiful: **"Start
  now"** — build alongside CR129, ready when it lands.
- **CR132** (proposed since 2026-07-30, Day Trader lesson track) — asked fresh →
  Saiful asked **"How many lessons and where will it be stored"** → answered from
  the CR doc + repo (6 lessons; `content/lessons/NNN_<slug>.en.mdx`, the 047/365
  convention) → Saiful asked **"In which lesson group?"** → checked lesson
  frontmatter live: 13 tracks exist, `edge_process` (99 lessons) already houses
  012/047/049/051 and matches CR132's own stated prerequisite chain → Saiful:
  **"Yes — edge_process."** Re-asked the original question with track settled →
  Saiful: **"Start lessons 1-5 now"** — lesson 6 (needs CR131's data) follows once
  CR131 lands.

**Running total: 20 proposed CRs found (Defects out of scope this run, per Saiful's
request) → 2 skipped (standing/self-flagged) → 18 asked, all ruled, 0 left
unresolved for a re-ask tomorrow.** Rulings needing follow-up build/governance
action (not done by this review): CR017/CR095/CR121/CR124/CR125/CR131/CR132/CR138/
CR139 start now; CR102 drop (CR103 absorbs it — needs a row-file merge decision by
CR103's owner); CR103 becomes the live vehicle; CR107 keep holding; CR109/CR133/
CR134/CR135 sequenced behind CR133 (deferred); CR123 split DEF-level-done from
CR124/125-open (governance action); CR140 shape = rolling 30 days, but its
FM-vs-Trader question reopened into a **credit-metered access model** ("We should
be using the credits") — needs a redraft pass before it's buildable, not resolved
today.

## 2026-08-10

Ran in-session (backtest-CR session; first session on/after 13:00 that day — triggered
at 20:48). `verify all` clean at start: 251 DEF rows / 158 CR rows, no drift. Scope:
full — 24 open Defects + 26 proposed CRs. Skipped per rule: CR022 (standing defer to
pre-release, 2026-07-31), CR122 (row self-instructs not to re-ask), CR134 (08-07 ruling
"fold into CR109's build" is visibly happening — 995a3008 pasted CR134's correction into
the CR109 slice-1 draft — logged as closed-by-action, row flip owed by its owner).

- **DEF100** (open since 07-24, RevenueCat/store billing, Saiful-liaison) — nagged, 12 days on → Saiful: "Still working on it"
- **DEF104** (open since 07-22, plaintext IMAP/SMTP credential) — re-asked (4th) → Saiful: "Keep deferring" (credential stays live)
- **DEF144** (open since 07-28, translation code-switching; 07-28 review said fix shipped) — asked flip-vs-keep → Saiful: "Still broken — keep open" (code-switching still seen since e294ed6/179ae1d; genuinely open, not a stale row)
- **CR017** (proposed since 07-10, multi-provider LLM routing) — 08-07 "start now" never executed; re-asked → Saiful: "Deprioritized again" (back to deferred)

Run interrupted by Saiful after batch 1 (batch 2 declined) — 4 of ~44 asked. Remaining
items (20 open DEFs incl. DEF178/DEF182 security pair, DEF230 no-APPROVE drought,
DEF251; proposed CR102/103/107/133/135/140, CR145–CR157, CR159–CR161) roll to the next
run's list untouched.

## 2026-08-12

Ran manually mid-session (Saiful: "lets go to the daily GTM list" — clarified via
AskUserQuestion to mean this routine after pointing at the command file). `verify all`
clean at start: 270 DEF rows / 166 CR rows, no drift. Scope: full — 20 open Defects +
21 proposed CRs. Skipped per rule: CR022 (standing defer to pre-release, 2026-07-31,
unchanged), CR122 (row self-instructs not to re-ask, unchanged), CR134 (08-10 already
logged closed-by-action — 995a3008 folded the correction into CR109's draft, row flip
still owed by CR109's owner; not re-asked).

- **DEF100** (open since 07-24, RevenueCat/store billing config, Saiful-liaison, 19 days) —
  re-asked → Saiful: "I am not sure I understand the problem, which is why i have not
  handled it. what is it that I needed to do?" — answered inline from the row: (1)
  RevenueCat dashboard — public SDK keys (iOS+Android) + webhook auth secret
  (`REVENUECAT_WEBHOOK_SECRET` in melehost `.env`); (2) 7 store products in App Store
  Connect + Play Console mapped to RC offerings/entitlements (`trader`/`floor_manager`
  subs + 3 credit consumables, exact SKUs/prices in the row); (3) Apple + Google paid-app
  agreements + banking. Code side (CR084) is done; this is store-identity/money setup
  only Saiful can do. Still open, unresolved this run — re-ask next time with this
  context already given.
- **DEF104** (open since 07-22, plaintext IMAP/SMTP credential, live) — re-asked (5th),
  flagged DEF204's new finding (a second divergent copy on melehost actively processing
  real customer email today, different hardcoded credential, trigger unidentified) →
  Saiful: "Keep deferring" (credential stays live; DEF204 asked separately below).
- **DEF144** (open since 07-28, translation code-switching) — re-asked (3rd) → Saiful:
  "Still broken, keep open" (unchanged from 08-10).
- **CR017** (proposed since 07-10, multi-provider LLM routing + caching) — re-asked after
  its 08-10 reversal → Saiful: "Start now, commit this time" — needs an actual lane this
  time, not another reversal.
- **CR102** (proposed since 07-27, in-app messaging to beta testers) — re-asked, row
  never flipped since the 08-07 "Drop it" ruling → Saiful: "drop it, and dont ask me
  again" — treating as a standing decision going forward (flagged for row flip below).
- **CR103** (proposed since 07-27, admin compose-tab UI for CR102) — re-asked → Saiful:
  "Yes, CR103 absorbs it" — confirms 08-07's reading, still owed a scope-merge + row
  flip by the owner.
- **CR107** (proposed since 07-28, agent icons vs letters, held since 07-29 pending
  DEF154) — re-asked → Saiful: "fire off a design research agent with the assignment
  to find the icons for each" — new instruction, not a hold/start answer; launched a
  background research agent (icon concepts per the 13-agent roster, checks DEF154's
  actual status) rather than logging a hold/start verdict.
- **CR133** (proposed since 07-30, bottom-nav restructure) — re-asked → Saiful: "Keep
  deferring" (unchanged from 08-07; CR109/CR135 stay queued behind it).
- **CR140** (proposed since 08-06, Portfolio Health cadence) — asked whether to draft
  the credit-metered redraft now → Saiful: "Keep holding" (no redraft yet).
- **DEF145** (open since 07-29, low severity, sim stop/target doesn't propagate to a
  linked Alpaca account, 0 users affected) — first ask, needs a design ruling (should
  AMI ever write to a linked external Alpaca account) → Saiful: "Keep deferring."
- **DEF178** (open since 07-30, SECURITY — live Adanos API key in git history on
  origin/main, quota-valid) — first ask, offered rotate-now/full-remediation/defer →
  Saiful: "Keep deferring" (live exposure stays live).
- **CR133** (proposed since 07-30, bottom-nav restructure + full YOU tab build) — re-asked
  3x with escalating clarification (asked which CR133 depends on — answer: none, it's
  the root, CR109/CR135 depend on it; confirmed full scope bundles Mandate/Journal/
  Insights, not just nav reorder; confirmed prototype exists — clickable prototype
  delivered, no Flutter written; explained why CR135 waits on it — needs a stable nav
  shell for the bell/badge, CR027 cut it live rather than build throwaway chrome) →
  Saiful: "Keep deferring. I am considering releasing 'game' as a separate app
  altogether." — new strategic consideration, not actioned, noted for future sessions.
- **CR135** (proposed since 07-31, in-app notification centre) — re-asked alongside
  CR133 per Saiful's request to see both together → follows CR133's "keep deferring"
  (stays queued; CR027's plumbing already shipped, only the browse/manage screen +
  bell/badge remain, waiting on a stable nav home).

## 2026-08-20

Review happened inline across the whole session rather than as a separate one-by-one pass —
Saiful was live all day and issued a blanket directive: **"Ok, lets build all the ones where I
am not the show stopper!"** A 26-CR classification sweep (workflow wf_9e58c791-30a, 5 read-only
agents, every claim verified in-tree) served as the review body; the specific asks and answers:

- **CR107** (agent icons, HELD) — asked: build the 13-icon program / font-floor-only / keep as-is?
  → Saiful: *"drop. agents will use english logos even in arabic"* → **dropped**
- **CR160** (agent rename) — asked: Social Media Analyst label, Flow & Positioning vs Sentiment
  & Flow? → Saiful: **"Flow & Positioning"** → sweep laned in wave 2
- **CR172** (options sim, D-register gate) — asked: D3 naked calls, forbid vs Reg-T margin?
  → Saiful: **"Forbid naked calls"**; other nine leans ratified; CR171 halal inform-not-block
  extended to sell-to-open → gate cleared, queued wave 3
- **Promotion operator gate** (alpha-2026-08-20-4) — asked per protocol → Saiful: "Yes, promote"

Dispositions that came out of the classification rather than a question (all row-recorded):
CR017 + CR188 effectively-done → **closed**; CR187 verified surfaced end-to-end → **closed**;
CR190 re-scoped (source reports were Floor-v0.2 reaction notes; residue = journal tour coverage)
→ **in_progress, wave 2**; CR102/CR103/CR120/CR129 built + closed this session; CR185 cycle run
live (DEF340–344 filed), unattended schedule blocked on the permission model → flagged to Saiful.

Still-blocked set left standing, each with its named blocker: CR004/CR036 (launch chores, Saiful),
CR022 (deferred-to-GTM ruling), CR024 (LunarCrush paid tier), CR049 (dashboard keys), CR084+CR198
(RevenueCat provisioning), CR123 (DEF178 vendor rotation), CR126 (GCP/Supabase), CR136 (device
passes), CR196 (GB10 run), CR159 (CR160 first + Saiful go-ahead), CR191 (horizontal-scale event),
CR194 (DEF305 lane), CR161 (Tier-1 prospect trigger), CR122+CR172 (queued wave 3, buildable).

Open defects: DEF340–344 filed today (routing recorded in their rows); DEF339 and the rest are
other tracks' or ride the blockers above. No status changed through this log (rows are the truth).

## 2026-08-21

Automated 0900 check-in (read-only sweep + `AskUserQuestion`). Yesterday's 26-CR classification
had already dispositioned the backlog, so only three items were genuinely undecided. All three
were put to Saiful inline; all three were answered and acted on in the same session.

- **CR185** (6-hourly bug monitor — the unattended schedule was blocked by the permission
  classifier) — asked: grant the rule / session-start check / both / stay manual?
  → Saiful: **"Both — scheduled job, session-start fallback"**. Shipped: `/bug-monitor`
  (`.claude/commands/bug-monitor.md`) as the cycle, `CLAUDE.md` step 2b as the >6h backstop, and
  five pre-approved commands in `.claude/settings.local.json` so a headless `/loop 6h /bug-monitor`
  no longer trips a prompt. The DB `status` column stays the shared watermark and the
  `AND status='open'` guard makes the flip idempotent, so the two paths cannot double-file.
  Remaining: arming the loop (one command); the fallback is live now.
- **DEF100 / CR084 / CR198 / DEF344** (RevenueCat — re-cut 2026-08-20 to the real-store-keys route
  after the Test Store proved dead) — asked: provision now / crash-fix only / both / defer the
  track? → Saiful: **"Defer the whole payments track"** until after the Beta cutover. All four rows
  carry a `[PAYMENTS TRACK PARKED — 2026-08-21]` marker; statuses unchanged (the register's status
  vocabulary has no `deferred`, and CR022 set the precedent of marking the description). **MVP M1
  is now blocked by decision, not oversight.** Flagged and not overridden: DEF344 is a live crash
  on the upgrade tap for anyone in the current cohort who taps it, and parking the track leaves it
  reproducible.
- **E5** (device-matrix verification — the sole open item on the Engagement close-out gate, open
  since 2026-07-25) — asked: book a session / narrow the matrix / hand to the melehost rig / waive?
  → Saiful: **"I can connect the phones to the Mac."** Shipped
  `CR004_release_readiness/e5_device_matrix_runbook.md`: cable-install commands per device, the
  off-LAN requirement, a delta checklist covering everything that shipped after the §A2 list was
  written (Floor v0.2 carousel, CR102 inbox, CR136 health, CR129 limits, CR187 resting orders,
  CR120 SHOW ALL, winzip 402, push, games), the five known-open defects not to re-file, and the
  gate-closure criterion. Linked from §A2.

No status flipped through this log — rows are the truth.

## 2026-08-22

Automated 0900 check-in (read-only sweep + `AskUserQuestion`). Two items were genuinely
undecided; both were answered inline.

- **`/bug-monitor` scheduling** — yesterday's ruling was "Both — scheduled job, session-start
  fallback", but the 6h loop was never armed and `git log --grep='docs(bug-monitor)'` returned
  nothing: **zero cycles had ever run**. Asked: run a cycle now / arm the loop / both / leave
  manual → Saiful: **"Run one cycle now, then arm the loop"**. The cycle ran: **0 open reports**
  in `bug_reports`, nothing filed, nothing flipped — the queue is genuinely clear, DEF340–344
  (2026-08-20) remain the last batch. On the arming half, `/loop` requires an explicit
  cloud-vs-session choice for any interval ≥60m; asked → Saiful: **"Just stop"**. **No loop is
  armed and no cloud schedule exists.** The operative path is the `CLAUDE.md` step-2b
  session-start backstop alone. CR185's "both" ruling is therefore half-implemented **by
  decision**, not oversight — and today's empty queue means the cost of that is currently zero.
- **CR134** (CR109 game screens vs the design system — 27 findings, conformance pass only, no
  redesign; `proposed` since 2026-07-30, never dispositioned in the 08-20 26-CR sweep, no named
  blocker) — asked: lane it with DEF343 / defer past dark launch / standalone / drop?
  → Saiful: **"Drop it"** → status **`dropped`** (`17e9be02`). The review and prototype stay on
  disk as the record of what was measured. DEF343 is unaffected — it is a presentation fix in
  the games lane.

Not asked, blockers unchanged and named: DEF305 (acute bleed already stopped in
`sim_resting_orders.py:128`; row stays open for the provenance column, CR194 sequenced behind
it), DEF321 (earliest defensible close 2026-08-24 — the bar is a week of greens, not a count),
the parked payments track (DEF100/CR084/CR198/DEF344), and E5 (Saiful's device time, ruled
2026-08-21).

**GTM pulse (CR036 §1):** active phase **Stealth Alpha distribution**; **Engagement close-out**
in progress with **E5 the sole open item** and no device pass logged since yesterday's runbook.
Beta (B1–B14) and MVP (M1–M12) unchanged at 0% started. No movement in the phase itself.

No status flipped through this log — rows are the truth.

## 2026-08-24

Session-start check (CLAUDE.md step 2) — last section was 08-22, so 08-23 and today were both
owed. Registers verified clean first (`gen_registers.py verify all`: DEF 365 rows, CR 201 rows,
content identical to live — no drift to self-heal). Working list: **17 open Defects + 8 proposed
CRs**. Per step 5, items carrying a standing disposition from the 08-20 classification sweep or the
08-21 check-in were **not re-asked** — they were carried forward with their blocker named:

- **DEF100 / DEF344 / CR084 / CR198** — `[PAYMENTS TRACK PARKED — 2026-08-21]`, unpark trigger is
  DEF100's provisioning. Unchanged.
- **CR022** — deferred-to-GTM ruling. Unchanged.
- **CR159** — needed CR160 first; **CR160 is now `done`**, so the only remaining gate is Saiful's
  go-ahead on whether the Floor re-band gets built at all ("may or may not be built", 08-09).
- **CR161** (Tier-1 prospect trigger), **CR191** (horizontal-scale event) — both wait on an external
  event, not on work. Unchanged.

**Register correction made in this run (not a status flip through the log — the rows were edited by
their domain owner and regenerated, per CLAUDE.md governance):** DEF340, DEF341 and DEF342 all
carried landed, guarded fixes from 2026-08-20 and still read `open`. Verified by running their
guards green (`finding_sections_test.dart::DEF340`, `def341_ticker_one_line_test.dart`,
`def342_brief_bottom_inset_test.dart` — 12 tests, all passing) before touching the rows. Flipped to
`fixed` in `eb8bf49e`. Same class as the CR136 sweep: the register had stopped describing reality.
**DEF343 and DEF339 were checked the same way and are genuinely unfixed** — only their filing
commits exist.

Asked and answered:

- **DEF204** (two divergent support-email processors on melehost, one auto-sending to real customers
  off an unidentified trigger, each with its own plaintext credential) — asked: kill it now /
  investigate first / you handle the mailbox / leave it? → Saiful: **"Leave it — it's working"**
  → DEF204 closes as **by-design**; the auto-replies are intended.
- **DEF178** (live Adanos key in git history — CR123's last hard blocker; rotation is a vendor
  action) — asked: rotate now / rotate later and work the rest / drop the integration?
  → Saiful: **"Rotate later — I'll work the rest"** → CR123's 11 Medium/Low items are mine to
  work now; the umbrella stays open on DEF178 alone, with Saiful named as its sole blocker.
- **The P18/DEF357 Dilemma** (DEF365 was the third instance inside CR172 alone; CLAUDE.md's
  third-occurrence rule fired) — asked: convene / guard is enough / write the brief only?
  → Saiful: **"Convene it — you may spawn agents"** → agents authorised for this Dilemma.
- **DEF362 / CR162** (iOS onboarding walk failed a second time after both its named blockers were
  fixed; a third failure is itself a Dilemma trigger) — asked: re-run once more / diagnose first /
  park CR162? → Saiful: **"Diagnose before re-running"** → read the failure artifacts and find the
  actual stopping point before spending a third run.

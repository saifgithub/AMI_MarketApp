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

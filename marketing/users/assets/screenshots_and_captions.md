# Screenshots and captions

**Status: DRAFT plan for capture. No screenshots taken yet.**

Six frames per platform. Store screenshots are the highest-leverage creative asset we have — most
store visitors decide from frames 1–3 without reading a word of the description.

Two rules govern the set:

- **Frame 1 sells the outcome, not the architecture** (`positioning_and_personas.md` Rule 1).
- **Frame 6 carries the disclaimer.** `store_compliance.md`'s App Review tips call for the
  disclaimer to be visible in at least one screenshot. Putting it last means it satisfies review
  without costing conversion on the frames people actually look at.

Captions are overlaid text, sentence case, one line, max ~7 words. Long captions get truncated by
the device frame and read as noise.

---

## The six frames

| # | Screen | Caption | Why this frame |
|---|---|---|---|
| 1 | **Convene the Room, mid-debate** — agents streaming, stances visible | `Thirteen specialists. One stock. Live.` | The product's single most demonstrable moment and the hardest thing for a competitor to fake. Nothing else earns the install as fast |
| 2 | **Room verdict board** — the CR106/CR120 verdict summary with the comb and stance chips | `You read the argument. You decide.` | Answers "so what happens at the end" and shows the user is the decider, not the app |
| 3 | **Portfolio Manager veto** — a trade refused against the user's own mandate, with the reason | `Your own rules, enforced.` | The proof the app is serious. This is the frame that converts Marcus (the burnt trader) |
| 4 | **Sharia verdict on a ticker** — compliant/non-compliant with the as-of date visible | `Screen your universe first.` | Shipped (N1), unique in the category, and the entry point for the whole halal channel |
| 5 | **Decision Journal entry, expanded** — a past call with its reasoning and the agents involved | `Every call. Every reason. Kept.` | The retention story made visible, and the answer to the chat-AI objection |
| 6 | **Lessons honeycomb** with the disclaimer band | `342 lessons. EN · AR · MS.` + disclaimer | Education-forward, closes the review requirement, and shows the content depth |

### Frame 6's disclaimer text

Legible at thumbnail size — small type that only resolves at full screen does not satisfy the
reviewer who is looking at the grid:

```
Educational simulation. Not investment advice. No real-money trading.
Market data delayed 15 minutes.
```

---

## What must not appear in any frame

Checked against `_facts/claim_register.md` before upload:

- **No profit or return figure anywhere on screen.** This is the one that will get us rejected.
  If the simulated portfolio in the capture account shows a large gain, **reset it or trade it
  down first** — a screenshot of a +40% simulated portfolio is a performance claim in the
  reviewer's eyes and in the user's, regardless of the word "simulated" underneath.
- No real-money, brokerage or "start trading" language.
- No feature from the FORBIDDEN block: no briefing screen (F1), no voice control (F2), no push
  prompt (F3), no share card (F4), no badge shelf (F5 — the table has 0 rows anyway), no credit
  purchase flow (F6).
- No "the AI" (F17). Any on-screen string saying that is a defect to file, not a caption to fix.
- No user count, leaderboard position implying scale, or "join N investors".
- **Frame 4 caution:** capture a ticker with a *definite* verdict, and never one showing
  `unknown`. An `unknown` state in a marketing screenshot is exactly the ambiguity DEF094 was
  filed to remove.

---

## Capture matrix

| Axis | Values |
|---|---|
| iOS | 6.9" (iPhone 17 / 16 Pro Max) — required. 6.5" if the console still asks for it |
| Android | Phone (1080×1920 min), plus 7" and 10" tablet if Play requires |
| Locale | EN first. AR (RTL — verify the whole layout mirrors and numbers do not, per CR120's bidi finding) and MS at v1.0 |
| Theme | Dark. It is the design language's default and the app's identity |
| Text scale | 1.0. Capture at 1.15 as a **check**, not for upload — if a caption or CTA clips at 1.15, that is a defect to file (the CR108 pattern) |

Saiful has both an iPhone 13 and an iPhone 17, so the 6.9" set is capturable today from a release
build (`flutter build ios --release` + `flutter install` — never a debug build; debug banners and
frame-rate overlays have shipped into store assets before at other companies and it is not a
recoverable mistake).

---

## Capture account setup

Do not screenshot a real user's data. Create a dedicated capture account:

1. Fresh anonymous account, then run onboarding to set a mandate that is **interesting but
   plausible** — moderate risk, long-only, Sharia flag **on** (frame 4 needs it), one ethical
   exclusion on.
2. Populate a small portfolio: 3–4 holdings, mixed small gains and losses, **no large gain**
   (see above), realistic cash balance.
3. Run 2–3 Rooms so the journal has content for frame 5, and so frame 1 can be captured
   mid-stream.
4. Attempt one trade that violates the mandate, so frame 3 has a genuine veto with a real reason
   rather than a staged one.
5. Pick well-known tickers. AAPL is on the compliant list (216-name snapshot) so it works for
   frame 4; a recognisable non-compliant name makes the contrast clearer.

---

## Also closes two open `docs/WEBSITE.md` items

Both have been open since CR049/CR072 and both are blocked on exactly this capture session:

| Open item | What this session produces |
|---|---|
| **Lessons-comb screenshot** — wanted for a fourth `#app-preview` frame on the website | Frame 6 |
| **Designed og-image** — a PIL-generated stopgap is live, reading "13 AI agents. One decision." | A designed 1200×630 built from frame 1 or 2, **re-led on outcome** rather than agent count (Rule 1). The current stopgap's line is the builder-first hero this plan is replacing, so the og-image and the hero should change together |

The website's `#app-preview` section currently uses iPhone frame placeholders. Frames 1, 2, 4 and
6 replace them — see `landing_page_changes.md`.

---

## Sequence

1. Build release, install to device.
2. Set up the capture account per above.
3. Capture all six frames, EN, dark, 1.0.
4. Re-capture at 1.15 as a clipping check only. File defects for anything that clips.
5. Add caption overlays in the AMI palette. Type must be legible in the store's thumbnail grid.
6. Run the "must not appear" list against every frame before upload — particularly the portfolio
   gain check and frame 4's verdict state.
7. Export the og-image and the four website `#app-preview` frames from the same set, so the store
   and the site tell one story.

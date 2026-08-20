# Lifecycle copy — email and push

**Status: DRAFT, and mostly DARK. Neither channel exists yet.**

| Channel | State |
|---|---|
| Push | **Not built** (F3). No OneSignal or FCM anywhere in `mobile/lib`. Blocked on Saiful's OneSignal account + APNs cert (A15/A16) |
| Email | Resend is configured and working, but `email_service.py` implements **only** `send_magic_link`. There is no lifecycle sender |

This is drafted now so that the day either channel lands, the sequences ship the same day instead
of becoming a fresh writing project. It is Gate C in `user_acquisition_plan.md` §2 — **a funnel
with no return path wastes every dollar spent at the top of it.**

## The rule that governs every message here

**Point at the user's own receipts, never at a feature.**

`positioning_and_personas.md` Rule 2 establishes that AMI Trade beats a chat AI on memory,
disagreement and receipts. A re-engagement message that says "check out our new lessons" throws
away all three. One that says "your last call is up 4% — the Bear said this would happen" uses all
three, and it is the only kind of message this product can send that a chat AI could not.

Every draft below is written to that rule. Any future message that fails it should be rewritten,
not shipped.

## Compliance floor for every message

Both channels are user-facing, so `_facts/claim_register.md` applies in full:

- **AMI, never "the AI"** (F17).
- **No returns, gains, performance or forecast claims** (F13). Reporting a user's *own* simulated
  position change is a statement of fact about their simulation, not a performance claim — but the
  word "simulated" appears whenever a number does, and we never aggregate it into a claim about
  outcomes.
- **No advice, recommendations, signals or picks** (F14). A notification saying "AMI recommends
  reviewing NVDA" is a signal. "Your NVDA position moved; your journal entry is here" is not.
- Push copy still has to be honest at 40 characters, which is where most of these go wrong.

---

## 1. Welcome — email, immediate

Trigger: account claimed with an email address.

**Subject:** `You've got thirteen analysts. Here's how to use them.`

```
You're in.

Your team is thirteen specialists: four analysts on fundamentals, market technicals, news and
sentiment; a bull researcher and a bear researcher who argue; three risk analysts who each
take the position size apart differently; a trader; a portfolio manager who can refuse your
trades; and AMI, who runs the place.

They already know your mandate — the goals, horizon and limits you set during onboarding. So
when they argue about a stock, they're arguing about your portfolio, not a hypothetical one.

Three things worth doing this week:

1. Convene the room on a stock you already have an opinion about. See whether the bear finds
   something you missed.
2. Disagree with someone. Open a one-to-one with whichever analyst you think is wrong and make
   them defend it.
3. Submit a trade that breaks your own risk limits, on purpose. Your portfolio manager will
   refuse it and tell you why. That's the feature, not a bug.

Everything is simulated. No real money, no brokerage, nothing at risk except being wrong in
front of an audience of thirteen.

— AMI

You're on the Floor Pass. Market data is delayed 15 minutes. This is an educational
simulation, not investment advice.
```

---

## 2. Mandate not set — push + email, 24h after install

Trigger: `app_open` happened, `mandate_set` did not.

The highest-value nudge in the set. Without a mandate, every agent is generic — which means the
user is holding a worse version of the chat AI they already have for free.

**Push** (40 char headline / 120 body):

```
Your team doesn't know you yet
Three minutes of questions and every analyst starts working from your rules.
```

**Email subject:** `Your analysts are guessing`

```
You've got the team, but they don't know what you're trying to do — so right now they're giving
you generic answers. That's the version of this you can get for free anywhere.

The onboarding interview takes about three minutes. Goals, time horizon, how much risk you can
actually live with, and any constraints — long-only, no fossil fuels, Sharia screening.

After that, every one of the thirteen argues from your rules. Your portfolio manager enforces
them. That's the whole difference.

Pick up where you left off →
```

---

## 3. First Room prompt — push + email, 48h after mandate set

Trigger: `mandate_set` happened, no `room_completed`.

**Push:**

```
Pick a stock. Watch them argue.
Your first room debate takes about two minutes. Thirteen analysts, one verdict, your call.
```

**Email subject:** `You haven't watched them argue yet`

```
Lessons teach you concepts. The room teaches you how a decision actually gets made — and it's
the thing this app exists for.

Pick any stock. Your four analysts report, your bull and bear researchers fight about it, the
three risk analysts test the size, and your portfolio manager decides. Two minutes,
start to finish, and you read all of it.

Then you make the call, and AMI keeps the record.

Convene your first room →
```

---

## 4. Trial day 5 — email

Trigger: day 5 of the 7-day Trader trial.

The honest framing is the differentiator here. **There is no auto-bill at expiry** — say so,
because nobody expects it.

**Subject:** `Two days left — and we won't charge you`

```
Your Trader trial ends in two days. When it does, nothing happens: no charge, no card, no
"we've started your subscription." You go back to the Floor Pass and keep everything you've
built.

If you want to keep the full team, you'll have to tell us. We'd rather ask than surprise you.

What you've used so far:
· [N] room debates
· [N] one-to-one conversations
· [N] journal entries

What goes back to the free tier: the full thirteen-agent team, unlimited sessions, and full
journal history.
```

**The bracketed counters must be real or absent.** A "0 room debates" line is more useful than a
fabricated number — it tells us the trial failed and tells the user honestly. Never seed these
with plausible values.

---

## 5. Trial day 7 — email

**Subject:** `Trial's over. Nothing was charged.`

```
Your Trader trial ended today and we didn't charge you, because we said we wouldn't.

You're back on the Floor Pass. Your journal, your mandate, your portfolio and your streak are
all still there — nothing was deleted.

If the full team was worth it, it's one tap. If not, the free tier stays free, permanently.
Either way you keep what you wrote.
```

---

## 6. Cooldown re-engagement — push

Trigger: the live `GTM_FUNNEL=winzip` cooldown expires.

The best-timed message in the set: a user who hit the cooldown wanted another Room. This just
tells them they can have it.

**Push:**

```
Your room is available again
Pick a stock. Thirteen analysts are waiting.
```

Keep it factual. This moment is also the upgrade prompt, and a hard sell here reads as a paywall
ambush — the app already handles the upsell in-product, so the notification's only job is to bring
the user back.

---

## 7. Dormant at 14 days — email

Trigger: no `app_open` for 14 days, and the user has at least one journal entry.

**The receipts message.** Only this product can send it.

**Subject:** `Your last three calls, two weeks on`

```
You made three calls before you stopped opening the app. Here's what happened to them:

· [TICKER] — [your call], [simulated position change] since
· [TICKER] — [your call], [simulated position change] since
· [TICKER] — [your call], [simulated position change] since

You wrote down why you made each one. That's the part that's worth coming back for — in six
months, that record is the only honest account of how you actually think under uncertainty.

Read your journal →

Simulated portfolio. Market data delayed 15 minutes. Not investment advice.
```

**Hard rule:** report what the user's own simulated positions did, and nothing else. Do not
aggregate into a score, do not compare to an index, do not congratulate. The moment this message
says "you're up 12%, nice work" it becomes a performance claim (F13) and a gambling loop, and it
stops being the thing that makes this product different.

If a user has no journal entries, they do not get this message — they get §3 again.

---

## 8. Dark until the mechanic ships — share card

**Blocked on F4.** No share mechanic exists; `share_plus` is a dependency with nothing behind it.
`user_acquisition_plan.md` §10 proposes a Room-verdict share card as the cheapest referral
mechanic.

Drafted so it is ready:

**In-app prompt, after a Room reaches a verdict:**

```
Send the argument
Thirteen analysts just disagreed about [TICKER]. Share the verdict card.
```

**Share card content:** ticker, the verdict, the split (how many agents took which side), the
date, and — baked into the image, not a caption — `Simulated. Educational. Not advice.`

**Do not include** the user's P&L, position size, or any figure that reads as a result. The card
shares the *argument*, which is the interesting part and the safe part. A card showing a gain is a
performance claim in a format designed to be forwarded.

---

## Message inventory

| # | Trigger | Channel | Blocked on |
|---|---|---|---|
| 1 | Account claimed | Email | Lifecycle sender |
| 2 | No mandate at 24h | Push + email | Push (F3) + sender |
| 3 | No Room at 48h | Push + email | Push (F3) + sender |
| 4 | Trial day 5 | Email | Sender + real counters |
| 5 | Trial day 7 | Email | Sender |
| 6 | Cooldown expiry | Push | Push (F3) |
| 7 | Dormant 14d | Email | Sender + journal data in the payload |
| 8 | Room verdict | In-app | Share mechanic (F4) |

Seven of eight are blocked on Gate C. That is the argument for closing it — the copy is written,
the triggers are defined, and the only missing piece is the pipe.

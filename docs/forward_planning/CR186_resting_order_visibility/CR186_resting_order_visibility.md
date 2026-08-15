# CR186 — the waiting-order card says what the order actually is

**Filed:** 2026-08-15 (AT:R70) · **Status:** in_progress · **Follows:** CR170, DEF309

Saiful, reviewing the resting-order journey end to end: *"How are we recording it, and how are we
showing it to the user while the user waits for it to be fulfilled. We need to see all these
'delayed action' transactions are displayed to the user."* And on the scope call: *"This is a very
important part of the trading simulation as it covers how a real brokerage house works."*

---

## Why

The recording half of CR170 is complete and correct. The **display** half stops one field short of
telling the user what they placed.

The card rendered `side · quantity · ticker · one price · state chip · distance`. Three facts the
model already carried never reached a pixel:

| Fact | On the model since | Rendered |
|---|---|---|
| `orderType` | CR170-FE | no |
| `limitPrice` on a **stop-limit** | CR170-FE | no — only the trigger showed |
| `expiresAt` / `tif` | CR170-FE | no |

### 1. A buy limit and a buy stop at the same price were the same card

They are opposite orders. CR170's own Rule 1 table:

|  | rests **below** | rests **above** |
|---|---|---|
| **BUY** | buy limit — buy the dip | buy stop — breakout entry |
| **SELL** | sell stop — stop-loss | sell limit — take profit |

`BUY 10 AAPL @ $190.00 · waiting` describes both. The one fact that distinguishes them was stated
once — in the ticket's live hint at placement, which CR170 §9 itself calls *"the highest-value
element in the feature"* — and then discarded the moment the sheet closed. A user returning a day
later to a book of four orders could not tell which way any of them were pointing.

### 2. A stop-limit hid the price that decides whether it ever fills

`namedPrice` returns the **trigger** for a stop-limit, and the card showed only that. But the
limit is the half that fails: CR170's worked example — *price gaps to $85 → triggers → sell limit at
$88 → rests, never fills* — is the classic stop-limit failure and, per the CR, **the reason the type
is in the curriculum**. The simulator reproduces it faithfully and then declined to show the user the
number it turns on.

### 3. Nothing said when an order dies

A DAY order retiring at the next session close and a 90-day order rendered identically. "Why did my
order disappear overnight" had no answer anywhere on the screen — and the expiry is not local
midnight, it is a **US market session close**, which for a user in Riyadh or Kuala Lumpur is
routinely a different day than the one they would guess.

### 4. A closed order had no date at all

`filled_at` existed; cancelled, expired and rejected orders carried no timestamp whatsoever. That is
**DEF309**, fixed alongside this — the group is headed RECENTLY CLOSED and could not say when.

---

## What

Client-render only. No new endpoint, no new backend field beyond DEF309's `retired_at`, no change to
placement, cancellation, the sweep, or any number that moves money.

**Line 2 of the card is new** — the type tag, then what this order is waiting for:

```
↓ BUY 10 AAPL @ $190.00                            [WAITING]
LIMIT  waits for a fall to $190.00
2.5% away · expires today 11:00 PM      [CANCEL ORDER]
```

```
↑ SELL 10 NVDA @ $90.00                            [WAITING]
STOP-LIMIT  waits for a fall to $90.00, then a limit at $88.00
1.1% away · expires in 87d              [CANCEL ORDER]
```

```
↓ BUY 10 AAPL @ $190.00                            [REFUSED]
LIMIT
refused · 3h ago
AAPL is on your blocklist
```

### Decisions taken while building it

- **The waiting clause reuses `restsBelow`**, the same pure predicate the ticket's live hint runs on,
  rather than a second switch over four cases. Two derivations of one directional rule is the DEF098
  shape, and here it would show as the book describing an order differently from the sheet that
  placed it.
- **It does not repeat the ticker or quantity.** Both are on the line above; the ticket's own hint
  strings were the obvious thing to reuse verbatim and would have read `BUY 10 AAPL @ $190.00 /
  Waits until AAPL falls to $190.00` — the same two values three times.
- **A triggered stop-limit stops describing its trigger.** It is no longer waiting for that price,
  and *"waits for a fall to $90.00"* on an order that already fell to $90.00 is the one sentence on
  the card that would be actively false. It becomes *"triggered — now a limit at $88.00"*.
- **An unrecognised order type names no type**, matching `simOrderTypeFromWire`'s existing refusal to
  fall back to `market`. Naming a type the order does not have is worse than naming none when the
  candidates behave oppositely (DEF210's shape).
- **No simulation mechanics.** Saiful, 2026-08-11: *"we do not need to explain the simulation rules to
  the user. thats our internal decision."* Everything added here is a property of **this user's own
  order** — its type, its two prices, its death date — not of how the simulator works. No polling
  cadence, no fill-price rule, no fill-in-full note.
- **Expiry renders the local clock time inside 24h**, days beyond it. `TimeOfDay.format(context)`
  rather than a hand-rolled string, so 24h/12h clock follows the device.
- **Absence renders as absence.** No `expiresAt`, no expiry line; no `retiredAt`, no date. Never a
  zero, never a guess — the same rule `last_seen_price` already follows with *"waiting for the first
  price check"*.

---

## Acceptance

1. A buy limit and a buy stop at the **same price** render visibly different cards, and each names the
   direction it waits in.
2. All four side/type combinations name the correct direction — the diagonal (buy-limit ≡ sell-stop,
   buy-stop ≡ sell-limit) holds.
3. A stop-limit shows **both** prices; a triggered stop-limit shows only the limit and does not claim
   to be waiting for its trigger.
4. A DAY order and a 90-day order render visibly different expiry text; an order with no `expires_at`
   renders no expiry line.
5. A closed order is dated from `retired_at`, and one from a server predating DEF309 shows no date
   rather than a wrong one.
6. An unrecognised order type names no type.
7. `flutter analyze` 0 errors; l10n key parity green across all three locales.

## Verification

`mobile/test/screens/sim/cr186_order_card_test.dart` — 15 widget tests, every one asserting on
**rendered text**. That is deliberate: all three facts were already on the model and none reached a
pixel, so a test that stopped at the model would have passed against the defect this CR fixes.

## Translation

14 new keys × 3 locales. `retranslate:[ar,ms]` — the AR and MS values are English placeholders, as
CR170's own resting-order keys still are.

## Not in scope

- **The fill notification** — CR187. The card is what the user sees when they look; the notification
  is what reaches them when they do not.
- **Any surface outside Portfolio → Positions.** A nav badge or count is CR133's territory.
- **Any change to placement, the ticket, the sweep, or a price.**

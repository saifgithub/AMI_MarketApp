# CR188 — one position, one exit

**Filed:** 2026-08-15 (AT:R70) · **Status:** in_progress (slice 1 complete) · **Follows:** CR186, CR187, DEF309–DEF313

Saiful, after tracing the sell paths end to end: *"make it less complex for the customer. thats too
many paths."* Proposal artifact reviewed and approved before any code was written.

---

## Why

The app shows the same position twice, and each view grew its own exit.

A user who bought 10 AAPL in two lots sees **one HOLDINGS row** and **two OPEN TRADES rows** for the
same shares, plus a WAITING ORDERS card if they set a stop. Four lists on one tab, three describing
the same position. Three ways to sell followed:

| exit | acts on | mechanic |
|---|---|---|
| CLOSE POSITION (Ticker Detail) | trade rows | market only |
| `×` on a row in OPEN TRADES | one trade row | market only |
| trade ticket, side = SELL | shares | market or resting |
| stop / target at entry | trade row | automatic (stays — it is protection, not a path) |

`manual_close` and the bracket act on a **trade row**; a resting sell acts on **shares**. That split
is what produced DEF311 — closing a position left its stop-loss resting, and the stop then opened a
short.

---

## Slices

**Slice 1 — the ticket. COMPLETE.** Self-contained, no screen restructuring, and where a user
currently loses money to a surprise.

**Slice 2 — one exit.** A SELL action on the position that opens the ticket prefilled; delete CLOSE
POSITION and the `×`. Three paths become one. Not started.

**Slice 3 — the collapse.** Merge HOLDINGS and OPEN TRADES into one row per ticker; pending orders
become row attributes; CR186's card becomes the detail view; closed orders move to HISTORY. Not
started — and deliberately last, because slices 1 and 2 stand on their own.

---

## Slice 1 — what shipped

The ticket did one of three different things on a SELL — reduce a holding, refuse, or **open a short
with uncapped loss** — decided entirely by a number that appeared nowhere on the sheet. The quantity
field defaulted to `1`, nothing named the holding, and the only mention of the word "short" arrived
in the snackbar *after* the position existed.

| state | the sheet now says | button |
|---|---|---|
| you hold it | *You hold 10 AAPL — selling 10 closes that much of the position.* | SUBMIT TRADE |
| you hold fewer than typed | the CR171 cross-zero refusal, unchanged | disabled |
| you hold none | *You hold no TSLA. This opens a short — you borrow the shares now and buy them back later, and the loss is not capped.* | **OPEN SHORT**, amber |

Plus: **SELL prefills the quantity from your holding** instead of `1`, and **DEF312's long-bracket
refusal** now runs on the client.

### Decisions worth not re-litigating

- **The button's LABEL is the structural half, not its colour.** CR171 already had the words and
  fires them *after* the fill via `_pendingAdvisories` — correct for the borrow-cost advisory, wrong
  for "this is a different kind of position than you think you are opening". A word on the control
  being pressed is structural; a sentence above it is an instruction, and this project's own rule is
  that instructions are not controls. The first attempt changed only the colour; the test that
  catches that is in the file.
- **The notice occupies the refusal's slot, not a second one.** They are mutually exclusive, and the
  last thing read before the button should be one sentence about this order.
- **Prefill only ever fills DOWN from a holding.** A ticker with nothing held is left alone rather
  than pre-loaded with a short the user never asked for, and switching back to BUY does not touch the
  field.
- **A sell that CLOSES a long is not bracket-checked**, matching the server exactly: an exit carries
  no bracket of its own, which is the same reason `bracket_hit` branches on what the *position* is.
- **`_localRefusal` stays one function** feeding both the panel and the CTA's enabled-state. A
  disabled button with no sentence is a dead control; a sentence over a live button is an instruction
  the user can ignore.

### The DEF312 half, and why it was invisible

`short_rules.dart`'s `stopIsWrongSide`/`targetIsWrongSide` have taken an `isShort` flag and handled
the long case **correctly** since CR171. They were called behind
`if (intent != SellIntent.opensShort) return null`, after `_localRefusal` had already returned early
on every buy — so the long branch existed, was right, and was unreachable. **P21.** The server had
the identical hole (`short_bracket_is_wrong_side` called only from `_open_short_fill`), which is why
reading either side made the rule look covered.

---

## Acceptance (slice 1)

1. Selling a held ticker names the holding and the button does not say SHORT.
2. Selling a ticker with nothing held says *short* **before** submit, and **the button says it**.
3. A buy never claims to be a short.
4. Crossing zero is still the refusal, and the notice does not also render — one sentence, never two.
5. Flipping to SELL fills the quantity from the holding; a ticker with nothing held is untouched.
6. A long with its stop at or above entry, or its target at or below, is refused on the client.
7. A correct long bracket says nothing, and an unset one is not a violation.

## Verification

`mobile/test/screens/sim/cr188_ticket_states_test.dart` — 10 widget tests, all asserting on rendered
text and on the **button's own label**, read off the widget tree rather than cast from
`ElevatedButton.icon`'s private child type.

Full suites: **Flutter 1,098 passed**, `flutter analyze` 0 errors (10 info, baseline).

## Translation

5 new keys × 3 locales, `retranslate:[ar,ms]`.

## Not in this slice

- Slices 2 and 3 above.
- Any change to placement, the sweep, the safety floor, or a price.

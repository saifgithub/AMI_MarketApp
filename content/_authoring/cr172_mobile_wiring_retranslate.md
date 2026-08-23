# CR172 mobile wiring — ARB strings awaiting AR/MS translation

**Filed 2026-08-23 (AT:R74).** Seventeen new keys landed in `mobile/lib/l10n/app_en.arb`
with the Room→ticket→re-price→open consent flow. All seventeen are seeded into
`app_ar.arb` and `app_ms.arb` **as English**, with their `@@x-ami-seeds` hashes recorded —
so `translate_arb.py` sees them as untranslated placeholders, not as finished work, and
the DEF137 parity guard passes without anyone pretending the strings are localised.

`retranslate:[ar,ms]`

| key | EN |
|---|---|
| `optionRepriceHeading` | THE PRICE MOVED |
| `optionRepriceHeadingUnchanged` | PRICE CONFIRMED |
| `optionRepriceSubheading` | AMI re-priced this against the live chain before opening it. Confirm the figures below. |
| `optionRepriceThen` | WHEN AMI PROPOSED |
| `optionRepriceNow` | NOW |
| `optionRepriceAged` | The price you were shown was {age} old. |
| `optionRepriceAgeMinutes` | ICU plural, minutes |
| `optionRepriceAgeSeconds` | ICU plural, seconds |
| `optionRepriceSpotLabel` | {ticker} PRICE |
| `optionRepriceConfirmCta` | OPEN AT THIS PRICE |
| `optionRepriceCancelCta` | DON'T OPEN |
| `optionRepriceFailedHeading` | AMI CANNOT PRICE THIS RIGHT NOW |
| `optionRepriceFailedBody` | Nothing was opened and nothing was charged. AMI will not fill a structure it cannot price. |
| `optionRepriceRefusedHeading` | THE FLOOR NOW REFUSES THIS |
| `optionVerdictAcceptCta` | REVIEW THE STRUCTURE |
| `optionVerdictCaption` | AMI costed this structure. You decide yes or no. |
| `optionOpenedConfirmation` | {strategy} opened · {cost} |

## Two that need a translator's judgement, not a literal rendering

- **`optionRepriceHeadingUnchanged` — "PRICE CONFIRMED".** This is shown when the
  re-price came back at the *same* figures. It must not read as "your order is
  confirmed" in AR or MS: nothing has been opened at that point, and the user still has
  to press the button below it. It means *the price was checked and it held*.
- **`optionRepriceCancelCta` — "DON'T OPEN".** Deliberately not "cancel". The user is
  declining a specific action they have just been quoted a price for, and "cancel" in
  several UIs means "close this sheet", which is a different thing from "do not take
  this trade".

Two ICU plurals (`optionRepriceAgeMinutes`, `optionRepriceAgeSeconds`) must keep their
plural forms — AR has six categories and the guard checks the form survives, not just
the placeholder.

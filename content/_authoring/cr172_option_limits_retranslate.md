# CR172 §9 — option limit settings: AR/MS retranslation required

**Filed:** 2026-08-24 (AT:R74) · **CR:** CR172 · `retranslate:[ar,ms]`

8 new EN keys in `mobile/lib/l10n/app_en.arb`, seeded into `app_ar.arb` and
`app_ms.arb` with `@@x-ami-seeds` hashes (`sha256(en_value)[:12]`).

| Key | EN |
|---|---|
| `settingsOptionPremiumCapLabel` | Option premium at risk |
| `settingsOptionPremiumCapExplain` | The most you can have paid for options at once… |
| `settingsOptionNotionalCapLabel` | Option contract size |
| `settingsOptionNotionalCapExplain` | How much stock your options control… |
| `settingsAssignmentCapLabel` | Assignment exposure |
| `settingsAssignmentCapExplain` | The cash you would need if every option you sold were exercised… |
| `settingsMinDteLabel` | Shortest time to expiry |
| `settingsMinDteExplain` | AMI will not open an option expiring sooner than this… |

## Four that need a translator's judgement

These are risk controls. A user who misreads one misjudges their own exposure,
and in three of the four cases the plausible mistranslation errs toward
*feeling safer than you are* — the dangerous direction.

1. **`settingsAssignmentCapExplain`** — the closing clause, *"It is not money
   set aside — it is money you could be asked for"*, is the whole control.
   Collateral IS set aside; assignment exposure is not. A rendering that reads
   as "money held" tells the user their risk is already funded when it is not.
   Do not compress this sentence away.

2. **`settingsOptionNotionalCapExplain`** — likewise the second sentence. The
   entire reason this control exists is the gap between what an option *costs*
   and what it *controls*: $910 of premium standing behind $19,500 of stock. A
   translation that keeps only the first sentence describes a number without
   saying why anyone would cap it.

3. **`settingsOptionPremiumCapExplain`** — *"lose value as they age"* is
   deliberately not the word **theta**. This is the setting where a beginner
   most needs the idea rather than the term of art. Use plain language in the
   target language too, not the transliterated Greek.

4. **`settingsMinDteExplain`** — *"no time to be right"* is a specific idea, not
   a statement about speed: the position can be correct about direction and
   still expire worthless. Render the meaning. This is also the one option
   limit where a **lower** number is the riskier setting, so any translation
   implying "smaller is safer" inverts the control.

## Note on the absent two

`max_portfolio_delta` and `max_portfolio_vega` are **not** here. D5
(2026-08-24) deferred them: they need full-portfolio greek aggregation that
does not exist. No strings were written for them, deliberately — a label for a
control that cannot be enforced is the half-wired state DEF191 forbids.

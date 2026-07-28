# DEF137 — translation packet: 24 keys missing from `ar` + `ms`

**What this is.** A translator-ready handover for the 24 strings that exist only in
`mobile/lib/l10n/app_en.arb`. Nothing here needs a Flutter developer to act on it — the EN text,
the placeholder contract and the on-screen context are all below. Hand this file (or the table in
§3) to a translator; the return is 24 AR strings + 24 MS strings.

**Measured** on `main` @ `9c4b74e`, 2026-07-28, by key-set difference — not by eye:

| Locale | Non-metadata keys | Missing vs `en` |
|---|---|---|
| `app_en.arb` | **470** | — |
| `app_ar.arb` | **446** | **24** |
| `app_ms.arb` | **446** | **24** |

The two missing sets are **identical**, so one packet serves both locales.

Reproduce:

```bash
cd mobile && ../backend/.venv/bin/python -c "
import json
en=json.load(open('lib/l10n/app_en.arb')); ar=json.load(open('lib/l10n/app_ar.arb'))
print(sorted(k for k in en if not k.startswith('@') and k not in ar))"
```

---

## 1. Why these are user-visible and not a scheduling note

The locked decision is **EN at alpha, AR + MS at v1.0**, so an incomplete AR/MS set does not violate
the alpha contract. What makes this a defect is that the locales are **already reachable in the
shipped binary**:

- `mobile/lib/app.dart:50` advertises all three in `supportedLocales`.
- `mobile/lib/screens/settings/settings_screen.dart:736` calls `.setLocale(opt.locale)` from a
  user-facing picker.

Flutter's delegate falls back **per key** to the template locale, so the widget renders English
inside an otherwise-Arabic screen rather than failing. That is a silent degrade — the exact shape
CR040 ("degrade loudly") exists to prevent — and there is no test, lint or CI step comparing locale
key sets, which is how 24 accumulated across five CRs unnoticed.

**Sharpest cluster: CR090.** Those keys are a paywall-adjacent disclosure explaining a credit
surcharge. Untranslated, an Arabic user is charged extra and reads the reason in the wrong language.

---

## 2. Two keys are NOT string swaps — read this before handing anything over

### 2.1 `roomAgentWithheldRosterNote` — ICU plural on an `int`

```
Next roster change: {agent} in {days, plural, =1{1 day} other{{days} days}}.
```

English needs **two** plural categories. **Arabic needs six** — `zero`, `one`, `two`, `few`, `many`,
`other`. Malay needs **one** (no grammatical number). A translator handed only the *rendered*
English ("in 3 days") cannot reconstruct the ICU form, and a returned flat string will silently
produce wrong agreement for Arabic 1, 2, 3–10 and 11+.

Give the translator the **ICU skeleton**, and expect back:

```jsonc
// ar — all six categories required
"roomAgentWithheldRosterNote": "…{days, plural, zero{…} one{…} two{…} few{…} many{…} other{…}}…"
// ms — a single form is correct, not a shortcut
"roomAgentWithheldRosterNote": "…{days, plural, other{{days} …}}…"
```

**Semantic trap, from the key's own description:** this is a **roster-level** countdown, identical on
every locked chair. It names the next *upcoming pull-back* — some **other** analyst going dark. It
must never read as "this analyst comes back in N days"; an analyst never un-withholds without an
upgrade. Arabic and Malay renderings must preserve that direction.

### 2.2 `portfolioSectorBreach` — three placeholders under RTL

```
{sector} at {pct}% exceeds your {limit}% mandate limit
```

Placeholder **order is not safe to assume** once the paragraph is RTL. Translators may reorder
freely — the names are what bind, not the position. Both `{pct}` and `{limit}` arrive
**pre-formatted** as percentages; do not add or move the `%`, and do not localise the digits in the
placeholder (the value is already a formatted `String`).

### 2.3 General placeholder rule

Every other placeholder below is an already-formatted `String` — dates, prices, share counts, P&L all
arrive with their sign, currency symbol and decimals applied. `{surcharge}` is the one plain `int`.
Translators reposition placeholders; they never reformat what is inside one.

---

## 3. The 24 keys

### Portfolio — sector allocation (CR026 / CR100) · 3 keys

| Key | EN | Placeholders | Context + constraints |
|---|---|---|---|
| `portfolioSectorAllocationHeading` | `SECTOR ALLOCATION` | — | Heading above the sector-allocation donut. All-caps is a **design-language** convention (AMI hex); render per locale convention — Arabic has no case, so weight/size carries the emphasis. |
| `portfolioSectorBreach` | `{sector} at {pct}% exceeds your {limit}% mandate limit` | `sector`, `pct`, `limit` (all `String`) | Warning under the donut when `compliance.compliant` is false. See §2.2. `{sector}` is never "Other". |
| `portfolioSectorOtherLabel` | `Other (unclassified)` | — | Legend label for the backend's "Other" bucket (no resolved sector). **Never a warning/red state** — this bucket is disclosed but never counts as a breach (DEF059 inversion guard). Keep the tone neutral in translation. |

### Ticker Detail — cost-basis lots (CR029 / CR100) · 9 keys

| Key | EN | Placeholders | Context + constraints |
|---|---|---|---|
| `tickerDetailLotsHeading` | `COST BASIS LOTS` | — | Section heading above the per-lot cards; shown only for a held ticker. |
| `tickerDetailLotEntry` | `Opened {date} @ ${price}` | `date`, `price` (`String`) | Entry line on a lot card. **The `$` lives in the string, not the placeholder** — keep it adjacent to `{price}` in whatever order the locale wants. |
| `tickerDetailLotQuantity` | `{open} open / {closed} closed` | `open`, `closed` (`String`) | Formatted share counts. The `/` is a separator, not a fraction. |
| `tickerDetailLotRealised` | `Realised {pnl}` | `pnl` (`String`) | Already carries sign and `$`. |
| `tickerDetailLotUnrealised` | `Unrealised {pnl}` | `pnl` (`String`) | Shown only when the price is known. Already carries sign and `$`. |
| `tickerDetailLotUnrealisedUnknown` | `Unrealised —` | — | Replaces the above when `unrealised_pnl` is null. **The em dash marks the value as absent and must survive translation** — it must never become `0`, `$0.00` or an empty string. |
| `tickerDetailLotStatusOpen` | `OPEN` | — | Status chip, fully-open lot. Short — chip width is tight. |
| `tickerDetailLotStatusClosed` | `CLOSED` | — | Status chip, fully-closed lot. Short. |
| `tickerDetailLotStatusPartiallyClosed` | `PARTIAL` | — | Status chip, partially drawn down (some shares sold/stopped, some open). Short. |

### Ticker Detail — dividend chip (CR030 / CR100) · 2 keys

| Key | EN | Placeholders | Context + constraints |
|---|---|---|---|
| `tickerDetailDividendExDate` | `ex-div {date}` | `date` (`String`) | Sub-chip beside the earnings pill. `{date}` is pre-formatted (e.g. `Aug 15`). "ex-div" is an **abbreviation of a finance term** (ex-dividend) — use the locale's accepted short form, not a literal gloss. Chip is hidden entirely when both dividend fields are null. |
| `tickerDetailDividendRate` | `{rate}/sh` | `rate` (`String`) | `{rate}` already carries `$` and 2 decimals. `/sh` = "per share", abbreviated for chip width. |

### Room console — live-data disclosure (CR090) · 7 keys

> These explain a **credit surcharge**. Accuracy outranks brevity here.

| Key | EN | Placeholders | Context + constraints |
|---|---|---|---|
| `roomLiveDataNoticeTitle` | `Live data` | — | Title of the card disclosing this run's News/Social live-data state. |
| `roomLiveDataFeedLive` | `{feed}: live feed used.` | `feed` (`String`) | AMI used the real live feed and the user paid the surcharge. |
| `roomLiveDataFeedWithheld` | `{feed}: live data available — needs credits.` | `feed` (`String`) | Data exists; the user did not pay. **Must read distinctly from `…Unavailable`** — pairs with the credits CTA. |
| `roomLiveDataFeedUnavailable` | `{feed}: live data unavailable right now.` | `feed` (`String`) | Nobody has this data right now. **Plain fact — no CTA, no upsell tone.** |
| `roomLiveDataFeedTenure` | `{feed}: live data available — needs a plan upgrade.` | `feed` (`String`) | Data exists; the analyst is off the roster on **account tenure**, not credits. **Buying credits will not fix this one** — must read distinctly from `…Withheld`. |
| `roomLiveDataSurchargeCharged` | `Live news + social cost {surcharge} extra credits this run.` | `surcharge` (**`int`** — the only one) | The surcharge actually debited, exactly as the backend reported it. Shown only when at least one feed was live. **If the AR/MS rendering needs plural agreement on "credits", raise it — do not silently flatten it**; that would need an ICU plural added to the EN template first, which is a code change, not a translation. |
| `roomLiveDataUpgradeCta` | `UPGRADE FOR LIVE DATA` | — | Credits CTA — opens the RevenueCat paywall. Shown only for `withheld_paid`. |

### Room console — withheld analyst chair (CR098) · 3 keys

| Key | EN | Placeholders | Context + constraints |
|---|---|---|---|
| `roomAgentWithheldChairLabel` | `{agent} — off your roster on this plan` | `agent` (`String`) | Label on a locked chair. **Names the analyst**, never a generic placeholder. |
| `roomAgentWithheldRosterNote` | `Next roster change: {agent} in {days, plural, …}` | `agent` (`String`), `days` (**`int`, ICU plural**) | See §2.1 — six categories for AR, one for MS, and the "some *other* analyst goes dark" direction must survive. |
| `roomLiveDataTenureUpgradeCta` | `UPGRADE YOUR PLAN` | — | **Deliberately distinct copy from `roomLiveDataUpgradeCta`.** A tenure gate is fixed by a *plan upgrade*; a credits gate by a *credit purchase*. Collapsing the two into one Arabic phrase re-creates the DEF059 inversion this wording exists to prevent — the user is told to spend money on the thing that does not fix their problem. **If AR/MS idiom pushes the two toward the same phrase, flag it rather than merging them.** |

---

## 4. Brand + voice constraints that apply to every string

- **AMI is a name, not a description.** Never render "the AI" — transliterate/keep `AMI`. (Project
  rule: code may say LLM; anything a user reads says AMI.)
- **Analyst-to-analyst voice.** Numbers over adjectives, no marketing puffery. The CTAs are the only
  imperative copy here and they stay plain.
- **Simulation-only.** Nothing may read as investment advice or as a real brokerage action.
- All-caps EN strings (`SECTOR ALLOCATION`, the status chips, both CTAs) are AMI-hex design
  emphasis. Arabic has no letter case — carry the emphasis with the design system's weight/size
  treatment, not by inventing an ornament.

---

## 5. Delivery + the guard that stops the 25th key

**Return format.** Two JSON fragments, keyed exactly as above, ready to merge into
`mobile/lib/l10n/app_ar.arb` and `app_ms.arb`. Metadata (`@key` blocks) stays in the EN template
only — do not duplicate it into the locale files.

**Verify after merge** — the same key-set difference must come back empty for both locales, and
`flutter gen-l10n` (or `flutter test`, which regenerates) must produce no `plural` warnings:

```bash
cd mobile && ../backend/.venv/bin/python -c "
import json
en=json.load(open('lib/l10n/app_en.arb'))
for loc in ('ar','ms'):
    t=json.load(open(f'lib/l10n/app_{loc}.arb'))
    miss=sorted(k for k in en if not k.startswith('@') and k not in t)
    print(loc, 'missing:', len(miss), miss)"
```

**The half that is not translation.** This packet closes today's 24. It does not stop the 25th — five
separate CRs each added EN-only strings and nothing noticed. The structural fix is a test that fails
when any locale's key set diverges from the template's, so the drift is caught at commit time
instead of at release time. It belongs with the code, not with the i18n lane, and it is the part
that actually discharges DEF137. Filing the packet without it just resets the counter.

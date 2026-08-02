<!-- CR136 M11 — collected retranslate:[ar,ms] flags for every new EN string shipped by M08/M09, per the content-change rule. -->

# CR136 — i18n retranslate register

**M11 flags; the i18n lane translates.** Nothing here is a translation task for
the build track — this file exists so no CR136 string reaches AR or MS readers
as untranslated English by accident.

Every ARB key below ships with its EN value duplicated verbatim into
`app_ar.arb` and `app_ms.arb` as a placeholder, which is the DEF210 convention:
`mobile/test/l10n_key_parity_test.dart` fails on a locale missing a key, so a
placeholder is the only way to ship the EN string and keep the parity guard
meaningful. A placeholder that is still English is a translation debt, not a
translation.

`source_sha` is the commit that introduced the key. It is the staleness anchor
(the DEF105-generalised guard): if the EN value changes at a later SHA, the
AR/MS values are stale even though they exist.

**AMI by name.** `grep -n "the AI" mobile/lib/l10n/app_en.arb` returns exactly
one hit, inside the *description* of `roomServerBusyTitle` where it says the
copy must never use that phrase. No CR136 value contains it.

---

## A. Mobile ARB keys — 48, all flagged `retranslate:[ar,ms]`

Verified mechanically: every key whose `@description` names CR136 carries the
flag, and every one exists in all three locales.

```bash
python3 - <<'PY'
import json, collections
en = json.load(open("mobile/lib/l10n/app_en.arb"), object_pairs_hook=collections.OrderedDict)
ar = json.load(open("mobile/lib/l10n/app_ar.arb"))
ms = json.load(open("mobile/lib/l10n/app_ms.arb"))
keys = [k for k in en if not k.startswith("@")
        and "CR136" in en.get("@"+k, {}).get("description", "")]
assert all("retranslate:[ar,ms]" in en["@"+k]["description"] for k in keys)
assert all(k in ar and k in ms for k in keys)
print(len(keys), "keys, all flagged, all present in ar+ms")
PY
```

### A1 — Journal (M08), `source_sha b20c9483`

| Key | EN |
|---|---|
| `journalEntryTypeHealth` | `HEALTH` |

The journal card badge for a `portfolio_health_analysis` entry. Shipped in M06's
audit commit rather than M08's own, because the Dart enum member and the badge
had to land in the same commit as the backend enum (`test_journal_entry_type_parity.py`).

### A2 — Health card + Finding screen (M09), `source_sha 1942ee22`

Card chrome: `portfolioHealthTitle`, `portfolioHealthWindowSubtitle`.

Tiles and their unit lines: `portfolioHealthTileVolatility`,
`…VolatilityUnit`, `…VolatilityBenchmark`, `portfolioHealthTileBeta`,
`…BetaUnit`, `portfolioHealthBetaLowR2`, `portfolioHealthTileBets`,
`…BetsUnit`, `portfolioHealthTileMdd`, `…MddUnit`,
`portfolioHealthTileConcentration`, `…ConcentrationUnit`,
`portfolioHealthEtfChip`.

Risk-vs-money block: `portfolioHealthBarsHeading`, `portfolioHealthBarsCaption`,
`portfolioHealthBarsNegativeNote`, `portfolioHealthLegendRisk`,
`portfolioHealthLegendMoney`, `portfolioHealthCashLine`.

State copy: `portfolioHealthPartialChip`, `portfolioHealthPartialNote`,
`portfolioHealthInsufficientTitle`, `portfolioHealthInsufficientBody`,
`portfolioHealthInsufficientDroppedBody`,
`portfolioHealthInsufficientGenericBody`, `portfolioHealthTnNote`,
`portfolioHealthBenchmarkNote`, `portfolioHealthMddNote`,
`portfolioHealthMockRefusalTitle`, `portfolioHealthMockRefusalBody`,
`portfolioHealthEmptyTitle`, `portfolioHealthErrorBody`.

Gate CTA: `portfolioHealthCtaFinding`, `portfolioHealthTrialChip`,
`portfolioHealthDailyCapNote`, `portfolioHealthUpgradeBody`,
`portfolioHealthUpgradeCta`.

Finding screen: `findingScreenTitle`, `findingSectionF1`…`findingSectionF5`,
`findingUnavailableBody`.

### A3 — M09 audit fix, `source_sha 0762f02d`

| Key | EN |
|---|---|
| `portfolioHealthUnknownStatusBody` | `AMI's engine returned a result this version of the app does not recognise. Tap to retry.` |

---

## B. Translator notes — the things a translator cannot infer

1. **Placeholders are pre-formatted strings, not numbers.** Every numeric
   placeholder arrives as a `String` already rounded to CR136's decimal pins
   and already wrapped in Unicode directional isolates (`⁦…⁩`,
   CR106's T-BIDI trap). **Keep the placeholder token intact and do not add
   locale digit formatting** — the isolates are what stop `+$5,423.69 (+5.33%)`
   reordering into `(5.33%+` under RTL, and re-formatting the value would strip
   them.
2. **Three numbers are literal thresholds, not copy.** `126` in
   `portfolioHealthInsufficientBody`, `80` in `…DroppedBody`, `21` in
   `portfolioHealthMddNote` mirror `T_MIN`, `DROPPED_WEIGHT_MAX` and
   `TIER2_MIN_SNAPSHOTS` in `portfolio_health_constants.py`. Translate the
   sentence, keep the number.
3. **The register is analyst-to-analyst, and the card never advises.**
   `findingSectionF5` is deliberately *"What the numbers point to"*, never
   "Recommendations" — AMI is a simulation-only training tool and is not
   licensed to advise. A translation that renders §F5 as advice is a
   compliance defect, not a style choice.
4. **"AMI" is a name.** It is never "the AI", and it is not translated or
   transliterated into a common noun.
5. **`portfolioHealthBarsCaption` is mandatory disclosure**, not a caption in
   the decorative sense. It names the basis of both bars and refuses two
   readings the chart invites. It must stay complete in every locale.
6. **`portfolioHealthWindowSubtitle`'s "≈66-DAY EFFECTIVE WINDOW"** is the
   estimator's *effective* sample (T_eff of the EWMA weights), not the 126-day
   minimum. They are different numbers and only the sufficiency copy mentions
   126.
7. **"S&P 500" and "beta" stay** as market terms; `× THE S&P 500` means "times",
   the multiplier, not a cross.

---

## C. Server-rendered EN — NOT ARB keys, and not yet on any translation path

The Finding's body is rendered **backend-side** and stored verbatim in the
journal entry, so it is English no matter what locale the app is running in.
Two families:

- **`RULE_TEMPLATES`** — `backend/app/services/portfolio_rules.py:76`, ids
  `R0, R1, R2, R2b, R3, R4, R5`. Deterministic sentences with slot
  substitution.
- **The §F1–§F5 renderer + head disclosure block** —
  `backend/app/services/portfolio_finding.py`, including the F19 disclosure
  lines and the deterministic fallback used whenever the LLM path is refused
  or rejected.

**This is a known gap, recorded here rather than fixed:** CR136 ships the
Finding in EN only. It is not a regression — no prior AMI-authored long-form
artefact is localised either — but an AR or MS user will see a localised card
above an English report, and that discrepancy is visible.

Localising it is a real design decision, not a string sweep, because the
Finding is **stored** at write time: translating at render time would make an
archived report change wording after the fact, and translating at write time
pins the locale the user happened to have that day. Either answer is defensible
and neither is M11's to make. Flagged for the i18n lane and for CR137's scope
discussion.

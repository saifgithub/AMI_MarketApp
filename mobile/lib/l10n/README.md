# AMI Trade — Flutter i18n

English is the source of truth (`app_en.arb`). AR + MS are auto-translated
via the on-prem Gemma 4 (vLLM) gateway and committed alongside.

## Files

| File | Role |
|---|---|
| `app_en.arb` | The truth. Every user-visible string lives here. Hand-curated. |
| `app_ar.arb` | Arabic — auto-translated. Manual edits survive re-runs. |
| `app_ms.arb` | Malay — auto-translated. Manual edits survive re-runs. |

A key missing from a locale file falls back to the English string (Flutter
gen-l10n behaviour) — silently, per key, mid-paragraph. **DEF137 forbids it:**
`mobile/test/l10n_key_parity_test.dart` fails the build if any locale is
missing a template key, so every string must exist in all three files.

## Adding a new string

1. Add `myScreen_shortDescriptor` to `app_en.arb`. Use placeholders for
   anything dynamic: `"foo": "Pick {count} tickers"` with
   `"@foo": { "placeholders": {"count": {"type": "int"}} }`.
2. Seed AR + MS so the parity guard passes:
   `backend/.venv/bin/python scripts/translate_arb.py --seed-missing`.
   **Do not hand-copy the English across** — see below.
3. Run `flutter gen-l10n` (or `flutter pub get` — pubspec triggers it).
4. Use it: `AppLocalizations.of(context).myScreen_shortDescriptor`.
5. Translate when the i18n lane next runs `scripts/translate_arb.py` — it
   fills the new key and leaves real translations alone.

### Why seeding has to go through the script (DEF295)

The translator skips any key whose target value is non-empty, so hand
translations survive re-runs. English hand-copied in to satisfy step 2 is
indistinguishable from a hand translation under that rule, so it is skipped
**forever**: the key is present, the parity guard is green, and the Arabic
screen renders English. 615 AR keys and 630 MS keys were in exactly that
state on 2026-08-17.

`--seed-missing` records what it seeded in an `@@x-ami-seeds` map (key →
hash of the seeded value), so the translator can tell a seed from a
translation. The marker is **self-healing**: a key stops being a seed the
moment its value changes, so translating by hand needs no knowledge of this
and clears nothing. `backend/tests/unit/test_def295_seeded_translations_are_
marked.py` fails on any English that sits in a target file unmarked.

`scripts/translate_arb.py --report` prints translated / seeded / missing per
locale.

## Auto-translate pipeline

`scripts/translate_arb.py` reads `app_en.arb`, batches strings ~40 at a
time, and POSTs to the Alpha backend's `/v1/llm/translate` endpoint. That
route is a thin non-streaming pass-through to the LLM gateway, which
prefers vLLM (Gemma 4 31B NVFP4 on `192.168.20.74:8000`) when reachable.

Run:

```bash
backend/.venv/bin/python scripts/translate_arb.py                       # both AR + MS
backend/.venv/bin/python scripts/translate_arb.py --locales ar          # AR only
backend/.venv/bin/python scripts/translate_arb.py --overwrite           # re-translate even filled keys
backend/.venv/bin/python scripts/translate_arb.py --batch-size 25       # smaller batches
backend/.venv/bin/python scripts/translate_arb.py --backend-url URL     # different backend
```

The script:

- Skips `@@locale` / `@<key>` metadata.
- Sends a strict JSON-object prompt; Gemma is told to preserve
  `{placeholder}` syntax + the brand name `AMI`.
- Persists after every batch — a partial run is still useful.
- Validates placeholder parity (`{ticker}` etc.) — keys where Gemma
  dropped a placeholder are skipped (English fallback kicks in).
- Retries each batch once; logs failures to stderr and continues.
- Exits non-zero if any batch ultimately failed.

After running, `flutter gen-l10n` to refresh `lib/generated/l10n/*`, then
flip the locale in Settings → Language to spot-check.

## RTL notes

Arabic flips the layout direction; Flutter's `Directionality` handles it
automatically once the AR locale is active. Specific things to watch:

- **Ticker symbols stay LTR.** They're inside RTL sentences but always
  Latin uppercase. Flutter's bidi algorithm gets this right for plain
  `Text` widgets; we don't do manual `<bdi>`-style wrapping.
- **Currency.** `\$` and digits render LTR inside an AR sentence — that's
  what we want.
- **Stop / target / horizon numerics** in `roomVerdictHeading` etc. are
  already isolated as placeholders, so they survive direction flips.

If a screen has a manual substring concat that breaks under RTL, prefer
a placeholder over hand-built strings. Example: don't do
`"${prefix}\${value}"` — use a localised string with `{value}`.

## Endpoint dependency

`/v1/llm/translate` ships in `backend/app/api/llm.py`. If the Alpha
backend has not yet been promoted to a build that includes that route,
the script will receive `404 Not Found` from every batch. Promote first,
then run the script.

# i18n Architecture

The pluggable locale system. Adding a new language is a content operation, not an engineering one.

## Locale pack structure

Every locale is a self-contained pack:

```
content/i18n/
├── en/
│   ├── strings.json              ← ~2000 UI keys (ICU MessageFormat)
│   ├── meta.json                 ← locale metadata
│   ├── fonts.json                ← font stack declaration
│   └── voice.json                ← TTS provider + voice IDs
├── ar/
│   ├── strings.json
│   ├── meta.json
│   ├── fonts.json
│   └── voice.json
├── ms/
│   ├── strings.json
│   ├── meta.json
│   ├── fonts.json
│   └── voice.json
└── _registry.json                ← list of available locales
```

Lessons live in `content/lessons/` (one MDX file per `lesson_id.locale.mdx`), separately from `i18n/strings.json` (which holds UI labels).

## `meta.json` per locale

```json
{
  "locale_id": "ar-SA",
  "display_name": "العربية (السعودية)",
  "english_name": "Arabic (Saudi Arabia)",
  "direction": "rtl",
  "decimal_separator": ".",
  "thousands_separator": ",",
  "default_currency": "SAR",
  "calendar": "gregory",
  "has_hijri_option": true,
  "first_day_of_week": "saturday"
}
```

## `fonts.json` per locale

```json
{
  "body": "IBMPlexSansArabic",
  "body_fallback": ["Inter", "system-ui"],
  "mono": "JetBrainsMono",
  "mono_fallback": ["IBMPlexMono", "monospace"]
}
```

Fonts are bundled into the Flutter app's `assets/fonts/`. Adding a new locale that needs a new font = bundle that font.

## `voice.json` per locale

```json
{
  "tts_provider": "azure",
  "voice_id": "ar-SA-HamedNeural",
  "fallback_provider": "google",
  "fallback_voice_id": "ar-XA-Standard-B",
  "premium_provider": "elevenlabs",
  "premium_voice_id": "ar-male-1"
}
```

Three tiers of voice: standard (Azure Neural), fallback (Google), premium (ElevenLabs for Floor Manager). All abstracted behind our TTS service facade.

## `strings.json` — the UI strings file

ICU MessageFormat for pluralization, gender, and number formatting:

```json
{
  "header.greeting": "Good morning, {name}.",
  "floor.agents_active": "{count, plural, =0 {No agents active} =1 {1 agent active} other {# agents active}}",
  "floor.drawdown_label": "Drawdown: {pct, number, percent}",
  "trial.expires_in": "Your trial ends {when, date, ::yMMMd}",
  "onboarding.scenario_1.prompt": "Two months in, your $10K simulator has dropped to $7K because the whole market corrected. Walk me through what you'd actually do.",
  "agent.fundamentals_analyst": "Fundamentals Analyst",
  "agent.bear_researcher": "Bear Researcher",
  "tier.floor_pass": "Floor Pass",
  "tier.trader": "Trader",
  "tier.floor_manager": "Floor Manager",
  "...": "..."
}
```

Estimated ~2,000 keys for the full MVP UI. Each key has translation context:

```json
{
  "header.greeting": {
    "value": "Good morning, {name}.",
    "context": "Top of Floor home screen. Shown in user's locale at user's local morning time."
  }
}
```

The context comment is for the translator. It tells them *where* and *when* the string appears so they can choose appropriate diction. **Saiful's note: this is what we hand to translators.**

## Build-time string compilation

```
content/i18n/en/strings.json
              ↓
build script: validate, normalize, output to Flutter
              ↓
mobile/lib/i18n/generated/strings_en.dart
mobile/lib/i18n/generated/strings_ar.dart
mobile/lib/i18n/generated/strings_ms.dart
```

Uses the Flutter `intl` package + `flutter_intl` plugin. Strict-mode: missing keys in any locale fail the build (caught in CI).

## Runtime locale switching

```dart
// User changes locale in Settings or Concierge
Provider.of<LocaleNotifier>(context).setLocale('ar-SA');

// MaterialApp rebuilds with new locale
MaterialApp(
  locale: Locale('ar', 'SA'),
  supportedLocales: [Locale('en'), Locale('ar'), Locale('ms')],
  localizationsDelegates: [
    AppLocalizations.delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ],
  // ...
)
```

Locale switch is instant — no app restart needed. Restored from user preference on next app launch.

## Concierge / agent multilingual handling

Per [`docs/initial_specs/02_agents/mandate_overlays.md`](../02_agents/mandate_overlays.md), agent reasoning happens in English internally (best model performance), with a final instruction to respond in `mandate.locale`. The LLM produces the output directly in the user's language.

Exceptions:
- Concierge always responds in `mandate.locale` (never English unless user is English-speaking)
- Lessons render the MDX file for the user's locale (no translation at runtime)
- Decision Journal entries are stored in whatever language the agent responded in (preserves the conversation's authentic language)

## Adding a new locale post-MVP

Suppose we add Indonesian (`id-ID`) in Phase 2:

1. **Create the locale pack**:
   ```
   content/i18n/id/
   ├── strings.json
   ├── meta.json
   ├── fonts.json
   └── voice.json
   ```

2. **Translate `strings.json`** (Saiful arranges, ~2000 keys, takes 1–2 weeks with an agency)

3. **Translate the 300 lessons**:
   ```
   content/lessons/001_what_is_a_stock.id.mdx
   ...
   ```
   Takes 3–4 weeks for a content agency

4. **Add to registry**:
   ```json
   // content/i18n/_registry.json
   ["en", "ar", "ms", "id"]
   ```

5. **Register fonts** in `pubspec.yaml` (if needed)

6. **Configure Azure TTS voice** for Indonesian

7. **Ship**: build artifact includes the new locale; users can pick it from Settings or Concierge

**Zero application code changes.** This is the point of the architecture.

## What's hard about Arabic specifically

| Concern | Handling |
|---|---|
| **RTL layout** | `Directionality(textDirection: TextDirection.rtl)` at app root. All flexbox/grid widgets flip. |
| **Bidirectional text** (Arabic + Latin number mix) | ICU BiDi algorithm via Flutter's RenderParagraph. `123` stays LTR inside Arabic. |
| **Font shaping** | IBM Plex Sans Arabic handles Arabic ligatures. JetBrains Mono Arabic-Latin mix needs careful testing. |
| **Numerals** | Use Western Arabic numerals (0–9) by default, not Eastern (٠١٢٣). User can switch in Settings. |
| **Truncation** | Truncate from the *correct* side per directionality |
| **Hijri calendar** | Phase 2 — adds a calendar pref to mandate |
| **Currency formatting** | `SAR 56.21` reads as `٥٦٫٢١ ر.س` in pure Arabic numerals; we default to Western numerals for consistency |

## i18n testing in CI

Automated tests at v1.0:
- All locales build cleanly (no missing keys, no type errors)
- All locales render the splash screen without crashing
- All locales render the Floor home (smoke test)
- Snapshot tests for key screens in each locale
- Bidi rendering test (mixed Arabic + English + numbers in a single paragraph)

## Cross-references

- Translation strategy: [`translation_and_languages.md`](translation_and_languages.md)
- AMI design system fonts: `/Volumes/Extreme Pro/AMI AI Design System/colors_and_type.css`
- Flutter design implementation: [`docs/initial_specs/05_design/ami_hex_in_flutter.md`](../05_design/ami_hex_in_flutter.md)
- RTL handling specifics: [`docs/initial_specs/05_design/colors_motion_rtl.md`](../05_design/colors_motion_rtl.md)

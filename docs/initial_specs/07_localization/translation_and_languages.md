# Translation & Languages

The 3 launch languages, font stacks, TTS providers, translation workflow.

## Launch languages

| Locale | Script | Direction | Body font | TTS provider | TTS voice |
|---|---|---|---|---|---|
| **English** `en-US` | Latin | LTR | Inter | Azure Speech (standard) / ElevenLabs (premium) | en-US-AriaNeural / ElevenLabs Adam |
| **Arabic** `ar-SA` | Arabic | **RTL** | IBM Plex Sans Arabic | Azure Speech / ElevenLabs | ar-SA-HamedNeural (M), ar-SA-ZariyahNeural (F) |
| **Malay** `ms-MY` | Latin | LTR | Inter (with diacritics) | Azure Speech | ms-MY-OsmanNeural (M), ms-MY-YasminNeural (F) |

### Why these three at launch

- **English**: source language, mandatory
- **Arabic**: strategic (Saudi market, halal positioning, big growth opportunity)
- **Malay**: strategic (Malaysia + Singapore + Brunei, halal positioning, English-borrowed financial vocab makes translation cheap)

## Font bundling

Per AMI hex spec, fonts ship with the app — not Google Fonts API at runtime (offline + non-GMS Android compatibility).

| Font | Size | Where |
|---|---|---|
| Inter (Regular, Medium, SemiBold, Bold) | ~280KB | `mobile/assets/fonts/Inter/` |
| JetBrains Mono (Regular, Medium, Bold) | ~210KB | `mobile/assets/fonts/JetBrainsMono/` |
| IBM Plex Sans Arabic (Regular, Medium, Bold) | ~640KB | `mobile/assets/fonts/IBMPlexSansArabic/` (v1.0+ — Arabic-only builds may exclude) |

**Total font footprint:** ~1.1MB. Acceptable on mobile.

For Malay, no additional font — Inter covers Latin with diacritics natively.

## Translation strategy

Per Saiful's decision: **Claude produces structured i18n string files with translation context comments; Saiful arranges actual translation externally.**

### What Claude produces

For every UI string:

```json
{
  "header.greeting": {
    "en": "Good morning, {name}.",
    "ar": "<TODO>",
    "ms": "<TODO>",
    "context": "Top of Floor home screen. Shown in user's locale at user's local morning time. {name} is the user's display name. Should feel warm but not overly familiar — this is a finance app."
  }
}
```

This `<TODO>` placeholder + rich `context` field is what gets handed to translators.

For lesson MDX, Claude produces the EN draft. Saiful arranges AR and MS translation.

### Translation workflow (Saiful's externally-run process)

1. **Translator brief**: a one-pager explaining the AMI Trade brand voice, target users, and tone. (Claude drafts this.)
2. **Glossary lock**: agreed translations for ~150 trading-finance terms. (Claude drafts; Saiful's finance-literate AR/MS reviewer locks.) Without a glossary, every lesson sounds like a different person wrote it.
3. **UI string translation**: AR + MS translation agency. ~$2K–4K per language.
4. **Lesson translation**: AR + MS agency. ~$0.10/word × ~75,000 words = ~$15K per language ≈ $30K total for both at v1.0.
5. **Native QA**: a separate native speaker for each language reviews the rendered app and flags awkwardness.
6. **Iteration**: 1–2 rounds of fixes pre-launch.

### Translation budget (estimate)

| Item | Cost |
|---|---|
| UI strings AR | $3K |
| UI strings MS | $2.5K |
| Glossary lock | $2K |
| Lessons AR (75K words × $0.10) | $7.5K |
| Lessons MS (75K words × $0.08, English-borrowed terms easier) | $6K |
| Native QA AR | $2K |
| Native QA MS | $1.5K |
| Agent overlay translations | $1K |
| Marketing pages AR + MS | $2K |
| Splash + onboarding voice scripts | $1K |
| **Total launch localization** | **~$28K–35K** |

This is for v1.0. At alpha (EN only), localization cost is $0.

## TTS providers

### Tiered TTS

| Plan | TTS provider | Why |
|---|---|---|
| Floor Pass | Text-only briefing | Free, no audio cost |
| Trader | Azure Neural TTS | Cheap (~$15/1M chars), great quality in all 3 languages |
| Floor Manager | ElevenLabs (premium) | Higher quality, ~$5/1M chars but more expressive |

### Voice selection

Each locale gets a default M and F voice. The user picks during onboarding (or accepts the default).

| Locale | M Voice (standard) | F Voice (standard) | Premium voice |
|---|---|---|---|
| en-US | en-US-AndrewNeural (Azure) | en-US-AriaNeural (Azure) | ElevenLabs Adam |
| ar-SA | ar-SA-HamedNeural | ar-SA-ZariyahNeural | ElevenLabs custom (curated) |
| ms-MY | ms-MY-OsmanNeural | ms-MY-YasminNeural | (none at v1.0; Azure for Floor Manager too) |

Voice IDs are stored in `mandate.daily_briefing.voice_id` and rendered via the TTS service facade.

## Hijri calendar (Phase 2)

Mandate gets an optional `calendar: "gregory" | "hijri"` preference. UI defaults to Gregorian; users in Saudi/Gulf can opt to display dates in Hijri.

- Calendar conversion via `intl` package
- Hijri-styled date formatting in journal entries, briefings
- Gregorian-equivalent always shown alongside (for clarity)

Hijri is informational only — internal data and APIs always use Gregorian.

## Multi-language agent quality

Tested behavioural quality of agent responses in each language (will validate during dev with real prompts):

| Model | English | Arabic | Malay |
|---|---|---|---|
| **Claude Opus 4.7** | A+ | A | A- |
| **Claude Sonnet 4.6** | A+ | A | A- |
| **Claude Haiku 4.5** | A | B+ | B+ |
| **GPT-5.4** | A+ | A+ | A |
| **GPT-5.4-mini** | A+ | A | A |
| **GPT-4o-mini** | A | B+ | B+ |
| **Gemini 3 Ultra** | A | A+ (esp. AR) | A |
| **Gemini 3 Pro** | A | A+ | A |
| **Gemini Flash** | A | A | A- |
| **DeepSeek V3** | A | B+ | B |

**Routing strategy:**
- AR queries preferentially routed to Gemini family (Google has invested heavily in Arabic)
- MS queries → any provider works; default to whoever's cheapest at quality bar
- EN → any, route by cost

OpenRouter abstracts this — we set routing rules per (tier, locale) and it picks at request time.

## Marketing & app store copy

Each store listing has its own localization:

| Asset | EN | AR | MS |
|---|---|---|---|
| App name | "AMI Trade" | "AMI Trade" (often kept as Latin) | "AMI Trade" |
| Subtitle | "Your 12 AI analysts." | "فريق المحللين الاثني عشر." | "Pasukan analisis AI anda." |
| Description | Localized per market | Localized | Localized |
| Screenshots | EN UI | AR UI (RTL) | MS UI |
| Keywords | English | Arabic | Malay |

Saiful arranges store-listing translation through the same translation pipeline.

## Pluggability — adding a new language later

Indonesia (`id-ID`) is the most likely Phase 2 add:
- Same script (Latin), no new fonts needed
- TTS exists in Azure
- Strong Muslim-majority market (halal positioning carries through)
- Translation ~$15K (similar to MS)

Adding Indonesian post-launch is:
- 1 week: translation procurement
- 3–4 weeks: translator delivery
- 1 week: native QA
- 1 day: Saiful drops the locale pack into `content/i18n/id/`
- 1 day: ship a new build

Total: ~6 weeks calendar time, ~$15K cost. The architecture pays off here.

## Cross-references

- The pluggable architecture: [`i18n_architecture.md`](i18n_architecture.md)
- RTL design specifics: [`docs/initial_specs/05_design/colors_motion_rtl.md`](../05_design/colors_motion_rtl.md)
- LLM routing per locale: [`docs/initial_specs/08_tech/llm_routing.md`](../08_tech/llm_routing.md)
- TTS service implementation: [`docs/initial_specs/08_tech/architecture.md`](../08_tech/architecture.md)

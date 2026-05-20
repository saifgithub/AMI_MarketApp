---
purpose: Verbatim quotes of every locked production decision the 07_voice research must respect or override. The boundary fence.
scope: Read-only extract from production docs and source files. Updated only when the source moves.
---

# Constraints — what the production app already decided about voice

This file is the **boundary fence**. Every claim the research makes about what's already locked must trace back to a quote here. If a constraint listed below is overridden in `05_recommendation/path_forward.md`, the override must say so explicitly and quote the original.

Quotes are verbatim. File paths are relative to repo root.

---

## C-1: TTS provider is "Azure OR ElevenLabs" — and undecided

Source: `docs/10_delivery/project_plan.md` line 65.

> **A13** | TTS provider — Azure Speech account + key OR ElevenLabs account + key. Decide based on Arabic voice quality (Azure stronger for AR; ElevenLabs stronger for English emotion). | Saiful | external | ⏳ blocked (Azure/ElevenLabs account) | Blocks A14.

Note: status is **blocked**, meaning no provider has been picked yet. This track has the standing to recommend a third option (on-device) and overturn the cloud framing entirely.

---

## C-2: TTS integration target is `app/services/tts_gateway.py` mirroring `llm_gateway`

Source: `docs/10_delivery/project_plan.md` line 66.

> **A14** | TTS integration. `app/services/tts_gateway.py` (mirrors `llm_gateway` shape) with `AzureSpeechProvider` or `ElevenLabsProvider`. Voice per agent family (analyst / researcher / risk / manager / concierge). Tap-to-listen on agent messages — not auto-play (keeps cost sane). Server-side caching by message hash. | Claude | 1 session | ◯ unstarted (blocked on A13) | |

Three sub-constraints worth surfacing:
- **Voice persona is per agent family** (analyst / researcher / risk / manager / concierge) — not per agent. Five voices total for the 12 chat surfaces.
- **Tap-to-listen, not auto-play** — keeps cost sane in the cloud model. In an on-device model, auto-play is still a UX choice but no longer a cost driver.
- **Server-side cache by message hash** — irrelevant if rendering moves on-device. A different kind of cache (per-utterance device-side) becomes the question.

The research recommendation must either preserve the `tts_gateway.py` abstraction shape (with an `OnDeviceProvider` slotting in alongside the cloud providers) or argue for a different architecture.

---

## C-3: Daily briefing is server-rendered today (CONFLICT with phone-everything mandate)

Source: `docs/10_delivery/project_plan.md` line 69.

> **A17** | Daily briefing flow. Background job (`apscheduler` on-prem; Cloud Scheduler at Beta) assembles a 60-second audio brief per user — pulls mandate + recent journal + open positions; renders via TTS; sends push with audio attachment URL. Delivered at user's chosen local time from their mandate. | Claude | 1 session | ⚡ partial (daily-challenge service AT:R15; full TTS-audio briefing not built) | Depends on A14 + A16. |

**This conflicts with the locked scope of 07_voice** (phone-everything). The research must produce an explicit go/no-go on phone-rendered daily briefings, recorded in `05_recommendation/daily_brief.md`. If phone rendering is infeasible on the alpha device floor, the research falls back to one of:
- On-prem GB10 server-side rendering (re-uses A17's batch shape, swaps Azure/ElevenLabs for an on-device-class model running on our hardware), or
- Phone rendering on capable devices only, with text-only fallback on older phones, or
- Defer the voice-briefing surface and ship text-only at v1.0.

---

## C-4: Daily briefing content shape is locked to ~90 spoken seconds

Source: `docs/02_agents/concierge.md` lines 164–176.

> ## Morning briefing
>
> The Concierge's signature daily output. Generated overnight (batched per user, cheap LLM, low cost) and delivered:
> - **Floor Pass:** text only, in-app + email
> - **Trader:** text + voice TTS, in-app + email + push
> - **Floor Manager:** text + premium voice + personalised analyst commentary, all delivery channels
>
> Content shape (~90 seconds spoken):
> 1. Greeting using user's name
> 2. 1–2 key overnight events for tickers in watchlist or portfolio
> 3. Any urgent agent attention items ("Bear wants to talk about TSLA")
> 4. Mandate health one-liner ("Drawdown: 4% / 30% cap. Halal: clean.")
> 5. CTA: tap to convene, tap to read journal, tap to start a lesson

Implications for the TTS recommendation:
- **~90 seconds** at typical reading rate (~150 wpm) ≈ 225 words ≈ 1.5 KB of input text. Small.
- **"Premium voice"** for Floor Manager tier implies a perceptible MOS-difference between tiers. The recommendation must support at least two quality grades — or argue the gap shouldn't exist.
- The CTA line (item 5) suggests user-tap routing — the audio file is paired with text and tap targets, not standalone audio.

---

## C-5: Voice briefing is a paid-tier feature; Floor Pass is text-only

Source: `docs/06_monetization/tiers_and_pricing.md` line 19.

> | **Morning briefing** | Text-only, email | Text + voice TTS, push + email + in-app | Text + premium voice + personalised analyst commentary |

Tier columns left-to-right: Floor Pass (free) / Trader / Floor Manager.

Implication: an on-device TTS that renders **on the user's phone** can ignore tier — there's no per-render cost for us. A "premium" tier could be modeled as a higher-quality voice / faster model rather than a cost-gated cloud call. But the *presence* of a tier difference is a product commitment that this research must respect.

---

## C-6: Voice-briefing TTS row in the feature matrix

Source: `docs/01_product/core_loop_and_features.md` lines 183–185.

> | Text morning briefing | 🟢 Alpha | Email-delivered at alpha; in-app + push 🟡 v1.0 |
> | TTS voice morning briefing | 🟡 v1.0 paid | Azure Speech + ElevenLabs |
> | In-app voice playback | 🟡 v1.0 | |

Note the v1.0 commitment for TTS voice morning briefing — same release window as AR + MS launch (see C-9). Voice + AR/MS launch together, which makes Arabic voice quality the dominant constraint.

---

## C-7: Concierge voice mode deferred to Phase 2 — STT to Phase 3

Source: `docs/03_onboarding/flow.md` lines 122–127.

> ## Voice mode (Phase 2)
>
> The entire conversation can be conducted via voice — TTS for Concierge, STT for user. Deferred to Phase 2 because:
> - Adds STT integration cost
> - Background noise testing required
> - Useful but not core

Source: `docs/10_delivery/roadmap.md` line 107.

> | **Voice STT for onboarding** (talk to Concierge, no typing) |

Listed under Phase 3 (months 18–24).

Implication: STT for onboarding is **not on the alpha or v1.0 path** today. This research pulls it forward. The recommendation must either propose a v1.0 STT shipment (re-prioritising the roadmap) or accept that STT recommendations apply to a Phase-2/3 surface and benchmark accordingly.

---

## C-8: Concierge auto-detects locale at onboarding

Source: `docs/03_onboarding/flow.md` lines 116–120.

> ## Locale handling during onboarding
>
> The Concierge auto-detects locale from the device (`en-US`, `ar-SA`, `ms-MY`, etc.) and begins in that language. The user can switch language inline at any point: *"Switch to Arabic"* → Concierge picks up in AR.
>
> If the locale isn't supported (e.g., user device set to French), Concierge defaults to English with a note: *"AMI Trade isn't available in your language yet. We can do this in English for now."*

Implication for STT: language detection happens *before* the first mic input. STT models can be initialised with a known language code, removing the need for language-ID. This favours single-language Whisper-class models over universal language-ID front-ends.

---

## C-9: Language launch order — EN at alpha, AR + MS at v1.0

Source: `docs/01_product/core_loop_and_features.md` lines 207–214.

> ### Languages
>
> | Language | Status |
> |---|---|
> | English (en-US) | 🟢 Alpha |
> | Arabic (ar-SA) | 🟡 v1.0 |
> | Malay (ms-MY) | 🟡 v1.0 |
> | Any others | ⚪ Phase 2 (architecture supports drop-in) |

Source: `docs/10_delivery/stealth_alpha_scope.md` lines 59–60.

> | Arabic + Malay languages + RTL | v1.0 |
> | Voice TTS briefings | v1.0 |

Voice and AR/MS launch in the **same release window** (v1.0). That means the Arabic voice quality question is not optional or deferrable — it gates v1.0.

Mandarin (`zh`) and Cantonese (`yue`) are not yet in any locked roadmap row. The research treats them as Phase 2 "Any others" candidates per `core_loop_and_features.md` line 214. Saiful's "+others" inclusion in this track is explicitly forward-looking.

---

## C-10: Q8 in the Concierge interview asks the user about voice preference

Source: `backend/app/services/concierge_engine.py` lines 128–132.

```python
Q8_TEXT = (
    "Do you want a 90-second briefing every morning from your team? "
    "I can deliver it as text, or text + voice."
)
Q8_CHIPS = ["Yes, text only", "Yes, with voice", "Not now"]
```

Implication: voice is **opt-in per user** at mandate creation. The system never silently delivers voice. This means:
- A user who picks "Yes, text only" never receives a TTS-rendered audio file — saving render cost for them entirely.
- The %-of-users-who-opt-in number directly scales total render cost. In a cloud-TTS world this matters a lot. In an on-device world it only matters for battery / storage.

---

## C-11: Microphone usage is currently declared as "not used"

Source: `history.md` (the Apple privacy declaration trail).

The app currently declares `NSMicrophoneUsageDescription = "AMI Trade does not use the microphone."` This was a transitive framework reference, not actual mic capture.

Implication: adding STT will require:
- Updating `NSMicrophoneUsageDescription` to honest copy ("AMI Trade uses the microphone to let you speak to your analyst team. Audio is processed on your device and is not uploaded.")
- Updating Android `Manifest.permission.RECORD_AUDIO` declarations.
- App-store privacy nutrition labels.
- A Concierge first-run permission prompt with a sensible decline path.

Not a *blocker* for the research, but a downstream task the recommendation should call out.

---

## C-12: Safety floor wraps every model output

Source: `Silent_Scout/README.md` "Hard constraints" section.

> - PM safety floor stays **deterministic, post-LLM** ([`../backend/app/agents/safety_floor.py`](../backend/app/agents/safety_floor.py)). Always wraps the model.

Implication: TTS renders text that has already been through the safety floor. The TTS layer is unaware of safety — it speaks what it's given. No safety logic moves into the voice layer.

---

## C-13: Storage architecture — text in DB, audio on device only

Falls out of the locked scope (phone-everything, zero audio leaves the device). Verified against the production data model at `backend/app/db/models.py`.

### Text → DB (existing storage paths)

| Surface | Production table | Model class | File |
|---|---|---|---|
| 1-on-1 agent chat (STT transcript in + LLM response out) | `one_on_one_messages` | `OneOnOneMessageRow` | `backend/app/db/models.py:419–424` |
| Room debate transcripts | `room_runs` | `RoomRunRow` | `backend/app/db/models.py:271–272` |
| Journal entries (user-authored or agent-suggested) | `journal_entries` | `JournalEntryRow` | `backend/app/db/models.py:150–151` |
| LLM audit trail (every gateway call) | `llm_audit` | `LLMAuditRow` | `backend/app/db/models.py:372–377` |
| Concierge interview answers | (carried in `mandates` / `user_overlays`) | `MandateRow` / `UserOverlayRow` | `backend/app/db/models.py:91, 113` |
| Daily briefing text | **does not exist yet** — new `daily_briefings` table needed when A17 ships | (new model class) | (to be added) |

Voice features **inherit these paths exactly**:

- STT transcripts are written to `one_on_one_messages` / `room_runs` as if the user typed them. No new table.
- TTS outputs are read from those tables and rendered client-side. No new table.
- Daily briefing assembled text needs a **new** `daily_briefings` row (user_id, render_date, text_body, voice_preference per Q8, status). The recommendation in `05_recommendation/path_forward.md` Stage 1 calls this out as part of A17.

### Audio → device only

- **TTS audio** is generated on the user's phone from text pulled out of the DB. Never uploaded.
- **STT mic capture** is processed by the on-device recogniser and discarded. Only the resulting transcript is uploaded.
- **No audio columns** in any production table. Don't add `audio_url` or `audio_blob`.
- **Local audio cache** (Flutter side): daily-briefing audio cached for 7 days then auto-purged. Chat tap-to-listen audio is ephemeral (re-rendered each time, or cached for the duration of the chat session). UI/state policy lives in the Flutter app, not the backend.

### Why the strict split

- **Privacy.** "Zero audio leaves the device" is a locked scope decision (C-3, Saiful's "phone for everything"). Storing raw user audio server-side would violate that, even if encrypted.
- **Cost.** No audio storage bills (S3 / Postgres bytea / etc.). No CDN bandwidth.
- **Compliance + locale.** Sovereignty story per `Silent_Scout/README.md` "Sovereignty + locale" — same logic applies to user voice.
- **Re-rendering is cheap.** Once on-device TTS is the path, the text *is* the canonical form. Audio is a derivative.

### What this means for the LLM gateway + safety floor

- LLM gateway (`backend/app/services/llm_gateway.py`) is unchanged. Input is text (STT-transcribed or typed), output is text (read aloud by TTS or read on screen).
- Safety floor (`backend/app/agents/safety_floor.py`) is unchanged. Wraps the text before it ever reaches TTS — TTS only ever speaks post-safety output.
- `llm_audit` continues to log every call. Voice surfaces produce more LLM calls (each spoken user turn is an LLM call) but the audit shape is identical.

### What this means for `tts_gateway.py` (C-2)

The originally-planned server-side `app/services/tts_gateway.py` (mirroring `llm_gateway.py` per A14) was sized to *render* audio. In the on-device path, the gateway either:

- **Disappears** — voice config is part of the user's mandate row; client reads voice config + text + renders locally. No server-side TTS abstraction needed.
- **Shrinks to voice-config-only** — `GET /v1/tts/voice-config?agent=fundamentals_analyst` returns "use voice X at quality Y for agent family Z." No audio bytes ever transit.

`05_recommendation/path_forward.md` picks one of these explicitly.

---

## What's NOT locked (and therefore in scope for this research to decide)

- Whether TTS runs on the phone, on GB10 on-prem, or in cloud APIs.
- Whether STT runs on the phone, on GB10 on-prem, or in cloud APIs.
- Which specific model wins per surface per language.
- Whether the daily briefing renders on the phone or on the server (the A17 framing is *open* given Saiful's phone-everything direction).
- Whether `tts_gateway.py` stays a server abstraction or becomes a Flutter-side abstraction.
- Whether Mandarin / Cantonese ship with v1.0 or wait for Phase 2.
- Whether STT for onboarding pulls forward to v1.0 (currently Phase 3 per C-7).

Each of these gets an answer in `05_recommendation/`.

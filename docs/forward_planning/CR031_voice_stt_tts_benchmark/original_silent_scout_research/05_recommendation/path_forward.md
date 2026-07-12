---
purpose: Proposed rewrite of `docs/10_delivery/project_plan.md` A13/A14/A17 once the 07_voice research lands a recommendation. The thing Saiful approves and Claude commits to the project plan.
scope: Decision document. Direct input into a future doc-edit session that touches production docs.
status: ⏳ awaiting `05_recommendation/interactive.md` + `05_recommendation/daily_brief.md` to land their verdicts.
---

# Path forward — what `project_plan.md` should now say

⏳ **Stub.** This file resolves once the interactive + daily-brief recommendations land. It carries:

1. The proposed new wording for A13 (TTS provider decision).
2. The proposed new wording for A14 (TTS integration).
3. The proposed new wording for A17 (daily briefing flow).
4. Any new rows the project plan should gain (e.g., STT pulled forward from Phase 3).

## A13 — current state (per `01_constraints/` C-1)

> **A13** | TTS provider — Azure Speech account + key OR ElevenLabs account + key. Decide based on Arabic voice quality (Azure stronger for AR; ElevenLabs stronger for English emotion). | Saiful | external | ⏳ blocked (Azure/ElevenLabs account) | Blocks A14.

### Proposed rewrite (post-benchmark)

> **TBD** — likely shape:
>
> > **A13** | TTS engine selection. Silent_Scout `07_voice` recommends **TBD-MODEL** for on-device rendering across EN/AR/MS/zh/yue per `Silent_Scout/07_voice/05_recommendation/interactive.md`. No third-party cloud TTS account required. | Claude | 0 sessions (research-driven) | ✅ resolved by Silent_Scout | A13 was external blocker; now resolved internally. |

If the benchmark instead points to cloud TTS, A13 keeps its current shape; only the *which provider* changes from "OR" to "Azure" or "ElevenLabs" with reasoning.

## A14 — current state (per `01_constraints/` C-2)

> **A14** | TTS integration. `app/services/tts_gateway.py` (mirrors `llm_gateway` shape) with `AzureSpeechProvider` or `ElevenLabsProvider`. Voice per agent family (analyst / researcher / risk / manager / concierge). Tap-to-listen on agent messages — not auto-play (keeps cost sane). Server-side caching by message hash. | Claude | 1 session | ◯ unstarted (blocked on A13) | |

### Proposed rewrite (post-benchmark)

> **TBD** — likely shape if on-device wins:
>
> > **A14** | TTS integration. Flutter-side `TtsGateway` (Dart class over Method Channel) calling **TBD-NATIVE-ENGINE** on iOS + **TBD-NATIVE-ENGINE** on Android. Voice per agent family (analyst / researcher / risk / manager / concierge). Tap-to-listen on agent messages. **No server-side caching needed — render is on-device.** | Claude | 1.5 sessions | ◯ unstarted | Native plugin scaffolding adds 0.5 session vs. the original cloud-only shape. |

The `app/services/tts_gateway.py` server-side abstraction either disappears (replaced by a Flutter-side `TtsGateway`) or shrinks to **voice-config-only** (`POST /v1/tts/voice-config` returns which voice the client should use for which agent for which user).

## A17 — current state (per `01_constraints/` C-3 — THE CONFLICT)

> **A17** | Daily briefing flow. Background job (`apscheduler` on-prem; Cloud Scheduler at Beta) assembles a 60-second audio brief per user — pulls mandate + recent journal + open positions; renders via TTS; sends push with audio attachment URL. Delivered at user's chosen local time from their mandate. | Claude | 1 session | ⚡ partial (daily-challenge service AT:R15; full TTS-audio briefing not built) | Depends on A14 + A16. |

### Proposed rewrite (post-benchmark)

Four candidate rewrites depending on `05_recommendation/daily_brief.md` outcome:

#### If phone-only wins

> **A17** | Daily briefing flow. Background job (`apscheduler` on-prem) assembles a text brief per user — pulls mandate + recent journal + open positions. Push notification fires at briefing time with the text payload. Flutter app receives push, renders TTS audio locally via `TtsGateway` in `BGProcessingTask` / `WorkManager`, then either auto-plays or holds for user tap per Q8 preference. **Zero server-side audio render. Zero audio bandwidth.** | Claude | 1 session | ◯ unstarted | Depends on A14 (Flutter-side `TtsGateway`). |

#### If hybrid (phone for capable languages, server for others)

> **A17** | Daily briefing flow. Background job (`apscheduler` on-prem) assembles text brief per user. **For locales with phone-rendering support (TBD: list)**, push payload is text-only; client renders audio locally. **For locales without (TBD: list)**, server (GB10 on-prem) renders audio via on-prem TTS engine, push delivers audio-attachment URL. | Claude | 1.5 sessions | ◯ unstarted | The split is by locale, not by user choice — implementation branches on `mandate.locale`. |

#### If tier-gated (phone on capable devices)

> **A17** | Daily briefing flow. As above, but the phone-vs-server split is determined by device capability (resolved at install time via a one-off render benchmark + cached flag). | Claude | 2 sessions | ◯ unstarted | Extra capability-detection logic adds complexity. |

#### If server-side render survives unchanged (phone rendering not feasible)

> **A17** | Daily briefing flow. Background job (`apscheduler` on-prem; Cloud Scheduler at Beta) assembles a 60-second audio brief per user — pulls mandate + recent journal + open positions; renders via **on-prem TTS engine on GB10** (no third-party cloud); sends push with audio attachment URL. Delivered at user's chosen local time from their mandate. | Claude | 1 session | ⚡ partial | Same shape as today, but TTS provider is on-prem not cloud. |

## New rows the project plan should add

### STT pull-forward

Currently Phase 3 per `roadmap.md:107`. If 07_voice produces a credible STT recommendation, add:

> **A30 (new)** | STT integration for Concierge voice onboarding + agent chat voice. Flutter-side `SttGateway` over Method Channel calling **TBD** on iOS + **TBD** on Android. Bundled per-language model lazy-load. Permission UX (`NSMicrophoneUsageDescription`, `RECORD_AUDIO`). | Claude | 1.5 sessions | ◯ unstarted (post-07_voice) | Pulled forward from Phase 3 per Silent_Scout research. |

Decision: does this ship at v1.0 (alongside AR/MS) or wait for Phase 2? The recommendation will name it.

### Microphone permission copy update

Per `01_constraints/` C-11, the current declaration says "AMI Trade does not use the microphone." Add:

> **A31 (new)** | Update microphone permission strings (`NSMicrophoneUsageDescription` + Android `RECORD_AUDIO` rationale) once STT ships. Update App Store / Play Store privacy nutrition labels. | Saiful + Claude | 0.25 session | ⏳ deferred (depends on A30) | App-store gates this; ship is blocked until the strings are honest. |

### Silent_Scout follow-on tracks

If the recommendation flags any of:
- Gulf-AR adaptation needed.
- MS adaptation needed.
- yue voice training needed.

…it spawns follow-on Silent_Scout tracks (numbered `08_*` and onward). The project plan does **not** need new rows for those — the Silent_Scout README index gets updated instead.

---

**This document gets rewritten once `05_recommendation/interactive.md` and `05_recommendation/daily_brief.md` carry their verdicts. Saiful reads this and decides whether to authorise a doc-edit session to update `docs/10_delivery/project_plan.md` directly.**

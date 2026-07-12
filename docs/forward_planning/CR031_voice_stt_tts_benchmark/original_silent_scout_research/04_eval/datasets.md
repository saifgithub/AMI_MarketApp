---
purpose: Public test sets per language + internal test bank for STT/TTS benchmarks. Defines what audio + text the harness feeds candidates.
scope: Methodology spec. Dataset downloads land outside the repo.
---

# Evaluation datasets

Five languages: EN, AR, MS, zh (Mandarin), yue (Cantonese). Each language needs:
- An **STT test set** — audio with ground-truth transcripts.
- A **TTS test set** — text prompts (the candidate synthesises; humans score MOS).
- **Internal sentences** derived from production prompts, so we're measuring on text the user will actually hear.

External datasets live at `/raid/silent_scout/voice/datasets/` (off-repo, mirrored on GB10). Sample-of-N rows (≤ 20 utterances per language) may be committed under `04_eval/samples/` for reproducibility if licenses allow.

---

## STT — primary test sets

### Common Voice 17 (Mozilla)

Source: <https://commonvoice.mozilla.org/datasets>. License: CC0 (public domain). The default STT test set across all five languages.

| Language | Common Voice locale | Test split size (CV 17, as of writing) | Notes |
|---|---|---|---|
| EN | `en` | Very large (>1M hours total corpus, test split ≈ 16k clips) | Use the official `test.tsv` |
| AR | `ar` | ~80 hours validated; test split ~3k clips | Modern Standard Arabic dominant; expect dialect gaps |
| MS | `ms` | Small (~10–20 hours validated) | Bahasa Malaysia under-represented; supplement with `id` (Indonesian) for confidence interval |
| zh | `zh-CN` | Substantial; test split ~5k clips | Putonghua / Mandarin |
| yue | `yue` | Small (~5–10 hours validated) | Hong Kong Cantonese; thinnest dataset of the five |

Action items at execution time:
- Download CV 17 splits for all five locales.
- Filter test splits to **validated + up-voted** clips only (typical CV filter: `up_votes >= 2 AND down_votes == 0`).
- Cap to 500 clips per language for the first benchmark pass — keeps wall-clock manageable. Expand to full test split for the final recommended candidate.

### FLEURS (Google, ICASSP 2022)

Source: <https://huggingface.co/datasets/google/fleurs>. Apache-2.0 license. Multilingual parallel; useful for cross-language fair comparison.

Coverage:
- EN, AR, MS, zh (cmn_hans_cn), yue (yue_hant_hk) all present.
- ~10 hours per language, ~2k test utterances.
- Same sentence translated across languages → directly comparable WER per language for a given model.

Use as the **secondary** test set — sanity-check that CV-based rankings hold up on a parallel corpus.

### HK-Cantonese supplement

For Cantonese specifically (CV 17 is thin):
- **HKCanCor** — small but quality-controlled. Academic license; check terms before redistributing samples.
- **CantoMap** — task-oriented Cantonese; useful for chat-like utterances.
- **MDCC** (Multi-Domain Cantonese Corpus) — broader domain coverage.

Pick one; the recommendation will name which.

### Arabic dialect supplement

CV 17 AR is MSA-heavy. Real AMI Trade users in the Gulf will speak Gulf Arabic.

- **MGB-2** (Multi-Genre Broadcast Arabic) — broadcast Arabic, multiple dialects. License: signed agreement required (delayed at execution if needed).
- **QASR** (Aljazeera Speech Recognition) — broadcast + interview; multiple dialects.
- **Synthetic dialect generation** — out of scope for selection research; flagged as a follow-on track if MSA models miss on Gulf speech.

For the initial benchmark, CV 17 AR + FLEURS AR are enough to rank candidates. Dialect drift gets called out in the recommendation as a known risk.

---

## TTS — text prompt sets

TTS candidates need **text in** + a human listener; there's no "ground-truth audio." The text bank is what matters.

### Public read-aloud sentence sets

For naturalness MOS scoring on each language:

| Language | Source | Notes |
|---|---|---|
| EN | LJSpeech / VCTK held-out sentences | Standard TTS eval text |
| AR | ArabicSpeechCorpus held-out | Modern Standard Arabic; includes diacritised + un-diacritised pairs |
| MS | Common Voice MS validated sentences | Use the transcript column, not the audio |
| zh | AISHELL-3 held-out sentences | Reading text, mixed domain |
| yue | HK-Cantonese sentence list (from HKCanCor or CantoMap transcripts) | Limited supply; supplement with translated EN sentences if needed |

For each language, draw **20 sentences** of varying length (5 short < 6 words, 10 medium 8–15 words, 5 long > 20 words). Each candidate synthesises all 20; the MOS panel rates the 20 outputs.

### Internal test bank — production-anchored

The recommendation needs to be confident on text the user will *actually hear*. Source three buckets from production:

| Bucket | Source | Examples |
|---|---|---|
| **Concierge prompts** | `backend/app/services/concierge_engine.py` Q1–Q9 text | "Do you want a 90-second briefing every morning from your team? I can deliver it as text, or text + voice." |
| **Daily briefing template** | Synthesised from `docs/02_agents/concierge.md:171–176` shape | "Good morning, Saiful. Overnight: TSLA dropped 4% on earnings; NVDA flat. Bear wants to talk about TSLA. Drawdown: 4% / 30% cap. Halal: clean. Tap to convene." |
| **Agent chat snippets** | Sample mock responses from `backend/app/services/agent_mock.py` (if exists) or hand-authored stand-ins approximating the persona | One per agent family — analyst / researcher / risk / manager / concierge |

Construct the internal test bank at execution time, store as `04_eval/internal_text_bank/{en,ar,ms,zh,yue}.txt`. Each file: 10 sentences, no PII, no user data.

Translation note: AR / MS / zh / yue versions of the internal bank need translation. Per CLAUDE.md "Translation is not blocking. Produce structured i18n string files with context comments; Saiful arranges translation externally." Same rule applies here — author EN, mark each sentence with context, Saiful gets it translated.

---

## Datasets we deliberately skip

- **LibriSpeech / TED-LIUM** for STT — EN only, audiobook/lecture register, doesn't reflect mobile mic captures. CV 17 EN test split is closer to our use case.
- **AISHELL-1/2 for STT zh** — reading-style, formal; CV 17 zh + FLEURS zh covers more conversational styles, which is what we'll see in agent chat.
- **VoxCeleb for STT** — speaker-ID dataset, not transcription.
- **Any dataset requiring per-utterance payment** — zero spend, per `README.md`.

---

## Dataset hygiene

- All test audio kept in WAV 16 kHz mono (the format every candidate ingests). Resample at preprocessing time, not inference time.
- Ground-truth transcripts normalised: lowercase, strip punctuation, collapse whitespace, map digits to words (for EN/AR) or keep as digits (for zh/yue, per convention).
- For CER (zh/yue), normalise traditional ↔ simplified characters where the candidate output is in the other variant; otherwise WER is unfairly inflated.
- Audio chunking: STT candidates that don't natively support > 30 sec input get utterances chunked at silence boundaries.

---

## Storage layout (off-repo)

```
/raid/silent_scout/voice/datasets/
├── common_voice_17/
│   ├── en/
│   ├── ar/
│   ├── ms/
│   ├── zh-CN/
│   └── yue/
├── fleurs/
│   ├── en_us/
│   ├── ar_eg/      # FLEURS uses ar_eg for Modern Standard Arabic; verify at download
│   ├── ms_my/
│   ├── cmn_hans_cn/
│   └── yue_hant_hk/
├── hkcancor/        # Cantonese supplement; verify license
└── internal_text_bank/
    ├── en.txt
    ├── ar.txt
    ├── ms.txt
    ├── zh.txt
    └── yue.txt
```

Sample-of-20 per language committed under `Silent_Scout/07_voice/04_eval/samples/` for reproducibility — only if the source license permits.

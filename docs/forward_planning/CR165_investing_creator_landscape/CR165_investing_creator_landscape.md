# CR165 — US/English investing-creator landscape

**Status:** done · **Filed:** 2026-08-11 · **Type:** research / content

## What

A neutral catalogue of the 50 largest US, English-language YouTube channels that present
themselves as teaching investing or trading — URL, subscriber count, strategy
classification, and what each sells. Deliverable:
[`creator_landscape_us_en.md`](creator_landscape_us_en.md).

## Why

Saiful's request, 2026-08-11: *"research the popolar internet and youtube channels that
are now suggesting that they can teach you investing. I just need you to get me a list,
their url, a classfication of their strategy types, a short brief of what they are
selling/teaching. this research is dispasionate. do not editorialized. that would be my
job later on."*

AMI Trade competes for the same attention these channels hold — someone deciding to learn
investing picks a channel or an app, not both. But the explicit instruction was to
produce facts, not a verdict. The interpretation shaping the deliverable follows.

## Scope, as answered by Saiful

| Axis | Locked |
|---|---|
| Geography / language | US + English only |
| Platform | YouTube as entry point, **plus** whatever paid product it funnels to |
| Size | 50 entries, ranked by popularity |
| Depth | Top 15 full detail · next 15 four-to-eight lines · remaining 20 two-to-three lines |

## How the no-editorializing constraint was implemented

This is the part of the CR that mattered most, because a landscape survey of this
particular field invites judgement at every line.

- **Every entry is evidenced from the channel's own words** — its About text and a
  sample of its most recent upload titles, both retrieved 2026-08-11. Claims by a
  creator are quoted and attributed, never asserted as fact and never rebutted in line.
- **Ordering carries no judgement.** The only ordering is subscriber count, descending.
  There is no quality ranking anywhere in the document.
- **Evaluative vocabulary is absent by construction** — no *solid, legit, sketchy,
  beware, worth it, overpriced, guru*. Verified by grep (see Verification).
- **Regulatory/legal facts appear only with a primary source** (FTC/SEC/court, cited by
  URL). Exactly one entry qualified — Warrior Trading's 2022 FTC action. Absence of an
  entry is explicitly documented as "nothing located", not as a clean record. No
  journalism-sourced or forum-sourced allegations were carried.
- **No "implications for AMI Trade" section.** That pass is Saiful's.

## Method

1. **Candidate generation (~95 names).** Two independent seeds: published
   "best investing YouTube channel" roundups, which over-index on passive and
   personal-finance creators; and YouTube channel-search per strategy term — day
   trading, options, dividends, technical analysis, value investing, futures, forex,
   crypto, real estate — which is the only way the trading-education half of the field
   surfaces at all.
2. **Verification.** Subscriber counts, About text and recent upload titles were read
   from each channel's own YouTube page with `hl=en&gl=US`. No count was taken from a
   listicle. Helper scripts used for the pass are in the session scratchpad, not
   committed — they are three throwaway `curl`+`grep` wrappers (`subs.sh`, `resolve.sh`,
   `titles.sh`) with no ongoing value.
3. **Inclusion rule.** US-based, English-language, subject is money or investing
   education. Screened out: brokerage and asset-manager marketing channels, news wires,
   and channels whose subject is business operation, tax structuring, or
   entrepreneurship. Every exclusion is listed with its reason in Appendix B — nothing
   was dropped silently.
4. **Ranking and tiering.** Sort by verified subscriber count; tier at 15 / 15 / 20.
5. **Monetisation.** Vendor pages fetched where reachable; provenance labelled per
   price (`vendor-verified` / `third-party` / `not verified this pass`).

## Findings worth flagging (facts, not conclusions)

- **Popularity rank and strategy coverage pull in opposite directions.** The 510K cut
  line removes almost the entire options-education, value-investing, dividend and
  retirement-decumulation segments — tastylive, projectoption, The Motley Fool, Timothy
  Sykes, Everything Money, Option Alpha, IBD and ~35 others all sit below rank 50.
  Ranking by subscribers produces a list dominated by personal-finance and lifestyle
  channels. Appendix A exists so that effect is visible rather than hidden.
- **Two of the top 50 monetise the audience with nothing at all**: Aswath Damodaran
  (NYU professor, rank 27) and Two Cents (PBS-funded, rank 34).
- **Two funnel to a security rather than to education**: Grant Cardone (Cardone Capital
  real-estate funds) and Meet Kevin (the Meet Kevin Pricing Power ETF, NYSE Arca: PP).
- **Three large channels branded as personal finance publish no investing instruction in
  their recent output** — Caleb Hammer, Erika Kullberg, Charlie Chang. They are retained
  at their subscriber rank and labelled `adjacent` with the evidence quoted, rather than
  being silently dropped.
- **Vendor pricing is frequently unobtainable.** warriortrading.com returns HTTP 403 to
  direct fetch; BiggerPockets, Ramsey, Minority Mindset and Into The Cryptoverse did not
  expose prices on the pages fetched. Those are recorded as unverified rather than
  estimated.

## Acceptance

- [x] 50 entries, ranked strictly descending by verified subscriber count
- [x] Tiers of 15 / 15 / 20 at the requested depths
- [x] URL, strategy classification, monetisation classification and brief for every entry
- [x] Fixed taxonomy vocabularies; no free-text strategy classes
- [x] Every subscriber figure and price carries provenance and a retrieval date
- [x] Zero evaluative adjectives (grep-verified)
- [x] Exclusions documented with reasons (Appendices A and B)
- [x] No recommendation or AMI-Trade-implications section

## Out of scope

Non-English and non-US creators (Arabic/GCC and Malay were offered and declined for this
pass); non-YouTube-first surfaces (Substack-native, X-native, TikTok-native creators);
audience-overlap or revenue estimation; any assessment of teaching quality or of the
performance claims recorded.

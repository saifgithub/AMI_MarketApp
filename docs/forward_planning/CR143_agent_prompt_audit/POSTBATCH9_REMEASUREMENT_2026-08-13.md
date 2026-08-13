# Batches 1–9, re-measured — the debt CR105 Amendment 1 warned about

**Corpus:** 40 live convenes, 440 prose turns + 40 PM turns, 2026-08-12 23:19 → 2026-08-13 01:58 UTC,
on `alpha-2026-08-13-2`. **Baseline:** the committed `2026-08-07` epoch, 18 convenes / 198 turns.

Nine batches of prompt and feed changes shipped between those two dates, each with an explicit
*"NOT claimed — response-side, re-measure post-promotion over ≥30 convenes, or it is the CR105
Amendment-1 trap."* This is that re-measure. It had never been run, and the corpus it needed did not
exist: the only post-Batch-9 traffic on Alpha was the DEF230 replay, which runs under `AsOfContext`
and **skips the news/social probes entirely**, so it is structurally blind to Batch 9.

**Design choice that matters:** the same **13 tickers** as the 08-07 epoch (`AMD ANET AVGO BAC GRAB
KTOS LITE MU NBIS NVDA SNDK SNOA TSLA`), run three times with a fresh anonymous user per batch to
defeat the 24-hour dedup. Holding the subject constant is deliberate — DEF230's row is explicit that
re-measuring without controlling the mix measures the mix shift, not the prompt.

---

## What moved

| Metric | 08-07 (pre) | 08-13 (post) | |
|---|---|---|---|
| **M1** role identifiability | 87.9% (n=198) | **97.5%** (n=440) | lift over chance 9.67 → **10.72** |
| **M2** role-vs-ticker margin | 0.103 | **0.163** | role signal still beats ticker signal, by 58% more |
| **M3** novel numbers | 4.3% | **2.7%** | grounded 92.6% → **95.3%**, inherited 3.1% → 2.0% |
| **M6** stance entropy | 1.48 bits | 1.45 bits | 0 unanimous convenes both epochs (max 1.58) |
| **M7** date accuracy | 0/30 | **0/67** | after DEF279; see below |
| **M4** risk spread | — | **UNRELIABLE** | DEF271, 27% extraction precision — do not cite |
| **M5** PM groundedness | *(empty)* | *(empty)* | produced nothing in **either** epoch — flagged, unexplained |

### M1 is the headline

**87.9% → 97.5%.** Strip the stance line and a nearest-centroid classifier recovers which of eleven
agents wrote a turn 97.5% of the time. That is the Batch 5 lane firewall plus the Batch 1 output
contract, and it is the direct answer to CR143's founding question — *do the prompts get twelve
agents to do twelve jobs?* At 87.9% one turn in eight was anonymous; at 97.5% it is one in forty.

M2 moving the same way (0.103 → 0.163) matters more than its size: it is the *contrast* metric, and
it says the gain is role signal strengthening rather than tickers becoming more distinguishable.

### M3 is CR166's gate, and it passed

CR166's acceptance is *"a post-promotion Leg 1 re-measure on ≥30 convenes where novel SHOULD fall;
if it does not, the fields were not the constraint and Tier B is partially reverted."*

**Novel fell 4.3% → 2.7%** on 40 convenes. Per agent:

```
market_analyst        3.1 → 0.6      research_manager      1.0 → 2.8   ↑
conservative_debator  5.4 → 1.2      fundamentals_analyst  2.3 → 3.6   ↑
neutral_debator       5.6 → 1.6      news_analyst          0.0 → 1.1   ↑
bull_researcher       7.5 → 2.8      trader                6.7 → 4.7
aggressive_debator    4.9 → 2.7      bear_researcher       6.0 → 4.8
social_media_analyst  0.0 → 0.0
```

Eight down, three up. The **market analyst is the clean read** — 3.1% → 0.6%, and Batch 6 is exactly
what handed it SMA-20, SMA-50, the volume ratio's value and the 52-week distances. An agent given the
number stops inventing it.

**The three that rose are the finding worth keeping.** `research_manager` nearly tripled and
`fundamentals_analyst` rose by half while the sheet got *larger* for both. Two candidate readings —
more supplied numbers inviting more derived ones, or Batch 5's firewall removing an input the
synthesis roles were leaning on — and this corpus cannot separate them.

---

## M7: the instrument was wrong, not the model

M7 first reported **11/82 = 13.4%** against a 0/30 baseline. Every one of the eleven was hand-read.
**None was a model error.** Three false-positive classes, all filed and fixed as **DEF279**:

- *"the FOMC decision in 34 days and Q4 earnings on 2026-11-03"* — two events in one clause, joined
  by a word that is not a clause break. 7 of 11.
- *"34 days from the current anchor date of 2026-08-13"* — the date is the anchor the count is
  measured **from**, so the pair is vacuous by construction. 3 of 11.
- *"10 mentions over 7 days"* — a lookback window, not an offset. 1 of 11.

After the fix, **0/67 = 0.0%** — consistent with the baseline and on a 2.2× larger sample, so
**CR169's `dropped` disposition stands and is better supported than when it was taken.**

Cost stated rather than hidden: scored pairs fell **82 → 67** (−18%); precision was bought with
recall. Eight newly-unscored pairs were hand-read to confirm they are genuinely unpairable rather
than real pairs silently dropped — that check is not optional, because an earlier M7 draft cut the
scored population from 29 to 3 with a guard that looked like precision and was blindness (P16).

---

## What this does NOT settle

**This is a before/after across a bundle, not a controlled experiment.** Batches 1–9 changed the
output contract, the parser, four agents' lanes, the fact sheet, the risk state, the PM verdict path
and both paid feeds. The prompt version changed with nearly every batch. **No number here attributes
a movement to a specific batch**, and anyone reading M1's jump as "the lane firewall worked" is
inferring, not measuring.

Still outstanding, and none of them is answered by this corpus:

1. **The 9/18 fabricated per-community attribution** (CR148 A). M3 cannot see it — it scores numeric
   provenance, and in that agent every *number* is real; it is the **attribution** that was invented.
   Needs an LLM-judge or hand-read pass over the social turns. `social_media_analyst` novel is 0.0%
   in both epochs, which is precisely why a numeric metric was never going to answer this.
2. **Cross-lane citation rates** (news valuation 16/18, technicals 13/18). Needs a per-turn
   domain-citation count, which no current metric computes.
3. **The 83%-for-−48% arithmetic error class** and **wrong asymmetry 2/6** — both need hand-reading.
4. **Whether any agent screens on market cap** now that it is rendered.
5. **M5 produced nothing in either epoch.** Unexplained. A metric returning an empty dict twice is
   the DEF271 shape — it may have been silently dead for longer than anyone noticed.

**Not claimed:** that agent reasoning improved. M1 and M2 measure *distinguishability*; twelve agents
can be perfectly distinguishable and all wrong. M3 measures where numbers came from, not whether the
conclusion drawn from them was sound.

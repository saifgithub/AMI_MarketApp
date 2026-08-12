# CR168 — Step 0 evidence gate: result

**Run:** 2026-08-12 · **Corpus:** `corpus/llm_audit_2026-08-07-epoch.json`, 216 turns, one epoch,
13 tickers, 12 agents × 18 convenes · **Verdict:** zero wrong-company instances → **prophylactic**,
per the CR's own fork table.

But the gate also **falsified the CR's premise**, and that is the more useful half.

---

## 1. The headline number the CR was built on is wrong

CR168 and CR167 §4.1 both assert the company name reaches **zero** prompts, measured as:

```
$ cd docs/forward_planning/CR143_agent_prompt_audit/assembled && grep -ril "apple" .
(no matches)
```

`assembled/` is a **synthetic reconstruction built on a single ticker**. Measured instead against the
216 real production prompts in the frozen epoch:

| | turns | rate |
|---|---|---|
| A company **name** (not the bare ticker) appears in the prompt | **156 / 216** | **72.2%** |
| Some **other** company is named in the prompt | 84 / 216 | 38.9% |
| The reply then **uses** the name | 3 / 216 | 1.4% |

The name arrives through exactly one channel: the **`Catalysts —` news-headline line**. It is not
rendered as identity anywhere.

The AAPL grep returned nothing by accident of which headlines that run fetched. The same assembled
prompt names **Nvidia, Amazon and OpenAI** in its catalyst line and never names Apple — so the
sharper statement of the problem is not *"the subject is unnamed"* but **"the prompt names other
companies more reliably than it names the subject."**

## 2. The supply is uncorrelated with the need

| | tickers |
|---|---|
| Name never reaches the prompt | **AMD, AVGO, KTOS** (3/13 — 60 turns, 27.8%) |
| Name reaches the prompt | ANET, BAC, GRAB, LITE, MU, NBIS, NVDA, SNDK, SNOA, TSLA |

Supply tracks *news coverage recency*, which is not the same variable as *how guessable the company
is from its ticker*. KTOS (Kratos Defense) gets nothing; NVDA gets it every turn.

## 3. Batch 9's news recency floor removes some of the supply

CR148/Batch 9 (shipped `alpha-2026-08-12-3`) added a 7-day news recency floor. Re-scoring the same
corpus with that floor applied:

| | turns | rate |
|---|---|---|
| Name in catalysts, pre-floor | 156 / 216 | 72.2% |
| Name in catalysts, **surviving a 7-day floor** | **144 / 216** | **66.7%** |

One ticker loses its entire supply: **SNOA**, whose only name-bearing headlines were **353 and 358
days old**. Every other ticker's youngest name-bearing headline was 0–1 days old.

This is a real interaction between CR168 and already-shipped work, and it cuts the way that makes
CR168 *more* attractive: the ticker whose identity is least guessable is the one whose incidental
supply the floor removed. It is not an argument against the floor — a 353-day-old headline is not a
catalyst — it is an argument that identity should not be riding on the news feed at all.

## 4. The gate proper: zero wrong-company instances

Scanned all 216 replies for (a) company-shaped named entities and (b) mentions of other corpus
tickers. Both candidate sets were hand-read in full:

- **`Sonoma Pharmaceuticals`** on a SNOA run — the *correct* name, and it was **in the prompt**
  (catalyst headline, line 108). Not a fabrication.
- **`NVDA` during BAC and AMD runs** (5 turns) — hand-read: NVDA is an **existing holding** in the
  portfolio block on the BAC run (`DIS/HPQ/NVDA`), and a peer reference on the AMD runs. Legitimate.

**No reply named a company other than its subject. No reply described a business line the ticker does
not have. No sector-narrative drift found.** 0/216; the 95% upper bound on the true rate is **1.4%**.

Upstream's cascade (`resolve_instrument_identity`: *"the market analyst would pattern-match the price
action to a narrative and invent an identity"*) did **not** reproduce here, consistent with CR167 §5 —
their graph tool-calls, ours pre-fetches.

## 5. What this does to the CR

Per the CR's own fork table, zero instances ⇒ **prophylactic, priced as a cheap render line**, competing
against the rest of the CR143 queue on that basis. Status stays `proposed`.

Three amendments the build should carry if it proceeds:

1. **Drop the "zero prompts" justification.** It is false at 72.2%. The real argument is *reliability*:
   identity arrives via a channel selected for news recency, is absent for 3 of 13 tickers, and Batch 9
   narrowed it further.
2. **Scope grew by the lane firewall.** Batch 5 (CR145 Tier C) made `_format_profile(profile, agent_id)`,
   so "render it for all 12" is no longer automatic — the two new fields need an explicit lane
   assignment in `_EXPECTED_LANES`, and `test_cr145_lane_firewall.py` pins that matrix literally (DEF268).
3. **`exchange` is a code, not a name.** Live `yf.Ticker().info` returns `NMS`, `NYQ`, `NCM` — not
   "Nasdaq"/"NYSE". Rendering `Exchange: NMS` to the model is jargon, and upstream's template implies a
   readable name. Either map the codes or drop the field.

**Free acceptance fixture found:** criterion 3 asks for an unresolvable name verified against a real
ticker rather than a mocked `None`. **NBIS** resolves (`exchange: NMS`) with **`longName: null`** — a
genuine partial-identity case, better than an unrecognised ticker because it exercises the
half-populated path.

---

## Reproduce

```bash
# name supply + wrong-company scan (both scripts are in the session scratchpad; the
# measurement is the artifact, the scripts are throwaway)
cd backend && .venv/bin/python -c "import yfinance as yf; print(yf.Ticker('NBIS').info.get('longName'))"
```

Corpus is committed; every figure above is recomputable from
`corpus/llm_audit_2026-08-07-epoch.json` alone.

# Phase 2.4 step 1 — Bull/Bear anchoring measurement (D19)

Date: 2026-09-30 · CR247 · Instrument: `docs/tools/room_investigation_V2/library/anchoring.py` (`measure(window_days=3)`, CLI `python -m library.anchoring --days 3` from `backend/`) · Read-only against melehost.

## 1. Question and design

CR219 R58 seeds the Bull/Bear speaker order per `run_id`. If that seeding is live, the captured `llm_audit` corpus is a natural experiment: the second speaker saw the first speaker's argument, the first speaker did not. Step 1 measures, per convene:

1. **Order** — a whitespace-normalized 300-char chunk of the Bull's response (`chars[200:500]`, spec-pinned) found inside the Bear's `system_prompt` ⇒ Bull spoke first (the second speaker's prompt embeds the full upstream transcript). The mirror test ⇒ Bear first. Neither or both ⇒ unclassified, counted, excluded.
2. **Citation overlap** — the set of numeric tokens (regex `\$?\d[\d,.]*%?x?`, spec-pinned) in the first speaker's response; the fraction reappearing in the second speaker's response. The anchor question is symmetric: does Bear's overlap on Bull exceed Bull's overlap on Bear across arms? Pooled per arm with a binomial SE (`√p(1−p)/N` over all first-speaker numbers).
3. **Stance/conviction by order** — the `[STANCE: … | CONVICTION: …]` envelope, parsed with the same patterns the backend parses (`scoring.extract_decision`).
4. **Verdict** — MEASURED ANCHORING only if both arms exist and their pooled overlaps differ by ≥ 0.05 and ≥ 2 pooled SEs; otherwise NOT MEASURED, with the reason stated.

## 2. Corpus and exclusions

| Item | Count |
|---|---|
| `llm_audit` Bull/Bear rows, last 3 days | 784 |
| user_ids with ≥1 Bull and ≥1 Bear row | 213 |
| Excluded: batch drivers (bear rows > 5) | 7 user_ids (15–30 bear rows each) |
| Included user_ids (1–5 bear rows) | 206 |
| (bull, bear) pairs, nth-paired in created_at order | 210 (202 users × 1, 4 users × 2) |
| Unclassified order | 1 — Bear response is an 82-char `[AMI error: HTTP 429 …]` stub |
| Missing/empty response | 0 |
| Mismatched bull/bear counts | 0 |

## 3. Order split — the sanity check FAILS

| Order | n |
|---|---|
| bull_first | 209 |
| bear_first | 0 |

Two-sided binomial p of a 209/0 split under working 50/50 seeding: **2.4e-63**. The randomization is not live: `ROOM_DEBATE_ORDER_SEEDED=false` in the running `ami_api_alpha` container (verified via `docker exec ami_api_alpha env` on melehost, 2026-09-30), the `Settings` default is `False` (`backend/app/core/config.py:851`), the compose comment says "Off pending WP13's replay measurement", and no evaluation script in `scripts/` sets it — so the deepinfra rows ran fixed-order too. **This corpus has no treatment arm; the natural experiment does not exist in it.**

## 4. Citation overlap (single available arm)

bear_first arm: n=0 → no comparator. Reported for the record, not as an anchoring estimate:

| Arm | n pairs | pooled overlap | binomial SE | N numbers | mean per-pair | mean #tokens 1st sp. | mean #tokens 2nd sp. |
|---|---|---|---|---|---|---|---|
| bull_first (Bear anchors on Bull) | 209 | 0.505 | 0.006 | 7,200 | 0.505 | 34.4 | 31.0 |
| bear_first (Bull anchors on Bear) | 0 | — | — | 0 | — | — | — |

The overlap-by-provider split inside the single arm (the only confound check available with one arm):

| Provider | n pairs | pooled overlap | SE |
|---|---|---|---|
| deepinfra (CR240 evaluation) | 179 | 0.511 | 0.006 |
| vllm (serving model, live alpha) | 30 | 0.440 | 0.020 |

The corpus is provider-confounded at the corpus level (86% deepinfra), but with no second arm there is no arm-level confound to correct — flagged so a future mixed-order re-run reports it per arm. The deepinfra/vllm overlap gap (0.511 vs 0.440, z≈3.4) most likely reflects corpus differences (deepinfra rows are EN benchmark draws; vllm rows include AR live-user convenes) rather than provider behavior — not interpreted further here.

## 5. Stance and conviction by order

Stance is role-pinned (`Bull=for`, `Bear=against`), so the stance table carries no order information — it is reported to confirm the corpus shape, not as evidence:

| Order | bull=for / bear=against | one envelope missing |
|---|---|---|
| bull_first | 207 | 2 (Bull or Bear wrote prose without the `[STANCE:` tag) |
| bear_first | 0 | 0 |

Conviction pairs (counts, not rates — multiple cells < 10):

| Order | med/med | low/high (Bull low, Bear high) | med/high | high/med | low/med | other |
|---|---|---|---|---|---|---|
| bull_first | 157 | 18 | 17 | 9 | 5 | 3 (one `sederhana` locale leak, two missing envelopes) |

Bear-high vs Bull-high counts (35 vs 9) look like a conviction asymmetry, but with a single order arm this is confounded with speaking order by construction (the second speaker may anchor, or bears may simply argue more loudly) — exactly what the missing arm would have separated.

## 6. Verdict

**NOT MEASURED — no randomized-order corpus.** Step 1's own sanity check (order split ≈ 50/50) fails at p=2.4e-63 because `ROOM_DEBATE_ORDER_SEEDED` is off; 209/210 convenes are Bull-first. The 0.505 second-speaker overlap number answers nothing about anchoring without the bear-first comparator, and no re-analysis of this corpus can produce one.

## 7. Step-2 go/no-go

**NO-GO for step 2 (blind parallel theses).** Step 2 is a prompt/architecture change justified only by measured anchoring; with anchoring unmeasurable from this corpus, step 2 would be spending +2 LLM calls per convene and a CR077-guard extension against an unquantified problem.

Path to a decision:

1. Enable `ROOM_DEBATE_ORDER_SEEDED=true` in the alpha compose env and re-promote (the compose comment says it was held for "WP13's replay measurement" — this measurement is that dependency, and it now says the hold is the only blocker).
2. Let a mixed-order corpus accumulate (live alpha traffic plus, optionally, a harness batch so the arms balance faster and per-provider).
3. Re-run `python -m library.anchoring --days N` — the module is written for exactly this re-run and will emit MEASURED ANCHORING / NOT MEASURED with the z-test once both arms are non-empty.

Caveats carried forward: the corpus mixes providers (deepinfra = CR240 evaluation rows, vllm = serving model) and locales (EN benchmark draws, AR/EN live users); any future arm comparison must report the provider mix per arm, and if an arm ends up provider-confounded the module's per-provider split is the check.

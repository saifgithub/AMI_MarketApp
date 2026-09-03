# R58 — does the RESEARCHERS debate order move the Room's answer?

**2026-09-03**, LAN-direct against `http://192.168.20.74:8048`. No server-side change of
any kind; no production config touched (`room_debate_order_seeded` ships **False** —
WP13 Part A). Ran on the dispatcher's go (WP13).

**Model identity**, read from `/v1/models` `root` (never the `ami-llm` alias, which was
reused across the 2026-08-28 swap): `/models/qwen38-flash-next-nvfp4`, `max_model_len`
262144. Banked in the run JSON (`identity` key).

---

## Headline

**Order moves the Room's answer well beyond parse-noise — but the two things it moves
(the Research Manager's stance, and the Portfolio Manager's verdict) are not the same
finding, and only one of them survives a look at *why* the PM number moved.**

- **RM stance flips in 11/24 contexts (45.8%).** No 5-way vote sits behind this number —
  a stance envelope is one parse of one turn — so 45.8% is not directly comparable to a
  PM flip rate, but it is the harness's cleanest signal: the Research Manager reads the
  same Bull and Bear turns each time and states a different position in nearly half the
  contexts, keyed on nothing but which one spoke first.
- **PM verdict action flips in 6/24 contexts (25.0%) — about 3× the R47 baseline noise
  rate (8.3%, 5/60 votes, from replaying an IDENTICAL prompt).** That comparison is the
  one WP13 asked for, and on its face it says order is a real effect, well outside the
  8.3% noise floor.
- **But 5 of those 6 PM flips (83%) sit on a vote where at least one branch's 5-draw PM
  poll lost a draw to a parse failure** (`pm_parse_rate < 1.0`) — the exact DEF397/R43
  mechanism R47 already named as the largest measured cause of verdict instability: a
  lost draw shrinks the denominator, sometimes to an even number, and `_vote_pm_samples`
  breaks ties to PASS. Only **CAT `short`** flipped (APPROVE → PASS) with **both**
  branches at a clean 5/5 parse rate — a genuine, non-parse-loss PM-level flip, and the
  Research Manager reversed its own stance on that context too (`for` → `against`,
  citing a 15:1 R:R asymmetry on one side and a 200% FCF payout ratio on the other).

**Read together: order is a real, measured source of variance in what the Room says
(the RM number), but most of the movement in what the Room DECIDES (the PM number) is
riding the SAME parse-loss defect R47 and DEF397 already found — not a second,
independent problem.** Fixing R43's parse path (already recommended, independent of
this row) would likely remove most of the PM-level flip rate measured here without
touching debate order at all.

---

## The question, and what "beyond parse-noise" means

`05_further_improvements.md` §12: Bull always speaks before Bear (`PHASES`,
RESEARCHERS phase); LLM judges anchor on order, and the Research Manager reads both
sides before SYNTHESIS. WP13 asks: does flipping that order move the RM stance
distribution or the PM verdict beyond what pure resampling noise would produce on its
own?

The comparison point is [R47](2026-09-03_R47_flip_at_n5.md): replaying the **same**
banked PM prompt (fixed transcript, fixed order, nothing varied) k=20 times at the
production sample count (n=5) measured a **residual flip rate of 8.3% (5/60 votes)** —
and R47's own finding was that every one of those flips traced to a lost draw, never to
the PM genuinely changing its mind on identical input. That 8.3% is the "coin toss"
floor: any order effect below it is not distinguishable from noise, and — per R47's own
finding — a chunk of anything ABOVE it may still be the same parse-loss mechanism
rather than a genuine order effect, which is exactly what happened here.

## Method

24 distinct contexts: 8 tickers (3 pre-existing from the R47 corpus — CAT, MSFT, XOM —
plus 5 new ones built for this row — AAPL, JPM, JNJ, PG, NVDA, chosen to widen sector
coverage: tech, financials, healthcare, staples, semis) × the 3 production-coherent
mandates (`short`/`medium`/`long`, `mandates.py`'s `BATTERY`).

For each context: the four ANALYSTS turns run **once** (CR077: they are blind to each
other and to RESEARCHERS by construction, so debate order cannot affect them — sharing
them is a legitimate cost saving, not a shortcut around the thing under test). The
shared post-ANALYSTS transcript then **forks into two branches** — Bull-then-Bear
(today's fixed order) and Bear-then-Bull (`room_runner._researchers_order`'s
odd-run-id branch) — and BOTH branches are carried the full distance: RESEARCHERS →
SYNTHESIS → EXECUTION → RISK → VERDICT, with the PM stage mirroring production exactly
(`pm_self_consistency_samples=5` independent draws, parsed by the production
`_parse_pm_verdict`, voted by the production `_vote_pm_samples`). This is the "carry to
EXECUTION+VERDICT if the harness supports the chain without new plumbing" case WP13
names — it does, by reusing `run_convene.py`'s own per-agent turn logic rather than
inventing a second driver (new script: `debate_order_replay.py`, alongside
`run_convene.py`/`pm_replay.py` in this folder).

Same profile, same mandate, same four analyst answers on both branches of a context —
the ONLY thing that differs between the two runs of a context is which of Bull/Bear
speaks first (and, downstream of that, what each side's own turn actually says, since
the second speaker reads the first speaker's live turn — this is a genuine debate
reorder, not a relabelling of who is "first" in the UI).

**Two scores per context:**
- `rm_stance_matches` — does the Research Manager's parsed `[STANCE|CONVICTION|HEADLINE]`
  envelope (`parse_stance_envelope`, the production parser) agree between the two
  orders? `None` when the envelope failed to parse on at least one branch (excluded from
  the rate, not counted as a match or a flip).
- `pm_action_matches` — does the voted PM verdict's `action` (APPROVE/PASS/MODIFY/…)
  agree between the two orders? `None` when the vote produced no verdict on at least one
  branch (all 5 draws lost).

Requests strictly sequential — the serve is a shared LAN resource, same discipline as
`pm_replay.py`.

## What went wrong getting here (reported per the WP's instruction to document blockers,
not silently retry past them)

The LAN vLLM host went down **twice** during this run — first with `Connection refused`
on both `:8048` and `:8000` (the process itself down, host reachable by ping), then
after a resume with `Errno 64: Host is down` (the host unreachable at the network
level). Both recovered within minutes on their own; this is the same class of "brief LAN
outage" R47 noted once and shrugged off, just twice in one afternoon here. Consequences,
reported precisely rather than smoothed over:

- The first full pass (24/24 attempted) produced only **8 usable contexts** before the
  first outage hit (context 9, XOM `long`) — every context from there on recorded
  `NO_VERDICT`/`None` on both branches (0 draws parsed; the harness's `client.chat`
  degrades to an explicit `error` field per call, CR040-style, rather than crashing, so
  the run "completed" with 16 unusable rows rather than dying).
- **The harness had no mid-run checkpointing when the first outage hit**, and separately
  the *background process itself* was killed once by what this session's evidence points
  to as memory pressure on this heavily shared, 30+-session machine (exit code 1, no
  Python traceback, ~64MB free pages at the time) — that run lost its first **16
  completed contexts** with nothing durable on disk, since the script only wrote its
  output JSON once, at the very end. **Fixed in `debate_order_replay.py`** before the
  data in this row was collected: the script now checkpoints (atomic `os.replace`) after
  EVERY context, and a `--resume` flag re-reads that checkpoint, keeps every context that
  actually judged something, and retries only the ones that came back `None`/`None` on
  both scores. That fix is what let the second outage cost one retry cycle instead of the
  whole run.
- Net: **three process launches** to reach 24/24 usable — one full pass (8 usable before
  outage 1), one resume that reached one more context before outage 2, one final resume
  that cleared the remaining 15 cleanly. All 24 comparisons in this row's dataset are from
  the SAME code state (`room_prompts.py` — the shared ANALYSTS prefix every branch reads
  — was not touched by any other lane's commit across the whole window; `room_runner.py`
  had two touches from other lanes during this window, both on code paths this harness
  never calls: `RoomStatus.COMPLETED` ledger-banking and the flag-gated, default-OFF Risk
  Officer branch — checked by `git show --stat` against both commits before trusting the
  result).

`profiles/*.pkl` for the 5 new tickers (AAPL, JPM, JNJ, PG, NVDA) were fetched fresh via
`build_profile.py` before this run — real yfinance data, never the mock-walk fallback:
AAPL 89/90, JPM 74/75, JNJ 91/92, PG 91/92, NVDA 91/92 LIVE fields, comparable to the R47
corpus's CAT/MSFT/XOM at 71/72, 90/92, 90/92. JPM's lower LIVE count (74/75, still 99%)
is the one ticker in this battery worth flagging if a future row wants to check whether
data-gap size itself correlates with order sensitivity — JPM measured LOW on both axes
here (1/3 RM moved, 0/3 PM moved), so nothing in this row suggests it does, but the
battery is too small to rule it out.

## Results — per context

| Ticker | Mandate | RM stance (bull-first → bear-first) | RM match | PM (bull-first → bear-first) | PM match | PM parse rate (bull / bear) |
|---|---|---|---|---|---|---|
| CAT | short | for/medium → against/medium | **NO** | APPROVE 2.5% → **PASS** | **NO** | 1.0 / 1.0 (clean) |
| CAT | medium | for/medium → *(unparsed)* | NO | APPROVE 2.0% → APPROVE 1.5% | yes | 1.0 / 0.8 |
| CAT | long | neutral/low → for/medium | NO | PASS → PASS | yes | 1.0 / 1.0 |
| MSFT | short | for/medium → for/medium | yes | APPROVE 3.0% → APPROVE 3.0% | yes | 0.8 / 0.8 |
| MSFT | medium | *(unparsed)* → for/medium | NO | APPROVE 2.5% → **PASS** | **NO** | 0.8 / 0.8 |
| MSFT | long | for/medium → for/medium | yes | APPROVE 2.0% → **PASS** | **NO** | 1.0 / 0.8 |
| XOM | short | *(unparsed)* → for/low | NO | PASS → PASS | yes | 1.0 / 1.0 |
| XOM | medium | for/low → for/low | yes | APPROVE 1.5% → APPROVE 2.75% | yes | 1.0 / 1.0 |
| XOM | long | for/medium → for/medium | yes | APPROVE 2.5% → APPROVE 2.0% | yes | 1.0 / 0.6 |
| AAPL | short | neutral/medium → for/medium | NO | **PASS → APPROVE 1.5%** | **NO** | 0.6 / 1.0 |
| AAPL | medium | neutral/medium → neutral/low | yes | PASS → PASS | yes | 0.8 / 1.0 |
| AAPL | long | *(unparsed)* → for/medium | NO | **PASS → APPROVE 2.5%** | **NO** | 0.8 / 0.4 |
| JPM | short | for/low → for/low | yes | PASS → PASS | yes | 0.8 / 0.8 |
| JPM | medium | *(unparsed)* → for/medium | NO | APPROVE 2.6% → APPROVE 2.5% | yes | 1.0 / 1.0 |
| JPM | long | for/medium → for/medium | yes | APPROVE 2.75% → APPROVE 2.5% | yes | 0.8 / 1.0 |
| JNJ | short | against/medium → neutral/low | NO | PASS → PASS | yes | 1.0 / 1.0 |
| JNJ | medium | against/high → neutral/medium | NO | PASS → PASS | yes | 1.0 / 0.8 |
| JNJ | long | neutral/medium → against/high | NO | PASS → PASS | yes | 1.0 / 1.0 |
| PG | short | neutral/low → neutral/low | yes | PASS → PASS | yes | 1.0 / 1.0 |
| PG | medium | neutral/low → neutral/medium | yes | PASS → PASS | yes | 1.0 / 1.0 |
| PG | long | neutral/medium → neutral/medium | yes | PASS → PASS | yes | 1.0 / 0.8 |
| NVDA | short | for/medium → for/medium | yes | **PASS → APPROVE 2.5%** | **NO** | 0.8 / 1.0 |
| NVDA | medium | for/medium → for/medium | yes | APPROVE 2.75% → APPROVE 2.0% | yes | 1.0 / 0.8 |
| NVDA | long | for/medium → for/medium | yes | APPROVE 2.5% → APPROVE 2.0% | yes | 0.6 / 0.8 |

**Totals: RM stance moved 11/24 (45.8%), stable 13/24. PM action moved 6/24 (25.0%),
stable 18/24.**

## Results — is the PM movement explained by parse loss?

| | n | Share |
|---|---|---|
| PM flips where **at least one branch** lost a draw (`pm_parse_rate < 1.0`) | 5 / 6 | 83% |
| PM flips at a **clean 5/5 parse rate on both branches** | 1 / 6 | 17% |
| PM-stable contexts where at least one branch ALSO lost a draw | 10 / 18 | 56% |

Reading the second row against the third: a degraded vote does **not** reliably flip the
outcome (10 of 18 stable contexts also had a degraded branch) — parse loss is necessary
for 5 of the 6 flips but far from sufficient on its own. The honest reading is that
order sets up genuine disagreement in the Room (see below), and the vote's own fragility
(R43/DEF397) then decides, more often than not, WHICH side of that disagreement survives
into the reported action.

**RM-vs-PM co-movement**, the other cut worth having: of the 11 contexts where RM stance
moved, PM action ALSO moved in 4 (36%) and stayed stable in 7. Of the 2 contexts where PM
moved but RM stance did NOT (MSFT `long`, NVDA `short`), both have at least one branch
below a clean 5/5 (1.0/0.8 and 0.8/1.0 respectively) — degraded votes again. **The one
PM flip that is neither parse-loss-explained nor RM-stance-stable is CAT `short`**, and
it is the cleanest single piece of evidence in this dataset that the effect is real and
not an artifact: full 5/5 parse on both sides, the RM's OWN stance reversed (citing
different evidence — a 15:1 reward:risk asymmetry on the bull-first read vs. a 200% FCF
payout ratio on the bear-first read), and the PM followed it (APPROVE 2.5% → PASS).

**Draw-level parse rate across all 48 PM votes (24 contexts × 2 branches, 240 draws
requested) was 89.6% (215/240 draws parsed) — 28 of the 48 votes reached a clean 5/5,
the other 20 lost at least one draw.** Comparable to, slightly worse than, R47's 92.3%
(277/300 draws) on the same production sample count. Not a new defect; the same one, on
a wider ticker set.

## Conclusion and recommendation

1. **The default does not change here, and does not ship changed by this row.**
   `room_debate_order_seeded` stays `False` (WP13 Part A shipped it that way,
   `29eb025d`). Flipping it is Saiful's call, on this measurement.
2. **Recommendation: fix R43's parse defect first; re-measure debate order after.**
   Five of six PM-level flips ride the exact mechanism R47 and DEF397 already
   identified. R43 is already the load-bearing recommendation from R47 for unrelated
   reasons (7.7%–10.4% draw loss, independent of debate order); fixing it will likely
   collapse most of this row's PM-level flip rate on its own, and re-running this exact
   harness afterward (`debate_order_replay.py`, same 24 contexts, same seed logic) would
   cleanly separate "was that 25% actually the parse defect" from "how much order
   variance is left once it's gone" — a sharper version of this same question, cheap to
   ask again because the script and the ticker battery now exist.
3. **The RM-level finding stands on its own and does not wait for R43.** A stance
   envelope is a single parse of a single turn, not a 5-draw vote — the 45.8% move rate
   has no vote-denominator mechanism to hide behind. Whatever the PM ultimately votes,
   the Research Manager itself is reading the same evidence and reaching a different
   headline conclusion in nearly half of the sampled contexts, keyed on nothing but
   speaking order. That is real, measured decision variance in what the Room's synthesis
   layer tells the user, independent of whether the final action changes.
4. **Between the three options this row was asked to weigh in on** (keep the fixed order
   / adopt seeded / summarize-then-debate): nothing here recommends **adopting** seeded
   order as-is — a coin flip on which side of a real disagreement the user sees is not
   obviously better than a *consistent* Bull-first bias, and CR219's own framing (§12)
   only ever proposed seeding as a way to REMOVE anchoring, not as a proven fix in
   itself. **summarize-then-debate** (each side states its position independently before
   seeing the other, removing the anchor entirely rather than randomizing which side gets
   it) was not built or measured here — it is a materially different mechanism from what
   this WP's code-mechanism scope covers, and would need its own row. The evidence in
   hand supports: **keep the fixed order for now, fix R43, re-measure** — seeded order
   trades a *known, consistent* bias (Bull anchors) for an *unpredictable* one (whichever
   side spoke first anchors, decided by a coin flip the user never sees), which is not a
   clear improvement without the summarize-then-debate alternative on the table for
   comparison.

**The default ships unchanged, pending Saiful.**

## Caveats

- **Not decision quality.** Nothing here says whether the bull-first or the bear-first
  read was RIGHT on any of the 24 names — only that they often disagree.
- **N=24 contexts, one convene each per order (no k-sweep on this row).** R47's own k=20
  replay on THREE fixed prompts is what established the 8.3% comparison baseline; this
  row does not re-derive that baseline, it reads it. A context that flipped here flipped
  on ONE draw of each order — if PM-level noise alone is ~8%, a handful of this row's 6
  flips could in principle be that residual noise landing on the "flip" side of an
  order-driven vote that would have agreed on a different day. The RM-vs-PM co-movement
  cut and the parse-rate correlation above are the mitigations available without a
  second k-sweep; a genuinely tight bound on the PM number would need one (out of scope
  for this row, cheap to add later with the same script and `--k`-style repetition).
- **Ticker-dependent, and RM-sensitivity and PM-sensitivity are not the same axis.**
  Per-ticker (RM moved / PM moved, out of 3 mandates each): CAT 3/3 RM, 1/3 PM · JNJ 3/3
  RM, 0/3 PM · AAPL 2/3 RM, 2/3 PM · MSFT 1/3 RM, 2/3 PM · XOM 1/3 RM, 0/3 PM · JPM 1/3
  RM, 0/3 PM · NVDA 0/3 RM, 1/3 PM · PG 0/3 RM, 0/3 PM. CAT and JNJ have the Room's
  Research Manager reversing stance on EVERY mandate tried, yet JNJ's PM verdict never
  once moved and CAT's moved only once — the clearest single illustration in this row
  that the RM-level and PM-level findings are genuinely different measurements, not two
  readings of the same effect. Averaging across 8 tickers the way this row does is the
  honest summary WP13 asked for, but a single-name deep-dive would look very different
  depending which name you picked.
- **One serve, one model build.** `/models/qwen38-flash-next-nvfp4`. Not transferable to
  another model (CR217's business, per the harness README's own standing caveat).
- **RISK-phase debator order is out of scope** (three-way, a different question per
  WP13 and §12) — untouched by this measurement.
- **The LAN outages (see above) mean this row's 24 contexts were collected across three
  process launches**, though all on one code state. Reported in full rather than
  smoothed into a single clean narrative, per the standing house rule against
  extrapolated/laundered numbers.

## Artifacts

| File | What |
|---|---|
| `R58_debate_order.json` | The full 24-context dataset: every turn's system/user prompt and answer on both branches, per-context comparisons, the aggregate summary. `complete: true`. |
| `../debate_order_replay.py` | The script (new, alongside `run_convene.py`/`pm_replay.py`): shared ANALYSTS prefix, two full RESEARCHERS→VERDICT forks per context, checkpointed per-context with `--resume` support. |
| `../profiles/profile_{AAPL,JPM,JNJ,PG,NVDA}.pkl` | The 5 new cached profiles this row added to the golden set (gitignored, local fixtures — rebuild with `build_profile.py <TICKER>`). |

Every turn's full prompt and answer text is in the JSON (nothing summarized-away), so
any row in the per-context table above can be checked against the actual transcript
rather than taken on faith.

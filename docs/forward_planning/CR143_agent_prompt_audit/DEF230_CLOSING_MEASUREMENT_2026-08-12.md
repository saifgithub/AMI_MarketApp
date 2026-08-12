# DEF230 — the closing measurement (AT:R68, 2026-08-12)

Batch 10 of the CR143 prompt + data-feed remediation programme. DEF230's own row
specifies this measurement exactly: *"a tier-stratified, mandate-version-pinned
replay of a fixed ticker set post-promotion, diffed against these corrected
human-only figures; specifying it without stratifying on tier would measure the
mix shift in (4) rather than the prompt."*

**Answer up front: the measurement was run, and it does NOT close DEF230.**
Neither instrument has the statistical power, and one of them says the pooled
drought figure is substantially a tier-mix artifact. Both are shown below with
the arithmetic, because a number that cannot settle the question is only useful
if its limits are stated with it.

---

## 1. The instrument was validated before it was used

DEF230's re-measurement (AT:R66) is the only trustworthy prior, and its own
lesson is that the *first* baseline was contaminated by benchmark traffic. So
the filter was validated by reproducing that corrected result before being
pointed at anything new.

Filter: `status='completed'` · `verdict IS NOT NULL` ·
`last_app_version <> 'room-benchmark'` · the 05-24 seed-fixture shape · the 12
by-id exclusions (2 CR125 probes + 10 DEF227/228/229 verification convenes) ·
`overridden_from_llm=false` (drops fail-safe stubs).

| window | tier | runs | APPROVE | rate | DEF230 (AT:R66) said |
|---|---|---|---|---|---|
| July 07-01..07-30 | mid | 39 | 15 | **38.5%** | 15/39 = 38% ✓ |
| July 07-01..07-30 | premium | 13 | 2 | **15.4%** | 2/13 = 15% ✓ |
| **pooled** | | **52** | **17** | **32.7%** | 52 genuine, 17 APPROVE = 32.7% ✓ |

Exact reproduction, run for run. **The first cut of this query was wrong** — it
scoped the baseline as "everything before 07-31" rather than July, pulling in
May/June traffic, and returned 47.8% / 56.0%. That version was discarded rather
than published; the discrepancy against a known-good prior is what caught it,
which is the entire reason for validating an instrument against one.

## 2. The human series, tier-stratified

| window | tier | runs | APPROVE | rate |
|---|---|---|---|---|
| **A** July 07-01..07-30 | mid | 39 | 15 | 38.5% |
| | premium | 13 | 2 | 15.4% |
| **B** 07-31 → 08-11 (pre-fix) | mid | 7 | 1 | 14.3% |
| | premium | 24 | 1 | 4.2% |
| **C** post-fix (`alpha-2026-08-12-3`) | premium | 3 | 1 | 33.3% |

**Two things follow, and only one of them is about the prompt.**

**(a) "Zero APPROVEs" is no longer true.** DEF230 was filed on *"14 consecutive
genuine verdicts … all PASS"* and re-measured at *"since 07-31 = 15 genuine runs,
0 APPROVE"*. Window B now holds **31 runs and 2 APPROVEs**. The drought as
originally described has ended; what remains is a depressed rate, not an absence.

**(b) The pooled collapse is substantially a TIER-MIX artifact, which
strengthens DEF230's own confound (4).** July ran **75% mid** (39 of 52). Window
B runs **77% premium** (24 of 31). Premium is the *lower*-approving tier in the
baseline — 15.4% against mid's 38.5% — so a shift toward premium drags the pooled
rate down with no prompt change at all. Pooled July 32.7% → pooled B 6.5% reads
as a catastrophe; tier-stratified it is 38.5→14.3 (mid, **n=7**) and 15.4→4.2
(premium). The premium arm is the only one with enough runs to look at, and its
drop is from a 13-run baseline.

**(c) Window C is n=3.** One approve in three premium runs. That is not a
measurement and no conclusion is drawn from it.

## 3. The controlled replay — the instrument DEF230 actually asked for

Fixed ticker set, same seed (`164`), same universe file, same synthetic mandate,
26 pairs. This is the only comparison where the prompt is the *only* thing that
moves.

| batch | build | n | APPROVE | rate |
|---|---|---|---|---|
| `pit-pilot-2` | pre-programme | 126 | 13 | 10.3% |
| `r68-postbatch9` | Batches 4–9 | 25 | 3 | 12.0% |
| `r68-postfix` | + DEF260–268 | 26 | 0 | **0.0%** |

**Not significant.** Fisher's exact on 3/25 vs 0/26 gives **p = 0.110**. And
`P(0 approves | true rate 10.3%, n=26) = 5.9%` — just above the 5% line.

**The replay is 2–4 runs short of being able to answer.** At a 10.3% true rate,
`n = 28` makes a zero-approve result significant at 5%; at 12%, `n = 24` does.
At n=26 the result sits exactly in the gap between those, which is the worst
possible place for it to land and is not something to round in either direction.

## 4. What would close DEF230

1. **Re-run the pinned replay at `--n-pairs 40`** (~1.6 h unattended, same
   recipe otherwise). Zero approves at n=40 is p≈0.013 against the 10.3% prior —
   decisive. Any approves at all, and the drought is over on the controlled
   instrument too.
2. **Human traffic, tier-stratified, to n≈30 per tier.** Not something to
   manufacture; it accrues as real users convene Rooms. Until then the human arm
   cannot distinguish a prompt effect from the tier mix.
3. **Do not pool the tiers again.** The pooled number has now been misleading
   twice — once via benchmark contamination (AT:R66) and once via tier mix
   (here).

## 5. What is NOT claimed

- That the nine DEF260–268 fixes changed the approve rate in either direction.
  The replay moved 12% → 0% on n=26 and that is inside noise.
- That the prompt-constraint thickening (CR055/CR026/CR101) is or is not the
  cause. This measurement was specified to isolate it and is underpowered to do
  so; DEF230's confound (5) — the dominant user changing his own mandate
  mid-window — is also untouched here.
- `prompt_version` partitioning, which DEF230 asks for, **cannot be applied to
  the baseline at all**: `llm_audit.prompt_version` is populated only from
  2026-08-09 (CR158), and it is a **per-agent** hash — twelve values per epoch,
  ~237 turns each — with no `run_id` on `llm_audit` to join to `room_runs`. The
  partition the row specifies is not executable on the July data it wants
  compared. Stated rather than approximated by date, which the row forbids.

**DEF230 stays `open`.** The measurement it named has been run and reported; the
question it asks is still unanswered, and the row now carries the n required.

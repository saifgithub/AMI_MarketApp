# ISS003 measurement: can our models write Room turns as prose segments plus atom references?

Run 2026-11-26 (AT:B1). Measures format compliance only; it does not judge the MAI_CODE2 or LUNA submissions. All Room text and model output stayed outside the repo (git carries this file, the script, and a labels file of ids only).

## 1. Setup

1. **Models** (identified by `/v1/models` `root`, not alias):
   1. Qwen, on-prem primary: `root=/models/qwen38-flash-next-abliterated-nvfp4`.
   2. Ling, Alpha's backup slot: `root=/models/Ling-3.0-flash-Fin-fp4`.
   3. DeepSeek via CheapLLM: model id `deepseek-v4.1-flash-1017`. The proxy's `/v1/models` has **no `root` field**, so the underlying checkpoint cannot be verified from the endpoint.
   4. Qwen and Ling were called with `enable_thinking:false` (what Alpha does today); DeepSeek was called with no extra body. Temperature 0.3. Max tokens 4000 (Qwen, Ling) and 8000 (DeepSeek).
2. **Sample.** Seed `20261126`. Completed Room runs triggered 2026-11-20 to 2026-11-26 that have a frozen fact sheet. 40 desk turns from 40 different Rooms (32 distinct tickers): 20 US, 20 `.KL`, all 9 desk ids (Fundamentals 5, Bull 4, Bear 4, Research Manager 4, Execution Desk 4, Aggressive/Conservative/Neutral Risk Officer 5/4/5, CIO 5). 14 of the 40 original turns are the coded Risk Officer structured-assessment template.
3. **Ledger.** Atoms are the numeric leaves of the frozen sheet (28 to 95 per Room; US median 93, KL median 70), rendered in `$` or `RM`, money in millions as the sheet stores it. **Mandate fields are not stored with the run** (`room_runs` keeps only `mandate_version`), so the ledger is sheet atoms only. Labels and units are my own mapping in the script, not the production field specs.
4. **DeepSeek ran 20 turns, not 40** (first 10 US and first 10 `.KL` of the sample). The account allows one request at a time and a call took a median of about 2 minutes. Qwen and Ling ran all 40.
5. **Checker.** Valid means: parses as JSON (a markdown fence is stripped and tolerated); non-empty array of single-key `{"text"}` or `{"atom"}` segments; no Unicode numeral character in any text segment; no English number word, ordinal, half/quarter/dozen/twice/double/triple, or percent word (`percent`, `percentage`, `pct`, `per cent`) in text; every atom id in that Room's ledger. One repair message naming the exact errors, then a second validation. "Withheld" means failed after repair.
6. **Arm B** is `response_format` json_schema (strict): text `pattern ^[^0-9]*$`, atom id enum of that Room's ids. A one-call probe on each endpoint showed the digit pattern enforced on all three.

## 2. Format compliance

| Model | Arm | n | First-pass valid | After-repair valid | Withheld | Latency per call, median / p90 |
|---|---|---|---|---|---|---|
| Qwen | A instruction | 40 | 20 (50%) | 33 (82%) | 7 (18%) | 16.4 s / 36.4 s |
| Qwen | B constrained | 40 | 25 (62%) | 38 (95%) | 2 (5%) | 16.4 s / 46.4 s |
| Ling | A instruction | 40 | 13 (32%) | 23 (58%) | 17 (42%) | 7.8 s / 15.0 s |
| Ling | B constrained | 40 | 21 (52%) | 28 (70%) | 12 (30%) | 8.3 s / 18.7 s |
| DeepSeek | A instruction | 20 | 13 (65%) | 19 (95%) | 1 (5%) | 124.5 s / 352.7 s |
| DeepSeek | B constrained | 20 | 13 (65%) | 19 (95%) | 1 (5%) | 133.0 s / 357.9 s |

No arm was rejected or unsupported. Capacity failures: **0 final** for DeepSeek. Three early DeepSeek jobs failed with HTTP 429 "this account already has a request running" because my first run used two workers; that is my concurrency error, not a capacity event. Those jobs were re-run at concurrency 1 and the final table uses the re-runs. The "kitchen is packed" error did not occur. Per-call latency counts every HTTP response including repair calls.

Failure classes, outputs affected on the first pass (an output can carry more than one class), with the class left on the output that was still failing after repair in brackets:

| Model | Arm | bad JSON | numeral in text | number word in text | unknown atom |
|---|---|---|---|---|---|
| Qwen | A | 2 [1] | 4 [4] | 10 [1] | 5 [1] |
| Qwen | B | 3 [1] | 0 [0] | 9 [1] | 4 [0] |
| Ling | A | 1 [1] | 11 [8] | 16 [10] | 8 [0] |
| Ling | B | 1 [0] | 4 [3] | 16 [10] | 0 [0] |
| DeepSeek | A | 3 [1] | 1 [0] | 1 [0] | 2 [0] |
| DeepSeek | B | 6 [1] | 0 [0] | 1 [0] | 0 [0] |

Observations on the classes, all from this run:

1. **Number words are the largest first-pass failure for Qwen and Ling.** The most common hits are `zero` (Qwen A 6, Qwen B 6, Ling A 9, Ling B 11), then `percent`, `double`, `first`/`second`, `three`. `zero` is mostly natural prose about a quantity ("zero insider buys"); the rule as written rejects it. I did not loosen the word list.
2. **The ASCII digit pattern in arm B is bypassed.** All 4 of Ling's first-pass numeral failures under B (4 different Rooms) contained no `0-9` character: they were mathematical bold digits or subscript digits (for example a bold-digit "200-day average", subscript digits in a price). The checker catches them; the schema pattern does not. A pattern that bans `\p{N}` is needed if a grammar is going to be the control.
3. **The atom enum was not fully enforced on Qwen under B**: 4 of 40 outputs contained an atom id outside the Room's enum (examples: `sheet.roe`, `sheet.insider_ownership`). The digit pattern was enforced on the same endpoint. I have not diagnosed why. Ling and DeepSeek under B produced no unknown ids.
4. **Bad JSON is mostly budget or runaway, not syntax.** Qwen: 5 of its 7 bad-JSON calls (first pass or repair) hit the 4000-token cap (an unbounded text segment can run on). Ling: 1 of 3 did. DeepSeek: 4 arm-A calls and 1 arm-B call returned **empty content with finish `length`** (hidden reasoning used the whole 8000 tokens), and 6 arm-B calls ended mid-string with no finish reason (cut off somewhere between the proxy and us).
5. **Repair helps a lot but is not free**: it converts 13 (Qwen A), 13 (Qwen B), 10 (Ling A), 7 (Ling B) and 6 and 6 (DeepSeek) outputs, at one extra call each.

## 3. Content

Mechanical: distinct atoms cited per output divided by numerals in the original turn (original turns with their appended `[AMI checked ...]` notes stripped; a numeral is any digit string).

| Model | Arm | Median atoms / original numerals | Outputs citing no atom |
|---|---|---|---|
| Qwen | A | 0.71 (n=33) | 2 of 33 valid |
| Qwen | B | 0.69 (n=38) | 1 of 38 valid |
| Ling | A | 0.55 (n=23) | 0 of 23 |
| Ling | B | 0.57 (n=28) | 0 of 28 |
| DeepSeek | A | 0.86 (n=19) | 0 of 19 |
| DeepSeek | B | 0.82 (n=19) | 0 of 19 |

Ledger coverage: **401 of 652 numerals (62%) in the original turns equal the value of some sheet atom** (US 55%, `.KL` 69%; this counts coincidental matches, so it is an upper bound). The other 38% are derived or non-sheet figures (a ratio of two sheet fields, a multiple of ATR, a stop price, a size, days to an event, history means). Those cannot be cited, so the ratios above cannot reach 1 even for a perfect writer.

Hand-read: 10 outputs per model on arm B, chosen with the same seed from the outputs that passed validation, labelled by me against the original turn. `kept` = the desk still makes its argument and cites the figures that carry it; `thinned` = argument survives but with fewer or vaguer figures, or the figures are dumped without being tied to the argument; `dodged` = the figures the original argued from are replaced by qualitative filler.

| Model | kept | thinned | dodged | Visibly mis-bound or dangling atoms |
|---|---|---|---|---|
| Qwen B | 6 | 3 | 1 | 5 of 10 |
| Ling B | 4 | 5 | 1 | 6 of 10 |
| DeepSeek B | 6 | 4 | 0 | 5 of 10 |

"Mis-bound or dangling" is a separate, subjective count of outputs where an atom is visibly attached to the wrong thing (for example a peer-median multiple swapped with the company's own, "[RM0.010] sits at [RM0.010]") or is dropped at the end of a sentence with no prose referring to it. It is not part of the kept/thinned/dodged label, and I did not verify every atom. The labels file holds ids and labels only.

Two content patterns seen while reading:

1. **Bare atoms.** Models often wrote "the [31.6%] suggests..." with no noun, because they knew the label was available to them. In my render only the value prints, so the reader cannot tell what the number is. A design that prints label plus value (as MAI_CODE2 describes) would remove that, but a model that stops naming the quantity in prose also stops explaining why it matters.
2. **Atom salad.** Several DeepSeek and Qwen outputs strung together "[x] and [y] show..." sentences. Provenance is valid in every case; whether the right atom was chosen is a separate question this measurement cannot answer at scale.

## 4. US vs Bursa

After-repair valid, first-pass in brackets (n per cell is 20, or 10 for DeepSeek):

| Model | Arm | US | `.KL` |
|---|---|---|---|
| Qwen | A | 16 of 20 (12) | 17 of 20 (8) |
| Qwen | B | 18 of 20 (15) | 20 of 20 (10) |
| Ling | A | 13 of 20 (6) | 10 of 20 (7) |
| Ling | B | 15 of 20 (12) | 13 of 20 (9) |
| DeepSeek | A | 9 of 10 (6) | 10 of 10 (7) |
| DeepSeek | B | 10 of 10 (6) | 9 of 10 (7) |

No consistent market effect with cells of 10 to 20; I draw no conclusion. `.KL` ledgers are smaller (median 70 atoms vs 93) and original numerals are more often covered by an atom (69% vs 55%).

## 5. What this does not measure

1. One week of Rooms (2026-11-20 to 2026-11-26), 40 turns per Qwen/Ling arm and 20 per DeepSeek arm; cells are small, so a difference of a few outputs is noise.
2. Not an implementation: my prompt, my ledger, my label map, my checker. No renderer, no streaming, no Risk Officer `key_number` path, and the 14 coded Risk Officer originals were treated as ordinary turns.
3. Mandate figures are absent (not stored per run), so a turn that quotes the single-name cap can only dodge it.
4. Derived figures have no atoms (38% of original numerals by the coverage count). A turn that needed one can only dodge it or cite a nearby atom.
5. Whether the atom a model chose is the right one is not measured beyond my 30 hand reads.
6. Qwen and Ling ran with thinking off, as Alpha does; thinking-on behaviour was not measured. DeepSeek's thinking behaviour is not controllable through this proxy and cost it empty replies.
7. Number-word rule is the English list from the brief, applied literally (`zero`, `first`, `quarter`, `percent` all rejected).
8. Hand-read labels are one reader's (mine), not blind.

## 6. Re-run

From the repo root (needs `ssh melehost`, LAN access to the on-prem hosts, and `.env` / `infra/alpha.env` in the main checkout; the script reads endpoint addresses and the CheapLLM key from those files and prints neither). Output goes to `--workdir`, outside the repo.

```
PY="/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python"
S=docs/dilemmas/ISS003_ROOM_FACTCHECK_FALSE_CORRECTIONS/MEASUREMENTS/format_compliance.py
"$PY" -I $S export
for m in qwen ling deepseek; do "$PY" -I $S probe --model $m; done
"$PY" -I $S run --model qwen
"$PY" -I $S run --model ling
"$PY" -I $S run --model deepseek --per-market 10
"$PY" -I $S report
"$PY" -I $S handread        # then label into <workdir>/handread_labels.json (see format_compliance_handread_labels.json)
```

Use concurrency 1 on Qwen (it serves live Alpha users) and on DeepSeek (single request per account). `--model` runs are resumable; capacity-failed jobs are retried on the next run.

# CR265 — AAPL ami-llm paired result, 2026-10-27

Harness-only evaluation of `cr265-prompt-improvements` against current
production personas. This is a one-ticker gate, not a production acceptance run.

## Verdict

**NO-GO as a stability improvement; do not fold the combined suite into
production.** The candidate increased willingness and used smaller approvals,
but verdict stability worsened. Contract health passed on both arms.

## Configuration

1. Ticker/mandate: AAPL, risk 4, long horizon, uncapped native R4 mandate.
2. Model: `ami-llm`, verified root `/models/qwen38-flash-next-abliterated-nvfp4`.
3. Thinking: explicitly OFF. Five PM samples per room; R4 APPROVE threshold 2/5.
4. Reviews: veto and resurrection OFF, matching the V2 matrix methodology.
5. Repetitions: five per arm, strictly sequential within each arm. The two arms
   ran concurrently with each other.
6. Data: real market data, not a frozen snapshot. Spot observations ranged from
   $346.76 to $347.38; input drift remains a confound.
7. Temperature: not pinned, matching current production gateway behaviour.
8. Candidate: 24,786 persona characters vs 84,334 production characters (70.6%
   reduction). Only personas changed; fact sheet, overlays, grammars, vote and
   safety machinery stayed unchanged.

Benchmarks: `cr265-ami-aapl-baseline-r4.yaml` and
`cr265-ami-aapl-improved-r4.yaml`.

## Headline results

| Metric | Production control | Improved candidate |
|---|---:|---:|
| Completed rooms | 5/5 | 5/5 |
| Contract gate | 5/5 OK | 5/5 OK |
| APPROVE | 1 | 2 |
| PASS | 4 | 3 |
| Top-action agreement | 4/5 = 80% | 3/5 = 60% |
| Adjacent verdict flips | 2/4 | 3/4 |
| PM approve-vote sequence | 0, 2, 1, 0, 0 | 1, 1, 2, 1, 2 |
| Mean room duration | 7.50 min | 7.32 min |
| Approval size | 4.0% | 2.5% |
| Scripted fallbacks / NO_VERDICT | 0 / 0 | 0 / 0 |
| Trader geometry repairs | 1 | 1 |
| Envelope repairs | 1 | 0 |

Verdict sequences:

| Rep | Control | Candidate |
|---:|---|---|
| 1 | PASS, 0/5 | PASS, 1/5 |
| 2 | APPROVE, 2/5 | PASS, 1/5 |
| 3 | PASS, 1/5 | APPROVE, 2/5 |
| 4 | PASS, 0/5 | PASS, 1/5 |
| 5 | PASS, 0/5 | APPROVE, 2/5 |

Only two of five paired repetitions reached the same verdict. Every candidate
room produced one or two APPROVE votes; every final decision was therefore one
PM vote away from flipping. The candidate shifted the vote distribution upward
without creating a comfortable decision margin.

## Upstream stances

| Agent | Control sequence | Candidate sequence |
|---|---|---|
| Fundamentals | for/for/against/neutral/against | for/for/against/for/neutral |
| Market | for ×5 | for ×5 |
| News | neutral ×5 | for/neutral/neutral/neutral/neutral |
| Social | neutral ×5 | neutral ×5 |
| Bull | for ×5 | for ×5 |
| Bear | against ×5 | against ×5 |
| Research Manager | neutral/against/neutral/repaired/neutral | neutral/neutral/neutral/against/neutral |
| Trader | neutral/neutral/neutral/against/against | neutral ×5 |

The candidate's Trader stance was stable, but the Fundamentals desk still used
three stance values and the Research Manager changed direction. This is direct
support for the original diagnosis: improving individual role contracts does not
stop evidence reinterpretation from compounding through the room.

## Contract and decision-quality observations

1. All ten rooms passed `scoring.gate_report`: no truncation, missing/displaced
   STANCE or PM JSON findings. The in-container gate could not call `ssh`;
   gates ran Mac-side against the same audit rows and exact run-time windows.
2. The control needed one Research Manager envelope repair and one Trader
   geometry repair. The candidate needed one Trader geometry repair and no
   envelope repair.
3. The control emitted one stance conflict and two unmatched PM direction-level
   annotations. The candidate emitted one Trader incoherent-R:R warning.
4. Control approval: 4.0%, entry $347.00, stop $326.18, target $360.00.
5. Candidate approvals: 2.5%; rep3 entry $347.29/stop $340.08/target $351.73,
   rep5 entry $346.88/stop $326.07/target $416.26.
6. The candidate's rep3 approval had reward/risk of roughly 0.62:1 and approved
   despite citing negative valuation asymmetry and immediate binary risk. The
   control approval had a similar roughly 0.62:1 geometry. Neither arm earns a
   general decision-quality claim from this sample.
7. Smaller candidate approvals are consistent with the intended sub-cap
   behaviour, but two approvals are insufficient to validate a sizing policy.

## Interpretation

1. **Prompt brevity and contract cleanup are viable.** A 70.6% persona reduction
   preserved every output contract and slightly reduced mean duration.
2. **Stability did not improve.** Candidate top-action agreement fell from 80%
   to 60% and adjacent flips rose from 2/4 to 3/4.
3. **Willingness increased.** Candidate PM votes were 1–2 in every room versus
   0–2 in the control; approvals used 2.5% rather than 4.0%.
4. **The combined arm cannot attribute effects.** It changed 12 personas at once.
   A stable Trader, a more permissive PM and a still-variable Fundamentals desk
   can coexist; no single edit gets credit or blame from this run.
5. **One ticker and live inputs are hard limits.** These results reject the
   combined candidate for this stability objective; they do not prove that every
   component is harmful or that the same pattern holds on other tickers.

## Focused checks

1. Prompt override probe: all 12 agents passed before the run.
2. Focused prompt tests: 126 passed, then the scripted-demo test failed because
   configured live providers made its premise false. With providers explicitly
   disabled, that test passed: 127/127 effective checks green.
3. `git diff --check`: clean for the committed CR265 files.

## Next measurement decision

1. Keep production unchanged.
2. Retain the variant for isolated ablations: PM policy alone, shared lane
   hygiene alone, and Execution Desk thesis/timing clarification alone.
3. Run the next comparison on a frozen AAPL input snapshot so market/news drift
   cannot contaminate the flip metric.
4. Measure per-desk direction agreement and PM vote margin, not only final
   APPROVE/PASS counts.
5. Do not spend a wider multi-ticker matrix on this combined suite. A wider run
   is justified only for an isolated component that improves the frozen AAPL
   gate without contract or geometry regressions.

## Artifacts

1. Local runs: `docs/tools/room_investigation_V2/out/cr265-ami-aapl/{baseline,improved}/`.
2. melehost runs: `~/cr265_ami_aapl/{baseline,improved}/`.
3. Logs: `baseline.log` and `improved.log` beside the local run JSONL files.

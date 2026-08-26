# CR196 — wrap-up

*Operational close-out, 2026-08-26. The verdict and its reasoning live in
[`CR196.md`](CR196.md) and the register row; this file records where everything ended up, what
is still on someone else's hardware, and what would have to be true to reopen the track.*

---

## Status

**Closed on a negative result.** The fine-tune does not ship. No further GPU spend authorised.

The CR's gate was *measure it, train it, then decide how it ships*. Run 2 decided: it doesn't.
On the objective it was actually trained for — fundamental-analysis quality — the tuned model
came back at parity or slightly worse than the untrained base. Its two real wins were output
structure, and the control arm showed structure needs no training at all.

## What it cost (measured, from the returned `run_report.json` files)

| Run | Steps | Wall | Final `train_loss` | Outcome |
|---|---|---|---|---|
| smoke9 / 10 / 11 | 10 each | 0.08h each | 1.97 | harness shakedown |
| `ami-lora-probe3` | 400 | 2.79h | 0.4157 | go/no-go probe for run 2 |
| `ami-lora-r1` | 3,212 | 25.17h | 0.2776 | **failed** — collapsed to short-form output |
| `ami-lora-r2` | 375 / 2,504 | ~2.7h | — | **OOM** at `cutoff_len=5120` |
| `ami-lora-r2b` | 2,504 | 18.39h | 0.2922 | **completed** — the run of record |

**≈46.6 GPU-hours of completed training**, plus the aborted r2 and every eval-generation pass on
top. Five calendar days on alpha-spark (Muneeb's GB10). The register row's "~42 GPU-hours" is an
undercount — it predates summing the returned reports.

Run 2 trained cleanly: loss 2.05 → 0.2337, `mean_token_accuracy` 0.545 → 0.9373, exit 0, no
truncation, 44/44 long-form S1 reports at ~3,950 chars. **The training was not the problem.**

## What it produced

`ami_finetune_kit/eval/surfaces/run2_results/acceptance_r2.md` — 4 clean, 2 weak-or-absent,
1 hard failure. The load-bearing rows:

| check | what it measures | vanilla | tuned | vanilla + grammar |
|---|---|---|---|---|
| S1 `l1_plus` | basis discipline (**the target**) | 43/44 | 43/44 | — |
| S1 `false_conflict` | invents disagreements (**the target**) | 0/44 | **2/44** | — |
| S7 `refused` | abstains on missing data (**the target**) | 27/60 | 30/60 | — |
| S5 `has_side` | Trader block parses (structure) | 18/68 | 68/68 | **68/68** |
| S6 `one_per_size` | sizes on the mandate ladder (structure) | 39/69 | 69/69 | **69/69** |

Read across the last two columns: **the untrained base with a grammar matched the fine-tune
exactly** on both surfaces the fine-tune won. Everything ~46 GPU-hours bought that survives is
in that observation, and it is now [CR210](../CR210_grammar_constrained_room_output/).

## Where the artifacts are now

Everything irreplaceable is off alpha-spark and on the local drive. **427 MB, 303 files**, at
`/Volumes/Extreme Pro/AMI_run2_adapter/`, with per-file checksums in
`MANIFEST.md` there — verify integrity without needing SSH.

**Trained weights — the final adapter of every real run**, each md5-verified against the box and
each byte-identical to its run's final checkpoint:

| run | steps | wall | path | md5 |
|---|---|---|---|---|
| **run 2** (the run of record) | 2,504 | 18.39h | `adapter_final/` | `57b39fa2d0ee7556512b5751c732c285` |
| run 1 (failed) | 3,212 | 25.17h | `alpha_spark_archive/runs/ami-lora-r1/adapter_final/` | `6228c7eba58c46d702319da2598f6ec6` |
| probe 3 | 400 | 2.79h | `alpha_spark_archive/runs/ami-lora-probe3/adapter_final/` | `ee1296aa843039ddee2e4305c28a7d60` |

**Everything else:**

| Path | What |
|---|---|
| `alpha_spark_archive/kit/…/data/train.jsonl` | **the corpus that actually trained run 2** — 20,021 rows, md5 `ccdfade3df04501f5ea252bb36f0def3` |
| `alpha_spark_archive/kit/…/data/val.jsonl` | 375 rows, md5 `5f2ff9136fe21bbbd9e136635ec03ff1` |
| `alpha_spark_archive/runs/*/trainer_state.json` | full per-step loss curves — 13 files, every run |
| `alpha_spark_archive/runs/*.jsonl`, `*.json`, `finish.log` | every completion set and scored result, incl. the probe-3 arms |
| `alpha_spark_archive/logs/` | 32 logs — training, eval, setup, plus `dockerlog_ami_train_r2.log` (the 18h run's stdout) |
| `alpha_spark_archive/eval/` | basis-rubric outputs, adapter/merge verification JSON |
| `run_report.json` | run-2 config + final metrics |

Scored results and raw completions are also in the repo under
[`ami_finetune_kit/eval/surfaces/run2_results/`](ami_finetune_kit/eval/surfaces/run2_results/)
(including `control_arm/`) — all ten files verified byte-identical to the copies on the box.

**Completeness was verified by difference, not by assertion.** Every one of the 2,699 files on
alpha-spark was enumerated and matched against the local copy; the 2,409 that are remote-only
were each classified into a deliberate exclude bucket, with **zero unclassified**. What remains
on the box and nowhere else is: intermediate training checkpoints (resume-only, and useless
without the optimizer state we are also not keeping), the aborted run-2 attempt's three
checkpoints, and 10-step smoke adapters.

### Two things that check caught

**The training corpus was nearly lost.** The `data/train.jsonl` sitting in the repo working tree
is the **unfiltered** 20,029-row file (md5 `3520e53227…`). The filtered 20,021-row corpus that
run 2 actually consumed existed *only* on alpha-spark. Purging the box on the standing assumption
that "everything irreplaceable is already local" would have destroyed the training corpus of
record — the same file the decontamination guard was verified against.

**The run-1 and probe-3 adapters were nearly lost too.** The first recovery pass excluded
`*.safetensors` wholesale to skip the 246 GB of base weights, which silently also skipped those
two adapters — 46 GPU-hours of the 46.6 reduced to logs. They were caught only by enumerating
remote-only files rather than trusting the exclude list. They are root-owned mode 600 (Docker
wrote them), so they had to be read out through a container. **Gotcha:** the NGC image prints a
banner on stdout, which prepends 1,859 bytes to any streamed binary — the first pull produced
files that were the right shape and the wrong bytes. `--entrypoint /bin/cat` bypasses it. The
mismatch was visible only because the md5 was checked against the source; a size-only or
"it downloaded fine" check would have passed a corrupt adapter into the archive.

## What is still on alpha-spark, and why

`amuneeb@alpha-spark:~/amitrade_tuning/` — **251 GB**, deliberately left in place per Saiful
("leave whatever else in alpha-spark in case we come back to it"). His box has 2.5 TB free, GPU
at 0% and 4/121 GB memory, so nothing we left is in his way.

| Left behind | Size | Why it is safe to lose |
|---|---|---|
| `models/fastino-finance-bf16` | 62 G | re-downloadable from HF, SHA256 manifest in the kit |
| `models/ami-finance-{r1,r2,probe3}-bf16` | 62 G each | re-derivable: base + the adapter we hold |
| `runs/*/checkpoint-*/` (optimizer + intermediate adapters) | ~5 G | resume-only; every run's **final** adapter is local and md5-verified |
| `runs/smoke*/` adapters | ~270 M | 10-step harness shakedowns |
| `runs/.hf/` arrow cache | ~1 G | regenerated on load |
| `venv/`, `.hf_cache/`, kit tarball | ~330 M | reinstallable |

Three exited containers (`ami_train_r2`, `ami_constr_s5`, `ami_probe`) — their logs are already
pulled; left in place rather than reaped, since removing them is not ours to decide.

**To get back in:** Tailscale must be up locally, then
`ssh -i ~/.ssh/id_ed25519 amuneeb@alpha-spark`. For anything that polls, multiplex —
`-o ControlMaster=auto -o ControlPath=/tmp/cm-aspark -o ControlPersist=2h` — the connection
setup is flaky under repeated dials, and the ControlPath must be short (macOS caps it at 104
bytes, which the session scratchpad path exceeds).

**If we do purge later**, Docker wrote much of the tree as root, so a plain `rm -rf` as
`amuneeb` leaves orphans. Chown through a container first:

```bash
docker run --rm -v /home/amuneeb/amitrade_tuning:/w ami-train:v1 chown -R $(id -u):$(id -g) /w
rm -rf ~/amitrade_tuning
rm -f ~/status_probe.sh ~/peek.py ~/rr.py ~/chk.py ~/fc.py
```

## What survives into the project

The model doesn't ship; four things do.

1. **[CR210](../CR210_grammar_constrained_room_output/)** — grammar-constrained Room output,
   approved and being built. The one real finding. Its most expensive operational detail is
   already written down there: **bound every free-text field with `maxLength`, or generation
   never terminates** — an unbounded JSON string is a state the grammar can always extend, so
   the model writes prose forever and runs to the token cap. Raising the cap makes it worse.
2. **The measurement rig** — `ami_finetune_kit/`: the datagen recipes, the 468-prompt held-out
   instrument, the Wilson-interval + McNemar scorer, and `run_constrained.py`. This is how any
   future model question gets answered here, and CR210's before/after runs through it.
3. **[P28](../../initial_specs/08_tech/failure_patterns.md)** — *the held-out set was generated
   by the code that generated the training set*. 167 of 456 eval prompts were verbatim training
   rows, which is what manufactured the fake "0% → 93% refusal breakthrough". `_assert_held_out()`
   now fails the build on any verbatim overlap.
4. **The habit that actually found everything.** Six instrument defects in three days — a
   negation-blind conflict check, a too-narrow refusal pattern, a scorer joining on a non-unique
   key (116/468 prompts scored against another prompt's completion), the decontamination
   failure, N/A rendered as 0%, and an absolute threshold the control arm itself failed. Every
   one was caught by reading raw completions after a number looked wrong **in either direction**
   — including the ones that looked too good.

## The mistake worth naming

**The control arm should have run first.** It cost roughly one GPU-hour and it answered the
question two 20-hour training runs were built to answer. We reached for it only after the
acceptance table came back ambiguous — by which point the alternative it described had already
been paid for twice.

The generalisable form: when a proposed intervention has a cheap inference-time substitute, the
substitute is the baseline, not the fallback. Nothing about that ordering required hindsight.

## Reopening

Not on the current evidence. Conditions that would change the answer:

- **A verifiable-reward stage (RLVR/GRPO).** Most of the Tier-A labels are computed, not judged —
  exactly the setting where SFT is the weaker lever. This is the honest next experiment, and it
  is the question the [forum write-up](POSTMORTEM_forum_post.md) puts to people who have run it.
- **A capacity result.** r=32 / 22.7 M trainable on a 31.6 B hybrid Mamba-MoE may simply be too
  small a surface. Untested here.
- **A different base.** Fastino is *already* finance-tuned; there may be no headroom left to take.

None of these is scheduled. Parked with it: NVFP4 quantization (Phase 3 — no accepted model to
quantize) and the backend idea of rendering the Trader numeric block in Python rather than
repairing the model's arithmetic after the fact (mentioned, never filed).

The kit stays. The GPU-hours don't get spent again without one of the above being answered first.

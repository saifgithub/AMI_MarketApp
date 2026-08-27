# CR196 — the reading we should have done first

> Compiled 2026-08-27 (AT:R70 CR196), after the track closed. Not a plan and not a
> reopening: a curated answer to "what would a competent version of this have read
> before spending 46.6 GPU-hours?" Every entry is annotated with the specific CR196
> failure or open question it speaks to, so a future reader can go straight to the
> two or three that matter rather than reading the list.
>
> Companions: [`WRAPUP.md`](WRAPUP.md) (what it cost, where the artifacts are),
> [`POSTMORTEM_forum_post.md`](POSTMORTEM_forum_post.md) (the public write-up).

## The two roots

CR196's negative result has two independent causes, and they are not equally bad.

**Root 1 — the eval instrument was never validated.** There was no *positive control*:
nothing ever established that the harness could register a win. Six scorer defects were
found in three days, each producing a confident wrong number in both directions, and
every one was found by reading raw completions after a number looked odd — by suspicion,
not by a check. Without a positive control a null result is uninterpretable: "the
intervention did nothing" and "the ruler does not move" are indistinguishable. We spent
46.6 GPU-hours producing a number we had no basis to read. This is the worse root,
because it is why the second went unnoticed for three days.

A positive control would have caught five of the six defects on day one — `false_conflict`
scoring a correct no-conflict read as a failure; `P_REFUSE` at 0/15 when 14/15 were correct
declines; `gave_code` reporting 0/60 when the truth was `_NA: 60`; the `l1_plus` threshold
the control arm itself could not reach; the non-unique join key scoring 116 prompts against
another prompt's completion. In each case a hand-authored known-good answer scores 0.

It would **not** have caught the 37% verbatim contamination (that needs the mirror-image
check, which is what `_assert_held_out` became — see P28) or root 2.

**Root 2 — the corpus had no variety.** The 453 refusal rows resolve to **13 distinct
question templates**, ~35 rows each, one brief skeleton, only the ticker's numbers changing.
All 13 also appear in the S7 eval set. Masking tickers and digits, five of the eight eval
surfaces are shapes the model trained on (S4 2/2, S7 13/13, S8 4/4, S5 27/30, S2 27/33,
S6 33/54); only **S1 is template-disjoint — 0/43 — and S1 is where we measured honest
parity**. The two surfaces we called wins are the template-saturated ones, and what moved
there was form. Decontamination guarded tickers and verbatim strings; it never guarded shape.

Everything below is sorted against those two.

---

## 1. The instrument — root 1

**[Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)**
Read this one first. It contains our exact failure as a named rule: *"a 0% pass rate across
many trials usually signals a broken task, not an incapable agent"* — which is `P_REFUSE`
scoring 0/15 against 14/15 correct declines. Also *"aggregate scores can hide broken
graders"*, calibrate a judge against human-labelled examples before trusting it, 20–50 tasks
drawn from real failures, grade the output rather than the path. The closest thing in print
to the diagnosis this CR arrived at by hand.

**[OpenAI — Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)**
The mechanical companion: grader design, and when a code-based check beats a model-based one.

**[Judge Reliability Harness — arXiv 2603.05399](https://arxiv.org/pdf/2603.05399)**
A library for validating that a grader is reliable *before* it decides anything. Its method
is the positive control formalised: hand-crafted cases instantiating each level of the scale,
checked that the grader reproduces the distinctions it claims to encode.

**[DeepEval — what an eval harness is](https://deepeval.com/blog/what-is-an-eval-harness)**
Names the one-sided-eval pitfall outright: *"a refusal policy tested only on things to refuse
looks perfect until it refuses everything."* We built exactly that shape and only avoided the
trap because `recipe9_refusal.py` happened to include ~25% answerable controls.

**The check this points at, stated once:** every scorer runs against hand-authored known-good
and known-bad fixtures per check, and must return 1.0 and 0.0, before it is permitted to score
a single model output. A check that cannot hit both ends does not measure anything. Cost is
fixtures, not GPU time.

## 2. Was SFT the right lever at all — postmortem Q1 and Q4

**[LoRA Learns Less and Forgets Less — arXiv 2405.09673](https://arxiv.org/pdf/2405.09673)**
The most directly relevant paper to our result. LoRA vs full fine-tuning on code and math:
LoRA **substantially underperforms on acquiring target-domain capability** but is better at
not forgetting, and full fine-tuning learns perturbations of **rank 10–100× greater** than
typical LoRA configurations. We ran r=32 on 0.07% of parameters (22.7M of 31.6B) with the
routed experts frozen. This makes postmortem Q3 (capacity) the main question rather than a
side one, and says the literature already leans toward "yes".

**[Mix-CPT — arXiv 2407.10804](https://arxiv.org/pdf/2407.10804)**
Explicitly decouples *knowledge learning* from *format alignment* and argues they need
separate stages. That is precisely the split our numbers showed: formats to 100%, capability
unmoved.

**[A Layer-wise Analysis of Supervised Fine-Tuning — arXiv 2604.11838](https://arxiv.org/pdf/2604.11838)**
and the superficial-alignment literature generally — SFT shifts stylistic tokens while
preserving semantic representations, and forcing knowledge injection at this stage disrupts
internal consistency and worsens hallucination. Our single regression was `false_conflict`
0/44 → 2/44, the model inventing disagreements. Consistent.

## 3. If the track ever reopens — the recipe we never searched for

We copied Fastino's published recipe wholesale (r=32, α=64, lr 1e-4, 2 epochs) and ran zero
ablations. `train_lora`'s own loss curve shows the run converged by step ~500 of 2,504
(loss 2.05 → 0.28, token accuracy 0.54 → 0.92) and then sat flat — roughly 14 of the 18
GPU-hours bought nothing measurable.

**[Unsloth — LoRA hyperparameters guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide)**
Practical and current. Flags one thing we took by default: PEFT scales by α/r, so α=2r
matters at high rank, and **α/√r** is the newer recommendation for stability as rank rises.

**[Amazon Science — optimizing LoRA target module selection](https://www.amazon.science/blog/optimizing-lora-target-module-selection-for-efficient-fine-tuning)**
The finding that bears on us: **targeting MLP or all modules beats attention-only.** Our 93
modules were attention q/k/v/o + Mamba `in_proj` + shared experts, with 3,072 routed expert
matrices frozen by a reasoned but never-tested choice (`train/config.yaml`).

## 4. RLVR — postmortem Q4

Every label we generate is computed rather than judged, which is the RLVR setup exactly.

- **[Unsloth RL guide](https://docs.unsloth.ai/get-started/reinforcement-learning-rl-guide)** — most practical entry point, runs on our hardware class.
- **[Acing AI — RLVR in practice with GRPO in TRL](https://acingai.com/tutorials/rlvr-verifiable-rewards)** — hands-on, TRL-based (the stack we already have working), covers the DAPO/GSPO stability fixes.
- **[awesome-RLVR](https://github.com/opendilab/awesome-RLVR)** — curated index, verifier design in particular.
- **[Promptfoo — RLVR makes models faster, not smarter](https://www.promptfoo.dev/blog/rlvr-explained/)** — read as the counterweight *before* committing. The claim is that RLVR sharpens sampling of capabilities already present rather than adding new ones. If true it predicts the same null we already have.

## 5. Adjacent — the distillation comparison

**[NVIDIA — Build Efficient Financial Data Workflows with AI Model Distillation](https://developer.nvidia.com/blog/build-efficient-financial-data-workflows-with-ai-model-distillation/)**
([blueprint repo](https://github.com/NVIDIA-AI-Blueprints/ai-model-distillation-for-financial-data))
Reviewed 2026-08-27 against CR196 and it does **not** change the verdict. Different problem:
13-way headline classification, optimising **cost** (70B → 1B, ~98% inference cost reduction),
labels from a **teacher** model, and F1 normalised so the teacher scores 1.00 — i.e. the metric
is agreement-with-teacher, not correctness. Distillation is not a third lever for us because we
have no teacher that beats our base: Fastino scored 43/44 on the basis rubric and Qwen3.6-35B
scored 21/43. Two things do carry over: their gains scale inversely with base competence
(1B base 0.32 → +0.63; 3B base 0.72 → +0.23), which is evidence for our Q2; and their
5k → 10k → 25k curve is **25k examples of one task**, i.e. narrow-and-deep, against our
broad-and-shallow 16 recipes. Their variety is free (distinct real headlines); ours is capped
at however many question shapes we hand-write, which is the honest cost of going narrow-and-deep.

---

## What this list is evidence for

None of it is exotic. Anthropic's eval guide, the Unsloth hyperparameter page and
LoRA-Learns-Less are the first things you would read before starting. We had the GPU, the
corpus and the harness before we had any of them — that is the shape of the mistake, more
than any individual wrong setting.

It also partly answers "did we simply not know how to fine-tune this?". Optimisation worked:
loss 2.05 → 0.23, token accuracy 0.54 → 0.94, every taught format at 100%. The model learned
what we put in front of it, thoroughly and early. What we can support is **"one untuned config,
run twice, on 13-template data, against an instrument with no positive control, did nothing"** —
a weak negative, not a general finding about SFT. Both papers in §2 predict that outcome, which
is corroboration of the result and no defence of the method.

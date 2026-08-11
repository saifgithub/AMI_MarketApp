# CR143 — agent prompt audit: what's in this folder

Everything from the audit of the 13 agent prompts. Start with whichever question you have.

## Read these

| File | What it answers |
|---|---|
| [CR143_agent_prompt_audit.md](CR143_agent_prompt_audit.md) | Why this audit exists, what each phase does, where it stands |
| [PHASE1_ground_truth.md](PHASE1_ground_truth.md) | What the model is actually sent; what reads its reply; what backs each claim in each prompt |
| [PHASE3B_quality.md](PHASE3B_quality.md) | **Are the prompts any good at their job?** The measurements — role separation, analyst differentiation, number grounding, disagreement |
| [EXTERNAL_REVIEW.md](EXTERNAL_REVIEW.md) | What an outside model (Kimi) found reading our prompts cold, and which of its claims survived checking |
| [PHASE5_feasibility_verdict.md](PHASE5_feasibility_verdict.md) | **Which of the proposed accuracy fixes are actually buildable.** Each of `research/accuracy_improvements.md`'s eight levers checked against the code, what to build in what order, and the five findings dropped with reasons |
| [../CR167_tradingagents_upstream_drift/](../CR167_tradingagents_upstream_drift/) | **What the repo we forked from learned in the 106 commits since our snapshot.** They hit our DEF063 (a prompt demanding data no tool could supply) and our P1 degrade-loudly class independently. Two gaps filed as CR168/CR169; two of §8's traps answered for free by their `517eeaf` — vLLM rejects the object-form `tool_choice`, and a thinking model can return no parsed result. §4's numeral-sweep rejection is reinforced there, not reopened |

## The evidence

| Path | What it is |
|---|---|
| `assembled/room/*.txt` | The **complete** prompt each of the 12 agents receives in a Convene. This is the real thing, not the `content/agents/*.md` source file — that file is only ~10–18% of it |
| `assembled/one_on_one/`, `assembled/concierge/`, `assembled/brief/` | The same 13 agents on their other three surfaces. 38 prompts total |
| `assembled/_manifest.json` | Where each layer sits inside each prompt, and how many characters it costs |
| `assembled/_profile.json` | The live market data (AAPL) the fact sheet was built from |
| `external_review/room/*.md` | Kimi's raw, unedited review of each of the 12 Room prompts |
| `quality_metrics_2026-08-07-epoch.json` | The raw output behind every number in `PHASE3B_quality.md` |

**Caveat on `assembled/`:** the mandate and portfolio in these files are a fixed synthetic fixture, not
a real user. Treat the *structure* as verified and the *values* as illustrative — an early version of
that fixture had four bugs in it (see `EXTERNAL_REVIEW.md`).

## Defects this produced

- **DEF235** — our level-scanner read a share price as a position size and published a drawdown figure
  63× too large, labelled "these are the figures of record". Root cause: the scanner needs a layout a
  later prompt layer forbids.
- **DEF236** — three instructions in every prose agent's prompt cannot all be satisfied; the model
  drops the one our token budgets were sized on.
- **DEF063** needs re-scoping — half of it is already fixed (the social feed is live via Adanos); only
  the Alpha Vantage sentiment tags are genuinely missing.

## Reproducing it

The scripts live in `backend/scripts/`. Run from `backend/`.

```bash
# 1. Rebuild the assembled prompts (needs live market data, or every field renders "unavailable")
USE_REAL_MARKET_DATA=true .venv/bin/python -m scripts.dump_assembled_prompts --ticker AAPL

# 2. Prove the reconstruction matches what Alpha really sent
.venv/bin/python -m scripts.dump_assembled_prompts --verify

# 3. Have an outside model review them
KIMI_API_KEY=$(ssh melehost "grep '^KIMI_API_KEY=' ~/ami_trade/.env | cut -d= -f2-") \
  .venv/bin/python -m scripts.kimi_prompt_review --surface room

# 4. Measure prompt quality (needs the corpus from step 5 below)
.venv/bin/python -m scripts.prompt_quality_sweep --corpus <dir> --out quality.json
```

### The raw corpus IS committed, under `corpus/`

Saved in full — Saiful's call, 2026-08-08: *"There is no real user data. we are in alpha still. save
it all otherwise it will be a waste."* Alpha traffic is his own test and benchmark users, so the
holdings blocks embedded in these prompts are synthetic portfolios, not anyone's finances. Revisit
this before Beta, when the same query would return actual customers.

| File | What it is |
|---|---|
| `corpus/llm_audit_2026-08-07-epoch.json` | 216 agent turns — the full prompt each one got and the reply it gave. 3.4 MB |
| `corpus/room_runs_2026-08-07-epoch.json` | 18 convenes — verdict, transcript, stances, status |
| `corpus/sample_real_alpha_pm_prompt.txt` | One untouched PM prompt straight out of `llm_audit`, used to prove the reconstruction faithful |
| `corpus/kimi_first_pass_pm_review.md` | Kimi's very first review — the one that caught four bugs in the dump fixture |

This is what makes every number in `PHASE3B_quality.md` re-checkable by hand rather than taken on
trust, which is the whole point of P16.

To regenerate it (e.g. for a later epoch):

```bash
# corpus.json — one row per agent turn, with the prompt it got and the reply it gave
ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -t -A -c \"
  select encode(convert_to(json_agg(row_to_json(t))::text,'UTF8'),'base64') from (
    select id, created_at, agent_id, flow, response_text, system_prompt
    from llm_audit where flow in ('room','room_pm') and created_at > '2026-08-07 12:00'
    order by created_at) t;\"" | tr -d '\n' | base64 -d > corpus.json

# runs.json — one row per convene, with the verdict and full transcript
ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -t -A -c \"
  select encode(convert_to(json_agg(row_to_json(t))::text,'UTF8'),'base64') from (
    select id, triggered_at, ticker, status, verdict, transcript
    from room_runs where triggered_at > '2026-08-07 12:00' order by triggered_at) t;\"" \
  | tr -d '\n' | base64 -d > runs.json
```

Base64 is not decoration: `psql`'s plain output escapes newlines inside the JSON and corrupts it.

**Always pick one prompt epoch.** Every rate here is meaningless if pooled across a prompt change —
that error is what made an 18.4% figure in the original filing wrong. The current epoch starts
**2026-08-07 12:00**; earlier boundaries are the commits listed in `CR143_agent_prompt_audit.md`.

# CR143 — an outside model reads our prompts

Every reading of these prompts so far has been by someone who knew what they were meant to say.
That is precisely the weakness CR105's Amendment 1 records: its findings came from a read of
`content/agents/*.md`, and two of four were wrong once checked against the code that parses the
output. A reader with no access to our intentions and no access to our code is a different
instrument — it can only see what the prompt actually says.

Reviewer: **`kimi-for-coding`** via the Coding Plan endpoint (`api.kimi.com/coding`) — the model this
project's `KIMI_API_KEY` reaches, not a general Moonshot model and not "k3". Harness:
`backend/scripts/kimi_prompt_review.py`. Input: the **assembled** prompts from
`dump_assembled_prompts.py`, never the base files. Raw reviews in [`external_review/room/`](external_review/room/).

**Its output is a hypothesis list, not findings.** It cannot see `enforce_safety_floor`, so it
reports confidently that our deterministic compliance gate does not exist. Every claim below was put
through a supplier check, a parser check, or a corpus measurement before it moved.

---

## First result: it audited the auditor

Of the eight contradictions it found in the PM prompt, **four were bugs in my dump fixture**, not in
the product:

| What it flagged | Verdict |
|---|---|
| holdings listed AAPL as held *and* asserted `You hold 0% of AAPL` | **my fixture** |
| cash + positions did not sum to the stated portfolio value | **my fixture** |
| `current sector allocation: Cash 5180%, Technology 3700%` | **my fixture** — I passed percentages to a formatter that multiplies by 100; `allocate_by_sector` returns fractions |
| `risk-tier ceiling 5.0% size` vs `Single-name position-size cap: 3.0%` | **my fixture** — I hardcoded `size_pct: 5.0`; production derives it from the same resolver. **72 of 72 real Alpha prompts carrying both numbers agree** |

All four are fixed and the corpus re-dumped. The uncomfortable part: **`--verify` passed every one of
them.** It compares layer order and segment sizes against real `llm_audit` rows and says nothing
about whether the content is coherent — a reconstruction can be structurally perfect and still be
nonsense. That limitation is now recorded in `PHASE1_ground_truth.md`.

## What survived: two defects, one root cause

### DEF236 — three adjacent instructions that cannot all be satisfied

Within five lines of each other, every prose agent is told to write *"2 sentences"*
(`_LENGTH_GUIDE`), to *"lead with a one-sentence thesis, then short bullet points"* (`_PROSE_FORMAT`),
and to emit a stance envelope line *before* the thesis (`_STANCE_FORMAT`). Measured on the epoch
(n=198), the model resolves it by discarding the length guide:

| agent | guide | median | over budget | bullets |
|---|---|---|---|---|
| neutral_debator | 2 | **5** | **100%** | 94% |
| conservative_debator | 2 | 3 | **100%** | 89% |
| bull_researcher | 3–5 | **8** | 83% | 83% |
| research_manager | 4–6 | **9** | 61% | 39% |
| trader | 3–4 | 5 | 61% | 61% |
| fundamentals_analyst | 2–4 | 5 | 61% | 83% |

`_AGENT_MAX_TOKENS` was sized per-agent by DEF125 to fit that guide, so every decode budget in the
Room is calibrated to a target the model cannot structurally meet.

### DEF235 — root cause found, and it is the same conflict

DEF235 (filed earlier from the Phase 3b sweep: AMI published a drawdown contribution **63× too
large** under *"These are the figures of record"*) was diagnosed as an under-tested regex. The
external review supplies the real cause. `_LEVEL_PATTERNS` reads the `Entry:`/`Stop:`/`Target:`/`Size:`
labels from `trader.md`'s ticket block — where each label sits alone on its own line inside a code
fence and collision is impossible. `_PROSE_FORMAT` then forbids code fences and demands prose.
**The parser depends on a format the Room instructs the model not to use.** Measured: of 16 Trader
turns stating an entry, only **5** used the line-anchored label; **11 (69%)** stated levels inline,
which is where `"size entry at $188.62"` becomes ordinary English and the pattern misfires.

## Confirmed but not yet filed

| Finding | Evidence |
|---|---|
| The base prompt's own example models fabrication — *"never vague language ('strong margins' → '32.4% gross margins, up 180bps YoY')"* — while gross margin and bps deltas are never supplied and the grounding directive forbids recall | verified: the only occurrence of "gross margin" in the assembled prompt is the example itself |
| An unfollowable compliance rule: *"Liquid only. Avoid microcaps (< $500M market cap)"*, while market cap is never supplied and the same prompt says *"Do NOT cite figures (…market cap) from training memory"* | verified in the assembled prompt |
| Tone vs format: `LearningStyle.QUICK` renders *"terse, tabular, declarative"* (`overlay_generator.py:229`) against `_PROSE_FORMAT`'s *"no tables"* | verified in code |
| The News Analyst is told *"Do NOT predict whether a stock will go up or down"* and then required to emit `STANCE: for\|against\|neutral` | measured: **5 of 18** convenes had it take an explicit for/against; `STANCE: none`, the designed escape, was used **0** times |
| The overlay asks for *"balance sheet strength, capital allocation"* while the base prompt says full financial statements and buyback/M&A history are unavailable | verified in the assembled prompt |
| `net cash` claimed in the input list; `Net debt $21945M` delivered | verified |

## Rejected

- **"There is no external checker; the model is being asked to simulate a deterministic gate."**
  `enforce_safety_floor` exists and runs on every verdict. The reviewer cannot see the code — this is
  the expected failure mode of the instrument, and the reason nothing here ships unverified.
- **"The scope firewalls are undermined by handing every analyst the same fact sheet"** (news, RSI and
  sentiment are visible to all four). Plausible on paper; Phase 3b measured the four parallel analysts
  as the **least similar pairing in the corpus (0.128)**. The firewall holds empirically.
- **`Side: BUY | SELL | HOLD | WAIT` contradicts long-only.** Partly right, but CR055 settled that
  long-only bars shorts and not sells; a SELL closing a held long is legitimate. The genuine residue —
  that the prompt never disambiguates close-a-long from open-a-short — is too thin to file alone.

## On the instrument itself

Two operational notes for anyone re-running this. Kimi shares one token budget between reasoning and
answer (the CR130 trap): at `max_tokens=64` the reply came back **empty** with 63 reasoning tokens,
and at 16k the two longest prompts still exhausted the budget before writing anything. The harness now
retries with a doubling budget rather than recording a false "no findings". The first full run also
died mid-way on a `ConnectionResetError` — an `OSError`, not a `urllib.error.URLError`, so it escaped
the handler and killed the whole pool; now caught and retried.

**Verdict on the method: worth repeating.** It found four defects in my own instrumentation that my
faithfulness check certified as sound, and it supplied the root cause for a defect I had already filed
with the wrong diagnosis. It did not find anything about model quality — that is what Phase 3b
measures — and roughly a third of its claims were artifacts or wrong. Used as a hypothesis generator
with mandatory verification, the yield was high; used as a verdict, it would have produced four false
defects on day one.

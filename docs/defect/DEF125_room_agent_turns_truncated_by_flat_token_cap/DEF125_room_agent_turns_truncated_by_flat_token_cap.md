# DEF125 — A flat 400-token cap cuts the Research Manager and Bull Researcher off mid-sentence in most convenes

**Filed:** 2026-07-27 · **Track:** AT:R59 (room-quality) · **Kind:** Defect · **Area:** backend / prompt
**Found by:** the BBAI convene review — the Bull Researcher's message ends
`…with a buzz score of **3` and stops.

---

## What happened

In BBAI run `1906ccf2-bae9-49c8-a83e-9e82e18ec144` the Bull Researcher's stored message is 1,609
characters and terminates mid-word, inside its third evidence bullet. That truncated text is what
was appended to the transcript, and therefore what the **Bear Researcher, Research Manager, Trader,
all three Risk debators and the PM** read as the bull case.

This is not a one-off. Every Room agent turn is issued with a hard-coded cap:

**`backend/app/services/room_runner.py:2260`**
```python
chunks = await asyncio.wait_for(
    _collect_agent_stream(gateway.stream_chat(
        …
        max_tokens=400,
```

One flat budget for all 11 streamed agents, regardless of what each one's own prompt asks for.
The Research Manager is asked for a three-part structured synthesis (points of agreement / points
of dispute / recommended stance); the researchers are asked for a thesis plus evidence bullets.
Those do not fit in 400 tokens.

## Scale — measured, not estimated

`llm_audit` on melehost, `flow='room' AND error IS NULL`, 30-day window, ~884 calls per agent.
"Ends mid-word" = `response_text ~ '[A-Za-z0-9]$'` — no terminal punctuation, no closing markdown.

| Agent | Ends mid-word | Total | Rate | Max chars | Avg chars |
|---|---:|---:|---:|---:|---:|
| **research_manager** | **584** | 884 | **66.1%** | 1,880 | 1,573 |
| **bull_researcher** | **536** | 885 | **60.6%** | 1,966 | 1,550 |
| **bear_researcher** | **226** | 884 | **25.6%** | 1,806 | 1,383 |
| neutral_debator | 61 | 883 | 6.9% | 1,608 | 1,115 |
| trader | 19 | 884 | 2.1% | 1,629 | 936 |
| fundamentals_analyst | 5 | 885 | 0.6% | 1,598 | 975 |
| news_analyst | 1 | 885 | 0.1% | 1,485 | 831 |
| aggressive_debator | 1 | 884 | 0.1% | 1,531 | 575 |
| market_analyst | 1 | 885 | 0.1% | 1,247 | 708 |
| conservative_debator | 0 | 884 | 0% | 1,439 | 518 |
| social_media_analyst | 0 | 885 | 0% | 1,283 | 729 |

The three affected agents' averages sit hard against their maxima (1,573 vs 1,880; 1,550 vs 1,966)
— the distribution is pinned at a ceiling, which is what a `max_tokens` cut looks like. ~1,900
chars ≈ 400 tokens at this model's ratio. The four analysts and two of the three debators are
comfortably inside the budget and unaffected.

**The Research Manager is the worst case and the most damaging one.** Its synthesis is the single
input the EXECUTION and RISK phases reason from, and it is cut off mid-sentence in **two out of
three convenes**. Whatever the RM was about to conclude, the Trader never sees it.

## Why it matters

- **The Room's conclusion is being silently amputated.** DEF095 established that the transcript is
  the contagion vector — downstream agents treat upstream text as fact. A truncated synthesis is
  worse than a wrong one: it reads as complete.
- **It is invisible.** Nothing logs a length-stop, nothing flags it in the transcript, and the
  client renders the fragment as a finished statement. Classic CR040 — the failure is total and
  silent.
- **It corrupts the paid product first.** The most expensive agents by decode time (Bull 10.7s,
  RM 10.6s, Bear 9.7s ≈ 40% of a convene's cost, measured for CR098) are precisely the three being
  cut off. We pay full price for a truncated output.
- **It may be why DEF058 looked prompt-shaped.** DEF058 (PM verdict fails to parse in ~22% of runs)
  suspected `max_tokens=600` truncating the JSON tail on the PM path. Same root cause, one line
  apart. Worth confirming the two are the same family.

## Proposed fix (build team decides the shape)

1. **Budget per agent, not per Room.** The cap should be a per-agent value sized to what that
   agent's prompt actually asks for — the analysts are fine at 400; RM / Bull / Bear demonstrably
   are not. Prefer a table keyed by `AgentId` over a single raised constant, so raising the
   researchers doesn't pay decode cost on the four analysts that never approach the limit.
2. **Never store or forward a length-truncated turn silently.** The gateway knows the stop reason;
   surface it. Minimum: log it. Better (CR040): mark the transcript entry so a truncated message is
   visibly incomplete rather than silently short, and never let a truncated Research Manager
   synthesis flow into EXECUTION unannounced.
3. **Re-measure after the change** — the mid-word rate for RM/Bull/Bear must fall to near zero, and
   the cost delta should be checked against the CR098 decode-time baseline before promotion.
4. Confirm whether the PM's `max_tokens=600` (`room_runner.py:2430`) and the reformatter's 400
   (`:2499`) are adequate, given DEF058.

## Verification

1. `cd backend && .venv/bin/python -m pytest tests/unit/ -q` green.
2. Unit test: an agent stream that hits the length stop must not be appended to the transcript as a
   normal completed turn.
3. Re-run the 30-day measurement query above post-fix; RM/Bull/Bear mid-word rate → ~0%.
4. Live smoke after promotion: convene a ticker, confirm every one of the 12 messages terminates on
   a sentence boundary.

## Related

**DEF058** (PM verdict JSON truncation, `max_tokens=600`, one line away — likely the same family),
**DEF095** (the transcript is the contagion vector; downstream agents inherit upstream defects),
**CR040** (degrade loudly — a silent length-stop is the definition of a quiet failure),
**CR098** (its measured decode-cost baseline is the yardstick for any budget increase),
**DEF123** / **DEF124** (the other two findings from the same BBAI convene).

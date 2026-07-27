# DEF129 — The Concierge is told it can schedule briefings and mute/promote agents; neither exists

**Filed:** 2026-07-28 · **Track:** AT:R59 (room-quality) · **Kind:** Defect · **Area:** backend / prompt
**Origin:** split out of **CR105** (original scope item 7, "verify before treating as a defect"). Verified — it is a defect, and it is live.

---

## What is claimed

Two capability claims reach the Concierge's live system prompt on **every** message, from two
separate layers:

- `content/agents/concierge.md:19-20`
  ```
  - Schedule morning briefings and reminders (paid tiers only)
  - Mute / promote agents
  ```
- `backend/app/agents/overlay_generator.py:484-485` — the same two lines, in
  `_concierge_overlay()`.

Both land in the assembled prompt: `concierge_prompts.py:115` calls
`build_agent_prompt(AgentId.CONCIERGE, …)`, which composes the base `.md` with the overlay
(`overlay_generator.py:47-49` dispatches the Concierge to `_concierge_overlay`), and `:142`
concatenates that into `system_prompt`.

## What exists

Neither.

| Claim | Wiring found in `backend/app` |
|---|---|
| Schedule briefings / reminders | **No scheduler, no cron, no sender.** `daily_briefing` is a *mandate field* (`schemas/mandate.py:117`) collected at onboarding (`Q8_BRIEFING`) and echoed back in the mandate summary (`concierge_engine.py:486-490`). Nothing delivers it. |
| Mute / promote agents | **Zero `mute` symbols anywhere in `backend/app`.** Every `promote` hit is league promotion (`league_service.py`), auth row promotion, or the `/promote-to-alpha` deploy path — none is agent control. |

The Concierge also has **no tool layer at all** — no tool/function-call machinery in
`concierge_engine.py`. It can only talk. So the claim is not "wired but broken"; there is nothing
to wire it to.

## It has already fired on a real user — measured

`llm_audit`, `agent_id='concierge'`, all time: **30 turns**, of which **1** offers the
non-existent agent controls. Verbatim from that reply:

> *"**To Mute/Promote an Agent:** Go to the **Agents** tab (the grid of 12). Tap the agent you
> want to adjust. You can **Mute** them (hide from the Room) or **Promote** them (boost priority
> in research)."*

The model did not merely repeat the bullet — it **invented the navigation path and the semantics**
("hide from the Room", "boost priority in research"), told the user where to tap, and opened by
asserting the absence from Settings was *"by design"*. A user following that goes looking for a
control that does not exist and concludes the app is broken or that they cannot find it.

Zero of the 30 turns mention briefings, so the scheduling claim has not yet been observed firing —
but the mechanism is identical and n is small; absence of an instance is not evidence of safety.

## Why it matters

- **CR023 fabricated-capability class**, exactly: a prompt asserts a product capability the
  backend does not have, and the model elaborates it into confident, specific user instructions.
- **CR040, degrade loudly** — this is the silent-confident-wrong shape. There is no failure signal
  anywhere: the reply is fluent, the run is green, nothing logs an error.
- **CR038** — the fix is *not* to add "only describe features that exist" to the prompt. Prompt
  instructions are ignored ~30% of the time. Remove the claim.
- It is the **Concierge**, the app's product-help surface — the one agent a confused user asks
  "how do I…". Wrong navigation advice from the help agent is worse than wrong advice anywhere else.

## Fix

Structural, per CR038 — **delete the claims, both copies**:

1. `content/agents/concierge.md:19-20` — remove both bullets. Optionally replace with an explicit
   negative in the same style the analysts already use (`market_analyst.md`: *"No MACD … do not
   cite them"*, `social_media_analyst.md`: *"No Twitter/X, StockTwits … they simply don't exist"*):
   *"You cannot schedule briefings, set reminders, or mute/promote agents — none of those controls
   exists in the app. If asked, say so plainly."* The negative form is what stops the model
   inventing the feature from the surrounding product context rather than from the bullet.
2. `backend/app/agents/overlay_generator.py:484-485` — same removal. **Both layers, or the drift
   just moves** (P4: a claim in any layer leaks).
3. Decide the `daily_briefing` mandate field separately — it is collected at onboarding and shown
   back to the user as *"07:00 daily briefing"*, which is itself a promise nothing keeps. Either
   wire a sender or stop presenting it as active. **Out of this defect's scope; flag to Saiful as
   a product call.**

## Guard

Fold into **CR105 scope item 5** (the analyst-inputs ↔ provenance alignment guard) rather than
adding a one-off test: assert no agent prompt — base `.md` or overlay — claims a capability with
no backing symbol, using the same assembled-prompt shape as
`test_def084_overlay_narration_copy_guard.py`. Second occurrence of the CR023 class ⇒
`failure_patterns.md` entry with the guard named, per CLAUDE.md conventions.

## Verification

1. Assembled Concierge system prompt (`build_concierge_prompt`) contains neither
   "Mute / promote" nor "Schedule … briefings".
2. `cd backend && .venv/bin/python -m pytest tests/unit/ -q` green.
3. Live smoke after promotion: ask the Concierge *"how do I mute an agent?"* and *"can you send me
   a morning briefing?"* — both must answer that the capability does not exist, with no invented
   navigation path.

## Related

**CR023** (fabricated capability — the originating class), **CR038** (structural over
prompt-instructional), **CR040** (degrade loudly), **CR105** (split from its scope item 7; the
guard lands there), **DEF084** (the copy-guard test shape to copy).

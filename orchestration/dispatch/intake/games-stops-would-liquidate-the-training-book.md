# Intake — a game stop/target would close the position against the TRAINING portfolio

**Handle:** `games-stops-would-liquidate-the-training-book` (pre-triage; no
`DEF###` minted — the Architect is the single ID-minter and other tracks are
live on this checkout).
**Found:** 2026-08-10 (AT:R66), while deciding whether to build §5.4's
stop/target presets onto the game trade ticket.
**Severity:** high if reached; **latent today** — nothing sets a stop on a
game trade, because the client has never sent one.

## Why this was looked at

CR109 §5.4 lists "stop/target presets" as part of the 3-tap ticket, and it is
one of the surfaces the slice-2 gap audit still had open. The API already
accepts them end to end: `GameTradeRequest.stop` / `.target` /
`.horizon_days` → `games_service.submit_trade` → `sim_engine` → the
`SimTradeRow`. Building the UI looked like a one-screen job.

It is not, and the reason matters.

## The defect

`SimEngine.evaluate_outcomes(user_id)` — `sim_engine.py:1193` — is what
actually fires a stop or a target. It selects the trades to check like this:

```python
select(SimTradeRow).where(
    SimTradeRow.user_id == user_id,
    SimTradeRow.status == "open",
)
```

**By `user_id` alone.** There is no `portfolio_id` filter and no `run_id`
filter, even though `_execute_fill` correctly stamps `portfolio_id=p_row.id`
on every row it writes, so a game trade IS attributable to its game
portfolio.

It then loads one portfolio to sell against:

```python
p_row = self._load_portfolio_row(s, user_id)
```

…which defaults to `kind="training", run_id=None` (`sim_engine.py:391`).

So for a user who has both a training book and a live game run, a stop set on
a GAME position would be evaluated by the training sim and liquidated against
the TRAINING portfolio: the training book's cash credited, the training
holdings reduced, for shares held in the game. The game position stays open
and the game's NAV is untouched.

Its only caller is `api/sim.py:467`, on the training path. Nothing in the
game's own lifecycle calls it — so today a game stop would ALSO simply never
fire, which is the second half of the problem.

## Why it has not bitten

The client has never sent `stop` or `target` on a game trade. `stop is None`
short-circuits the loop body (`sim_engine.py:552`), so game rows are found by
the query and then skipped. The bug is one UI control away from live.

## Why the UI was NOT built

Shipping the presets would have put a control on the ticket that either does
nothing or corrupts the training book — the same class as the ticket's
"free to cancel any time before it fills" copy shipping for a week with no
cancel mechanism behind it (fixed 2026-08-10). A control the backend does not
honour is a promise, and CR040's rule is that we do not make one we cannot
keep.

## What a fix needs

1. **Scope the query.** `evaluate_outcomes` must filter to the portfolio it is
   about to sell against — pass `kind`/`run_id` through and join, rather than
   sweeping every open row the user owns. This is worth doing on its own
   merits regardless of stops: it is a cross-book leak waiting for any second
   portfolio kind, and CR109 already introduced one.
2. **Decide whether the game evaluates stops at all**, and if so, where it is
   called from. The game's market-hours rule (§5.1) means a stop that "hits"
   while the US market is shut has no honest price to fill at — the same
   reasoning that keeps a queued order unpriced. That is a design question for
   the CR, not an implementation detail.
3. Only then the ticket UI.

## Note

`horizon_days` has the same shape — accepted by the API, stored, and acted on
by nothing in the game path.

# DEF093 — With the screen disabled, every halal-flagged trade is blocked. "Off" is not a safe default.

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Found by:** Saiful — *"this CR was about getting
the sharia back online. why are we dark?"*
**Against:** CR069-BE, and the Architect's acceptance of it

## What

`sharia_screen_enabled` defaults to `False` ([`config.py:167`](../../../backend/app/core/config.py)),
forwarded as `${SHARIA_SCREEN_ENABLED:-false}` in `docker-compose.yml:146`, and `infra/alpha.env`
carries no override — so the shipped state is **off**.

Off is not neutral. `_build()` returns `_paused()`, which resolves **everything** to `UNAVAILABLE`
([`sharia_universe.py:302-308`](../../../backend/app/services/sharia_universe.py)), and
`ShariaVerdict.is_blocking` treats `UNAVAILABLE` as blocking
([`schemas/sharia.py:61-67`](../../../backend/app/schemas/sharia.py)).

**Net effect: a user with the halal flag on can trade nothing at all**, and is told *"AMI couldn't
refresh the AAOIFI Sharia screen. The halal filter is paused until it can."*

That is a **regression against DEF084's state**, where the flag at least permitted seven tickers. The
CR whose purpose was to bring the screen online shipped it in a state strictly worse than the
placeholder it replaced.

## The conflation

`UNAVAILABLE` is the right answer to *"the source failed"* — for an observance filter, blocking is
the safe direction, and constraint 3 demands the failure be loud. It is the wrong answer to *"we
have not switched the feature on."* Those are different conditions with different owners:

| Condition | Whose problem | Right behaviour |
|---|---|---|
| Source fetch failed / stale | ours, at runtime | block + say so — current behaviour is correct |
| Feature not enabled in config | ours, at deploy time | the user should never have been able to switch on a filter that cannot run |

Blocking a user's trades because *we* have not enabled a feature punishes them for our deployment
state. The honest shape is that the halal toggle is unavailable when the screen cannot run, not that
it silently rejects everything.

## The screen works — measured, not assumed

Run 2026-07-23 through the **shipped provider** with the **shipped config URLs**, on the Mac:

```
sharia_universe_loaded  as_of=2026-07-23  compliant=216  parent=503
  AAPL  pass          blocking=False
  MSFT  pass          blocking=False
  META  screened_out  blocking=True
  JPM   screened_out  blocking=True
  KO    screened_out  blocking=True
  ASML  unknown       blocking=False
  ZZZZ  unknown       blocking=False
```

Correct on every axis: the known AAOIFI exclusions are excluded, non-index names resolve `unknown`
and **permit** per G3, `stale=False`, as-of is today. DEF089 and DEF092 are genuinely fixed.

**So the reason we are dark is not that the screen does not work.** It is that it shipped behind a
default-off flag, and the Architect (me) then treated an already-fixed blocker as though it were
still open.

## Correction to what the Architect told the stakeholder

I said promoting with the flag off would be *"close to inert — nothing user-facing changes."* That is
**wrong**. Promoting with the flag off would take every halal-flagged user from seven tradeable
tickers to zero. The promote is not inert in either direction; it has to go out with the flag **on**.

## Fix

1. **`SHARIA_SCREEN_ENABLED=true` in `infra/alpha.env`**, shipped with the promote. The go-live
   evidence DEF089/DEF092 asked for is the live run above, through the shipped client rather than
   curl.
2. **The disabled-vs-failed conflation stays open** and belongs with `CR069-MOBILE`: when the screen
   cannot run, the toggle should not be offerable. Filed here so it is not lost — it is a real gap,
   just not the one blocking go-live.

## Residual, unchanged

The parent-index mirror carries **no as-of of its own**, so SPUS's date is the only freshness signal.
A frozen parent list would not trip the staleness pause, and could wrongly resolve a name to
`screened_out` (blocking) rather than `unknown`. Lower severity than this defect, still owed a
separate freshness signal.

# DEF094 — The Sharia verdict is computed, enforced, and never sent to the client

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Found by:** `coder.mobile` building CR069-MOBILE
**Owner:** `coder.api` (its path) · **Blocks:** G3's permitted-unknown disclosure

## What

`ComplianceResult.sharia_verdict` exists (`backend/app/schemas/trade.py:91`) and is populated. But
`sim.py:186-190` and `:230-234` **hand-build a three-key dict** for the response and drop it.

Confirmed against the **deployed** `openapi.json`: `ShariaVerdict` appears in **no response schema
across all 102 live paths**. Two trades — `AAPL` (pass) and `ASML` (unknown) — return
**byte-identical** bodies:

```json
{"accepted":true,"compliance":{"passed":true,"violations":[],"blocked_by":null}, …}
```

## Why it matters

**A successful trade carries nothing that distinguishes a screened PASS from an unscreened UNKNOWN.**
G3's whole ruling — *unknown is permitted, with the disclosure attached* — cannot render, because the
disclosure never crosses the wire.

That is the failure this CR exists to prevent, one layer out: the user gets silent permission on a
ticker no scholar body has ruled on, which is a silent pass on an observance decision.

`coder.mobile` explicitly refused the tempting workaround — inferring state from `passed: true` — on
the grounds that it is *"a two-state answer to a four-state question and would mark every unscreened
ticker as screened-and-cleared."* Correct, and it is exactly DEF084's shape.

## How it survived

**This is DEF089/DEF092's lesson pointed at a new surface.** The go-live evidence verified the
resolver **inside the container** — `compliant=216 parent=503`, correct verdicts — and never once
checked that a *client* receives the verdict. Verifying the component is not verifying the contract.

Third time this session that a check proved less than it appeared to: curl instead of the shipping
client (DEF092), one of two sources fetched (DEF089), now the resolver instead of the response.

## Fix

~2 lines in `sim.py`: serialize `sharia_verdict` into the trade response at both sites.

**Answer to `coder.mobile`'s Q1** (it asked rather than reaching into another instance's path —
right call): **a CR069-BE follow-up lane, not this lane widening.** `sim.py` is `coder.api`-owned,
and CR069-MOBILE must not cross that boundary.

## What ships anyway

The Settings copy the stakeholder called *"rubbish"* is fixed and needs **no** backend change. The
mobile half is built and tested; its last fixture asserts the exact payload that lights up the
per-ticker disclosure once this defect is fixed. **App delivery is not blocked by this** — the
unknown-state disclosure simply stays dark until the response carries the verdict.

## Related, accepted knowingly

The **as-of date is absent from the Settings subtitle** — a knowing miss against design constraint 1,
recorded rather than hidden. No client-side source for it exists; fabricating one is DEF084 again,
and rendering the *paused* copy would tell users the screen is down while it healthily serves 216
names. The date does appear on each per-ticker verdict. The ARB `@`-entry records the reasoning.

The AR/MS values still asserted "not a Sharia screen" — false in those locales too. They were removed
so the keys fall back to EN rather than machine-translating observance-sensitive copy.

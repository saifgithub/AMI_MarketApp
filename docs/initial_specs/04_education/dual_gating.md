# Dual Gating — Earn Path vs Skip Path

The mechanism that controls how a user gets access to the 12 agents. **Both paths are first-class.** Neither is the "real" way.

## The two paths

| | Earn Path | Skip Path |
|---|---|---|
| **Who** | Floor Pass (free) users | Trader / Floor Manager (paid) users |
| **Cost** | Time — ~3 hours total for full Earn Path | Money — $14.99/mo or $34.99/mo |
| **Mechanism** | Complete Agent Academy module → agent activates | Subscribe → all 12 agents instantly active |
| **Per-agent unlock** | Yes — granular | All-at-once |
| **Stays unlocked if user downgrades?** | Earn-Path agents always stay unlocked | Skip-Path unlocks revert when subscription ends |

## Why both paths exist

| Cohort | Their need | Path they pick |
|---|---|---|
| **Beginners with time** | Want to learn, broke or value-conscious | Earn Path |
| **Time-poor professionals** | Know fundamentals, don't want to grind tutorials | Skip Path |
| **Curious explorers** | Not sure if app fits, want to try | Earn Path (start) → maybe Skip Path |
| **Serious learners** | Want the agents AND the badge AND the leaderboard placement | Both (Skip + complete Academy in parallel) |
| **Returning users post-trial** | Have completed some Academy during trial | Hybrid — keep earned agents free, pay for rest |

## The mechanics

### State per user

```python
AgentActivation(
    user_id: uuid,
    agent_id: str,
    activated_at: datetime,
    activation_method: "earn_path" | "skip_path" | "trial" | "founder_grant",
    earn_path_completed_at: datetime | None,  # if Academy module passed
    skip_path_valid_until: datetime | None,    # if from active subscription
    can_use_now: bool,                          # computed property
)
```

**`can_use_now`** is computed each request:
- `True` if `earn_path_completed_at` is not null (permanent)
- `True` if `skip_path_valid_until > now` (subscription active)
- `True` if `activation_method = "trial"` and trial not expired
- `True` if `activation_method = "founder_grant"` (e.g., bug-bounty reward)
- Otherwise `False`

### When a user subscribes

```
SUBSCRIBE
   ↓
For each agent_id:
   if no row for (user_id, agent_id):
      insert new row: activation_method = "skip_path"
   if existing row with earn_path_completed_at NOT NULL:
      keep it (permanent)
   if existing row from trial:
      update to skip_path
```

### When a user cancels / downgrades

```
CANCEL / DOWNGRADE to Floor Pass
   ↓
For each agent_id:
   if earn_path_completed_at NOT NULL:
      can_use_now stays True (earned)
   else:
      can_use_now becomes False (revoked)
```

A user who subscribed for 6 months and never did the Academy will see all 12 agents lock on downgrade. A user who subscribed AND completed Academy modules keeps those modules' agents on Floor Pass.

### When the 7-day trial ends

```
TRIAL EXPIRES (day 8)
   ↓
For each agent_id:
   if earn_path_completed_at NOT NULL:
      stays unlocked (user completed module during trial)
   else if user converts to paid:
      becomes skip_path (active)
   else:
      reverts to locked
```

The user sees a clear summary on day 8:

```
TRIAL ENDED — HERE'S WHERE YOU STAND

Earned during trial (yours to keep, free):
  ⬢ FUNDAMENTALS ANALYST
  ⬢ MARKET ANALYST
  ⬢ BEAR RESEARCHER

Locked (subscribe to keep, or finish Academy to earn free):
  ⬢ NEWS ANALYST
  ⬢ SOCIAL MEDIA ANALYST
  ⬢ BULL RESEARCHER
  ⬢ RESEARCH MANAGER
  ⬢ TRADER
  ⬢ AGGRESSIVE DEBATOR
  ⬢ CONSERVATIVE DEBATOR
  ⬢ NEUTRAL DEBATOR
  ⬢ PORTFOLIO MANAGER

[Continue with Floor Pass (free)]
[Upgrade to Trader ($14.99/mo — keep all 12)]
[See pricing]
```

## Why this design beats alternatives

| Alternative | Why we rejected it |
|---|---|
| **Pay-only access (Finelo-style "pay or you get nothing")** | Misses the value-aligned users who'd pay later if they could try first |
| **Free-only access (give everything away, monetize through ads)** | Doesn't fund LLM costs at scale |
| **Time-locked (can't do Academy faster than 1 module/day)** | Frustrating for fast learners. Solves no real problem. |
| **Pay-to-skip but free path has caps (e.g., 1 module/week)** | Predatory. Users pay to avoid artificial friction. |
| **Earn Path only (no subscription)** | Misses time-poor users entirely. Limits revenue ceiling. |

Our design is **honest**: free users can fully use the product if they're willing to learn. Paying users buy time. The two paths converge on the same product experience.

## Promotion gating model (visual)

The Floor home screen reflects activation state:

```
                ⬢ FUND   ⬢ MKT
                                          ← active agents: solid colors,
              ⬢ NEWS   [⬢]   ⬢ SOC          status dots, pulse on signal
                  ⬢CNC ⬢
              ⬢ BULL   [⬢]   ⬢ BEAR       ← locked agents: dimmed,
                                              lock glyph overlay,
                ⬢ AGG   ⬢ CON                tap → Academy or upgrade
                   ⬢ NEU
              ⬢ RES-M  ⬢ TRADE  ⬢ PM
```

Tapping a locked hex:
- Shows agent role description + "How to unlock"
- Two CTAs: "Start the Academy module" or "Upgrade to skip"

## Bootcamp Graduate Promo (Phase 2)

A future incentive that captures the value of dual-gating:

| Trigger | Reward |
|---|---|
| User completes all 12 Academy modules on Floor Pass | 25% off first year of Trader |

This rewards the dedicated learner cohort and converts them at peak engagement.

## Cross-references

- The Agent Academy itself: [`agent_academy.md`](agent_academy.md)
- The 12 agents: [`docs/initial_specs/02_agents/twelve_agents.md`](../02_agents/twelve_agents.md)
- Trial mechanics: [`docs/initial_specs/03_onboarding/flow.md`](../03_onboarding/flow.md)
- Tiers and pricing: [`docs/initial_specs/06_monetization/tiers_and_pricing.md`](../06_monetization/tiers_and_pricing.md)

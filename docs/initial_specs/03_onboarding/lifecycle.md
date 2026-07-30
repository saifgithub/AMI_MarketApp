# Mandate Lifecycle

How the mandate evolves: edits, versioning, audits, drift.

## Phases

```
   CREATE (onboarding) ──► version 1
        ↓
   EDIT (any time)     ──► version 2, 3, ...
        ↓
   AUDIT (on hard edits) ──► resolve violations
        ↓
   DRIFT CHECK (daily background) ──► alert if drift
        ↓
   REFINE (Phase 2 multi-mandate) ──► add secondary mandate
```

## Editing the mandate

Entry: **Settings → My Mandate**

UI: a hex-clipped "ID card" showing the current state at a glance. Tap any field to edit.

Editable fields:

| Field | Edit type | Effect on save |
|---|---|---|
| `display_name`, `locale`, `timezone` | Soft | Immediate, no audit |
| `primary_goal`, `horizon`, `target_outcome`, `path` | Soft | Immediate, agents re-overlay on next call |
| `risk_score`, `risk_components`, `max_drawdown_pct` | **Hard** (could affect open positions) | Audit triggered |
| `compliance.*` flags | **Hard** | Audit triggered |
| `ticker_blocklist`, `ticker_allowlist` | **Hard** | Audit triggered |
| `learning_style` | Soft | Immediate (tutor adapts) |

Every edit increments `mandate.version` and creates a new row.

## Mandate Audit — Not yet delivered

The intended behaviour: when a user makes a **hard** edit, the system runs an audit on existing sim holdings + pending trades against the new mandate, then offers a resolve flow (Liquidate / Postpone / Override).

**Today (Alpha):** `PATCH /v1/mandate/{user_id}` simply increments `mandate.version`, writes a new row with the JSONB snapshot, and emits a `mandate_edit` journal entry. There is no audit pass, no holdings scan, no resolve modal. The mandate-violation warning users may see is the **trade-time** check (`safety_floor.check_mandate_compliance()` invoked from `sim_engine.execute_trade()`), not a hard-edit retroactive sweep. See BL6 (resolve flow) + BL12 (audit on edit).

For reference, the intended audit shape:

```python
def run_audit(user_id, new_mandate, old_mandate) -> AuditResult:
    """Find every current sim holding or pending trade that violates new mandate."""
    violations = []
    for holding in portfolio.holdings(user_id):
        if violates(holding, new_mandate):
            violations.append(Violation(
                holding=holding,
                rule=which_rule(holding, new_mandate),
                suggested_action=resolve_action(holding, new_mandate)
            ))
    return AuditResult(violations)
```

**User flow:**

```
USER edits halal flag to TRUE
   ↓
Audit runs
   ↓
Modal:
   "You just turned on halal-only. Your sim holds 3 positions 
    that no longer comply:
    
    • PYPL — interest-based payment processing
    • BAC — conventional banking  
    • LMT — weapons / defence
    
    What would you like to do?"
   
   [Liquidate all]  [Liquidate individually]  [Override mandate flag]
   [Postpone — let me think]
```

If user picks **Liquidate all**: sim trades execute at current 15-min-delayed prices, P&L recorded in journal, mandate version increments.

If user picks **Liquidate individually**: per-holding decision.

If user picks **Override mandate flag**: the mandate edit is *reverted* (kept as halal=false). User can re-attempt later.

If user picks **Postpone**: the mandate edit saves, but Mandate Drift Alerts immediately fire on those holdings. User has 30 days to act before any new agent analyses also flag them.

## Version history

Every mandate has a full version history. Users can:
- View any historical version (read-only) — useful for "what was I thinking back then?"
- See the diff between any two versions
- Rollback to an old version (creates a new version that mirrors the old one — preserves history)

| Tier | Version history retained |
|---|---|
| Floor Pass | Last 5 versions |
| Trader | Last 20 versions |
| Floor Manager | Unlimited |

**Traceability:** Every Decision Journal entry (Room, 1-on-1, trade) is tagged with `mandate_version` so the user can always see *which* mandate was in effect when that entry was generated.

## Mandate Drift Detection

A background job runs daily for every active user. It checks whether the current sim portfolio still matches the current mandate's intent.

### What "drift" means

Drift is not the same as violation:
- **Violation** = a position breaks a compliance rule (caught immediately by PM compliance check)
- **Drift** = the portfolio's *aggregate profile* has gradually moved away from the mandate's intent

### Drift signals

| Signal | Threshold |
|---|---|
| Beta drift | Portfolio beta deviates from horizon-implied range by >0.3 |
| Sector concentration | Any sector > 40% (default) or user-specified cap |
| Risk-score mismatch | Realised volatility implies risk_score ≠ stated risk_score by ≥2 |
| Drawdown approaching cap | Current drawdown within 20% of `max_drawdown_pct` |
| Compliance erosion | A holding's underlying business changes (rare — e.g., a halal company acquires a non-halal subsidiary) |
| Cash drag | Cash > 30% for 60+ days without rebalancing action |

### Alert delivery

| Tier | Alert cadence | Channels |
|---|---|---|
| Floor Pass | Weekly digest | Email |
| Trader | Daily | Email + push |
| Floor Manager | Real-time + tunable thresholds | Email + push + in-app |

Alerts are framed conversationally by Concierge in the morning briefing:

> *"Heads up: your portfolio drifted toward higher beta this week — sitting at 1.4 vs your moderate-risk target around 1.0. Your Conservative Debator wants to talk."*

Tap → opens 1-on-1 with Conservative.

### Suppression

User can mute drift alerts for a holding ("I know — I'm deliberately overweight"), an entire signal (e.g. "stop alerting me on cash drag"), or globally for a period.

## Multi-mandate (Phase 2)

The schema already supports it via `user.mandates[]`. At MVP / v1.0, users have exactly one mandate. Phase 2 adds:

- Multiple mandates (e.g., "Retirement" + "Speculative bucket")
- Per-mandate portfolios
- Mandate switching per session ("run this Room under my speculative mandate")
- Cross-mandate reporting

**Why deferred:** complexity in UX (which mandate is active for *this* trade?), schema migration is trivial, but the user-facing flows need careful design and aren't critical at MVP.

## Cross-references

- The mandate schema: [`mandate_schema.md`](mandate_schema.md)
- How agents use it: [`docs/initial_specs/02_agents/mandate_overlays.md`](../02_agents/mandate_overlays.md)
- Safety floor: [`docs/initial_specs/02_agents/safety_floor.md`](../02_agents/safety_floor.md)
- Background workers: [`docs/initial_specs/08_tech/architecture.md#background-jobs`](../08_tech/architecture.md)

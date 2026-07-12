# 16 — Multiple Sim Portfolios (Tier 3 — Deferred)

**Folder:** `16_multi_sim_portfolio/`  
**Purpose:** Document the deferral of multi-portfolio support and pre-conditions for re-opening.  
**Status:** Explicitly deferred per locked decision.

---

## Why deferred

The CEO mental model is **one mandate, one chair, one portfolio**. Multi-portfolio without multi-mandate produces orphaned portfolios without clear decision authority.

Per `core_loop_and_features.md:119`:

> 1 portfolio at alpha; multi-portfolio v1.0 paid.

---

## Use case (rejected at Tier 1, possible at v1.0)

"Create an aggressive portfolio and a conservative portfolio to compare strategies."

**Problem:** which mandate rules apply? Which agent feedback does the user trust? The single-chair UX breaks.

---

## Pre-conditions for re-opening

1. **Multi-mandate ships** (Phase 2 per project_plan.md)
2. **Concierge can route between mandates** — "switch to my aggressive portfolio"
3. **Safety floor can adjudicate across portfolios** — mandate compliance is per-portfolio

---

## What would ship with it

- `users.current_portfolio_id` to track active portfolio
- Portfolio list on Home screen (switch via selector)
- Per-portfolio mandates (one mandate per portfolio)
- Per-portfolio agent chat contexts

---

## Not doing at Tier 1 / Alpha

This is a major UX and data model change. Defer until the foundational multi-mandate work is complete.

---

## See also

- [project_plan.md](../../docs/10_delivery/project_plan.md) — Phase 2 multi-mandate roadmap
- [core_loop_and_features.md:119](../../docs/01_product/core_loop_and_features.md) — product decision

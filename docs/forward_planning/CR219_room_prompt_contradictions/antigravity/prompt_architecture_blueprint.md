# AMI Room Prompt Architecture Blueprint

**Location:** `docs/forward_planning/CR219_room_prompt_contradictions/antigravity/prompt_architecture_blueprint.md`  
**Purpose:** Detailed before/after prompt specifications, persona contract standards, and fact sheet data schemas for CR219.

---

## 1. Dynamic Data Contract Standard for Persona Files (`content/agents/*.md`)

All 13 persona files will adopt the standardized **Dynamic Data Contract** block. Static availability lists that rotted over time will be replaced with field-state aware specifications.

### Standardized Persona Section: `## Inputs & Data Contract`

```markdown
## Inputs & Data Contract

You receive a dynamic Fact Sheet generated specifically for this ticker run. 

1. **LIVE Data Integrity:** Any metric labelled `(LIVE)` or presented with numerical values on your Fact Sheet is real data provided for this run. You must analyze and reference these numbers freely in your evaluation.
2. **Dynamic Availability:** The Fact Sheet states what data arrived for this ticker. Where a field is explicitly marked unavailable or absent, do not fabricate a value.
3. **Domain Focus:** Analyze data strictly within your specialist domain. Do not make statements or predictions outside your role boundaries (e.g. Fundamentals Analyst does not evaluate price charts; Technical Strategist does not compute valuation multiples).
```

---

## 2. Before / After Persona Refactoring Specs

### 2.1 Fundamentals Analyst (`content/agents/fundamentals_analyst.md`)

| Section | Current Contradictory Text | Enhanced Refactored Standard |
|:---|:---|:---|
| `## Inputs` L29-31 | *"What you do **not** have is a margin trend — every figure is a point-in-time reading, so never describe a margin as rising, falling, expanding or compressing"* | *"Analyze margin structure (gross, operating, net) and YoY margin trend when present on your sheet."* |
| `## Inputs` L48-49 | *"Buybacks and M&A history are **not available** — never claim a number for either"* | *"Analyze buybacks and capital return metrics when present on your Fact Sheet."* |
| `## Inputs` L59-60 | *"no history for any of them: every figure is a single point in time."* | *"Multi-period window trends and TTM series are provided on the sheet where available."* |
| `## Output style` L66 | *"There is still no margin trend on the sheet — quote the levels, never a direction"* | *"Cite exact numbers and YoY trend bps provided on your sheet to support your thesis."* |

---

### 2.2 Market / Technical Analyst (`content/agents/market_analyst.md`)

| Section | Current Contradictory Text | Enhanced Refactored Standard |
|:---|:---|:---|
| `## Inputs` L19-22 | *"any claim that needs a series … is not one this data can support"* | *"Evaluate the price series, window trend, primary trend, 52-week range, and ATR volatility metric provided on your sheet."* |
| `## Inputs` L54 | *"you do not have a series, so you cannot say an indicator is clearing, rolling over"* | *"Use the provided window trend, moving average relations, and ATR range to describe price momentum and technical structure."* |

---

### 2.3 News Analyst (`content/agents/news_analyst.md`)

| Section | Current Contradictory Text | Enhanced Refactored Standard |
|:---|:---|:---|
| `## Inputs` L25 | *"You are **not supplied consensus estimates**"* | *"Reference consensus EPS estimates and earnings dates provided on your Fact Sheet alongside news headlines."* |

---

### 2.4 Social Media Analyst (`content/agents/social_media_analyst.md`)

| Section | Current Contradictory Text | Enhanced Refactored Standard |
|:---|:---|:---|
| `## Inputs` L28 | *"You have no historical baseline for this ticker"* | *"Evaluate the mention count, sentiment score, and mention trend over the available baseline window on your sheet."* |

---

### 2.5 Execution Desk / Trader (`content/agents/trader.md`)

| Section | Current Contradictory Text | Enhanced Refactored Standard |
|:---|:---|:---|
| `## You DO NOT` L45 | *"Skip the stop-loss"* (Fails on `Side: WAIT` / `HOLD`) | *"Skip the stop-loss on BUY orders. When Side is WAIT or HOLD, output Entry: N/A, Target: N/A, Stop: N/A."* |

---

## 3. Fact Sheet Data Schema Extensions (Zero-Cost Data Enrichment)

### 3.1 New Calculations in `backend/app/services/fundamentals.py`

```python
def interest_coverage_line(profile: dict[str, Any]) -> str | None:
    """Compute Interest Coverage Ratio from operating income and interest expense.
    Both figures exist in quarterly_income_stmt already fetched by yfinance."""
    op_inc = profile.get("operating_income_ttm")
    int_exp = profile.get("interest_expense_ttm")
    if op_inc is None or int_exp is None or int_exp == 0:
        return None
    ratio = op_inc / int_exp
    return f"Interest coverage (LIVE): {ratio:.1f}x (Operating income ${_fmt_usd(op_inc)} / Interest expense ${_fmt_usd(int_exp)})"

def atr_volatility_line(profile: dict[str, Any]) -> str | None:
    """Compute 14-day Average True Range (ATR) from daily bars in memory."""
    atr_val = profile.get("atr_14d")
    spot = profile.get("price")
    if atr_val is None or spot is None or spot == 0:
        return None
    pct = (atr_val / spot) * 100
    return f"Volatility / 14d ATR (LIVE): ${atr_val:.2f} ({pct:.1f}% of spot ${spot:.2f})"
```

---

## 4. Overlay Generator Wiring for `mandate.primary_goal`

In `backend/app/agents/overlay_generator.py`:

```python
def _role_specific_block(agent_id: AgentId, mandate: Mandate) -> str:
    base_block = _ROLE_BUILDERS[agent_id](mandate)
    goal_block = _primary_goal_guidance(agent_id, mandate.primary_goal)
    return base_block + "\n\n" + goal_block if goal_block else base_block
```

---

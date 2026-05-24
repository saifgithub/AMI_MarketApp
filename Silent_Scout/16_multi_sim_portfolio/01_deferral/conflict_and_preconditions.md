# Multi-portfolio conflict and pre-conditions

## The conflict

**Current design:** 1 user → 1 mandate → 1 portfolio → 12 agents

**User request:** create 2 portfolios to test "aggressive vs conservative" strategies

**Problem:** which mandate rules apply to each portfolio?

```
User has:
  Mandate A: no shorting, halal-compliant
  Mandate B: aggressive, allows shorting

Which mandate rules the aggressive portfolio?
Answer: Mandate B.

But the current system assumes 1 user → 1 mandate.
Flipping the mandate at runtime is confusing; the user loses context.
```

---

## Solution: multi-mandate (Phase 2)

```
1 user → N mandates → N portfolios → 12 agents (per mandate)

User can switch mandates to switch portfolios.
Each mandate has its own agent team, its own rules, its own audit trail.
```

---

## Pre-conditions to re-open multi-portfolio

### 1. Multi-mandate architecture ships (Phase 2)

Modify `users` table:
```python
users
  ├── id
  ├── email
  ├── current_mandate_id  # NEW
  └── mandates []  # NEW; 1-to-many
```

Modify `mandates` table:
```python
mandates
  ├── id
  ├── user_id
  ├── portfolio_id  # FK to sim_portfolios
  └── ... compliance rules ...
```

### 2. Concierge can route between mandates

Add a system command:
```
User: "Switch to my aggressive portfolio"
Concierge: loads mandate B, refreshes agent context, updates the UI
```

### 3. Safety floor can adjudicate across portfolios

The compliance checker needs to know:
```python
def check_compliance(trade: SimTrade, mandate: Mandate) -> bool:
    # Use mandate B's rules (no shorting flag, halal list, etc.)
    # NOT the user's default mandate
```

---

## Schema delta (when re-opening)

**New table: `user_mandates`**
```python
class UserMandate(Base):
    __tablename__ = "user_mandates"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String)  # "Aggressive", "Conservative"
    
    # Existing mandate fields (concentration_tolerance, etc.)
    # ... all mandate columns ...
    
    created_at = Column(DateTime)
```

**Update `users` table:**
```python
class User(Base):
    # ... existing fields ...
    current_mandate_id = Column(Integer, ForeignKey("user_mandates.id"), nullable=True)
```

**Update `sim_trades` table:**
```python
class SimTrade(Base):
    # ... existing fields ...
    mandate_id = Column(Integer, ForeignKey("user_mandates.id"))  # NEW
    # (audit which mandate governed this trade)
```

---

## Timeline

- **Alpha (now):** 1 mandate, 1 portfolio, 1 agent team
- **Beta (Phase 2):** multi-mandate, multi-portfolio, mandate switching
- **v1.0:** full customization per mandate (agent weights, tone, etc.)

---

## Not doing at Alpha

This is intentional deferral, not a limitation. The product is designed for single-mandate focus at Alpha. Multi-mandate opens up comparison/experimentation at Beta.

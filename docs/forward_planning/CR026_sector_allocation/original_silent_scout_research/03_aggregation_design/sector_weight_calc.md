# Aggregation design: sector weight calculation

## Algorithm

```python
def allocate_by_sector(holdings: List[SimHolding], quotes: Dict[str, Quote]) -> Dict[str, float]:
    """
    Compute portfolio allocation by sector.
    
    Args:
        holdings: list of SimHolding objects (ticker, quantity, avg_cost, etc.)
        quotes: dict of ticker → current Quote (price, etc.)
    
    Returns:
        dict of sector → weight (0.0–1.0)
    """
    sector_values = defaultdict(float)
    total_value = 0.0
    
    for holding in holdings:
        # Skip if no price available
        if holding.ticker not in quotes:
            continue
        
        current_price = quotes[holding.ticker].price
        position_value = holding.quantity * current_price
        total_value += position_value
        
        # Get sector from yfinance (cached)
        sector = get_sector(holding.ticker)  # returns "Technology", "Unknown", etc.
        if not sector:
            sector = "Other"
        
        sector_values[sector] += position_value
    
    # Normalize to weights
    if total_value == 0:
        return {}  # Empty portfolio
    
    allocation = {
        sector: value / total_value
        for sector, value in sector_values.items()
    }
    
    return allocation
```

---

## Edge cases

1. **Empty portfolio:** return `{}` (no sectors to display)
2. **Single holding:** return `{sector: 1.0}` (100% in that sector)
3. **No prices available:** skip that holding (missing quote)
4. **Sector unknown:** bucket as "Other"
5. **Negative cash position (margin):** don't weight; audit separately

---

## Caching sector data

```python
@cache.cached(timeout=None)  # Cache forever; sectors rarely change
def get_sector(ticker: str) -> str | None:
    """Get sector for a ticker from yfinance; cache locally."""
    try:
        sector = yf.Ticker(ticker).info.get('sector')
        return sector or "Other"
    except Exception as e:
        logger.warning(f"Sector lookup failed for {ticker}: {e}")
        return "Other"
```

---

## Backend endpoint

```python
@router.get("/v1/portfolio/sector-allocation")
async def get_sector_allocation() -> SectorAllocationResponse:
    """
    Return current portfolio allocation by sector.
    
    Returns:
        {
            "allocation": {
                "Technology": 0.35,
                "Healthcare": 0.20,
                "Financials": 0.15,
                "Other": 0.30,
            },
            "total_value": 50000.0,
            "compliance": {
                "max_sector": 0.35,
                "max_allowed": 0.40,
                "compliant": true
            }
        }
    """
    # Fetch holdings + quotes
    holdings = get_user_holdings(user_id)
    quotes = fetch_all_quotes([h.ticker for h in holdings])
    
    # Compute allocation
    allocation = allocate_by_sector(holdings, quotes)
    
    # Compute total portfolio value
    total_value = sum(h.quantity * quotes[h.ticker].price for h in holdings)
    
    # Check mandate compliance
    max_sector = max(allocation.values()) if allocation else 0.0
    mandate = get_user_mandate(user_id)
    compliance = {
        "max_sector": max_sector,
        "max_allowed": mandate.concentration_tolerance,
        "compliant": max_sector <= mandate.concentration_tolerance,
    }
    
    return SectorAllocationResponse(
        allocation=allocation,
        total_value=total_value,
        compliance=compliance,
    )
```

**Schema:**

```python
class SectorAllocationResponse(BaseModel):
    allocation: Dict[str, float]  # sector → weight
    total_value: float
    compliance: Dict[str, Any]  # {max_sector, max_allowed, compliant}
```

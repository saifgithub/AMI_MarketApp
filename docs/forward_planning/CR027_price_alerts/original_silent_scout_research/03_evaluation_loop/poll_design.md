# Evaluation loop: polling and state transitions

## Polling cadence

**Frequency:** Every 5 minutes (300 seconds)

**Trigger:** APScheduler job (already in `backend/app/scheduler.py`). Add a new job:

```python
scheduler.add_job(
    evaluate_price_alerts,
    'interval',
    seconds=300,
    id='evaluate_price_alerts',
    name='Evaluate price alerts',
    replace_existing=True,
)
```

**Rationale:**
- 5 min matches the yfinance quote cache TTL (section 12, watchlist badge)
- Fast enough for interactive feeling ("check my stop every 5 min")
- Slow enough to avoid rate-limiting Yahoo (yfinance ~2000 calls/hour free tier limit)

---

## Evaluation function signature

```python
async def evaluate_price_alerts() -> dict:
    """
    Poll all active price alerts against current market prices.
    Fire alerts when thresholds are crossed; update state to FIRED.
    """
    try:
        # 1. Fetch all active alerts
        # 2. For each ticker, fetch current price
        # 3. For each alert, check threshold
        # 4. If crossed, fire push notification + update status
        # 5. Return stats: {evaluated: N, fired: M, errors: P}
    except Exception as e:
        logger.error(f"Price alert evaluation failed: {e}")
        return {"error": str(e)}
```

---

## Threshold evaluation logic

```python
def check_threshold(alert: PriceAlert, current_price: float) -> bool:
    """Returns True if threshold is breached."""
    if alert.threshold_type == "stop":
        # Alert fires when price FALLS BELOW stop
        return current_price < alert.threshold_price
    
    elif alert.threshold_type == "target":
        # Alert fires when price RISES ABOVE target
        return current_price > alert.threshold_price
    
    elif alert.threshold_type == "manual_above":
        return current_price > alert.threshold_price
    
    elif alert.threshold_type == "manual_below":
        return current_price < alert.threshold_price
    
    return False
```

---

## State transition: ACTIVE → FIRED

When `check_threshold()` returns True:

```python
def fire_alert(alert: PriceAlert, current_price: float):
    """Fire an alert and update its state."""
    
    # 1. Update alert status
    alert.status = "fired"
    alert.fired_at = datetime.utcnow()
    db.session.commit()
    
    # 2. Build push payload (see section 10/04_push_payload/)
    payload = build_push_payload(alert, current_price)
    
    # 3. Fire push (OneSignal)
    try:
        onesignal_client.send_notification(
            include_external_user_ids=[alert.user_id],
            contents=payload,
        )
    except Exception as e:
        logger.error(f"Failed to push alert {alert.id}: {e}")
        # Continue — alert is still marked FIRED even if push failed
    
    # 4. Log the event
    logger.info(f"Alert {alert.id} fired: {alert.ticker} @ {current_price}")
```

---

## Backoff on yfinance error

If a quote fetch fails (timeout, rate limit, API error):

```python
def fetch_with_backoff(ticker: str, max_retries: int = 2) -> float | None:
    """Fetch price with exponential backoff."""
    for attempt in range(max_retries):
        try:
            quote = fetch_live_quote(ticker)  # yfinance call
            return quote.price
        except Exception as e:
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(f"Quote fetch failed ({ticker}, attempt {attempt}): {e}")
            if attempt < max_retries - 1:
                time.sleep(wait_time)
    
    logger.error(f"Quote fetch exhausted for {ticker}")
    return None  # Return None, skip this ticker for this cycle
```

When `fetch_with_backoff()` returns None, skip that ticker — don't fire false alerts.

---

## Polling loop pseudocode

```python
async def evaluate_price_alerts():
    stats = {"evaluated": 0, "fired": 0, "errors": 0}
    
    # Fetch all active alerts, grouped by ticker for efficiency
    alerts_by_ticker = defaultdict(list)
    active_alerts = db.session.query(PriceAlert).filter_by(status="active").all()
    
    for alert in active_alerts:
        alerts_by_ticker[alert.ticker].append(alert)
    
    # Fetch prices once per ticker
    for ticker, ticker_alerts in alerts_by_ticker.items():
        current_price = fetch_with_backoff(ticker)
        if current_price is None:
            stats["errors"] += 1
            continue
        
        # Evaluate all alerts for this ticker
        for alert in ticker_alerts:
            stats["evaluated"] += 1
            
            if check_threshold(alert, current_price):
                fire_alert(alert, current_price)
                stats["fired"] += 1
    
    logger.info(f"Price alert evaluation complete: {stats}")
    return stats
```

---

## No simultaneous duplicate fires

Once an alert is FIRED, subsequent cycles see `status="fired"` and skip it. No duplicate push notifications.

---

## Mandate compliance check

Before firing an alert, verify it doesn't violate the user's mandate:

```python
def is_alert_compliant(user_id: str, alert: PriceAlert, current_price: float) -> bool:
    """Check if firing this alert respects the user's mandate."""
    mandate = db.session.query(Mandate).filter_by(user_id=user_id).first()
    
    # If mandate forbids short selling and alert would imply short, reject
    if not mandate.allow_short and alert.threshold_type == "target":
        # Target alerts on short positions are not allowed
        return False
    
    # Add more mandate-specific checks as needed
    return True
```

If not compliant, log a warning and DON'T fire (keep alert as ACTIVE).

---

## Monitoring / alerts on the alert system

Log every fired alert to a metrics system (e.g., Datadog, Grafana):

```python
emit_metric("price_alert_fired", tags={
    "ticker": alert.ticker,
    "type": alert.threshold_type,
    "user_id": alert.user_id,
})
```

This gives Saiful visibility into usage patterns and system health.

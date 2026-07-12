# Push payload specification

## OneSignal JSON payload

```json
{
  "include_external_user_ids": ["user_123"],
  "headings": {
    "en": "Price Alert: AAPL"
  },
  "contents": {
    "en": "AAPL crossed your stop at $150. Risk Agent: Position size ($5K) is within mandate limits. Consider averaging down on further weakness."
  },
  "data": {
    "alert_id": "12345",
    "ticker": "AAPL",
    "threshold_type": "stop",
    "current_price": "150.25",
    "threshold_price": "150.00",
    "action": "open_holding_detail"
  },
  "ios_badgeType": "Increase",
  "ios_badgeCount": 1,
  "big_picture": null,
  "chrome_web_icon": null
}
```

---

## Field breakdown

### User targeting
- `include_external_user_ids`: array of user IDs to send to (in this case, just the alert owner)

### Content (localized)
- `headings.en`: "Price Alert: {TICKER}"
- `contents.en`: "[Risk Agent commentary — 280 chars max]"

The content is the most important part — it provides context. A bare "AAPL crossed $150" is useless without explanation.

### Deep linking
- `data.action`: "open_holding_detail"
- `data.ticker`: "AAPL"

When the user taps the notification, the app should:
1. Route to `/sim/AAPL` (holding detail screen)
2. Highlight the alert (if a visual indicator is added later)

### Badge
- `ios_badgeCount`: 1 per notification (system auto-increments)

---

## Agent commentary format

The Risk Agent (or Concierge) injects 280-char commentary into the push content:

```python
def generate_alert_commentary(alert: PriceAlert, current_price: float, trade: SimTrade | None) -> str:
    """Generate Risk Agent commentary for the alert."""
    
    if alert.threshold_type == "stop":
        # Stop fired — explain the risk implication
        if trade:
            position_size = trade.quantity * current_price
            commentary = (
                f"Stop triggered. Position ${position_size:,.0f} "
                f"is below your {trade.stop_pct}% risk tolerance. "
                f"Review mandate compliance."
            )
        else:
            commentary = f"Price breached your stop threshold. Review your position."
    
    elif alert.threshold_type == "target":
        # Target hit — suggest profit-taking
        commentary = (
            f"Target hit! Consider taking profit or moving your stop higher. "
            f"Check the News for context."
        )
    
    elif alert.threshold_type in ("manual_above", "manual_below"):
        # Generic watchlist alert
        commentary = f"Price alert triggered. Tap to view the holding."
    
    else:
        commentary = "Price alert triggered."
    
    # Truncate to 280 chars if needed
    return commentary[:280]
```

---

## Example notifications

### Example 1: Stop fired

```
Heading: "Price Alert: AAPL"
Body: "Stop triggered at $150. Position size ($4.2K) exceeds 5% drawdown tolerance. 
       Risk Agent suggests reviewing your mandate or closing 50% of the position."
Data: {"ticker": "AAPL", "threshold_type": "stop", "current_price": "149.95", ...}
```

### Example 2: Target hit

```
Heading: "Price Alert: TSLA"
Body: "Target hit! TSLA crossed $250. News Analyst flagged 3 positive headlines today. 
       Consider locking in gains or moving your stop higher."
Data: {"ticker": "TSLA", "threshold_type": "target", "current_price": "250.15", ...}
```

### Example 3: Manual watchlist alert

```
Heading: "Price Alert: GOOGL"
Body: "GOOGL dropped below $100 as you requested. Tap to view the holding and consider an entry."
Data: {"ticker": "GOOGL", "threshold_type": "manual_below", "current_price": "99.85", ...}
```

---

## Payload construction in code

```python
def build_push_payload(alert: PriceAlert, current_price: float) -> dict:
    """Build OneSignal payload for a fired alert."""
    
    # Fetch trade if it exists (for context)
    trade = alert.trade if alert.trade_ref else None
    
    # Generate commentary
    commentary = generate_alert_commentary(alert, current_price, trade)
    
    # Build notification content
    payload = {
        "include_external_user_ids": [alert.user_id],
        "headings": {"en": f"Price Alert: {alert.ticker}"},
        "contents": {"en": commentary},
        "data": {
            "alert_id": str(alert.id),
            "ticker": alert.ticker,
            "threshold_type": alert.threshold_type,
            "current_price": str(round(current_price, 2)),
            "threshold_price": str(round(alert.threshold_price, 2)),
            "action": "open_holding_detail",
        },
        "ios_badgeType": "Increase",
        "ios_badgeCount": 1,
    }
    
    return payload
```

---

## Testing payload

Before shipping, test with a sandbox alert:

```python
# In a test or admin endpoint:
test_alert = PriceAlert(
    user_id="test_user",
    ticker="AAPL",
    threshold_type="stop",
    threshold_price=150.0,
)
payload = build_push_payload(test_alert, 149.95)
print(json.dumps(payload, indent=2))
# Verify: heading, content, and data all present and valid
```

---

## Fallback when push is unavailable

If OneSignal is unreachable (A15 not provisioned yet):

```python
def fire_alert(alert: PriceAlert, current_price: float):
    # ... state transition to FIRED ...
    
    payload = build_push_payload(alert, current_price)
    
    try:
        onesignal_client.send_notification(**payload)
    except Exception as e:
        logger.warning(f"OneSignal unreachable; alert {alert.id} marked FIRED but not pushed: {e}")
        # Alert is still FIRED (user will see it in the app next time they open)
        # The notification would have fired, but silent failure is acceptable at Alpha
```

---

## Rate limiting OneSignal

To avoid spamming OneSignal:
- Max 1 alert notification per user per minute (if 2 alerts fire simultaneously, queue the second)
- Max 3 alert notifications per user per hour
- No more than 10 distinct alerts for a user at once (older ones auto-close)

Implement via a `fired_alerts_recent` cache (Redis):

```python
cache_key = f"fired_alerts:{alert.user_id}:last_minute"
if cache.get(cache_key):
    logger.info(f"Rate limit: skipping push for {alert.id} (already sent one in last min)")
    return
cache.set(cache_key, True, ttl=60)
# Safe to send
onesignal_client.send_notification(**payload)
```

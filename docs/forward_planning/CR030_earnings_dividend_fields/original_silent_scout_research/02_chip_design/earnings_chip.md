# Chip design — earnings and dividend

## Widget specification

**Widget class name:** `EarningsChip`

**Location:** `mobile/lib/widgets/sim/earnings_chip.dart` (new file)

**Props:**

```dart
class EarningsChip extends StatelessWidget {
  final String ticker;
  final DateTime? earningsDate;
  final DateTime? exDividendDate;
  final double dividendRate;  // e.g., 0.96
  
  const EarningsChip({
    required this.ticker,
    this.earningsDate,
    this.exDividendDate,
    this.dividendRate = 0.0,
  });
  
  @override
  Widget build(BuildContext context) { ... }
}
```

---

## Visibility logic

The chip is **entirely hidden** if both dates are None:

```dart
if (earningsDate == null && exDividendDate == null) {
  return SizedBox.shrink();  // Render nothing
}
```

---

## Visual design

### Case 1: Both dates present

```
┌────────────────────────────────────┐
│ Earnings: Jun 12  │  Ex-div: Sep 19 │
└────────────────────────────────────┘
```

**Height:** ~32 px  
**Layout:** horizontal row, two items separated by pipe (|)  
**Font:** `AmiTypography.bodySmall` (12 px)  
**Color:** `AmiColors.hexBlue` (accent, earnings-specific context)

### Case 2: Only earnings date

```
┌──────────────────┐
│ Earnings: Jun 12 │
└──────────────────┘
```

### Case 3: Only ex-dividend date

```
┌────────────────────┐
│ Ex-div: Sep 19     │
│ (Dividend: $0.96)  │
└────────────────────┘
```

Add a second line if dividend rate is non-zero:  
**Format:** `Dividend: $0.96` (annual per share)

### Case 4: Earnings date in the past

Do not render. Check client-side: `if (earningsDate.isBefore(DateTime.now())) return SizedBox.shrink();`

---

## Interaction

**Tap action (future enhancement):**
- When the user taps the chip, open the Decision Journal filtered to the earnings date ("Show me all trades I made on Jun 12, when earnings were released")
- At Tier 2, tap does nothing (informational only)

**No styling change on tap** (informational, read-only).

---

## Integration into holding_detail_screen.dart

Add `EarningsChip` to the holding detail `ListView`:

```dart
import 'package:sim_app/widgets/sim/earnings_chip.dart';

// In the ListView.builder():
if (earningsDateDate != null || exDividendDate != null)
  EarningsChip(
    ticker: widget.ticker,
    earningsDate: earningsDate,
    exDividendDate: exDividendDate,
    dividendRate: dividendRate,
  ),
```

Position: after the news strip (zone 4), before the stop/target chip (zone 6).

---

## Data flow

```
API: GET /v1/ticker/{ticker}/earnings
  ↓
Response: { earningsDate: ISO 8601, exDividendDate: ISO 8601, dividendRate: 0.96 }
  ↓
Parse to DateTime in Flutter
  ↓
Render EarningsChip
```

---

## Accessibility

- Earnings date is announced as "Earnings on June 12"
- Ex-dividend date is announced as "Ex-dividend date September 19"
- Dividend rate is announced if present: "Annual dividend $0.96 per share"

---

## Responsive behavior

No responsive changes — chip stays single-line on all screen widths (14-char max per item, e.g., "Earnings: Jun 12" is 14 chars). If needed to fit, abbreviate to "E: Jun 12  D: Sep 19".

---

## Empty state

No empty state. If no dates, chip is not rendered at all.

---

## Dark mode

All colors use `AmiColors.*` tokens, which are theme-aware. No hardcoded colors.

---

## Animation / transitions

None. Chip appears/disappears based on data availability (no fade-in).

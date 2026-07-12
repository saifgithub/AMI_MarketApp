# Chart design: sector allocation visualization

## Two options for Portfolio screen

### Option A: Pie chart

```
        Tech (35%)
          /     \
        /         \
      Health  Finance
      (20%)    (15%)
        \         /
          \     /
         Other
         (30%)
```

**Pros:**
- Iconic, familiar to users (every finance app uses pie)
- Easy to compare slices at a glance

**Cons:**
- Hard to label sectors (overlapping text on small screens)
- Difficult to read values > 6 sectors

### Option B: Horizontal stacked bar

```
├─ Tech (35%)    ─┤
├─ Health (20%)  ─┤
├─ Finance (15%) ─┤
├─ Other (30%)   ─┤
```

**Pros:**
- All labels visible without overlap
- Scalable to many sectors
- Supports Tier 2 enhancement: click a sector to see holdings

**Cons:**
- Less iconic / familiar
- Harder to eyeball total at a glance

---

## Recommendation

**Use pie chart at Tier 2** (simpler, more familiar). If users request filtering or detailed sector views, upgrade to horizontal bar at Tier 3.

---

## Pie chart spec (fl_chart)

```dart
import 'package:fl_chart/fl_chart.dart';

class SectorPieChart extends StatelessWidget {
  final Map<String, double> allocation;  // {"Technology": 0.35, ...}
  
  @override
  Widget build(BuildContext context) {
    final sections = allocation.entries
        .map((entry) => PieChartSectionData(
          value: entry.value * 100,  // convert to %
          title: '${(entry.value * 100).toStringAsFixed(0)}%',
          color: getColorForSector(entry.key),
          radius: 60,
          titleStyle: AmiTypography.bodySmall.copyWith(
            color: AmiColors.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ))
        .toList();
    
    return PieChart(
      PieChartData(
        sections: sections,
        centerSpaceRadius: 40,  // donut style
        sectionsSpace: 2,
      ),
    );
  }
  
  Color getColorForSector(String sector) {
    // Assign distinct colors per sector
    return switch(sector) {
      "Technology" => AmiColors.hexBlue,
      "Healthcare" => AmiColors.hexGreen,
      "Financials" => AmiColors.hexOrange,
      "Industrials" => AmiColors.hexPurple,
      "Consumer Discretionary" => AmiColors.hexPink,
      "Consumer Staples" => AmiColors.hexTeal,
      "Energy" => AmiColors.hexRed,
      "Utilities" => AmiColors.hexYellow,
      "Real Estate" => AmiColors.hexBrown,
      "Materials" => AmiColors.hexGray,
      "Communication Services" => AmiColors.hexCyan,
      _ => AmiColors.textSubtle,  // "Other"
    };
  }
}
```

**Height:** 280 px  
**Width:** Full screen width, minus padding (48 px safe margin)  
**Position on Portfolio screen:** below the summary card (value, P&L, drawdown %), above the holdings list

---

## Legend

Add a legend below the pie chart:

```
Technology    35%
Healthcare    20%
Financials    15%
Other         30%
```

**Each row:**
- Color swatch (10×10 px square)
- Sector name
- Weight %

**Height:** 20 px × N sectors (~100 px total for 5 sectors)

---

## Mandate compliance overlay (future)

If a sector exceeds mandate max (e.g., 40%), overlay a warning:

```
⚠️ Technology (35%) exceeds your 25% mandate limit
```

At Tier 2, show the chart cleanly. At Tier 3, add the warning.

---

## Empty state

If portfolio is empty (no holdings):

```
No portfolio yet
Add a trade to see sector allocation.
```

---

## Dark mode

All colors use `AmiColors.*` tokens. Pie chart text (%) is visible in both light and dark.

---

## Tap interaction (future)

At Tier 3, tapping a sector can filter the holdings list to show only that sector. At Tier 2, chart is informational only.

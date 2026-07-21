# DEF075 — Bottom-sheet primary buttons clipped under the Android nav bar

**Source:** `bug:3a10a0f8` (+12 duplicates) · **Reporter:** Vector Lynx (`e5777149`, floor_pass, Xiaomi 2412DPC0AG, Android 16, `0.1.0+43`) · **Filed:** 2026-07-21 (AT:R64) · **Status:** resolved (AT:R64) — fix implemented, ships in the next Android build (+44).

## Symptom

13 reports in 8 minutes — *"UI Clipping. Unclickable/Unaccessible"* on route `/floor`.
Every screenshot shows the **primary button drawn behind the Android 3-button system
navigation bar**:

- the agent-unlock sheet's green **"GO TO LESSONS"** CTA (Fundamentals Analyst, Bear
  Researcher, … — same sheet, different agents), and
- the bug-report sheet's own blue **"Send report"** button.

The lower third of each button sits under the nav buttons, so it is hard or impossible to
tap. The reporter was hitting it repeatedly across the agent-unlock flow.

## Root cause — two proximate causes, one class

The app's modal bottom sheets did not reserve the **bottom system inset** (the nav-bar
area, `MediaQuery.viewPadding.bottom`) for their content:

1. **`bug_report_sheet` / `convene_sheet` / `trade_ticket_sheet`** padded their content by
   `MediaQuery.viewInsets.bottom` — the **keyboard** height — *only*. With the keyboard
   closed that is `0`, so the CTA sat flush against the screen edge, under the nav bar.
2. **`floor_screen._showLockedSheet`** (the agent-unlock sheet) *had* a `SafeArea`, but was
   **not** `isScrollControlled`, so it was capped at ~9/16 of the screen. An agent with a
   full 5-lesson gateway (title + 5 rows + two buttons) overflowed that cap; in a release
   build the overflow paints silently, pushing the CTA down under the nav bar.

`viewInsets.bottom` (keyboard) and `viewPadding.bottom` (system bars) are independent — a
sheet needs the larger of the two to clear whatever is at the bottom in any state. This is
a device-general Android issue (any bottom system inset), not Xiaomi-specific; it was
invisible on iOS home-indicator devices because the home indicator overlays content
without stealing taps.

## Resolution (AT:R64)

New shared helper — [`mobile/lib/widgets/sheet_insets.dart`](../../../mobile/lib/widgets/sheet_insets.dart):

```dart
double sheetBottomInset(MediaQueryData mq) =>
    math.max(mq.viewInsets.bottom, mq.viewPadding.bottom);
```

- **`bug_report_sheet.dart`**, **`convene_sheet.dart`**, **`trade_ticket_sheet.dart`** — the
  content's bottom padding now uses `sheetBottomInset(...)` instead of `viewInsets.bottom`
  alone. Keyboard-up behaviour is unchanged (keyboard height still wins); keyboard-down now
  clears the nav bar.
- **`floor_screen.dart._showLockedSheet`** — now `isScrollControlled: true` and the content
  is wrapped in `SingleChildScrollView`, so a full gateway list scrolls instead of
  overflowing; the existing `SafeArea` keeps the CTA above the nav bar.

**Guard:** [`mobile/test/widgets/sheet_insets_test.dart`](../../../mobile/test/widgets/sheet_insets_test.dart)
— 4 cases including the exact clip (nav bar present, keyboard closed → returns the nav
inset, not 0). `flutter analyze` clean on touched files (2 pre-existing infos in the
untouched tour code).

## Scope / follow-up

Fixed the four sheets with the defect. The rest already wrap in `SafeArea`
(`agent_action_sheet`, `watchlist_sheet`, `merge_sheet`, `league`, `ai_coach`,
`term_block`, `tour_intro_sheet`). New sheets should use `sheetBottomInset` or a `SafeArea`
— worth a `failure_patterns.md` line if a third instance appears.

## Not this DEF

The separate **Google sign-in** failure the same reporter filed (`56d6d6cb`) is **DEF076**.

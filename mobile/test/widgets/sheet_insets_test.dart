/// DEF075 — a modal sheet's bottom padding must clear the system nav bar even
/// with the keyboard closed, or the primary button ("Send report", "GO TO
/// LESSONS") renders under the Android 3-button nav and can't be tapped.
library;

import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  MediaQueryData mq({double insets = 0, double padding = 0}) => MediaQueryData(
        viewInsets: EdgeInsets.only(bottom: insets),
        viewPadding: EdgeInsets.only(bottom: padding),
      );

  test('keyboard down: uses the nav-bar inset (the exact DEF075 clip)', () {
    // 48px nav bar, no keyboard — the old viewInsets-only code returned 0,
    // so the CTA sat under the nav bar. Now it clears it.
    expect(sheetBottomInset(mq(insets: 0, padding: 48)), 48);
  });

  test('keyboard up: keyboard height wins (it already covers the nav bar)', () {
    expect(sheetBottomInset(mq(insets: 320, padding: 48)), 320);
  });

  test('no nav bar, no keyboard: zero', () {
    expect(sheetBottomInset(mq()), 0);
  });

  test('gesture nav (small inset), keyboard down: still clears it', () {
    expect(sheetBottomInset(mq(insets: 0, padding: 24)), 24);
  });
}

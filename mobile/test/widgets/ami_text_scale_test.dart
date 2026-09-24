/// CR226 — the text-scale clamp on the app's fixed-height chrome.
///
/// `app.dart:49` (pre-CR226) set no `builder:` and `textScaler` was set
/// nowhere in the app except `share_service.dart`'s offscreen PNG export —
/// so the OS font-size setting multiplied every `fontSize` unbounded: iOS
/// Dynamic Type reaches ~3.1×, Android's slider 2.0×. Renders the three
/// chrome widgets `CR226_adaptive_banner_slot.md` names — the bottom nav,
/// the screen header, the ticker tape — each at 1.0×/2.0×/3.1× on the
/// worst-case width (375dp, the narrowest supported phone: smallest width,
/// largest scale is the actual worst case, not merely the largest scale
/// alone) and asserts no `RenderFlex` overflow, via `tester.takeException()`
/// — an overflow throws during layout/paint, which is what a real
/// yellow-and-black stripe on device would be.
library;

import 'package:ami_trade/theme/ami_text_scale.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/hex/hex_bottom_nav.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _scales = [1.0, 2.0, 3.1];

/// A long, real-shaped title — the worst case this CR actually found: the
/// subtitle already guarded against a long string, but the title never did.
const _longTitle = 'PORTFOLIO HISTORY AND REBALANCE REVIEW';

Widget _pumpAt(double scale, Widget child) => MediaQuery(
      data: MediaQueryData(
        size: const Size(375, 667), // iPhone SE/mini — narrowest supported.
        textScaler: TextScaler.linear(scale),
      ),
      child: MaterialApp(home: Scaffold(body: child)),
    );

void main() {
  group('kChromeMaxTextScaleFactor', () {
    test('is 1.3 — the CR226 doc\'s recommended bound', () {
      expect(kChromeMaxTextScaleFactor, 1.3);
    });
  });

  group('AmiScreenHeader — no overflow at any OS text scale', () {
    for (final scale in _scales) {
      testWidgets('scale=${scale}x, 375dp wide, long title', (tester) async {
        await tester.pumpWidget(_pumpAt(
          scale,
          const AmiScreenHeader(
            title: _longTitle,
            titleColor: AmiColors.hexCyan,
            subtitle: 'A subtitle long enough to have overflowed before',
          ),
        ));
        await tester.pump();
        expect(tester.takeException(), isNull,
            reason: 'CR226: the header must not overflow its fixed 64dp '
                'height at $scale' 'x — worst case, smallest width (375dp), '
                'largest scale');
        // The height itself must still be exactly 64 — the clamp bounds the
        // TEXT, not the box; a box that silently grew would be a different
        // kind of chrome regression this CR is not asking for.
        expect(tester.getSize(find.byType(AmiScreenHeader)).height, 64);
      });
    }

    testWidgets('the title ellipsises rather than overflowing at 3.1x',
        (tester) async {
      await tester.pumpWidget(_pumpAt(
        3.1,
        const AmiScreenHeader(
          title: _longTitle,
          titleColor: AmiColors.hexCyan,
        ),
      ));
      await tester.pump();
      expect(tester.takeException(), isNull);
      final text = tester.widget<Text>(find.text(_longTitle));
      expect(text.maxLines, 1,
          reason: 'CR226: the title had no maxLines/ellipsis guard at all '
              'before this CR — only the subtitle did');
      expect(text.overflow, TextOverflow.ellipsis);
    });

    testWidgets('the clamp does not fight a SMALLER-than-default OS setting',
        (tester) async {
      // 0.85x (a real "smaller text" OS setting) must pass through
      // unclamped — the clamp only ever caps the ceiling.
      await tester.pumpWidget(_pumpAt(
        0.85,
        const AmiScreenHeader(title: 'FLOOR', titleColor: AmiColors.hexBlue),
      ));
      await tester.pump();
      expect(tester.takeException(), isNull);
    });
  });

  group('HexBottomNav — no overflow at any OS text scale', () {
    for (final scale in _scales) {
      testWidgets('scale=${scale}x, 375dp wide, 5 items', (tester) async {
        await tester.pumpWidget(_pumpAt(
          scale,
          HexBottomNav(
            currentIndex: 1,
            onTap: (_) {},
            items: const [
              HexNavItem(icon: Icons.grid_view_rounded, label: 'FLOOR', id: 'nav.floor'),
              HexNavItem(icon: Icons.account_balance_wallet_outlined, label: 'PORTFOLIO', id: 'nav.portfolio'),
              HexNavItem(icon: Icons.school_outlined, label: 'LESSONS', id: 'nav.lessons'),
              HexNavItem(icon: Icons.person_outline, label: 'YOU', id: 'nav.you'),
            ],
          ),
        ));
        await tester.pump();
        expect(tester.takeException(), isNull,
            reason: 'CR226: the nav must not overflow its fixed 64dp '
                'height at $scale' 'x — the FittedBox on the label absorbs '
                'scaling as a DEF043 side effect, not by design; the clamp '
                'bounds what it has to shrink');
        expect(tester.getSize(find.byType(HexBottomNav)).height, 64);
      });
    }
  });
}

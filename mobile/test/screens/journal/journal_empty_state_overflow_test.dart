// DEF427 (E5-U2) — the Journal empty state overflowed by 29px on an iPhone
// 17 Simulator debug build: Flutter's own "BOTTOM OVERFLOWED BY 29 PIXELS"
// banner across the illustration/copy area below "No entries yet." The
// screenshot came from the automated iOS Appium gate
// (docs/forward_planning/CR004_release_readiness/e5_device_matrix_runbook.md),
// a debug build, so the yellow/black stripe itself is debug-only chrome —
// but the underlying layout overflow it renders is real regardless of build
// mode; a release build just wouldn't show it.
//
// Root cause: `_EmptyState` (journal_screen.dart) is
// `Padding(all: xl) > Center > Column(mainAxisSize: max) [icon, gap, title,
// gap, body]`, sitting inside the JOURNAL segment's `Expanded` area ABOVE a
// second sibling — `AdSlot(placement: journalEmptyState)` — that also claims
// height from the same `Column`. `Center` does not protect its child from
// overflowing when the child is intrinsically taller than the space
// `Expanded` actually left it (all of xl*2 padding + icon + 2 gaps + 2 text
// blocks, on a screen short enough that the ad slot's own reserved row plus
// the bottom nav / home indicator already ate into what `Expanded` was
// given) — worse at a large text scale, where the body copy alone can wrap
// to 3+ lines.
//
// Fix: `_EmptyState`'s content is now wrapped in a `SingleChildScrollView`
// (mirrors CLAUDE.md's own framing of the failure class this harness exists
// to catch: "screens that do not scroll when they need to") and the fixed
// `Center` requirement dropped in favour of `AlwaysScrollableScrollPhysics`.
// The visual centring most viewports see happens because the content is
// wrapped in a `ConstrainedBox(minHeight: available)` + `Center`, which is a
// no-op scroll physically when there's slack, and becomes a real scroll only
// when there is not.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _ScriptedJournalNotifier extends JournalNotifier {
  _ScriptedJournalNotifier(super.ref, {String searchQuery = ''}) {
    state = JournalState(
      entries: const [],
      retentionLoaded: true,
      searchQuery: searchQuery,
    );
  }

  @override
  Future<void> refresh({JournalEntryType? filterType, String? q}) async {}
}

class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref) {
    state = MandateState(
      mandate: UserMandate(
        userId: 'u1',
        version: 1,
        displayName: 'Trader',
        locale: 'en',
        timezone: 'UTC',
        primaryGoal: 'long_term_wealth',
        horizon: 'long',
        path: 'long_horizon',
        riskScore: 3,
        riskComponents: const RiskComponents(
          drawdownResponse: 3,
          regretAsymmetry: 0,
          concentrationTolerance: 3,
        ),
        maxDrawdownPct: 30,
        learningStyle: 'quick',
        compliance: const ComplianceFlags(),
        plan: 'floor_pass',
        creditBalance: 0,
      ),
    );
  }

  @override
  Future<void> refresh() async {}
}

/// Pins the viewport to [size] and [textScale]. `embedded: true` matches how
/// `YouScreen` actually mounts `JournalScreen` (CR133 §4) — the Scaffold and
/// SafeArea belong to the parent there, and the overflow this DEF is about
/// happens inside that embedded body, not inside a screen-owned Scaffold.
Future<void> _pumpEmptyState(
  WidgetTester tester, {
  required Size size,
  double textScale = 1.0,
  bool searching = false,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({});

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        journalNotifierProvider.overrideWith(
          (ref) => _ScriptedJournalNotifier(
            ref,
            searchQuery: searching ? 'nonexistent query' : '',
          ),
        ),
        mandateNotifierProvider
            .overrideWith((ref) => _FixedMandateNotifier(ref)),
      ],
      child: MediaQuery(
        data: MediaQueryData(
          size: size,
          textScaler: TextScaler.linear(textScale),
        ),
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(
            body: SizedBox(
              height: size.height,
              width: size.width,
              child: const JournalScreen(embedded: true),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

void main() {
  group('DEF427 — Journal empty state does not overflow', () {
    // Sizes named in the DEF: 320/375/430dp phones, the iPhone 17's own
    // simulator size (where E5-U2 was actually captured), and one landscape
    // phone — a short-height case is exactly where a fixed illustration +
    // two text blocks + a sibling ad slot run out of vertical room.
    const sizes = <String, Size>{
      '320dp (small phone)': Size(320, 690),
      '375dp (iPhone baseline)': Size(375, 812),
      '430dp (large phone)': Size(430, 932),
      'iPhone 17 (iOS Simulator, E5-U2)': Size(393, 852),
      'landscape phone/844x390': Size(844, 390),
    };

    for (final entry in sizes.entries) {
      for (final scale in [1.0, 1.3]) {
        testWidgets('no overflow at ${entry.key}, scale $scale',
            (tester) async {
          await _pumpEmptyState(tester, size: entry.value, textScale: scale);
          expect(find.text('No entries yet.'), findsOneWidget,
              reason: '${entry.key} @ $scale');
          expect(tester.takeException(), isNull,
              reason: '${entry.key} @ $scale');
        });
      }
    }

    testWidgets('the searching-empty variant also does not overflow',
        (tester) async {
      // Shorter copy (no body line, see journal_screen.dart's `!isSearching`
      // guard) but worth pinning at the tightest size regardless — a future
      // edit adding a body line here should trip this, not ship silently.
      await _pumpEmptyState(
        tester,
        size: const Size(320, 690),
        textScale: 1.3,
        searching: true,
      );
      expect(find.text('No entries match your search.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('the empty state remains reachable via scrolling, not clipping',
        (tester) async {
      // 320x568 is the shortest portrait height any shipping iPhone has ever
      // used (iPhone 5/SE 1st-gen) — the tightest real case, not an
      // unrealistic one, at the DEF's own large text scale. Asserts the fix
      // is a SCROLL, per CLAUDE.md's own framing of this harness's whole
      // purpose ("screens that do not scroll when they need to") — not a
      // silent RenderFlex clip that would hide the same content instead of
      // fixing the overflow.
      await _pumpEmptyState(
        tester,
        size: const Size(320, 568),
        textScale: 1.3,
      );
      expect(tester.takeException(), isNull);
      expect(find.byType(Scrollable), findsWidgets);
      expect(find.text('No entries yet.'), findsOneWidget);
      final body = find.textContaining('Talk to an agent');
      expect(body, findsOneWidget);

      // The body text must be reachable, not merely present in the tree
      // clipped out of the viewport — scroll it into view and confirm it
      // actually paints on screen afterwards.
      await tester.scrollUntilVisible(body, 100.0,
          scrollable: find.byType(Scrollable).first);
      await tester.pump();
      expect(tester.getRect(body).overlaps(Offset.zero & const Size(320, 568)),
          isTrue);
    });
  });
}

/// CR109 — the field board, tested on the rules rather than the pixels.
///
/// Every assertion here corresponds to a decision the design wrote down
/// *because* the obvious implementation gets it wrong:
///
///   * §6.1 — rank on % return, never on money. A board that ranks AMI Cash
///     makes capital tier pay-to-win.
///   * §11.2 — a desk is visibly a desk on every surface that renders an
///     entrant, with its rule reachable. Saiful's own framing: an undisclosed
///     house account means the user "is copying what they thought is a
///     person", and a screenshot leaving the app carries no disclosure.
///   * The `?? 0` class, ninth instance and counting — an entrant with no
///     completed close must draw as a dash, not as 0.00%. Flat and unmeasured
///     are different facts, and this feature has now conflated them nine
///     separate times in nine different places.
///
/// DEF420 adds a second class of assertion — the screen's *chrome*, which was
/// out of line with the rest of the app (a bare Material `AppBar`, a
/// `statBig`-sized empty-state heading that wraps at small widths / large
/// text scales, and a YOU row tinted almost to invisibility). Those checks
/// live in the `DEF420 — restyle` group below and do not duplicate the rule
/// tests above: same data, same behaviour, different pixels.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_board_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/ami_window_size.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_games_api_client.dart';

const _runId = 'run-1';

GameBoardRow _row({
  required String handle,
  int? rank,
  double? twrPct,
  bool isDesk = false,
  String? deskRule,
  bool isYou = false,
  int closesCounted = 1,
}) =>
    GameBoardRow(
      handle: handle,
      isDesk: isDesk,
      deskKey: isDesk ? 'momentum' : null,
      deskRule: deskRule,
      twrPct: twrPct,
      rank: rank,
      closesCounted: closesCounted,
      isYou: isYou,
    );

GameBoard _board({
  required List<GameBoardRow> rows,
  int? yourRank,
  double? yourTwrPct,
  bool standingsOpen = true,
  int? entrantCount,
  int deskCount = 0,
}) =>
    GameBoard(
      fieldId: 'f1',
      cadence: 'week',
      rows: rows,
      entrantCount: entrantCount ?? rows.length,
      deskCount: deskCount,
      standingsOpen: standingsOpen,
      yourRank: yourRank,
      yourTwrPct: yourTwrPct,
    );

Future<void> _pump(WidgetTester tester, GameBoard board) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient(board: board)),
        gamesBoardProvider(_runId).overrideWith((ref) async => board),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const GamesBoardScreen(runId: _runId),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

/// Same as [_pump], but pins the viewport to [size] and an optional
/// [textScale] — the DEF420 adaptive-layout sweep's workhorse. Resets the
/// view via [addTearDown] so one test's size never leaks into the next.
Future<void> _pumpSized(
  WidgetTester tester, {
  required GameBoard board,
  required Size size,
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient(board: board)),
        gamesBoardProvider(_runId).overrideWith((ref) async => board),
      ],
      child: MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const GamesBoardScreen(runId: _runId),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

void main() {
  group('standings', () {
    testWidgets('ranks the field and marks the player', (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'careful-vector', rank: 2, twrPct: 2.0, isYou: true),
            _row(handle: 'Index Desk', rank: 3, twrPct: -0.2, isDesk: true),
          ],
          yourRank: 2,
          yourTwrPct: 2.0,
          deskCount: 2,
        ),
      );

      expect(find.text("You're #2 of 3"), findsOneWidget);
      expect(find.text('Momentum Desk'), findsOneWidget);
      expect(find.text('+4.50%'), findsOneWidget);
      expect(find.text('+2.00%'), findsWidgets);
      expect(find.text('-0.20%'), findsOneWidget);
    });

    testWidgets('discloses how much of the field is house desks',
        (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'careful-vector', rank: 2, twrPct: 2.0, isYou: true),
          ],
          yourRank: 2,
          yourTwrPct: 2.0,
          deskCount: 1,
        ),
      );
      expect(find.text('2 entrants'), findsOneWidget);
      expect(find.text('including 1 house desk'), findsOneWidget);
    });

    testWidgets('says out loud that it only moves once per close',
        (tester) async {
      await _pump(tester, _board(rows: [_row(handle: 'me', rank: 1, twrPct: 1)]));
      expect(
        find.text('Standings move once per US close — not tick by tick.'),
        findsOneWidget,
      );
    });
  });

  group('unmeasured is not zero — the ?? 0 class, ninth instance', () {
    testWidgets('an entrant with no close draws a dash, never 0.00%',
        (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'measured', rank: 1, twrPct: 1.0),
            _row(handle: 'brand-new', closesCounted: 0),
          ],
          yourRank: 1,
          yourTwrPct: 1.0,
        ),
      );

      expect(find.text('0.00%'), findsNothing);
      expect(find.text('+0.00%'), findsNothing);
      expect(find.text('No close yet'), findsOneWidget);
      // Both the rank column and the return column render a dash.
      expect(find.text('—'), findsNWidgets(2));
    });

    testWidgets('the player with no close is told so, not shown a position',
        (tester) async {
      await _pump(
        tester,
        _board(
          rows: [_row(handle: 'brand-new', isYou: true, closesCounted: 0)],
          standingsOpen: false,
        ),
      );

      expect(find.text('Not ranked yet'), findsOneWidget);
      expect(find.text('Standings open after the first US close.'),
          findsOneWidget);
      expect(find.textContaining("You're #"), findsNothing);
    });
  });

  group('disclosure — §11.2', () {
    testWidgets('every desk row carries the DESK chip', (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'Index Desk', rank: 2, twrPct: 1.0, isDesk: true),
            _row(handle: 'careful-vector', rank: 3, twrPct: 0.5, isYou: true),
          ],
          yourRank: 3,
          yourTwrPct: 0.5,
          deskCount: 2,
        ),
      );
      expect(find.text('DESK'), findsNWidgets(2));
      expect(find.text('YOU'), findsOneWidget);
    });

    testWidgets("tapping a desk shows the rule the SERVER published",
        (tester) async {
      const rule = 'Equal-weights the 5 highest trailing 12-month returns.';
      await _pump(
        tester,
        _board(
          rows: [
            _row(
              handle: 'Momentum Desk',
              rank: 1,
              twrPct: 4.5,
              isDesk: true,
              deskRule: rule,
            ),
          ],
          yourRank: null,
        ),
      );

      await tester.tap(find.text('Momentum Desk'));
      await tester.pumpAndSettle();

      expect(find.text(rule), findsOneWidget);
      expect(find.text('How this desk trades'), findsOneWidget);
      // The disclosure line must never let a desk read as a person.
      expect(
        find.textContaining('Desks are AMI-run strategies, not people.'),
        findsOneWidget,
      );
    });

    testWidgets('a human row opens nothing — the board renders no one\'s book',
        (tester) async {
      await _pump(
        tester,
        _board(
          rows: [_row(handle: 'other-player', rank: 1, twrPct: 3.0)],
        ),
      );

      await tester.tap(find.text('other-player'));
      await tester.pumpAndSettle();
      expect(find.text('How this desk trades'), findsNothing);
    });
  });

  group('§6.1 — the board ranks percentages, never money', () {
    testWidgets('renders no currency amount for anyone', (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'careful-vector', rank: 2, twrPct: 2.0, isYou: true),
          ],
          yourRank: 2,
          yourTwrPct: 2.0,
          deskCount: 1,
        ),
      );

      // A currency glyph or a thousands-separated figure on this screen would
      // mean somebody's AMI Cash reached it.
      final texts = tester
          .widgetList<Text>(find.byType(Text))
          .map((t) => t.data ?? '')
          .toList();
      for (final t in texts) {
        expect(t.contains(r'$'), isFalse, reason: 'money on the board: $t');
        expect(
          RegExp(r'\d{1,3},\d{3}').hasMatch(t),
          isFalse,
          reason: 'money-shaped figure on the board: $t',
        );
      }
    });
  });

  group('empty', () {
    testWidgets('an empty field says so', (tester) async {
      await _pump(tester, _board(rows: const [], standingsOpen: false));
      expect(find.text('No one has entered this field yet.'), findsOneWidget);
    });
  });

  group('DEF420 — restyle to match the rest of the app', () {
    testWidgets('wears the shared AmiScreenHeader, not a bare AppBar',
        (tester) async {
      await _pump(
        tester,
        _board(rows: [_row(handle: 'me', rank: 1, twrPct: 1)]),
      );
      expect(find.byType(AmiScreenHeader), findsOneWidget);
      expect(find.byType(AppBar), findsNothing);
      expect(find.text('Standings'), findsOneWidget);
    });

    testWidgets(
        'the not-ranked-yet empty state does not overflow at 375dp, '
        '1.0x and 1.3x text scale', (tester) async {
      for (final scale in [1.0, 1.3]) {
        await _pumpSized(
          tester,
          board: _board(
            rows: [_row(handle: 'brand-new', isYou: true, closesCounted: 0)],
            standingsOpen: false,
          ),
          size: const Size(375, 812),
          textScale: scale,
        );

        expect(find.text('Not ranked yet'), findsOneWidget,
            reason: 'at scale $scale');
        expect(tester.takeException(), isNull, reason: 'at scale $scale');
      }
    });

    testWidgets('the YOU row renders the accent highlight, not a flat tint',
        (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'careful-vector', rank: 2, twrPct: 2.0, isYou: true),
          ],
          yourRank: 2,
          yourTwrPct: 2.0,
          deskCount: 1,
        ),
      );

      // The YOU row's own container carries a visible cyan wash + border —
      // the accent-card vocabulary the rest of the screen uses — rather than
      // the old `slate800` (a colour shared with every OTHER row's own
      // background, which is how it read as barely-visible).
      final decoratedBoxes = tester.widgetList<DecoratedBox>(
          find.descendant(
              of: find.ancestor(
                  of: find.text('careful-vector'),
                  matching: find.byType(Column)),
              matching: find.byType(DecoratedBox)));
      final containers = tester.widgetList<Container>(find.descendant(
          of: find.ancestor(
              of: find.text('careful-vector'), matching: find.byType(Column)),
          matching: find.byType(Container)));

      bool carriesCyanAccent(BoxDecoration? d) {
        if (d == null) return false;
        final fill = d.color;
        final border = d.border;
        final fillIsCyan = fill != null &&
            fill.toARGB32() ==
                AmiColors.hexCyan.withValues(alpha: 0.12).toARGB32();
        final borderIsCyan = border is Border &&
            border.top.color.toARGB32() ==
                AmiColors.hexCyan.withValues(alpha: 0.5).toARGB32();
        return fillIsCyan || borderIsCyan;
      }

      final found = [
        ...decoratedBoxes.map((b) => b.decoration).whereType<BoxDecoration>(),
        ...containers.map((c) => c.decoration).whereType<BoxDecoration>(),
      ].any(carriesCyanAccent);

      expect(found, isTrue,
          reason: 'no cyan-accent decoration found around the YOU row');
    });

    testWidgets('renders a populated board cleanly', (tester) async {
      await _pump(
        tester,
        _board(
          rows: [
            _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
            _row(handle: 'careful-vector', rank: 2, twrPct: 2.0, isYou: true),
          ],
          yourRank: 2,
          yourTwrPct: 2.0,
          deskCount: 1,
        ),
      );
      expect(find.text('Momentum Desk'), findsOneWidget);
      expect(find.text('careful-vector'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('renders the empty board cleanly', (tester) async {
      await _pump(tester, _board(rows: const [], standingsOpen: false));
      expect(find.text('No one has entered this field yet.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('DEF420 round 2 — adaptive across window sizes', () {
    // Architect correction, Saiful: "really it should be adaptive to the
    // different screen size surely?" — the sweep spans compact phones
    // through an expanded tablet width, plus one landscape phone, for both
    // a populated and an empty board.
    const sizes = <String, Size>{
      'compact/320 (small phone)': Size(320, 690),
      'compact/375 (iPhone baseline)': Size(375, 812),
      'compact/430 (large phone)': Size(430, 932),
      'medium/600 (foldable/small tablet)': Size(600, 900),
      'medium/840 boundary': Size(840, 1000),
      'expanded/1024 (tablet)': Size(1024, 1366),
      'landscape phone/844x390': Size(844, 390),
    };

    final populated = _board(
      rows: [
        _row(handle: 'Momentum Desk', rank: 1, twrPct: 4.5, isDesk: true),
        _row(handle: 'careful-vector', rank: 2, twrPct: 2.0, isYou: true),
        _row(handle: 'Index Desk', rank: 3, twrPct: -0.2, isDesk: true),
      ],
      yourRank: 2,
      yourTwrPct: 2.0,
      deskCount: 2,
    );
    final empty = _board(
      rows: [_row(handle: 'brand-new', isYou: true, closesCounted: 0)],
      standingsOpen: false,
    );

    for (final entry in sizes.entries) {
      for (final scale in [1.0, 1.3]) {
        testWidgets(
            'populated board — no overflow at ${entry.key}, scale $scale',
            (tester) async {
          await _pumpSized(tester,
              board: populated, size: entry.value, textScale: scale);
          expect(tester.takeException(), isNull,
              reason: '${entry.key} @ $scale');
        });

        testWidgets('empty board — no overflow at ${entry.key}, scale $scale',
            (tester) async {
          await _pumpSized(tester,
              board: empty, size: entry.value, textScale: scale);
          expect(tester.takeException(), isNull,
              reason: '${entry.key} @ $scale');
        });
      }
    }

    testWidgets('the content column is capped and centred on a wide window',
        (tester) async {
      await _pumpSized(tester, board: populated, size: const Size(1024, 1366));

      final constraint = tester.widget<AmiContentWidthConstraint>(
          find.byType(AmiContentWidthConstraint));
      expect(constraint.maxWidth, AmiBreakpoints.maxContentWidth);

      // AmiContentWidthConstraint's OWN box (the Align) legitimately fills
      // its parent's width — Align always does. What must be capped is the
      // CONTENT inside it, so measure the actual column the screen renders
      // into, not the Align wrapper.
      final renderBox = tester.renderObject<RenderBox>(
          find.byKey(const Key('games_board_content_column')));
      expect(renderBox.size.width,
          lessThanOrEqualTo(AmiBreakpoints.maxContentWidth));

      // And centred: equal space on both sides of a 1024-wide window.
      final topLeft = tester
          .getTopLeft(find.byKey(const Key('games_board_content_column')));
      final topRight = tester
          .getTopRight(find.byKey(const Key('games_board_content_column')));
      final leftGap = topLeft.dx;
      final rightGap = 1024 - topRight.dx;
      expect((leftGap - rightGap).abs(), lessThan(1.0),
          reason: 'left gap $leftGap vs right gap $rightGap — not centred');
    });

    testWidgets(
        'the content column fills the compact window rather than capping',
        (tester) async {
      await _pumpSized(tester, board: populated, size: const Size(375, 812));

      final renderBox = tester.renderObject<RenderBox>(
          find.byKey(const Key('games_board_content_column')));
      // 375dp is well under AmiBreakpoints.maxContentWidth (640) — the cap
      // must never SHRINK a compact layout, only ever bound a wide one.
      expect(renderBox.size.width, greaterThan(300));
    });

    testWidgets('windowWidthClassOf resolves the three M3 classes correctly',
        (tester) async {
      expect(windowWidthClassOf(320), AmiWindowWidthClass.compact);
      expect(windowWidthClassOf(599.9), AmiWindowWidthClass.compact);
      expect(windowWidthClassOf(600), AmiWindowWidthClass.medium);
      expect(windowWidthClassOf(839.9), AmiWindowWidthClass.medium);
      expect(windowWidthClassOf(840), AmiWindowWidthClass.expanded);
      expect(windowWidthClassOf(1024), AmiWindowWidthClass.expanded);
    });
  });

  group('DEF420 MINOR-1 — nextUsCloseEstimate is DST-correct', () {
    // 2026 US DST transitions (verified against the "second Sunday of March
    // / first Sunday of November, 2:00am local" rule the fix implements):
    //   DST starts 2026-03-08 07:00 UTC (2:00am EST -> 3:00am EDT)
    //   DST ends   2026-11-01 06:00 UTC (2:00am EDT -> 1:00am EST)
    // The old fixed-20:30-UTC estimate was wrong by 30 minutes on BOTH sides
    // of every transition and, worse, could count down to an already-passed
    // close depending on which side of the true boundary "now" landed.

    test('deep winter (EST, UTC-5) — close resolves to 21:00 UTC', () {
      // Tuesday 2026-01-06, well clear of both transitions.
      final now = DateTime.utc(2026, 1, 6, 14, 0);
      final close = nextUsCloseEstimate(now);
      expect(close, DateTime.utc(2026, 1, 6, 21, 0));
    });

    test('deep summer (EDT, UTC-4) — close resolves to 20:00 UTC', () {
      // Wednesday 2026-07-15, well clear of both transitions.
      final now = DateTime.utc(2026, 7, 15, 14, 0);
      final close = nextUsCloseEstimate(now);
      expect(close, DateTime.utc(2026, 7, 15, 20, 0));
    });

    test('the day before spring-forward is still EST (21:00 UTC close)', () {
      // Saturday 2026-03-07 — a weekend, so the estimate must also roll to
      // Monday 2026-03-09, which is AFTER the spring-forward transition and
      // therefore an EDT (20:00 UTC) close.
      final now = DateTime.utc(2026, 3, 7, 10, 0);
      final close = nextUsCloseEstimate(now);
      expect(close!.weekday, DateTime.monday);
      expect(close, DateTime.utc(2026, 3, 9, 20, 0));
    });

    test('the day of spring-forward (Sunday) rolls to Monday, already EDT',
        () {
      final now = DateTime.utc(2026, 3, 8, 10, 0);
      final close = nextUsCloseEstimate(now);
      expect(close, DateTime.utc(2026, 3, 9, 20, 0));
    });

    test('the first weekday close after spring-forward is 20:00 UTC (EDT)',
        () {
      // Monday 2026-03-09, morning — the transition (Sun 07:00 UTC) is
      // already behind us, so today's own close must be EDT.
      final now = DateTime.utc(2026, 3, 9, 12, 0);
      final close = nextUsCloseEstimate(now);
      expect(close, DateTime.utc(2026, 3, 9, 20, 0));
    });

    test('the last weekday close before fall-back is still 20:00 UTC (EDT)',
        () {
      // Friday 2026-10-30 — before the Nov 1 transition, still EDT.
      final now = DateTime.utc(2026, 10, 30, 12, 0);
      final close = nextUsCloseEstimate(now);
      expect(close, DateTime.utc(2026, 10, 30, 20, 0));
    });

    test('fall-back Sunday rolls to Monday, already EST (21:00 UTC)', () {
      final now = DateTime.utc(2026, 11, 1, 10, 0);
      final close = nextUsCloseEstimate(now);
      expect(close, DateTime.utc(2026, 11, 2, 21, 0));
    });

    test('the first weekday close after fall-back is 21:00 UTC (EST)', () {
      // Monday 2026-11-02, morning — the transition (Sun 06:00 UTC) is
      // already behind us, so today's own close must be EST.
      final now = DateTime.utc(2026, 11, 2, 12, 0);
      final close = nextUsCloseEstimate(now);
      expect(close, DateTime.utc(2026, 11, 2, 21, 0));
    });

    test('a plain weekend (no DST transition involved) still rolls to Monday',
        () {
      // Saturday 2026-07-18 -> Monday 2026-07-20, both EDT.
      final now = DateTime.utc(2026, 7, 18, 10, 0);
      final close = nextUsCloseEstimate(now);
      expect(close, DateTime.utc(2026, 7, 20, 20, 0));
    });

    test('Friday evening after close rolls straight to Monday, not Saturday',
        () {
      // Friday 2026-07-17 21:30 UTC is after that day's 20:00 UTC EDT close.
      final now = DateTime.utc(2026, 7, 17, 21, 30);
      final close = nextUsCloseEstimate(now);
      expect(close!.weekday, DateTime.monday);
      expect(close, DateTime.utc(2026, 7, 20, 20, 0));
    });

    test('a second year (2027) resolves the correct transition dates too',
        () {
      // 2027: 2nd Sunday of March = 2027-03-14; 1st Sunday of Nov = 2027-11-07.
      final beforeSpringForward = nextUsCloseEstimate(
        DateTime.utc(2027, 3, 12, 12, 0), // Friday, still EST
      );
      expect(beforeSpringForward, DateTime.utc(2027, 3, 12, 21, 0));

      final afterSpringForward = nextUsCloseEstimate(
        DateTime.utc(2027, 3, 15, 12, 0), // Monday, already EDT
      );
      expect(afterSpringForward, DateTime.utc(2027, 3, 15, 20, 0));
    });
  });
}

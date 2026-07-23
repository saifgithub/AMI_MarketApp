/// CR069 guard — the four Sharia states must stay four, and `unknown` must
/// never wear the screened-out copy.
///
/// The failure this file exists to catch is CR069 design constraint 2: a
/// universe is not a screen, and collapsing "the standard never looked at this
/// company" into "the standard excluded this company" is a false assurance in
/// the direction nobody checks. It is also the direction a well-meaning edit
/// drifts — both strings are about a ticker that is not in the compliant set,
/// and the difference between them lives only in the words.
///
/// The second guard here is the wire mirror. The backend↔mobile seam is
/// hand-mirrored JSON with no codegen (roster: coder.mobile, contract
/// boundary), so a rename on the backend fails silently behind a `??`. The
/// fixtures below are REAL response bodies captured from
/// https://api-alpha.agenticmarketintel.ai on 2026-07-23, not hand-written
/// shapes — see CR069-MOBILE.coder.mobile.md for the capture and for the gap
/// they expose.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sharia.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/widgets/sharia_verdict_banner.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ShariaVerdict _verdict(ShariaStatus status, String ticker) => ShariaVerdict(
      status: status,
      ticker: ticker,
      standard: 'AAOIFI',
      source: 'S&P 500 Sharia Industry Exclusions Index (via SPUS)',
      asOf: DateTime.utc(2026, 7, 23),
    );

/// Pumps the banner and returns every string it rendered.
Future<List<String>> _render(WidgetTester tester, ShariaVerdict v) async {
  await tester.pumpWidget(MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(body: ShariaVerdictBanner(verdict: v)),
  ));
  await tester.pumpAndSettle();
  return tester
      .widgetList<Text>(find.byType(Text))
      .map((t) => t.data ?? '')
      .toList();
}

void main() {
  group('unknown is not screened-out', () {
    testWidgets('the unknown state renders the unknown copy', (tester) async {
      final texts = await _render(tester, _verdict(ShariaStatus.unknown, 'ASML'));
      final body = texts.join(' ');

      expect(body, contains('ASML'));
      expect(body, contains("isn't in the S&P 500"));
      expect(body, contains("hasn't reviewed it"));
      // The humility is the point of the string, not decoration.
      expect(body, contains("AMI doesn't know"));
      expect(body, contains('not a ruling either way'));
    });

    testWidgets('the unknown state renders NONE of the screened-out copy',
        (tester) async {
      final texts = await _render(tester, _verdict(ShariaStatus.unknown, 'ASML'));
      final body = texts.join(' ');

      // The screened-out sentence's load-bearing clauses. Any of these
      // appearing on an unknown means an absence of a ruling is being
      // rendered as an exclusion.
      expect(body, isNot(contains('does not pass')));
      expect(body, isNot(contains("won't trade it")));
      expect(body, isNot(contains('is in the S&P 500 but')));
      // Nor may it read as a refusal or a warning: the trade was PERMITTED.
      expect(body.toLowerCase(), isNot(contains('blocked')));
      expect(body.toLowerCase(), isNot(contains('rejected')));
    });

    testWidgets('unknown never blocks, screened-out and paused always do',
        (tester) async {
      expect(ShariaStatus.unknown.isBlocking, isFalse,
          reason: 'G3: unknown is permitted. If this flips, an absence of a '
              'ruling starts behaving like a prohibition.');
      expect(ShariaStatus.pass.isBlocking, isFalse);
      expect(ShariaStatus.screenedOut.isBlocking, isTrue);
      expect(ShariaStatus.unavailable.isBlocking, isTrue);
    });
  });

  group('all four states are distinct and carry their provenance', () {
    testWidgets('pass, screenedOut, unknown and paused render four different '
        'strings', (tester) async {
      final seen = <String>{};
      for (final s in ShariaStatus.values) {
        final texts = await _render(tester, _verdict(s, 'AAPL'));
        seen.add(texts.join(' '));
      }
      expect(seen.length, 4,
          reason: 'Two states collapsed to the same copy — the exact shape of '
              'CR069 design constraint 2.');
    });

    testWidgets('pass and screened-out name the standard, source and as-of '
        'date (design constraint 1)', (tester) async {
      for (final s in [ShariaStatus.pass, ShariaStatus.screenedOut]) {
        final body = (await _render(tester, _verdict(s, 'AAPL'))).join(' ');
        expect(body, contains('AAOIFI'), reason: 'standard missing for $s');
        expect(body, contains('S&P 500 Sharia Industry Exclusions Index'),
            reason: 'source missing for $s');
        expect(body, contains('2026-07-23'), reason: 'as-of date missing for $s');
      }
    });

    testWidgets('a null as-of stamp reads "unknown", never a fabricated date',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: ShariaVerdictBanner(
            verdict: const ShariaVerdict(
              status: ShariaStatus.unavailable,
              ticker: 'AAPL',
              standard: 'AAOIFI',
              source: 'S&P 500 Sharia Industry Exclusions Index (via SPUS)',
            ),
          ),
        ),
      ));
      await tester.pumpAndSettle();
      final body = tester
          .widgetList<Text>(find.byType(Text))
          .map((t) => t.data ?? '')
          .join(' ');
      expect(body, contains('last updated unknown'));
      expect(body, contains('paused'));
      expect(body, isNot(contains('2026')));
    });
  });

  group('wire mirror vs real backend JSON', () {
    test('ShariaStatus.fromWire accepts every value the backend enum emits', () {
      // backend/app/schemas/sharia.py::ShariaStatus
      expect(ShariaStatus.fromWire('pass'), ShariaStatus.pass);
      expect(ShariaStatus.fromWire('screened_out'), ShariaStatus.screenedOut);
      expect(ShariaStatus.fromWire('unknown'), ShariaStatus.unknown);
      expect(ShariaStatus.fromWire('unavailable'), ShariaStatus.unavailable);
    });

    test('an unrecognised status yields NO verdict, never a defaulted one', () {
      // Enum drift must surface as an empty surface, not a confident wrong one.
      expect(ShariaStatus.fromWire('halal'), isNull);
      expect(ShariaStatus.fromWire(null), isNull);
      expect(ShariaVerdict.fromJson({'status': 'screened-out'}), isNull);
      expect(ShariaVerdict.fromJson(null), isNull);
    });

    test('fromJson parses the backend ShariaVerdict field shape', () {
      final v = ShariaVerdict.fromJson({
        'status': 'screened_out',
        'ticker': 'meta',
        'standard': 'AAOIFI',
        'source': 'S&P 500 Sharia Industry Exclusions Index (via SPUS)',
        'as_of': '2026-07-23',
      })!;
      expect(v.status, ShariaStatus.screenedOut);
      expect(v.ticker, 'META');
      expect(v.standard, 'AAOIFI');
      // `as_of` is a calendar date, not an instant — the backend stamps it
      // from the source CSV's own `Date` column with no timezone. Assert the
      // calendar fields, not a UTC instant: forcing UTC here would only make
      // the test agree with itself while the rendered digits stayed the same.
      expect(v.asOf!.year, 2026);
      expect(v.asOf!.month, 7);
      expect(v.asOf!.day, 23);
      expect(v.isBlocking, isTrue);
    });

    // REAL bodies, captured 2026-07-23 from POST /v1/sim/preview on
    // api-alpha with a halal mandate. Verbatim.
    test('LIVE FIXTURE — a screened-out rejection parses', () {
      final r = SimSubmitResult.fromJson({
        'ok': false,
        'compliance': {
          'passed': false,
          'violations': [
            'META is in the parent index but does not pass the AAOIFI screen '
                '(S&P 500 Sharia Industry Exclusions Index (via SPUS), as of '
                "2026-07-23), so this mandate won't trade it."
          ],
          'blocked_by': 'compliance',
        },
      });
      expect(r.ok, isFalse);
      expect(r.violations, hasLength(1));
      expect(r.blockedBy, 'compliance');
      // The live backend does NOT serialize the structured field yet — the
      // sentence arrives only as English prose in violations[]. When
      // compliance.sharia_verdict starts shipping this becomes non-null and
      // the localized banner takes over. Until then this assertion is the
      // honest record of the gap, not an accepted state.
      expect(r.shariaVerdict, isNull);
    });

    test('LIVE FIXTURE — pass and unknown are byte-identical on the wire', () {
      // AAPL (in the compliant set) and ASML (outside the parent index) both
      // returned exactly this from POST /v1/sim/preview on 2026-07-23, modulo
      // price. Nothing distinguishes a screened PASS from an UNSCREENED
      // UNKNOWN, so the app cannot render either state from what it is served.
      Map<String, dynamic> permitted() => {
            'ok': true,
            'trade': {
              'id': '064164db-c0ce-4c14-b926-6b0423fd315a',
              'user_id': 'b99a5ee7-0d63-475d-a60a-8a9c2ac7a296',
              'portfolio_id': '29a39b65-80ed-4e81-bc99-cc8e55acca88',
              'ticker': 'AAPL',
              'side': 'buy',
              'quantity': 1.0,
              'entry_price': 325.8900146484375,
              'stop': null,
              'target': null,
              'horizon_days': null,
              'opened_at': '2026-07-23T13:01:32.611684+00:00',
              'closed_at': null,
              'closed_price': null,
              'status': 'open',
              'verdict_ref': null,
              'realised_pnl': 0.0,
            },
          };
      final r = SimSubmitResult.fromJson(permitted());
      expect(r.ok, isTrue);
      expect(r.shariaVerdict, isNull,
          reason: 'CR069-MOBILE blocker: /v1/sim/submit and /v1/sim/preview '
              'drop ComplianceResult.sharia_verdict when hand-building their '
              'response dict, so the permitted-unknown disclosure G3 requires '
              'has no field to travel in.');
    });

    test('once the backend serializes the field, the success path carries it',
        () {
      // The same permitted body with compliance.sharia_verdict attached — the
      // shape ComplianceResult already defines in schemas/trade.py. This is
      // the assertion that flips green the moment the backend emits it.
      final r = SimSubmitResult.fromJson({
        'ok': true,
        'trade': {
          'id': '26c19f21-b20c-4bf8-8c00-7868b5a60859',
          'user_id': 'b99a5ee7-0d63-475d-a60a-8a9c2ac7a296',
          'portfolio_id': '29a39b65-80ed-4e81-bc99-cc8e55acca88',
          'ticker': 'ASML',
          'side': 'buy',
          'quantity': 1.0,
          'entry_price': 1801.8599853515625,
          'stop': null,
          'target': null,
          'horizon_days': null,
          'opened_at': '2026-07-23T13:01:37.220537+00:00',
          'closed_at': null,
          'closed_price': null,
          'status': 'open',
          'verdict_ref': null,
          'realised_pnl': 0.0,
        },
        'compliance': {
          'passed': true,
          'violations': <String>[],
          'blocked_by': null,
          'sharia_verdict': {
            'status': 'unknown',
            'ticker': 'ASML',
            'standard': 'AAOIFI',
            'source': 'S&P 500 Sharia Industry Exclusions Index (via SPUS)',
            'as_of': '2026-07-23',
          },
        },
      });
      expect(r.ok, isTrue);
      expect(r.shariaVerdict, isNotNull);
      expect(r.shariaVerdict!.status, ShariaStatus.unknown);
      expect(r.shariaVerdict!.isBlocking, isFalse);
    });
  });
}

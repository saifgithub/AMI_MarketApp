/// CR267 (WP-24) - a Room handed back because the convene's inputs are
/// unchanged says so, plainly, and says it cost nothing.
///
///   1. the `done` frame's `banked` / `banked_at` reach the client (and a
///      backend that predates WP-24 sends neither: not banked, never guessed);
///   2. the notifier reads them off `done`;
///   3. the line renders the date in the user's locale, drops it when the
///      server gave none, and carries its semantics id.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:ami_trade/widgets/credits_line.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _ScriptedApiClient extends ApiClient {
  _ScriptedApiClient(this.events) : super(baseUrl: 'test://localhost');

  final List<Map<String, dynamic>> events;

  @override
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
    Map<String, dynamic>? alpaca,
  }) =>
      Stream.fromIterable(events);
}

class _NoopJournal extends JournalNotifier {
  _NoopJournal(super.ref);
  @override
  Future<void> refresh({
    JournalEntryType? filterType,
    String plan = 'trial_trader',
    String? q,
  }) async {}
}

class _NoopLessons extends LessonsNotifier {
  _NoopLessons(super.ref);
  @override
  Future<void> refresh() async {}
}

Future<RoomState> _runToDone(Map<String, dynamic> done) async {
  SharedPreferences.setMockInitialValues({});
  const ticker = 'AAPL';
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(_ScriptedApiClient([
        {'kind': 'done', 'run_id': 'r1', ...done},
      ])),
      journalNotifierProvider.overrideWith((ref) => _NoopJournal(ref)),
      lessonsNotifierProvider.overrideWith((ref) => _NoopLessons(ref)),
    ],
  );
  addTearDown(container.dispose);
  final sub = container.listen(
    roomNotifierProvider(ticker),
    (_, __) {},
    fireImmediately: true,
  );
  addTearDown(sub.close);
  await container.read(roomNotifierProvider(ticker).notifier).start();
  return sub.read();
}

Widget _host(Widget child, {Locale locale = const Locale('en')}) => MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: child),
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('done frame', () {
    test('banked and banked_at are forwarded', () {
      final parsed = parseRoomSseEvent(
        'done',
        '{"run_id": "r", "credit_cost": 0, "banked": true, '
            '"banked_at": "2026-11-20T09:00:00+00:00", "refunded": false}',
      );
      expect(parsed!['banked'], true);
      expect(parsed['banked_at'], '2026-11-20T09:00:00+00:00');
      expect(parsed['credit_cost'], 0);
    });

    test('a backend that predates WP-24 sends neither key', () {
      final parsed = parseRoomSseEvent('done', '{"run_id": "r"}');
      expect(parsed!.containsKey('banked'), isFalse);
      expect(parsed.containsKey('banked_at'), isFalse);
    });
  });

  group('notifier', () {
    test('a banked done is read off the frame', () async {
      final s = await _runToDone({
        'credit_cost': 0,
        'banked': true,
        'banked_at': '2026-11-20T09:00:00+00:00',
      });
      expect(s.done, isTrue);
      expect(s.banked, isTrue);
      expect(s.bankedAt, isNotNull);
      expect(s.creditCost, 0);
    });

    test('an ordinary done is not banked', () async {
      final s = await _runToDone({'credit_cost': 8, 'refunded': false});
      expect(s.banked, isFalse);
      expect(s.bankedAt, isNull);
    });

    test('a malformed banked_at is no date, not a crash', () async {
      final s = await _runToDone({'banked': true, 'banked_at': 'yesterday-ish'});
      expect(s.banked, isTrue);
      expect(s.bankedAt, isNull);
    });
  });

  group('RoomBankedLine', () {
    testWidgets('states the date and that no credits were used', (t) async {
      await t.pumpWidget(_host(
        RoomBankedLine(bankedAt: DateTime(2026, 11, 20, 9)),
      ));
      expect(
        find.text('Inputs unchanged since your last run on Nov 20, 2026 '
            '— showing that Room. No credits used.'),
        findsOneWidget,
      );
      expect(find.bySemanticsIdentifier(RoomBankIds.bankedLine), findsOneWidget);
    });

    testWidgets('drops the date when the server gave none', (t) async {
      await t.pumpWidget(_host(const RoomBankedLine(bankedAt: null)));
      expect(
        find.text('Inputs unchanged since your last run — showing that Room. '
            'No credits used.'),
        findsOneWidget,
      );
    });
  });
}

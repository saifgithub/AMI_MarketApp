// DEF478 — hardcoded English across Settings, the trade ticket, the Portfolio
// Alpaca relink prompt, the Q&A library, the bug sheet and the glossary sheet,
// plus "NO AI VERDICT" breaking the AMI naming rule ("never say 'the AI'
// anywhere a user might read", CLAUDE.md).
//
// Three layers:
//   1. a source guard: no user-visible string literal in `lib/` says "AI";
//   2. each surface renders in Arabic with its English wording absent;
//   3. the trade ticket's no-verdict advisory is AMI-voiced in English.

import 'dart:io';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/coach/ai_coach_screen.dart';
import 'package:ami_trade/screens/feedback/bug_report_sheet.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/me_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _Api extends ApiClient {
  _Api() : super(baseUrl: 'test://localhost');
}

class _ClaimedAuthNotifier extends AuthNotifier {
  _ClaimedAuthNotifier(super.ref) {
    state = AuthState(
      user: AuthUser(
        id: 'u1',
        email: 'trader@example.com',
        isAnonymous: false,
        createdAt: DateTime.utc(2026, 1, 1),
      ),
      token: 'tok',
    );
  }

  @override
  Future<void> bootstrap() async {}
}

class _NoopSimNotifier extends SimNotifier {
  _NoopSimNotifier(super.ref);
  @override
  Future<void> refresh() async {}
}

class _FixedSimNotifier extends SimNotifier {
  _FixedSimNotifier(super.ref, SimState fixed) {
    state = fixed;
  }
}

class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref) {
    state = MandateState(
      mandate: UserMandate.fromJson({
        'user_id': 'u1',
        'plan': 'trial_trader',
        'display_name': 'Trader',
      }),
    );
  }

  @override
  Future<void> refresh() async {}
}

SimPortfolio _portfolio() => SimPortfolio.fromJson({
      'user_id': 'u',
      'portfolio_id': 'p',
      'starting_capital': 10000,
      'current_cash': 10000,
      'holdings': const [],
      'total_value': 10000,
      'drawdown_pct': 0,
      'price_source': 'yfinance',
      'cash_committed': 0,
      'cash_available': 10000,
      'resting_order_count': 0,
      'shares_committed': const {},
      'shorts': const [],
      'closed_shorts': const [],
    });

MaterialApp _app(Locale locale, Widget home) => MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: home,
    );

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 6; i++) {
    await t.pump(const Duration(milliseconds: 80));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
  });

  test('no user-visible string literal in lib/ says "AI"', () {
    final literal = RegExp(r"""(?:'[^'\n]*\bAI\b[^'\n]*'|"[^"\n]*\bAI\b[^"\n]*")""");
    final offenders = <String>[];
    for (final f in Directory('lib')
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))) {
      final rel = f.path.replaceAll('\\', '/');
      if (rel.contains('/generated/')) continue;
      var n = 0;
      for (final line in f.readAsLinesSync()) {
        n++;
        final t = line.trimLeft();
        if (t.startsWith('//') || t.startsWith('///')) continue;
        if (t.contains('debugPrint(')) continue;
        if (literal.hasMatch(line)) offenders.add('$rel:$n  ${line.trim()}');
      }
    }
    expect(offenders, isEmpty,
        reason: 'user copy names the assistant AMI, never "the AI" (CLAUDE.md)');
  });

  testWidgets('trade ticket no-verdict advisory is AMI-voiced (en)',
      (t) async {
    await t.binding.setSurfaceSize(const Size(390, 1600));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(ProviderScope(
      overrides: [
        simNotifierProvider.overrideWith(
            (ref) => _FixedSimNotifier(ref, SimState(portfolio: _portfolio()))),
        alpacaLinkedProvider.overrideWith((ref) async => true),
      ],
      child: _app(const Locale('en'), const TradeTicketSheet(tickerPrefill: 'AAPL')),
    ));
    await _settle(t);

    expect(find.text('NO AMI VERDICT'), findsOneWidget);
    expect(find.text('NO AI VERDICT'), findsNothing);
    expect(find.textContaining(RegExp(r'\bAI\b')), findsNothing);
  });

  testWidgets('trade ticket advisory + destination picker render in Arabic',
      (t) async {
    await t.binding.setSurfaceSize(const Size(390, 1600));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(ProviderScope(
      overrides: [
        simNotifierProvider.overrideWith(
            (ref) => _FixedSimNotifier(ref, SimState(portfolio: _portfolio()))),
        alpacaLinkedProvider.overrideWith((ref) async => true),
      ],
      child: _app(const Locale('ar'), const TradeTicketSheet(tickerPrefill: 'AAPL')),
    ));
    await _settle(t);
    final l = await AppLocalizations.delegate.load(const Locale('ar'));

    for (final english in [
      'NO AMI VERDICT',
      'Convene the Room',
      'Proceed without',
      'DESTINATION',
      'AMI SIM',
      'BOTH',
    ]) {
      expect(find.text(english), findsNothing, reason: '"$english" is English in ar');
    }
    expect(find.text(l.tradeTicketNoVerdictTitle), findsOneWidget);
    expect(find.text(l.tradeTicketDestinationLabel), findsOneWidget);
    expect(find.text(l.tradeTicketDestAmiSim), findsOneWidget);
    expect(find.text(l.tradeTicketDestBoth), findsOneWidget);
  });

  testWidgets('Q&A library and bug sheet render in Arabic', (t) async {
    await t.pumpWidget(ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(_Api())],
      child: _app(const Locale('ar'), const AICoachScreen()),
    ));
    await _settle(t);
    final l = await AppLocalizations.delegate.load(const Locale('ar'));
    expect(find.text('AI Coach'), findsNothing);
    expect(find.text(l.aiCoachTitle), findsOneWidget);

    await t.pumpWidget(ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(_Api())],
      child: _app(
        const Locale('ar'),
        Scaffold(
          body: Consumer(
            builder: (context, ref, _) => ElevatedButton(
              onPressed: () => showBugReportSheet(context, ref),
              child: const Text('x'),
            ),
          ),
        ),
      ),
    ));
    await t.tap(find.text('x'));
    await _settle(t);
    for (final english in [
      'Report a bug',
      'UI glitch',
      'Wrong data',
      'Slow / freeze',
      'Feature request',
      'Short description',
      'Send report',
      'Attach photo',
    ]) {
      expect(find.text(english), findsNothing, reason: '"$english" is English in ar');
    }
    expect(find.text(l.bugSheetTitle), findsOneWidget);
    expect(find.text(l.bugSheetCatUiGlitch), findsOneWidget);
    expect(find.text(l.bugSheetAttachPhoto), findsOneWidget);
  });

  testWidgets('Settings chrome and the Alpaca row render in Arabic',
      (t) async {
    await AlpacaCredentialStore.save('PKKEY', 'secret',
        baseUrl: kDefaultAlpacaBaseUrl);
    const size = Size(390, 900);
    t.view.physicalSize = size;
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);
    await t.pumpWidget(ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith((ref) => _FixedMandateNotifier(ref)),
        simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
        authNotifierProvider.overrideWith((ref) => _ClaimedAuthNotifier(ref)),
        myHandleProvider.overrideWith((ref) async => null),
        apiClientProvider.overrideWithValue(_Api()),
      ],
      child: MediaQuery(
        data: const MediaQueryData(size: size),
        child: _app(const Locale('ar'), const SettingsScreen()),
      ),
    ));
    await _settle(t);
    final l = await AppLocalizations.delegate.load(const Locale('ar'));

    final scrollable = find.byType(Scrollable).first;
    for (final heading in [
      l.settingsSectionAppearance,
      l.settingsSectionHelp,
      l.settingsSectionConnectedAccounts,
    ]) {
      await t.scrollUntilVisible(find.text(heading), 300, scrollable: scrollable);
    }
    await _settle(t);
    await t.scrollUntilVisible(find.text(l.settingsAlpacaDisconnect), 300,
        scrollable: scrollable);
    expect(find.text('APPEARANCE'), findsNothing);
    expect(find.text('HELP'), findsNothing);
    expect(find.text('CONNECTED ACCOUNTS'), findsNothing);
    expect(find.text('Disconnect'), findsNothing);
    expect(find.text('Connected'), findsNothing);
    expect(find.text('AI Coach — Q&A library'), findsNothing);
    expect(find.text(l.settingsAlpacaDisconnect), findsOneWidget);
    expect(find.text(l.settingsAlpacaConnected), findsOneWidget);
    expect(find.text(l.settingsHelpQaLibrary), findsOneWidget);
    expect(find.textContaining(RegExp(r'\bAI\b')), findsNothing);
  });
}

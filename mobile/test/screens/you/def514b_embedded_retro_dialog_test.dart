/// DEF514 device re-check (AMI-DL-12, build 122): the retro-tightening dialog
/// must appear within seconds of saving a cap from SETTINGS embedded in the
/// YOU tab of the real `HomeShell` (the path testers use), through the REAL
/// notifiers and the real `ApiClient` over a scripted transport serving the
/// audit payload Alpha returned (NFLX 46.52% against a 3% single-name cap).
/// The transport makes the portfolio reload take 10 s, as it did on Alpha:
/// the dialog used to queue behind it, so a tester looking at 0.3 / 1.5 /
/// 3.5 s saw no disclosure.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/settings/risk_limits_section.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/screens/home_shell.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:ami_trade/screens/you/insights_providers.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/me_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _uid = '11111111-1111-1111-1111-111111111111';

Map<String, dynamic> _mandateJson(int version, double? cap) => {
      'user_id': _uid,
      'version': version,
      'display_name': 'Trader',
      'locale': 'en',
      'timezone': 'UTC',
      'primary_goal': 'long_term_wealth',
      'horizon': 'long',
      'path': 'long_horizon',
      'risk_score': 3,
      'risk_components': {
        'drawdown_response': 3,
        'regret_asymmetry': 0,
        'concentration_tolerance': 3,
      },
      'max_drawdown_pct': 30,
      'single_name_cap_pct': cap,
      'learning_style': 'quick',
      'compliance': <String, dynamic>{},
      'plan': 'trial_trader',
      'credit_balance': 75,
    };

const Map<String, dynamic> _alphaAudit = {
  'passed': false,
  'mandate_version': 17,
  'portfolio_value': 100000.0,
  'current_drawdown_pct': 0.0,
  'drawdown_breach': false,
  'max_open_positions_breach': false,
  'max_open_risk_pct_breach': false,
  'single_name_cap_breach': true,
  'single_name_cap_pct': 3.0,
  'single_name_breaches': [
    {
      'name': 'NFLX',
      'weight_pct': 46.52,
      'tickers': ['NFLX']
    }
  ],
  'sector_cap_breach': false,
  'sector_cap_pct': 100.0,
  'sector_breaches': [],
  'violations': [
    {
      'ticker': 'NFLX',
      'quantity': 40.0,
      'market_value': 46520.0,
      'weight_pct': 46.52,
      'issues': ['position size 46.5% exceeds single-name cap 3.0%']
    }
  ],
};

class _Transport implements HttpClientAdapter {
  final List<String> calls = [];
  int version = 16;
  double? cap;

  Object _body(RequestOptions o) {
    final p = o.path;
    if (p.endsWith('/audit')) return _alphaAudit;
    if (p.startsWith('/v1/mandate/')) {
      if (o.method == 'PATCH') {
        version++;
        cap = ((o.data as Map)['single_name_cap_pct'] as num?)?.toDouble() ?? cap;
      }
      return _mandateJson(version, cap);
    }
    if (p.contains('/portfolio')) {
      return {'cash': 100000.0, 'holdings': [], 'total_value': 100000.0};
    }
    return <String, dynamic>{};
  }

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    calls.add('${options.method} ${options.path}');
    // Alpha, 2026-11-21: the portfolio reload re-quotes the whole book and
    // took 10-20 s between the PATCH and the audit being asked.
    if (options.path.contains('/sim/') && options.method == 'POST') {
      await Future<void>.delayed(const Duration(seconds: 10));
    }
    if (options.method == 'PATCH' && options.data is! Map) {
      throw StateError('PATCH body was not a map: ${options.data}');
    }
    final body = _body(options);
    return ResponseBody.fromString(jsonEncode(body), 200, headers: {
      Headers.contentTypeHeader: ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  testWidgets(
      'DEF514b: single-name cap saved from SETTINGS embedded in YOU shows the '
      'retro dialog naming NFLX', (tester) async {
    SharedPreferences.setMockInitialValues({
      'ami.device_user_id': _uid,
      'tour_floor_seen': true,
      'tour_portfolio_seen': true,
      'tour_journal_seen': true,
      'tour_lessons_seen': true,
      'tour_you_seen': true,
      'tour_nav_v2_seen': true,
    });
    DeviceUser.resetCacheForTest();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    final transport = _Transport();
    final api = ApiClient(baseUrl: 'http://x', dioAdapter: transport);

    await tester.pumpWidget(ProviderScope(
      overrides: [
        insightsProvider
            .overrideWith((ref) async => const InsightsData(entryCount: 0)),
        authNotifierProvider.overrideWith((ref) => _FixedAuthNotifier(ref)),
        myHandleProvider.overrideWith(
            (ref) async => throw Exception('no network in test')),
        apiClientProvider.overrideWithValue(api),
      ],
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const HomeShell(),
      ),
    ));
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    final l = AppLocalizations.of(tester.element(find.byType(HomeShell)));
    final container = ProviderScope.containerOf(tester.element(find.byType(HomeShell)));
    container.read(activeTabProvider.notifier).state = AmiTab.you;
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }

    final expand = find.text(l.settingsRiskLimitsExpand);
    await tester.scrollUntilVisible(expand, 300,
        scrollable: find.descendant(of: find.byType(SettingsScreen), matching: find.byType(Scrollable)).first);
    await tester.tap(expand);
    await tester.pump();
    final field = find.byKey(const Key('riskLimitField_single_name_cap_pct'));
    await tester.scrollUntilVisible(field, 300,
        scrollable: find.descendant(of: find.byType(SettingsScreen), matching: find.byType(Scrollable)).first);
    await tester.enterText(field, '3');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.tap(find.text(l.settingsSave));
    // The tester's screenshots: 0.3 s, 1.5 s, 3.5 s after the tap.
    for (var i = 0; i < 70; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }

    expect(transport.calls.any((c) => c.startsWith('PATCH ')), isTrue);
    expect(transport.calls.any((c) => c.endsWith('/audit')), isTrue);
    expect(find.byType(RetroTighteningDialog), findsOneWidget,
        reason: 'the disclosure must not wait on the portfolio reload');
    expect(find.textContaining('NFLX 46.5%'), findsOneWidget);

    // Let the slow reload finish so no timer outlives the test.
    for (var i = 0; i < 260; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(tester.takeException(), isNull);
  });
}

class _FixedAuthNotifier extends AuthNotifier {
  _FixedAuthNotifier(super.ref);
  @override
  Future<void> bootstrap() async {}
}

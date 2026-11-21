/// DEF522: `MandateNotifier.patch` swallowed its own failure into
/// `state.error`, and `SettingsScreen._save` then cleared the dirty flag,
/// showed "Mandate updated" and ran the retro audit anyway — a failed save
/// (500, 422, network) told the user it saved and threw away their edit.
/// A failed PATCH must keep the edit, show the error, run no audit and leave
/// SAVE available; a retry that succeeds then behaves as before.
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
  int patchStatus = 500;
  bool failPatch = true;
  int version = 16;
  double? cap;

  int get auditCalls => calls.where((c) => c.endsWith('/audit')).length;
  int get patchCalls => calls.where((c) => c.startsWith('PATCH')).length;

  Object _body(RequestOptions o) {
    final p = o.path;
    if (p.endsWith('/audit')) return _alphaAudit;
    if (p.startsWith('/v1/mandate/')) {
      if (o.method == 'PATCH') {
        version++;
        cap = ((o.data as Map)['single_name_cap_pct'] as num?)?.toDouble() ??
            cap;
      }
      return _mandateJson(version, cap);
    }
    if (p.startsWith('/v1/journal/')) return {'entries': [], 'total': 0};
    if (p.contains('/portfolio')) {
      return {'cash': 100000.0, 'holdings': [], 'total_value': 100000.0};
    }
    return <String, dynamic>{};
  }

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    calls.add('${options.method} ${options.path}');
    var status = 200;
    Object body;
    if (options.method == 'PATCH' && failPatch) {
      status = patchStatus;
      body = {'detail': 'rejected'};
    } else {
      body = _body(options);
    }
    return ResponseBody.fromString(jsonEncode(body), status, headers: {
      Headers.contentTypeHeader: ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

Future<void> _run(WidgetTester tester, int failStatus) async {
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
  final transport = _Transport()..patchStatus = failStatus;
  final api = ApiClient(baseUrl: 'http://x', dioAdapter: transport);

  Future<void> advance(int ms) async {
    for (var i = 0; i < ms ~/ 50; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
  }

  await tester.pumpWidget(ProviderScope(
    overrides: [
      insightsProvider
          .overrideWith((ref) async => const InsightsData(entryCount: 0)),
      authNotifierProvider.overrideWith((ref) => _FixedAuthNotifier(ref)),
      myHandleProvider
          .overrideWith((ref) async => throw Exception('no network in test')),
      apiClientProvider.overrideWithValue(api),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: HomeShell(),
    ),
  ));
  await advance(1000);
  final l = AppLocalizations.of(tester.element(find.byType(HomeShell)));
  final container =
      ProviderScope.containerOf(tester.element(find.byType(HomeShell)));
  container.read(activeTabProvider.notifier).state = AmiTab.you;
  await advance(500);

  final scrollable = find
      .descendant(
          of: find.byType(SettingsScreen), matching: find.byType(Scrollable))
      .first;
  await tester.scrollUntilVisible(find.text(l.settingsRiskLimitsExpand), 300,
      scrollable: scrollable);
  await tester.tap(find.text(l.settingsRiskLimitsExpand));
  await tester.pump();
  final field = find.byKey(const Key('riskLimitField_single_name_cap_pct'));
  await tester.scrollUntilVisible(field, 300, scrollable: scrollable);
  await tester.enterText(field, '3');
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));

  // First attempt: the PATCH is rejected.
  await tester.tap(find.text(l.settingsSave));
  await advance(1500);

  expect(transport.patchCalls, 1);
  expect(find.text(l.settingsMandateUpdated), findsNothing,
      reason: 'a failed save must not claim "Mandate updated"');
  expect(transport.auditCalls, 0, reason: 'no audit after a failed save');
  expect(find.byType(RetroTighteningDialog), findsNothing);
  expect(find.textContaining("Couldn't save your mandate"), findsOneWidget,
      reason: 'the failure must be shown to the user');
  expect(find.text(l.settingsSave), findsOneWidget,
      reason: 'SAVE stays available to retry');
  expect(find.widgetWithText(TextField, '3'), findsOneWidget,
      reason: 'the user\'s pending edit must survive the failure');

  // Retry succeeds: everything behaves as a normal save.
  transport.failPatch = false;
  await tester.tap(find.text(l.settingsSave));
  await advance(1500);

  expect(transport.patchCalls, 2);
  expect(find.text(l.settingsSave), findsNothing);
  expect(transport.auditCalls, 1);
  expect(find.byType(RetroTighteningDialog), findsOneWidget);
  expect(tester.takeException(), isNull);
}

void main() {
  testWidgets('DEF522: a 500 on save keeps the edit, shows the error, no audit',
      (tester) => _run(tester, 500));
  testWidgets('DEF522: a 422 on save behaves the same way',
      (tester) => _run(tester, 422));
}

class _FixedAuthNotifier extends AuthNotifier {
  _FixedAuthNotifier(super.ref);
  @override
  Future<void> bootstrap() async {}
}

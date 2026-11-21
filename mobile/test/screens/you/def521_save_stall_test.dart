/// DEF521 device finding (AMI-DL-13, build 123): after SAVE of a single-name cap
/// in SETTINGS embedded in YOU, the keyboard stayed up and SAVE stayed shown
/// for ~17 s with NO request reaching the server, then the retro dialog came.
/// Cause: `MandateNotifier.patch` awaited the journal re-read (and `_save`
/// awaited `patch`) before clearing the dirty flag, dismissing the keyboard and
/// asking for the audit — so a slow journal download (100 full-payload rows,
/// several concurrent copies) gated the disclosure.
///
/// Here the journal list takes 17 s to arrive. The audit must still be asked
/// within 1 s (fake time) of the PATCH completing, the header must leave the
/// SAVE state, and the keyboard must be dismissed.
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


int _elapsedMs = 0;

Map<String, dynamic> _journalRow(int i) => {
      'id': 'e$i',
      'user_id': _uid,
      'entry_type': 'room_run',
      'title': 'Run $i',
      'created_at': '2026-11-20T10:00:00Z',
      'payload': {'blob': List.filled(50, 'x' * 200)},
    };

class _Transport implements HttpClientAdapter {
  final List<String> calls = [];
  int? patchDoneMs;
  int? auditAskedMs;
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
    if (p.startsWith('/v1/journal/')) {
      return {
        'entries': [for (var i = 0; i < 5; i++) _journalRow(i)],
        'total': 5,
      };
    }
    if (p.contains('/portfolio')) {
      return {'cash': 100000.0, 'holdings': [], 'total_value': 100000.0};
    }
    return <String, dynamic>{};
  }

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    calls.add('${options.method} ${options.path} @${_elapsedMs}ms');
    if (options.path.endsWith('/audit')) auditAskedMs ??= _elapsedMs;
    // Alpha, 2026-11-21: the journal list took ~17 s to reach the phone.
    if (options.path.startsWith('/v1/journal/') &&
        options.method == 'GET' &&
        patchDoneMs != null) {
      await Future<void>.delayed(const Duration(seconds: 17));
    }
    if (options.method == 'PATCH' && options.data is! Map) {
      throw StateError('PATCH body was not a map: ${options.data}');
    }
    final body = _body(options);
    if (options.method == 'PATCH') patchDoneMs = _elapsedMs;
    return ResponseBody.fromString(jsonEncode(body), 200, headers: {
      Headers.contentTypeHeader: ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  testWidgets(
      'DEF521: a slow journal re-read must not delay the audit, the SAVE state '
      'or the keyboard', (tester) async {
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
    _elapsedMs = 0;
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    final transport = _Transport();
    final api = ApiClient(baseUrl: 'http://x', dioAdapter: transport);

    Future<void> advance(int ms) async {
      for (var i = 0; i < ms ~/ 50; i++) {
        await tester.pump(const Duration(milliseconds: 50));
        _elapsedMs += 50;
      }
    }

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
    final expand = find.text(l.settingsRiskLimitsExpand);
    await tester.scrollUntilVisible(expand, 300, scrollable: scrollable);
    await tester.tap(expand);
    await tester.pump();
    final field = find.byKey(const Key('riskLimitField_single_name_cap_pct'));
    await tester.scrollUntilVisible(field, 300, scrollable: scrollable);
    await tester.enterText(field, '3');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(FocusManager.instance.primaryFocus, isNotNull,
        reason: 'precondition: the cap field holds focus');
    _elapsedMs = 0;
    await tester.tap(find.text(l.settingsSave));
    await advance(1000);

    expect(transport.patchDoneMs, isNotNull, reason: 'PATCH went out');
    expect(transport.auditAskedMs, isNotNull,
        reason: 'the audit was not asked within 1 s of the PATCH while the '
            'journal re-read was still in flight; calls=${transport.calls}');
    expect(transport.auditAskedMs! - transport.patchDoneMs!, lessThan(1000));
    expect(find.byType(RetroTighteningDialog), findsOneWidget);
    expect(find.text(l.settingsSave), findsNothing,
        reason: 'the header must leave the SAVE state once the PATCH landed');
    expect(FocusManager.instance.primaryFocus?.context?.widget is EditableText,
        isFalse,
        reason: 'the keyboard must be dismissed after SAVE');
    // Drain the slow journal reads so no timer outlives the test.
    await advance(20000);
    expect(tester.takeException(), isNull);
  });
}

class _FixedAuthNotifier extends AuthNotifier {
  _FixedAuthNotifier(super.ref);
  @override
  Future<void> bootstrap() async {}
}

/// CR276 (CR267 WP-30) — Settings > Delete account and Export my data, and the
/// restore offer when a sign-in matches an account scheduled for deletion.
///
/// Driven through the real `SettingsScreen`. Deletion goes through the DEF479
/// confirm: tapping it asks first and calls NOTHING until confirmed. The dialog
/// has to say what is deleted, what is kept and for how long, and the restore
/// window; and its wording is "delete" in Beta, "close" only when the server
/// reports archive mode.
library;

import 'dart:typed_data';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/account.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/account_providers.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/me_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _Api extends ApiClient {
  _Api() : super(baseUrl: 'test://localhost');

  int closeCalls = 0;
  int exportCalls = 0;
  bool closeFails = false;
  bool exportFails = false;

  @override
  Future<AccountClosure> closeAccount() async {
    closeCalls++;
    if (closeFails) throw Exception('network');
    return AccountClosure(
        restorableUntil: DateTime.utc(2026, 12, 18), graceDays: 30);
  }

  @override
  Future<Uint8List> exportAccountData() async {
    exportCalls++;
    if (exportFails) throw Exception('network');
    return Uint8List.fromList([123, 125]);
  }

  @override
  Future<void> alpacaReportLinkState(bool linked) async {}
}

class _AuthNotifier extends AuthNotifier {
  _AuthNotifier(super.ref, this.log, {required bool claimed}) {
    state = AuthState(
      user: AuthUser(
        id: 'u1',
        email: claimed ? 'trader@example.com' : null,
        isAnonymous: !claimed,
        createdAt: DateTime.utc(2026, 1, 1),
      ),
      token: 'tok',
    );
  }

  final List<String> log;

  @override
  Future<void> bootstrap() async {}

  @override
  Future<void> signOut() async {
    log.add('signOut');
  }
}

class _NoopSimNotifier extends SimNotifier {
  _NoopSimNotifier(super.ref);
  @override
  Future<void> refresh() async {}
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

Future<void> _pump(
  WidgetTester tester,
  _Api api,
  List<String> log, {
  bool claimed = true,
  AccountPolicy policy = AccountPolicy.fallback,
  List<(Uint8List, String)>? shared,
}) async {
  const size = Size(390, 900);
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith((ref) => _FixedMandateNotifier(ref)),
        simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
        authNotifierProvider
            .overrideWith((ref) => _AuthNotifier(ref, log, claimed: claimed)),
        myHandleProvider.overrideWith((ref) async => 'OLDHANDLE'),
        apiClientProvider.overrideWithValue(api),
        accountPolicyProvider.overrideWith((ref) async => policy),
        accountExportSinkProvider.overrideWithValue((bytes, name) async {
          shared?.add((bytes, name));
        }),
      ],
      child: const MediaQuery(
        data: MediaQueryData(size: size),
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: SettingsScreen(),
        ),
      ),
    ),
  );
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

Future<void> _scrollTo(WidgetTester tester, Finder target) async {
  await tester.scrollUntilVisible(target, 300,
      scrollable: find.byType(Scrollable).first);
  await tester.pump(const Duration(milliseconds: 50));
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _Api api;
  late List<String> log;

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
    api = _Api();
    log = [];
  });

  group('Delete account', () {
    testWidgets('asks first, in plain words; CANCEL changes nothing',
        (tester) async {
      await _pump(tester, api, log);
      await _scrollTo(tester, find.text('Delete account'));

      await tester.tap(find.text('Delete account'));
      await _settle(tester);

      expect(find.text('DELETE ACCOUNT?'), findsOneWidget);
      final body = tester
          .widget<Text>(find.textContaining('This deletes your AMI account'))
          .data!;
      expect(body, contains('mandate, journal, trades'));
      expect(body, contains('For 30 days you can restore it'));
      expect(body, contains('permanently deleted'));
      expect(body, contains('Kept:'));
      expect(body, contains('7 years'));
      expect(body, isNot(contains('the AI')));
      expect(api.closeCalls, 0, reason: 'nothing is sent while the dialog is open');

      await tester.tap(find.text('CANCEL'));
      await _settle(tester);
      expect(api.closeCalls, 0);
      expect(log, isEmpty);
    });

    testWidgets('confirming closes the account, signs out, and says when it can be restored',
        (tester) async {
      await _pump(tester, api, log);
      await _scrollTo(tester, find.text('Delete account'));

      await tester.tap(find.text('Delete account'));
      await _settle(tester);
      await tester.tap(find.text('DELETE ACCOUNT'));
      await _settle(tester);

      expect(api.closeCalls, 1);
      expect(log, ['signOut']);
      expect(find.textContaining('scheduled for deletion'), findsOneWidget);
    });

    testWidgets('a failed close keeps the user signed in and says so',
        (tester) async {
      api.closeFails = true;
      await _pump(tester, api, log);
      await _scrollTo(tester, find.text('Delete account'));

      await tester.tap(find.text('Delete account'));
      await _settle(tester);
      await tester.tap(find.text('DELETE ACCOUNT'));
      await _settle(tester);

      expect(api.closeCalls, 1);
      expect(log, isEmpty, reason: 'still signed in; nothing was deleted');
      expect(find.textContaining("Couldn't delete your account"), findsOneWidget);
    });

    testWidgets('a guest account is told it cannot be restored later',
        (tester) async {
      await _pump(tester, api, log, claimed: false);
      await _scrollTo(tester, find.text('Delete account'));

      await tester.tap(find.text('Delete account'));
      await _settle(tester);

      expect(find.textContaining('cannot be restored later'), findsOneWidget);
    });

    testWidgets('the wording becomes "close" only when the server runs archive',
        (tester) async {
      await _pump(tester, api, log,
          policy: const AccountPolicy(
              mode: 'archive', wording: 'close', graceDays: 30));
      await _scrollTo(tester, find.text('Close account'));

      expect(find.text('Delete account'), findsNothing);
      await tester.tap(find.text('Close account'));
      await _settle(tester);
      expect(find.text('CLOSE ACCOUNT?'), findsOneWidget);
      expect(find.textContaining('closed archive'), findsOneWidget);
    });

    testWidgets('a different grace period from the server shows in the dialog',
        (tester) async {
      await _pump(tester, api, log,
          policy: const AccountPolicy(
              mode: 'delete', wording: 'delete', graceDays: 14));
      await _scrollTo(tester, find.text('Delete account'));
      await tester.tap(find.text('Delete account'));
      await _settle(tester);
      expect(find.textContaining('For 14 days you can restore it'), findsOneWidget);
    });
  });

  group('Export my data', () {
    testWidgets('downloads then hands the file to the share step',
        (tester) async {
      final shared = <(Uint8List, String)>[];
      await _pump(tester, api, log, shared: shared);
      await _scrollTo(tester, find.text('Export my data'));

      await tester.tap(find.text('Export my data'));
      await _settle(tester);
      await tester.tap(find.text('Share'));
      await _settle(tester);

      expect(api.exportCalls, 1);
      expect(shared, hasLength(1));
      expect(shared.single.$1, [123, 125]);
      expect(shared.single.$2,
          matches(RegExp(r'^ami-data-export-\d{4}-\d{2}-\d{2}\.json$')));
    });

    testWidgets('a failed export says so and shares nothing', (tester) async {
      api.exportFails = true;
      final shared = <(Uint8List, String)>[];
      await _pump(tester, api, log, shared: shared);
      await _scrollTo(tester, find.text('Export my data'));

      await tester.tap(find.text('Export my data'));
      await _settle(tester);

      expect(shared, isEmpty);
      expect(find.textContaining("Couldn't export your data"), findsOneWidget);
    });
  });

  group('Export my data - save to device (DEF524)', () {
    final calls = <MethodCall>[];
    late Object? Function(MethodCall) reply;

    setUp(() {
      calls.clear();
      reply = (c) => 'ami-data-export-2026-11-21.json';
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(accountExportSaveChannel, (c) async {
        calls.add(c);
        return reply(c);
      });
    });
    tearDown(() {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(accountExportSaveChannel, null);
    });

    Future<void> openSheet(WidgetTester tester,
        {List<(Uint8List, String)>? shared}) async {
      await _pump(tester, api, log, shared: shared);
      await _scrollTo(tester, find.text('Export my data'));
      await tester.tap(find.text('Export my data'));
      await _settle(tester);
    }

    testWidgets('offers both Save to device and Share', (tester) async {
      await openSheet(tester);
      expect(find.text('Save to device'), findsOneWidget);
      expect(find.text('Share'), findsOneWidget);
    });

    testWidgets('Save calls the channel with name, mime and bytes and says Saved',
        (tester) async {
      final shared = <(Uint8List, String)>[];
      await openSheet(tester, shared: shared);
      await tester.tap(find.text('Save to device'));
      await _settle(tester);

      expect(calls, hasLength(1));
      expect(calls.single.method, 'saveFile');
      final args = calls.single.arguments as Map;
      expect(args['mime'], 'application/json');
      expect(args['name'],
          matches(RegExp(r'^ami-data-export-\d{4}-\d{2}-\d{2}\.json$')));
      expect(args['bytes'], [123, 125]);
      expect(find.text('Saved ami-data-export-2026-11-21.json'),
          findsOneWidget);
      expect(shared, isEmpty);
    });

    testWidgets('a failed write shows an error, not Saved', (tester) async {
      reply = (c) => throw PlatformException(code: 'write_failed');
      await openSheet(tester);
      await tester.tap(find.text('Save to device'));
      await _settle(tester);

      expect(find.textContaining("Couldn't save the file"), findsOneWidget);
      expect(find.textContaining('Saved '), findsNothing);
    });

    testWidgets('cancelling the Save dialog shows nothing', (tester) async {
      reply = (c) => null;
      await openSheet(tester);
      await tester.tap(find.text('Save to device'));
      await _settle(tester);

      expect(calls, hasLength(1));
      expect(find.byType(SnackBar), findsNothing);
    });

    testWidgets('dismissing the sheet saves and shares nothing',
        (tester) async {
      final shared = <(Uint8List, String)>[];
      await openSheet(tester, shared: shared);
      await tester.tapAt(const Offset(5, 5));
      await _settle(tester);

      expect(calls, isEmpty);
      expect(shared, isEmpty);
      expect(find.byType(SnackBar), findsNothing);
    });

    testWidgets('iOS goes straight to the share sheet', (tester) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
      final shared = <(Uint8List, String)>[];
      await openSheet(tester, shared: shared);

      debugDefaultTargetPlatformOverride = null;

      expect(find.text('Save to device'), findsNothing);
      expect(shared, hasLength(1));
      expect(calls, isEmpty);
    });
  });

  group('restore offer', () {
    test('reads the 409 account_pending_deletion body', () {
      final err = AccountPendingDeletion.fromResponse(409, {
        'detail': {
          'code': 'account_pending_deletion',
          'restorable_until': '2026-12-18T00:00:00+00:00',
        },
      });
      expect(err, isNotNull);
      expect(err!.restorableUntil.toUtc(), DateTime.utc(2026, 12, 18));
    });

    test('ignores every other error', () {
      expect(AccountPendingDeletion.fromResponse(403, {'detail': {'code': 'account_closed'}}),
          isNull);
      expect(AccountPendingDeletion.fromResponse(409, {'detail': 'conflict'}), isNull);
      expect(AccountPendingDeletion.fromResponse(409, null), isNull);
    });

    test('a 409 from sign-in becomes a restore offer, not an error', () async {
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(_PendingApi()),
        authNotifierProvider.overrideWith((ref) => _AuthNotifier(ref, [], claimed: false)),
      ]);
      addTearDown(container.dispose);
      final out = await container
          .read(authNotifierProvider.notifier)
          .signInWithGoogle('id-token');
      expect(out.success, isFalse);
      expect(out.restorableUntil, isNotNull);
      expect(container.read(authNotifierProvider).error, isNull);
    });
  });
}

class _PendingApi extends ApiClient {
  _PendingApi() : super(baseUrl: 'test://localhost');

  @override
  Future<AuthVerifyResponse> signInWithGoogle({
    required String identityToken,
    String? userId,
    String? onboardingSessionId,
    bool restoreAccount = false,
  }) async {
    final req = RequestOptions(path: '/v1/auth/google');
    throw DioException(
      requestOptions: req,
      response: Response(
        requestOptions: req,
        statusCode: 409,
        data: {
          'detail': {
            'code': 'account_pending_deletion',
            'restorable_until': '2026-12-18T00:00:00+00:00',
          },
        },
      ),
      type: DioExceptionType.badResponse,
    );
  }
}

/// DEF430 — the `open_privacy_policy` deep link, ridden by the one-time
/// Privacy Policy v2.1 notification's row (`backend/app/services/
/// policy_notice.py`) and tappable from the notification centre
/// (`NotificationCentreScreen` already routes taps through this exact
/// dispatcher — CR027's "one route table" lock).
///
/// `privacyPolicyUrlFromParams` is asserted directly as a pure function —
/// the same "extracted decision function" convention
/// `alpaca_client_paper_only_test.dart` uses for `isAlpacaPaperHost` — so
/// the URL resolution is pinned independent of pushing (and thereby
/// constructing) the real `LegalScreen`/`WebViewController`, which asserts
/// in this test binary without a registered `WebViewPlatform.instance` (no
/// test in this codebase mocks that channel today).
///
/// `dispatch` itself is then driven end-to-end against a minimal `Navigator`
/// to prove the route is actually wired into `DeepLinkDispatcher`'s table —
/// a `NavigatorObserver` captures the pushed route's `RouteSettings`-free
/// identity is enough to show `dispatch` returned `handled` rather than
/// `unknownRoute`, without needing the pushed page to fully build.
library;

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/nav/home_shell_navigation.dart';
import 'package:ami_trade/services/notifications/deep_link_dispatcher.dart';
import 'package:ami_trade/services/notifications/notification_models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('privacyPolicyUrlFromParams', () {
    test('uses the server-supplied url', () {
      expect(
        privacyPolicyUrlFromParams(
            const {'url': 'https://www.agenticmarketintel.ai/privacy/'}),
        'https://www.agenticmarketintel.ai/privacy/',
      );
    });

    test('a future url change is a server-side edit — any https url passes '
        'through verbatim', () {
      expect(
        privacyPolicyUrlFromParams(
            const {'url': 'https://www.agenticmarketintel.ai/privacy/v3/'}),
        'https://www.agenticmarketintel.ai/privacy/v3/',
      );
    });

    test('a missing url param falls back to the public Privacy Policy',
        () {
      expect(
        privacyPolicyUrlFromParams(const {}),
        contains('agenticmarketintel.ai/privacy'),
      );
    });

    test('a non-String url param falls back rather than throwing', () {
      expect(
        privacyPolicyUrlFromParams(const {'url': 7}),
        contains('agenticmarketintel.ai/privacy'),
      );
    });
  });

  group('DeepLinkDispatcher — open_privacy_policy is wired into the table',
      () {
    testWidgets('dispatch resolves it (not unknownRoute) and pushes exactly '
        'one route', (t) async {
      final navKey = GlobalKey<NavigatorState>();
      var pushCount = 0;
      final container = ProviderContainer(overrides: [
        homeShellNavKeysProvider.overrideWith((ref) => {AmiTab.you: navKey}),
      ]);
      addTearDown(container.dispose);

      await t.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Navigator(
              key: navKey,
              observers: [
                _CountingObserver(onPush: () => pushCount++),
              ],
              onGenerateRoute: (_) => MaterialPageRoute<void>(
                builder: (_) => const Scaffold(body: Text('home')),
              ),
            ),
          ),
        ),
      );
      await t.pump();
      final pushesBeforeDispatch = pushCount;

      final result = DeepLinkDispatcher.dispatch(
        _FakeRef(container),
        const DeepLink(
          route: 'open_privacy_policy',
          params: {'url': 'https://www.agenticmarketintel.ai/privacy/'},
        ),
      );

      expect(result, DeepLinkDispatchResult.handled,
          reason: 'the route must be in the table, not fall through to '
              'unknownRoute');
      expect(pushCount, pushesBeforeDispatch + 1,
          reason: 'dispatch must push exactly one page for this route');
      // The push itself constructs LegalScreen -> WebViewController, which
      // throws in this test binary (see file header) — draining it keeps
      // the test from being reported as an unexpected failure.
      t.takeException();
    });

    testWidgets('an unrelated tab\'s navigator receives no push', (t) async {
      final youKey = GlobalKey<NavigatorState>();
      final floorKey = GlobalKey<NavigatorState>();
      var floorPushCount = 0;
      final container = ProviderContainer(overrides: [
        homeShellNavKeysProvider.overrideWith(
            (ref) => {AmiTab.you: youKey, AmiTab.floor: floorKey}),
      ]);
      addTearDown(container.dispose);

      await t.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Row(
              textDirection: TextDirection.ltr,
              children: [
                Expanded(
                  child: Navigator(
                    key: youKey,
                    onGenerateRoute: (_) => MaterialPageRoute<void>(
                      builder: (_) => const Scaffold(body: Text('you')),
                    ),
                  ),
                ),
                Expanded(
                  child: Navigator(
                    key: floorKey,
                    observers: [
                      _CountingObserver(onPush: () => floorPushCount++),
                    ],
                    onGenerateRoute: (_) => MaterialPageRoute<void>(
                      builder: (_) => const Scaffold(body: Text('floor')),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
      await t.pump();
      final floorPushesBefore = floorPushCount;

      DeepLinkDispatcher.dispatch(
        _FakeRef(container),
        const DeepLink(route: 'open_privacy_policy', params: {}),
      );
      t.takeException();

      expect(floorPushCount, floorPushesBefore,
          reason: 'open_privacy_policy is routed on AmiTab.you — pushing '
              'there must not touch another tab\'s navigator');
    });
  });
}

class _CountingObserver extends NavigatorObserver {
  _CountingObserver({required this.onPush});
  final void Function() onPush;

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    onPush();
  }
}

/// `DeepLinkDispatcher.dispatch` only ever calls `ref.read` — a real
/// `WidgetRef` is a `BuildContext`-bound interface this file has no widget
/// to hand one from at the call site, so this stands in for the one method
/// actually used, backed by the real `ProviderContainer` above.
class _FakeRef implements WidgetRef {
  _FakeRef(this._container);
  final ProviderContainer _container;

  @override
  T read<T>(ProviderListenable<T> provider) => _container.read(provider);

  @override
  dynamic noSuchMethod(Invocation invocation) =>
      throw UnimplementedError('${invocation.memberName} not needed here');
}

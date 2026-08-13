/// RevenueCat SDK configuration (CR084).
///
/// The **public** RevenueCat SDK keys (iOS + Android) are Saiful's, tracked as
/// DEF100 (RC dashboard + App Store Connect / Play Console product config). They
/// are supplied at build time via `--dart-define`, NEVER committed here:
///
///     flutter build ios --release \
///       --dart-define=REVENUECAT_IOS_SDK_KEY=appl_xxx \
///       --dart-define=REVENUECAT_ANDROID_SDK_KEY=goog_xxx
///
/// Until those keys land, [publicSdkKey] is empty and the billing layer
/// **degrades loudly** (CR040): the paywall renders the plain out-of-credits
/// info state (no dead buy button), never a broken checkout. `purchases_flutter`
/// is never even configured without a key. A public SDK key is safe to embed in
/// a shipped client (that is what "public" means); the server-side webhook
/// secret is the sensitive one and lives only on the backend (CR084-BE).
library;

import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kDebugMode, visibleForTesting;

class BillingConfig {
  const BillingConfig._();

  /// RevenueCat's Test Store key prefix. Purchases against such a key are
  /// simulated end to end — paywall, webhook, entitlement grant, credit
  /// top-up — which is exactly what alpha wants, but ONLY in a debug build.
  static const String _testStorePrefix = 'test_';

  static const String _iosKey = String.fromEnvironment(
    'REVENUECAT_IOS_SDK_KEY',
    defaultValue: '',
  );

  static const String _androidKey = String.fromEnvironment(
    'REVENUECAT_ANDROID_SDK_KEY',
    defaultValue: '',
  );

  /// The public SDK key for the current platform, or '' when unset (DEF100)
  /// **or unusable** — a Test Store key outside a debug build is treated as no
  /// key at all. See [_usable].
  static String get publicSdkKey {
    if (Platform.isIOS) return _usable(_iosKey);
    if (Platform.isAndroid) return _usable(_androidKey);
    return '';
  }

  /// DEF282 — a `test_…` key in a non-debug build is not a key, it is a crash.
  ///
  /// RevenueCat does not degrade on a Test Store key in release; it calls
  /// `fatalError` on purpose, so that a Test Store key can never reach the App
  /// Store (`ios/Pods/RevenueCat/Sources/Purchasing/Configuration.swift:532`,
  /// guarded `#if !DEBUG`). Both our keys are `test_…` and every build that
  /// reaches a device is a release build, so configuring the SDK killed the app
  /// the first time a paywall opened.
  ///
  /// Returning '' here converts that crash into the degrade DEF100 already
  /// designed: no key ⇒ never configured ⇒ info-not-buy. The condition mirrors
  /// RevenueCat's own — `kDebugMode` is Dart's `#if DEBUG`, so a profile build
  /// (release pods) is correctly treated as unusable too.
  ///
  /// This is a *fence*, not the off switch: billing is currently disabled at
  /// [purchaseServiceProvider] (see `disabled_purchase_service.dart`). The
  /// fence is what makes switching it back on safe — it cannot resurrect this
  /// crash, and it lifts by itself the moment a real `appl_…`/`goog_…` key
  /// lands, with no code to remember to change.
  /// Pure so the rule can be tested without a `--dart-define`: the keys
  /// arrive as compile-time constants, so the only way to exercise the release
  /// branch from a test is to pass the inputs in.
  @visibleForTesting
  static String usableKey(String key, {required bool debug}) {
    if (key.startsWith(_testStorePrefix) && !debug) return '';
    return key;
  }

  static String _usable(String key) => usableKey(key, debug: kDebugMode);

  /// True when a **usable** key is present for this platform — the only
  /// condition under which the RC SDK may be configured. When false, the
  /// paywall degrades to the info-not-buy state (DEF100).
  static bool get isConfigured => publicSdkKey.isNotEmpty;
}

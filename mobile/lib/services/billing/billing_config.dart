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

class BillingConfig {
  const BillingConfig._();

  static const String _iosKey = String.fromEnvironment(
    'REVENUECAT_IOS_SDK_KEY',
    defaultValue: '',
  );

  static const String _androidKey = String.fromEnvironment(
    'REVENUECAT_ANDROID_SDK_KEY',
    defaultValue: '',
  );

  /// The public SDK key for the current platform, or '' when unset (DEF100).
  static String get publicSdkKey {
    if (Platform.isIOS) return _iosKey;
    if (Platform.isAndroid) return _androidKey;
    return '';
  }

  /// True when a key is present for this platform — the only condition under
  /// which the RC SDK may be configured. When false, the paywall degrades to
  /// the info-not-buy state (DEF100).
  static bool get isConfigured => publicSdkKey.isNotEmpty;
}

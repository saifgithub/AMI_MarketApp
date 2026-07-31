/// OneSignal SDK configuration (CR027).
///
/// Unlike RevenueCat's per-platform SECRET SDK keys (DEF100), the OneSignal
/// App ID is public/safe to embed in a shipped client — that is what
/// OneSignal's own docs mean by "App ID", distinct from the backend-only
/// REST API key that never leaves the server. Provisioned 2026-07-31.
library;

class OneSignalConfig {
  const OneSignalConfig._();

  static const String appId = String.fromEnvironment(
    'ONESIGNAL_APP_ID',
    defaultValue: '3c2020b6-d8b0-493f-b0e3-5d6ede868d7b',
  );

  static bool get isConfigured => appId.isNotEmpty;
}

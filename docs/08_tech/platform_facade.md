# Platform Service Facade

> **Status: design doc — not yet built.** The directory
> `mobile/lib/services/platform/` exists but is empty. No
> `PushService`, `AuthService`, `BillingService`, or `AdsService`
> facade interfaces are defined in code yet, and no GMS/HMS/iOS
> implementations have been written. The Android-GMS + Android-HMS
> targets do not ship in Alpha (iOS only).
>
> Real Apple Sign-In is wired (`sign_in_with_apple` package + the
> backend `oidc_verifier`), but it's a direct integration in
> `mobile/lib/services/auth/`, not through this facade.
>
> The whole abstraction lands when Android-GMS prep starts (v1.0
> milestone — see project_plan.md Phase 3 / Stream 5). Until then,
> the design below is **forward-looking** and may be revised
> against current Android-GMS / Huawei AppGallery rules at build
> time.

---

Abstraction layer that lets the same app code run on iOS, Android-GMS, and Android-HMS by swapping service implementations at runtime.

## Why this exists

| Capability | iOS | Android-GMS | Android-HMS |
|---|---|---|---|
| Push notifications | APNs | FCM | HMS Push Kit |
| Auth federation | Apple Sign-In | Google Sign-In | HMS Account Kit |
| In-app purchases | Apple IAP | Google Play Billing | HMS IAP |
| Ads | AdMob | AdMob | Huawei Ads Kit |
| Maps (if used) | Apple Maps | Google Maps | HMS Maps |
| Analytics | Firebase | Firebase | HMS Analytics + AppGallery Connect |

Without abstraction, app code is full of `if (isHMS) ...else if (isGMS) ...` branches. Unmaintainable.

## Facade pattern

```dart
// mobile/lib/services/push_service.dart

abstract class PushService {
  Future<void> initialize();
  Future<String?> getDeviceToken();
  Stream<PushMessage> messages();
  Future<void> unregister();
}

class ApplePushService implements PushService { /* APNs impl */ }
class GMSPushService implements PushService    { /* FCM via Firebase */ }
class HMSPushService implements PushService    { /* HMS Push Kit */ }
```

App code consumes the interface:

```dart
final pushService = ref.read(pushServiceProvider);
await pushService.initialize();
pushService.messages().listen((msg) {
  // handle push
});
```

## Service registry

A platform-detector picks the right implementation at startup:

```dart
// mobile/lib/services/service_registry.dart

class PlatformDetector {
  static Future<Platform> detect() async {
    if (Platform.isIOS) return Platform.ios;
    if (Platform.isAndroid) {
      // Detect HMS vs GMS
      try {
        final result = await GooglePlayServices.checkAvailability();
        return result == GooglePlayServicesAvailability.success
            ? Platform.androidGMS
            : Platform.androidHMS;
      } catch (e) {
        return Platform.androidHMS;
      }
    }
    throw UnsupportedError('Unsupported platform');
  }
}

// In Riverpod provider:
final pushServiceProvider = Provider<PushService>((ref) {
  final platform = ref.watch(platformProvider);
  return switch (platform) {
    Platform.ios => ApplePushService(),
    Platform.androidGMS => GMSPushService(),
    Platform.androidHMS => HMSPushService(),
  };
});
```

## The full set of services

| Service | iOS | Android-GMS | Android-HMS |
|---|---|---|---|
| `PushService` | APNs via `flutter_apns_only` | FCM via `firebase_messaging` | HMS Push via `huawei_push` |
| `AuthService.federatedSignIn(provider)` | Apple via `sign_in_with_apple` | Google via `google_sign_in` | HMS Account via `huawei_account` |
| `BillingService` | RevenueCat (Apple IAP) | RevenueCat (Play Billing) | RevenueCat (HMS IAP) |
| `AdsService` | AdMob via `google_mobile_ads` | AdMob | Huawei Ads via `huawei_ads` |
| `AnalyticsService` | PostHog (universal) | PostHog | PostHog |
| `CrashService` | Sentry (universal) | Sentry | Sentry |
| `MapsService` (if needed) | MapKit | Google Maps | HMS Maps or Mapbox |
| `LocationService` | Core Location | Google Location | HMS Location |

Most universal services (PostHog, Sentry, RevenueCat, OneSignal for push aggregation) work across all three. Only the platform-native federated and ad SDKs need per-platform code.

## Using OneSignal to abstract push

We use **OneSignal** as a push aggregation layer:

```
OneSignal SDK
  ↓
On iOS: registers with APNs
On Android-GMS: registers with FCM (uses Firebase under the hood)
On Android-HMS: registers with HMS Push Kit (OneSignal HMS SDK)
  ↓
Backend POSTs to OneSignal REST API
  ↓
OneSignal routes to APNs/FCM/HMS Push appropriately
```

OneSignal makes push *almost* a single integration — we still have to bundle the right native SDK per build flavor, but our backend code is one API call.

## Build flavors

Flutter supports build flavors for compile-time switching:

```
mobile/
├── ios/Runner/
│   └── (single iOS build — Apple is uniform)
├── android/
│   ├── app/src/main/    ← shared
│   ├── app/src/gms/     ← GMS-specific manifests, gradle deps
│   │   └── google-services.json
│   ├── app/src/hms/     ← HMS-specific manifests, gradle deps
│   │   └── agconnect-services.json
```

Two Android binaries:
- `app-gms-release.apk` for Play Store
- `app-hms-release.apk` for AppGallery

Could be one universal binary with runtime detection — slightly larger app size but simpler ops. We'll start with two flavors and consolidate if it makes sense.

## Build pipeline per flavor

```yaml
# .github/workflows/build.yml
matrix:
  flavor: [ios, android-gms, android-hms]

steps:
  - uses: actions/checkout@v3
  - name: Setup Flutter
    uses: subosito/flutter-action@v2
  - name: Install platform-specific deps
    run: |
      if [[ "${{ matrix.flavor }}" == "android-hms" ]]; then
        echo "Using HMS gradle deps"
      else
        echo "Using GMS gradle deps"
      fi
  - name: Build
    run: flutter build ${{ matrix.flavor }} --release
```

## Conditional code

For Dart code that absolutely cannot be abstracted:

```dart
import 'package:flutter/foundation.dart' show kIsWeb;
import 'dart:io' show Platform;

if (Platform.isIOS) {
  // iOS-specific
} else if (PlatformDetector.isHMS) {
  // HMS-specific
} else {
  // GMS or web fallback
}
```

This should be **rare** — most code is platform-agnostic. The facade isolates the platform code to service implementations.

## Testing per platform

| Test type | Where |
|---|---|
| Unit tests (services in isolation) | All platforms (mocked service impls) |
| Integration tests (real platform SDKs) | Per-platform CI run |
| Manual smoke tests | Saiful tests each platform on real devices |
| Receipt validation tests | Sandbox environments per platform |

Saiful's role: he is the human who tests on real iOS and Android (and Huawei when v1.1 lands).

## Cross-references

- Auth flow (federated providers): [`auth.md`](auth.md)
- Payment integration: [`payments.md`](payments.md)
- Ads SDKs per platform: [`docs/06_monetization/ads.md`](../06_monetization/ads.md)
- Push notifications via OneSignal: [`architecture.md`](architecture.md)

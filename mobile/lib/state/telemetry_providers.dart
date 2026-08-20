/// CR181 — Riverpod wiring for the persona telemetry emitter.
///
/// One emitter per [ApiClient]: the send path is the client's authed Dio
/// (bearer + version header ride the existing interceptors), and the locale
/// read at record time is the app locale in force — the Settings override
/// when one is set, else the device locale. A backend-mode flip in dev
/// rebuilds the client and therefore the emitter; the outgoing emitter's
/// dispose logs anything it still held (it cannot forward its own drop
/// marker once dead).
library;

import 'dart:ui' show PlatformDispatcher;

import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/services/telemetry/telemetry_emitter.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final telemetryProvider = Provider<TelemetryEmitter>((ref) {
  final api = ref.watch(apiClientProvider);
  final emitter = TelemetryEmitter(
    send: api.telemetryEvents,
    locale: () => (ref.read(localeNotifierProvider) ??
            PlatformDispatcher.instance.locale)
        .languageCode,
  );
  ref.onDispose(emitter.dispose);
  return emitter;
});

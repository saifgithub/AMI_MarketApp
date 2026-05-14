/// AMI Trade — Flutter entry point.
///
/// Wraps `runApp` in `SentryFlutter.init` (A10) when a DSN is provided
/// via `--dart-define=SENTRY_DSN=...`. No DSN → no init, no network,
/// no PII leaving the device. Set env via `--dart-define=AMI_ENV=prod`
/// (default `local`).
library;

import 'package:ami_trade/app.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _sentryDsn = String.fromEnvironment('SENTRY_DSN');
const _amiEnv = String.fromEnvironment('AMI_ENV', defaultValue: 'local');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock to portrait for the alpha — horizontal layouts come later
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
  ]);

  // Dark status bar content on our dark slate canvas
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: AmiColors.slate900,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  final prefs = await SharedPreferences.getInstance();
  final startOnFloor = prefs.getBool('ami_onboarding_done') ?? false;

  if (_sentryDsn.isEmpty) {
    runApp(ProviderScope(child: AmiTradeApp(startOnFloor: startOnFloor)));
    return;
  }

  await SentryFlutter.init(
    (options) {
      options.dsn = _sentryDsn;
      options.environment = _amiEnv;
      options.release = 'ami-trade@0.1.0';
      options.sendDefaultPii = false;
      // Alpha: conservative traces. Beta will bump once we see traffic.
      options.tracesSampleRate = _amiEnv == 'prod' ? 0.1 : 0.0;
      options.attachStacktrace = true;
      // Scrub Authorization / cookies before shipping. Sentry already
      // drops `Authorization` by default; we belt-and-brace.
      options.beforeSend = (event, hint) async {
        final req = event.request;
        if (req == null) return event;
        final headers = Map<String, String>.from(req.headers);
        for (final k in headers.keys.toList()) {
          final lower = k.toLowerCase();
          if (lower == 'authorization' ||
              lower == 'cookie' ||
              lower == 'x-api-key') {
            headers[k] = '***';
          }
        }
        return event.copyWith(request: req.copyWith(headers: headers));
      };
    },
    appRunner: () => runApp(ProviderScope(child: AmiTradeApp(startOnFloor: startOnFloor))),
  );
}

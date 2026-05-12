/// AMI Trade — MaterialApp root.
///
/// A11 wires `localizationsDelegates` + `supportedLocales` so Flutter's
/// gen-l10n machinery picks up `lib/l10n/app_*.arb`. The locale is
/// driven by `localeNotifierProvider` — null means follow the system,
/// non-null is the user's Settings → Language override. RTL is handled
/// automatically by MaterialApp when the language is `ar`.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/screens/dev_preview_screen.dart';
import 'package:ami_trade/screens/home_shell.dart';
import 'package:ami_trade/screens/onboarding/onboarding_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AmiTradeApp extends ConsumerWidget {
  const AmiTradeApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locale = ref.watch(localeNotifierProvider);
    return MaterialApp(
      title: 'AMI Trade',
      debugShowCheckedModeBanner: false,
      theme: amiTheme(),
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: supportedLocales,
      initialRoute: '/onboarding',
      routes: {
        '/onboarding': (_) => const OnboardingScreen(),
        '/floor': (_) => const HomeShell(),
        '/dev-preview': (_) => const DevPreviewScreen(),
      },
    );
  }
}

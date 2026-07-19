/// AMI Trade — MaterialApp root.
///
/// A11 wires `localizationsDelegates` + `supportedLocales` so Flutter's
/// gen-l10n machinery picks up `lib/l10n/app_*.arb`. The locale is
/// driven by `localeNotifierProvider` — null means follow the system,
/// non-null is the user's Settings → Language override. RTL is handled
/// automatically by MaterialApp when the language is `ar`.
///
/// A7 (adversarial audit 2026-05-18): the home is gated behind
/// `authNotifierProvider` — we wait for `state.token != null` before
/// rendering Onboarding or HomeShell, so feature providers never fire
/// API calls before the Dio interceptor has a token attached.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/screens/dev_preview_screen.dart';
import 'package:ami_trade/screens/feedback/bug_resolution_toasts.dart';
import 'package:ami_trade/screens/home_shell.dart';
import 'package:ami_trade/screens/onboarding/onboarding_screen.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AmiTradeApp extends ConsumerWidget {
  const AmiTradeApp({super.key, this.startOnFloor = false});

  final bool startOnFloor;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locale = ref.watch(localeNotifierProvider);
    return MaterialApp(
      title: 'AMI Trade',
      debugShowCheckedModeBanner: false,
      theme: amiLightTheme(),
      darkTheme: amiTheme(),
      // D-062: dark-only for v1.0. The light theme stays wired for a v1.1
      // revival, but the mode is pinned dark and the Settings toggle is gone.
      themeMode: ThemeMode.dark,
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: supportedLocales,
      home: _AuthGate(startOnFloor: startOnFloor),
      routes: {
        '/onboarding': (_) => const OnboardingScreen(),
        '/floor': (_) => const HomeShell(),
        '/dev-preview': (_) => const DevPreviewScreen(),
      },
    );
  }
}

/// Splash widget that waits for `authNotifierProvider.bootstrap()` to finish
/// before rendering the real home. Without this, the Onboarding/HomeShell
/// providers can fire API calls before the Dio interceptor has a bearer token.
class _AuthGate extends ConsumerWidget {
  const _AuthGate({required this.startOnFloor});

  final bool startOnFloor;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // BL16 (AT:R38): when user.id flips (sign-in adopting a different
    // existing user, sign-out + re-bootstrap, merge that deletes the
    // orphan), the per-user Riverpod caches (sim, journal, mandate,
    // watchlist, lessons) still hold the previous user's data and
    // would render stale. Invalidate them whenever AuthState transitions
    // through a `previousUserId != null` tick.
    ref.listen<AuthState>(authNotifierProvider, (prev, next) {
      if (next.previousUserId == null) return;
      ref.invalidate(simNotifierProvider);
      ref.invalidate(journalNotifierProvider);
      ref.invalidate(journalTrashNotifierProvider);
      ref.invalidate(mandateNotifierProvider);
      ref.invalidate(watchlistNotifierProvider);
      ref.invalidate(lessonsNotifierProvider);
    });
    final auth = ref.watch(authNotifierProvider);
    if (auth.token == null) {
      // Bootstrap is in flight (or never started, or errored). Show the
      // brand splash and let `Future.microtask(n.bootstrap)` in
      // authNotifierProvider's factory do the work.
      return const Scaffold(
        backgroundColor: AmiColors.slate900,
        body: Center(child: HexPulseLoader()),
      );
    }
    // CR043: bug-resolution toasts wrap the home shell only — a user still
    // in onboarding has no reported bugs, and the sheet that files them
    // isn't reachable from there.
    return startOnFloor
        ? const BugResolutionToasts(child: HomeShell())
        : const OnboardingScreen();
  }
}

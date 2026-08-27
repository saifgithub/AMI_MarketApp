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

import 'package:ami_trade/features/games/games_gate.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/screens/dev_preview_screen.dart';
import 'package:ami_trade/screens/feedback/bug_resolution_toasts.dart';
import 'package:ami_trade/screens/games/games_home_screen.dart';
import 'package:ami_trade/screens/home_shell.dart';
import 'package:ami_trade/screens/inbox/inbox_screen.dart';
import 'package:ami_trade/screens/notifications/push_notification_listener.dart';
import 'package:ami_trade/screens/onboarding/onboarding_screen.dart';
import 'package:ami_trade/screens/version_gate/version_gate_screen.dart';
import 'package:ami_trade/services/notifications/app_navigator_key.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/version_gate_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
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
      navigatorKey: appNavigatorKey,
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
      home: _VersionGateGate(startOnFloor: startOnFloor),
      routes: {
        '/onboarding': (_) => const OnboardingScreen(),
        '/floor': (_) => const HomeShell(),
        '/dev-preview': (_) => const DevPreviewScreen(),
        // CR102 — the tester inbox, pushed from the Floor header's bell.
        '/inbox': (_) => const InboxScreen(),
        // CR109 Amendment F — the dark-launch gate. `kGamesEnabled` is a
        // const bool.fromEnvironment, so with the AMI_GAMES dart-define off
        // the compiler const-folds this whole entry out of the map — no
        // store binary contains a reachable '/games' route, and the games
        // screen tree-shakes out with it. NO other entry point exists: no
        // tab, no card, no settings row, no tap gesture reaches this route
        // in any build. See features/games/games_gate.dart.
        if (kGamesEnabled) '/games': (_) => const GamesHomeScreen(),
      },
    );
  }
}

/// CR121 — outermost gate, ahead of `_AuthGate`: a `block` verdict must
/// pre-empt onboarding/home rendering entirely, not just the parts of the
/// app that happen to make API calls. Also owns the `AppLifecycleState`
/// observer that re-checks on every foreground-resume (the launch check
/// alone can't catch a floor raised while the app was already open), and
/// the nag-sheet trigger, deferred until `_AuthGate` has cleared its own
/// splash so a dismissible sheet never appears over a loading screen.
class _VersionGateGate extends ConsumerStatefulWidget {
  const _VersionGateGate({required this.startOnFloor});

  final bool startOnFloor;

  @override
  ConsumerState<_VersionGateGate> createState() => _VersionGateGateState();
}

class _VersionGateGateState extends ConsumerState<_VersionGateGate>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      // A session left open for days must not outlive a floor raise —
      // fire-and-forget; VersionGateController.check() fails open on its
      // own and never throws out of here.
      ref.read(versionGateControllerProvider.notifier).check();
    }
  }

  @override
  Widget build(BuildContext context) {
    final gate = ref.watch(versionGateControllerProvider);
    if (gate.isBlocked && gate.floor != null) {
      return VersionGateBlockScreen(floor: gate.floor!);
    }

    final auth = ref.watch(authNotifierProvider);
    ref.listen<VersionGateState>(versionGateControllerProvider, (prev, next) {
      if (next.isNagging && next.floor != null && auth.token != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) showVersionGateNagSheet(context, ref, next.floor!);
        });
      }
    });

    return _AuthGate(startOnFloor: widget.startOnFloor);
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
      ref.invalidate(inboxProvider);
    });
    final auth = ref.watch(authNotifierProvider);
    if (auth.token == null) {
      // DEF380. This branch used to render the brand splash unconditionally,
      // with a comment that said "in flight (or never started, **or errored**)"
      // — the failure was named and then shown as a loading spinner, forever.
      // `bootstrapAnon` sets `error` and clears `loading` on its catch
      // (auth_providers.dart), and nothing here read either field, so a 502 on
      // the very first request left every user on an animating hexagon with no
      // message, no retry and no way forward. Measured in the iOS simulator:
      // `ServerUnavailableException(status: 502)` in the log, 60s+ on the logo.
      // CR040 — a feature gated on a call that can fail must fail visibly.
      if (!auth.loading && auth.error != null) {
        return _BootstrapFailed(
          message: auth.error!,
          onRetry: () => ref.read(authNotifierProvider.notifier).bootstrap(),
        );
      }
      return const Scaffold(
        backgroundColor: AmiColors.slate900,
        body: Center(child: HexPulseLoader()),
      );
    }
    // CR043: bug-resolution toasts wrap the home shell only — a user still
    // in onboarding has no reported bugs, and the sheet that files them
    // isn't reachable from there.
    return startOnFloor
        ? const PushNotificationListener(
            child: BugResolutionToasts(child: HomeShell()),
          )
        : const OnboardingScreen();
  }
}

/// DEF380 — what the app shows when the anonymous bootstrap cannot reach the
/// backend.
///
/// Deliberately a real screen and not a longer spinner. The bootstrap is the
/// first request the app makes; if it fails there is no session, so every
/// screen behind this one would be empty anyway. The alternative that shipped
/// until now — keep animating the brand loader — is indistinguishable from a
/// slow network on the user's side and indistinguishable from a crash on ours.
///
/// The message is `AuthState.error`, which `friendlyError(e, action: 'reach
/// AMI')` already wrote; this widget adds the way out rather than a second
/// wording of the same failure.
class _BootstrapFailed extends StatelessWidget {
  const _BootstrapFailed({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(AmiSpacing.l),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.cloud_off_outlined,
                    size: 32, color: AmiColors.hexAmber),
                const SizedBox(height: AmiSpacing.m),
                Text(
                  l.bootstrapFailedTitle,
                  style: AmiTypography.h2,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AmiSpacing.s),
                Text(
                  message,
                  style: AmiTypography.body,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AmiSpacing.l),
                HexButton(label: l.bootstrapRetry, onPressed: onRetry),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

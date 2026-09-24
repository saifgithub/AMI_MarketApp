/// Post-onboarding home — the bottom nav (CR133 §2), now with persistent
/// chrome across pushed pages (CR232).
///
/// `FLOOR · PORTFOLIO · GAME · LESSONS · YOU`, or the same four without GAME
/// when the compile-time `AMI_GAMES` gate is off. Journal and Settings left the
/// bar in CR133 and live inside `YOU` as segments.
///
/// **Nothing here counts.** Every index is an index into [AmiTab.visible], and
/// the panes below are built by the same const-folded condition that filters
/// it, so the bar, the `IndexedStack` and the tab enum cannot drift apart —
/// asserted in `home_shell_test.dart` rather than maintained by hand. CR133 §3
/// measured what the alternative costs: three of the five old integer literals
/// kept working through the reorder, so a smoke test would have passed while
/// "Review in Journal" opened the game.
///
/// **CR232 — a nested `Navigator` per tab.** Saiful: *"Some pages are simply
/// using an 'X' to exit — obscure and not in line with the app's aesthetics.
/// The bottom menu, the ad, and the ticker tape should always be on every
/// screen."* Before CR232, every `Navigator.of(context).push` resolved to the
/// single ROOT navigator, which sat ABOVE this Scaffold in the tree (it's
/// `MaterialApp`'s own navigator) — so a pushed detail page covered this
/// entire Scaffold, chrome included, and needed its own exit affordance (the
/// `Icons.close` buttons this CR removes). Giving each [AmiTab] its own
/// `Navigator` (via [_TabNavigator]) fixes that structurally rather than by
/// convention: `Navigator.of(context)` resolves to the *nearest* ancestor
/// Navigator, and a push from inside a tab's pane now finds that tab's own
/// nested Navigator first — landing the pushed page inside the `IndexedStack`
/// cell, below the chrome, which therefore never gets covered. No call-site
/// changes were needed for the ~56 ordinary `Navigator.of(context).push`
/// sites; only genuinely modal sheets and the two trade tickets needed
/// attention (see CR232 doc's site-classification table).
///
/// The chrome itself — nav / ad slot / ticker tape (CR226 §Scope 1 order) —
/// stays a sibling of the `IndexedStack`, in this Scaffold's own
/// `bottomNavigationBar`, so it is structurally unreachable by anything a tab
/// pushes on its own nested Navigator.
library;

import 'dart:async' show unawaited;

import 'package:ami_trade/features/games/games_gate.dart';
import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/nav/home_shell_navigation.dart';
import 'package:ami_trade/features/tour/nav_change_sheet.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/floor/floor_screen.dart';
import 'package:ami_trade/screens/games/games_home_screen.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/screens/you/you_screen.dart';
import 'package:ami_trade/services/telemetry/telemetry_emitter.dart';
import 'package:ami_trade/state/telemetry_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/shell_banner_slot.dart';
import 'package:ami_trade/widgets/hex/hex_bottom_nav.dart';
import 'package:ami_trade/widgets/ticker_tape.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell>
    with WidgetsBindingObserver {
  AmiTab _tab = AmiTab.floor;

  /// CR181 — dedupe guard for `app_open`. Cold start records in
  /// [initState]; after that only a genuine return from the background
  /// (paused/hidden/detached → resumed) counts as a new open, so the
  /// inactive↔resumed flapping around permission sheets and app-switcher
  /// peeks never inflates the bounce denominator.
  AppLifecycleState? _lastLifecycle;

  /// CR232 — one nested-Navigator key per [AmiTab], keyed on the full enum
  /// (not just [AmiTab.visible]) so a key exists even for `game` in a
  /// gated-off build — nothing reads it there, but a `Map` built from
  /// `visible` alone would need a null-check at every lookup instead of one
  /// at construction.
  final Map<AmiTab, GlobalKey<NavigatorState>> _navKeys = {
    for (final tab in AmiTab.values) tab: GlobalKey<NavigatorState>(),
  };

  /// One pane per entry of [AmiTab.visible], in the same order.
  ///
  /// The `if (kGamesEnabled)` is a **const** condition, so in a gated-off build
  /// the compiler removes the entry and nothing references `GamesHomeScreen` —
  /// the games screens tree-shake out, which is the store-binary guarantee
  /// CR109's dark launch rests on. A `switch` returning the screen would have
  /// been a live reference and would have quietly shipped the whole feature
  /// into every binary.
  static const _panes = <Widget>[
    FloorScreen(),
    PortfolioScreen(),
    if (kGamesEnabled) GamesHomeScreen(),
    LessonsScreen(),
    YouScreen(),
  ];

  /// CR232 round 2 — the notifier itself, captured once in [initState] while
  /// `ref` is still valid, so [dispose] can clear the published keys WITHOUT
  /// touching `ref`. `ConsumerStatefulElement.unmount()` invalidates `ref`
  /// before calling this `State`'s own `dispose()` (confirmed by a `Bad
  /// state: Cannot use "ref" after the widget was disposed` thrown from
  /// exactly that call site the first time this used `ref.read(...)` in
  /// `dispose` directly) — an uncaught exception there aborts the rest of
  /// the widget-tree unmount, including sibling providers' own `onDispose`
  /// (e.g. `telemetryProvider`'s flush-timer cleanup), which is why the
  /// regression this caused surfaced as an unrelated "Timer is still
  /// pending" failure in `home_shell_test.dart` rather than pointing at
  /// itself. A `StateController` reference stays valid after the widget
  /// that read it is gone (it's owned by the provider, not the widget).
  late final StateController<Map<AmiTab, GlobalKey<NavigatorState>>?>
      _navKeysController;

  @override
  void initState() {
    super.initState();
    _navKeysController = ref.read(homeShellNavKeysProvider.notifier);
    // CR232 round 2 (MAJOR-1) — publish the real nav keys once the first
    // frame lands. Same `addPostFrameCallback` shape as the nav-change-sheet
    // callback below (and Riverpod forbids writing a provider mid-build,
    // which `initState` still is) — a stream event a listener subscribed to
    // in ITS OWN `initState` can only fire asynchronously, never before this
    // callback, so there is no frame where the shell is mounted but a
    // dispatcher reading this provider would still see null.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _navKeysController.state = _navKeys;
    });
    // CR181 — the bounce denominator: reaching the shell IS "opened the
    // app". Fire-and-forget; the emitter owns batching and failure.
    WidgetsBinding.instance.addObserver(this);
    ref.read(telemetryProvider).record(TelemetryEvents.appOpen);
    // CR180 — tell the people who learned the OLD bar that it moved.
    //
    // Every section tour is gated on a `tour_*_seen` flag, so the walkthrough
    // system is silent for exactly the population whose mental model CR133
    // just invalidated: they already took every tour. `shouldShowNavChange`
    // returns false for a brand-new user, so this cannot land on top of the
    // Floor tour it would otherwise be competing with.
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final service = ref.read(tourServiceProvider);
      if (!await service.shouldShowNavChange()) return;
      await service.markNavChangeSeen();
      if (!mounted) return;
      await NavChangeSheet.show(context);
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    // CR232 round 2 — the shell is gone; a dispatch that raced past this
    // point must see null and queue/log, not push through a stale key whose
    // NavigatorState no longer exists. Goes through the captured
    // [_navKeysController], NOT `ref` (see its doc comment for why).
    _navKeysController.state = null;
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // CR181 — each return from the background is a fresh open; going to the
    // background flushes the session's tail past the debounce window.
    final was = _lastLifecycle;
    _lastLifecycle = state;
    final emitter = ref.read(telemetryProvider);
    if (state == AppLifecycleState.resumed &&
        (was == AppLifecycleState.paused ||
            was == AppLifecycleState.hidden ||
            was == AppLifecycleState.detached)) {
      emitter.record(TelemetryEvents.appOpen);
    } else if (state == AppLifecycleState.paused) {
      unawaited(emitter.flush());
    }
  }

  /// CR232 rule 5 — tapping the already-selected tab pops its stack to root.
  /// Switching tabs never touches the other tab's stack — each tab's history
  /// is its own, which is why this can only fire on a same-tab tap.
  void _onNavTap(AmiTab tab) {
    if (tab == _tab) {
      _navKeys[tab]!.currentState?.popUntil((r) => r.isFirst);
      return;
    }
    setState(() => _tab = tab);
    ref.read(activeTabProvider.notifier).state = tab;
  }

  /// CR232 rule 5 — Android system back pops within the active tab first.
  /// Only when that tab's own Navigator cannot pop (it's already at its
  /// root pane) does the system default (leaving the shell) apply.
  Future<bool> _onWillPop() async {
    final nav = _navKeys[_tab]!.currentState;
    if (nav != null && nav.canPop()) {
      nav.pop();
      return false;
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final tabs = AmiTab.visible;
    // DEF190 — `activeTabProvider` used to be write-only from this shell's own
    // tap handler below; a screen buried inside a tab (Portfolio History's
    // "Review in Journal") had no way to actually switch tabs, so it pushed a
    // second, orphaned screen on top of the shell instead — which covers the
    // bottom nav, because the nav lives in THIS Scaffold, below the pushed
    // route. Listening here makes an external write to the provider do what the
    // tap handler already does: switch `_tab`. Guarded on `next != _tab` so the
    // tap handler's own write (which already set `_tab` directly, synchronously,
    // before this listener next fires) is a no-op here, not a second rebuild.
    ref.listen<AmiTab>(activeTabProvider, (prev, next) {
      // A tab this binary does not render cannot be shown. Nothing writes
      // `game` in a gated-off build, so this is a guard against a future caller
      // rather than a live path — and it drops the write rather than
      // substituting a different tab, because landing the user somewhere they
      // did not ask for is the failure this whole CR is about.
      if (!tabs.contains(next)) {
        assert(
            false,
            'activeTabProvider was set to $next, which this build '
            'does not render (AMI_GAMES=$kGamesEnabled)');
        return;
      }
      if (next != _tab) setState(() => _tab = next);
    });
    // CR232 rule 2 exception (a) — the keyboard hides the persistent chrome.
    // `viewInsetsOf` rebuilds this widget on every inset change (open/close),
    // which is exactly the signal: a nonzero bottom inset means the software
    // keyboard is covering that much of the screen.
    final keyboardOpen = MediaQuery.viewInsetsOf(context).bottom > 0;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) async {
        if (didPop) return;
        if (await _onWillPop()) {
          // The active tab's own Navigator cannot pop any further — fall
          // through to whatever this shell's own ancestor (if any) does with
          // a pop. HomeShell is normally the MaterialApp's `home`/`/floor`
          // route, so in practice this is a no-op and the OS handles the
          // back gesture (Android: minimize) — see PopScope docs on the
          // no-parent-route case.
          if (context.mounted) {
            final nav = Navigator.of(context);
            if (nav.canPop()) nav.pop(result);
          }
        }
      },
      child: Scaffold(
        backgroundColor: AmiColors.slate900,
        body: IndexedStack(
          index: tabs.indexOf(_tab),
          // `tabs` and `_panes` are both filtered/declared in bar order by the
          // same `kGamesEnabled` condition (see `_panes`'s own comment) — so
          // `tabs[i]` and `_panes[i]` name the same tab at every index, and
          // wrapping each pane in its own `_TabNavigator` here cannot
          // introduce a mismatch that indexing separately would risk.
          children: [
            for (var i = 0; i < tabs.length; i++)
              _TabNavigator(navigatorKey: _navKeys[tabs[i]]!, child: _panes[i]),
          ],
        ),
        bottomNavigationBar: keyboardOpen
            ? null
            : Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    decoration: const BoxDecoration(
                      color: AmiColors.glassChrome,
                      border:
                          Border(top: BorderSide(color: AmiColors.slate700)),
                    ),
                    // Strip the bottom inset from MediaQuery so the nav doesn't
                    // absorb it internally — TickerTape owns that space.
                    child: MediaQuery.removePadding(
                      context: context,
                      removeBottom: true,
                      child: HexBottomNav(
                        currentIndex: tabs.indexOf(_tab),
                        onTap: (i) => _onNavTap(tabs[i]),
                        items: [for (final tab in tabs) _itemFor(tab, l)],
                      ),
                    ),
                  ),
                  // CR226 §Scope 1 order: nav / ad slot / ticker tape.
                  // Zero height until CR226 lands the real AdMob banner.
                  const ShellBannerSlot(),
                  const TickerTape(),
                ],
              ),
      ),
    );
  }

  /// One arm per [AmiTab]. A `switch` on the enum with no `default`, so adding
  /// a destination is a compile error here rather than a tab that renders with
  /// someone else's icon.
  HexNavItem _itemFor(AmiTab tab, AppLocalizations l) {
    return switch (tab) {
      AmiTab.floor => HexNavItem(
          icon: Icons.grid_view_rounded,
          label: l.floorTabUpper,
          id: NavIds.floor),
      AmiTab.portfolio => HexNavItem(
          icon: Icons.account_balance_wallet_outlined,
          label: l.portfolioTabUpper,
          id: NavIds.portfolio),
      AmiTab.game => HexNavItem(
          icon: Icons.emoji_events_outlined,
          label: l.gameTabUpper,
          id: NavIds.game),
      AmiTab.lessons => HexNavItem(
          icon: Icons.school_outlined,
          label: l.lessonsTabUpper,
          id: NavIds.lessons),
      AmiTab.you => HexNavItem(
          icon: Icons.person_outline, label: l.youTabUpper, id: NavIds.you),
    };
  }
}

/// CR232 — one tab's own navigation stack.
///
/// `Navigator(key: ..., onGenerateRoute: ...)` rather than the `pages:`/
/// `Navigator.pages` API: every existing call site already pushes with
/// `Navigator.of(context).push(MaterialPageRoute(...))`, and
/// `onGenerateRoute`'s single root route is exactly what that imperative API
/// needs to land on — the tab's `child` (its `HomeShell` pane) becomes route
/// zero, and everything the pane itself pushes stacks on top of it, still
/// inside this Navigator, still below the shell's own chrome.
class _TabNavigator extends StatelessWidget {
  const _TabNavigator({required this.navigatorKey, required this.child});

  final GlobalKey<NavigatorState> navigatorKey;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Navigator(
      key: navigatorKey,
      onGenerateRoute: (settings) => MaterialPageRoute<void>(
        settings: settings,
        builder: (_) => child,
      ),
    );
  }
}

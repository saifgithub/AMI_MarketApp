/// Riverpod providers for the walkthrough system.
///
/// activeTabProvider: updated by HomeShell whenever the user switches tabs.
/// Each screen watches it and fires its section tour the first time its tab
/// becomes active (guards against IndexedStack firing initState for all tabs).
library;

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final tourServiceProvider = Provider<TourService>((ref) => TourService());

/// The active tab. HomeShell writes it; screens read it to decide when to
/// show their tour.
///
/// CR133 §3 — this was `activeTabIndexProvider`, a `StateProvider<int>`, and
/// its readers compared against bare literals. Typing it on [AmiTab] means a
/// future insert into the tab set turns every comparison into a compile
/// error instead of into a screen that quietly listens for the wrong tab.
final activeTabProvider = StateProvider<AmiTab>((ref) => AmiTab.floor);

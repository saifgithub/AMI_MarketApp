/// Riverpod providers for the walkthrough system.
///
/// activeTabIndexProvider: updated by HomeShell whenever the user switches tabs.
/// Each screen watches it and fires its section tour the first time its tab
/// becomes active (guards against IndexedStack firing initState for all tabs).
library;

import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final tourServiceProvider = Provider<TourService>((ref) => TourService());

/// Current active tab index (0=Floor, 1=Portfolio, 2=Journal, 3=Lessons, 4=Settings).
/// HomeShell writes this; screens read it to decide when to show their tour.
final activeTabIndexProvider = StateProvider<int>((ref) => 0);

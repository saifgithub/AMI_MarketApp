/// State for the `YOU` tab (CR133 §4).
///
/// Two things live here rather than inside `YouScreen`, and both for the same
/// reason: something outside the screen has to be able to reach them.
///
///   * [youSegmentProvider] — Portfolio History's *"Review in Journal"* has to
///     land on a **tab and a segment**. `AmiTab` alone cannot say which segment,
///     so a deep link that only set the tab would land on whichever segment
///     `YOU` happened to be showing and leave the entry the user asked for one
///     invisible tap away (CR133 §3).
///   * [settingsHeaderProvider] — `YOU` owns the header, but everything the
///     header needs while SETTINGS is active (mandate version, unsaved edits,
///     an in-flight save) is `SettingsScreen`'s state. It publishes; `YOU`
///     renders. The `dirty` half is not cosmetic: the mandate has an explicit
///     Save, so switching segments mid-edit is silent data loss, and CR040 says
///     that must fail visibly rather than quietly (CR133 §4.2).
library;

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The segments of `YOU`, in on-screen order.
///
/// CR178 inserts `insights` after `journal`. The bar sizes with `Expanded`, so
/// that is one line here plus one pane — not a re-layout.
enum YouSegment { settings, journal }

final youSegmentProvider =
    StateProvider<YouSegment>((ref) => YouSegment.settings);

/// True exactly when the Journal is the thing on screen.
///
/// The Journal's coach-mark tour used to fire on `activeTabProvider == journal`.
/// The Journal is no longer a tab, and nothing would have failed — the tour
/// would simply never have run again, silently, forever (CR133 §3). Both halves
/// are needed: `YOU` keeps its panes alive in an `IndexedStack`, so
/// `JournalScreen.build` runs whether or not its segment is showing.
final journalVisibleProvider = Provider<bool>((ref) =>
    ref.watch(activeTabProvider) == AmiTab.you &&
    ref.watch(youSegmentProvider) == YouSegment.journal);

/// What `YOU`'s header renders on SETTINGS' behalf.
@immutable
class SettingsHeaderState {
  const SettingsHeaderState({
    this.version,
    this.dirty = false,
    this.saving = false,
  });

  /// Mandate version, or null before the mandate has loaded.
  final int? version;

  /// Edits made and not yet sent.
  final bool dirty;

  /// A save is in flight.
  final bool saving;

  @override
  bool operator ==(Object other) =>
      other is SettingsHeaderState &&
      other.version == version &&
      other.dirty == dirty &&
      other.saving == saving;

  @override
  int get hashCode => Object.hash(version, dirty, saving);
}

final settingsHeaderProvider =
    StateProvider<SettingsHeaderState>((ref) => const SettingsHeaderState());

/// Bumped by `YOU`'s header to ask the mounted settings pane to save.
///
/// A counter rather than the `VoidCallback` this first carried. A published
/// closure holds the `State` it came from, so it has to be cleared on dispose,
/// and clearing it means touching `ref` after the widget is gone — which threw
/// `Bad state: Cannot use "ref" after the widget was disposed` the first time
/// the shell rebuilt. A counter has no such lifetime: if nothing is listening,
/// the bump is simply ignored, which is the correct behaviour for a Save button
/// whose editor is not on screen.
final settingsSaveRequestProvider = StateProvider<int>((ref) => 0);

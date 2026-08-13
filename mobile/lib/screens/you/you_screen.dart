/// `YOU` — the tab that owns the user rather than the market (CR133 §4).
///
/// Portfolio owns the money, Lessons owns the curriculum, GAME owns the score.
/// Nothing owned *you*: the mandate — your standing order to the team, and the
/// object the curriculum tells you to revisit — sat at the bottom of the fifth
/// nav slot, and the Decision Journal sat in prime real estate as a log nobody
/// re-reads.
///
/// **Structure is Saiful's, 2026-08-13, not §4's.** §4 proposed splitting the
/// mandate into its own MANDATE segment with the remaining ten Settings
/// sections behind a gear. His ruling was simpler: *"'You' is suppose to have
/// (1) Mandate & Settings (this is currently settings, and we can still call it
/// just settings) (2) Journal (all that we have in journal today) (3) Insights
/// (This is the new one)"*. So Settings moves in **whole and keeps its name**,
/// and there is no gear and no split. INSIGHTS is [CR178] and lands as a third
/// segment — the bar sizes with `Expanded`, so that is an insertion, not a
/// re-layout.
///
/// **No identity card.** §4's pinned card would have shown path, horizon, goal,
/// mandate version and plan — every one of which Settings' first section
/// already renders, directly editable, immediately below it. Under Saiful's
/// structure the card is a read-only duplicate of the thing it sits on top of.
/// The mandate version survives in the header, where it already lived.
///
/// **The hazard this layout creates, and the guard for it (§4.2).** The mandate
/// has a dirty state and an explicit Save. Putting it in a segment means
/// switching segments mid-edit is silent data loss — the exact shape CR040
/// exists for. Three things answer it: the Save stays pinned in the header, a
/// marker appears on the SETTINGS segment while edits are pending, and a switch
/// away prompts rather than discarding. The prompt is the load-bearing one; the
/// marker only tells you why.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/screens/journal/journal_trash_screen.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/hex/ami_segment_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class YouScreen extends ConsumerWidget {
  const YouScreen({super.key});

  /// The panes, in [YouSegment] order. Kept alive by `IndexedStack` so
  /// switching back does not reload the journal or drop a half-finished
  /// mandate edit.
  static const _panes = <Widget>[
    SettingsScreen(embedded: true),
    JournalScreen(embedded: true),
  ];

  Future<void> _select(
      BuildContext context, WidgetRef ref, YouSegment next) async {
    final current = ref.read(youSegmentProvider);
    if (next == current) return;

    // §4.2 — leaving SETTINGS with unsaved mandate edits is data loss, so it
    // asks. Only that direction: nothing else in `YOU` holds an unsaved edit.
    if (current == YouSegment.settings &&
        ref.read(settingsHeaderProvider).dirty) {
      final leave = await _confirmDiscard(context);
      if (leave != true) return;
    }
    ref.read(youSegmentProvider.notifier).state = next;
  }

  Future<bool?> _confirmDiscard(BuildContext context) {
    final l = AppLocalizations.of(context);
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AmiColors.slate800,
        title: Text(l.youUnsavedTitle,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber)),
        content: Text(l.youUnsavedBody, style: AmiTypography.body),
        actions: [
          // Non-destructive first — the destructive action should not be the
          // one under the thumb.
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l.youUnsavedKeep, style: AmiTypography.body),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l.youUnsavedDiscard,
                style: AmiTypography.body.copyWith(color: AmiColors.hexAmber)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final segment = ref.watch(youSegmentProvider);
    final settings = ref.watch(settingsHeaderProvider);

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            AmiScreenHeader(
              title: l.youTabUpper,
              titleColor: AmiColors.hexPurple,
              // The mandate version rides with SETTINGS, where it means
              // something; on JOURNAL it would be chrome from another screen.
              subtitle: segment == YouSegment.settings && settings.version != null
                  ? l.settingsMandateVersion(settings.version!)
                  : null,
              actions: [
                if (segment == YouSegment.settings && settings.dirty)
                  TextButton(
                    onPressed: settings.saving
                        ? null
                        : () => ref
                            .read(settingsSaveRequestProvider.notifier)
                            .state++,
                    child: Text(
                        settings.saving ? l.settingsSaving : l.settingsSave,
                        style: AmiTypography.labelMono
                            .copyWith(color: AmiColors.hexBlue)),
                  ),
                if (segment == YouSegment.journal)
                  IconButton(
                    icon: const Icon(Icons.delete_outline,
                        color: AmiColors.textMed, size: 22),
                    tooltip: l.journalTrashHeading,
                    onPressed: () =>
                        Navigator.of(context).push(MaterialPageRoute<void>(
                      builder: (_) => const JournalTrashScreen(),
                    )),
                  ),
              ],
            ),
            AmiSegmentBar(
              selected: segment.index,
              onSelect: (i) => _select(context, ref, YouSegment.values[i]),
              segments: [
                AmiSegment(
                  label: l.settingsTabUpper,
                  // Why the pending edit is not lost, shown where the switch
                  // that would lose it is made.
                  trailing: settings.dirty ? const _DirtyPip() : null,
                ),
                AmiSegment(label: l.journalTabUpper),
              ],
            ),
            Expanded(child: IndexedStack(index: segment.index, children: _panes)),
          ],
        ),
      ),
    );
  }
}

/// The unsaved-edit marker. Amber, not cyan: unlike Portfolio's live pip this
/// is a warning — something will be lost if it is ignored.
class _DirtyPip extends StatelessWidget {
  const _DirtyPip();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      width: 6,
      height: 6 * 0.8660254, // flat-top regular hexagon: h = w·√3/2
      child: ClipPath(
        clipper: FlatTopRegularHexagon(),
        child: ColoredBox(color: AmiColors.hexAmber),
      ),
    );
  }
}

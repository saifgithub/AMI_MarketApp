/// CR173 acceptance #12 — a way for the next complaint to arrive as data.
///
/// This whole CR exists because a complaint reached Saiful *by word of mouth*:
/// the Floor felt "like walking into a meeting with 12 staff waiting for you".
/// Nothing in the app carried that. §5.12 asks the rollout to include some
/// capture path so the next one does not travel the same way, and names the
/// minimum acceptable version — a prompt logged to `bug_reports`. That table,
/// its endpoint and the client's `submitBug` already exist, so this adds no
/// backend surface.
///
/// **It is a card, not a modal.** The surface it asks about is the one the user
/// is trying to use; interrupting them to ask how the room feels is its own
/// answer. It appears once, after enough visits that there is something to
/// react to, and dismissing it is as final as answering it.
///
/// **It asks about "the Floor", not "the new Floor".** A user who installed
/// today never saw the old one, and there is no flag that can tell them apart
/// after the fact — `tour_floor_seen` is set by both. Asking everyone the
/// neutral question beats asking half of them a question with a false premise.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _visitsKey = 'floor_v02_visits';
const _askedKey = 'floor_v02_reaction_done';

/// Visits before asking. Low enough to catch a first impression while it is
/// still an impression, high enough that the user has seen the surface work.
const int kFloorReactionAfterVisits = 3;

/// Counts this visit and answers whether to ask. Increments **only** until the
/// threshold — after that it stops writing, so the counter cannot grow forever
/// on a preference that is already spent.
Future<bool> registerFloorVisit() async {
  try {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool(_askedKey) ?? false) return false;
    final visits = (prefs.getInt(_visitsKey) ?? 0) + 1;
    await prefs.setInt(_visitsKey, visits);
    return visits >= kFloorReactionAfterVisits;
  } catch (_) {
    // Best-effort. A prompt that cannot be counted is simply not shown; it is
    // not worth failing a screen over.
    return false;
  }
}

Future<void> markFloorReactionDone() async {
  try {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_askedKey, true);
  } catch (_) {}
}

class FloorReactionCard extends ConsumerStatefulWidget {
  const FloorReactionCard({super.key, required this.onDone});

  final VoidCallback onDone;

  @override
  ConsumerState<FloorReactionCard> createState() => _FloorReactionCardState();
}

class _FloorReactionCardState extends ConsumerState<FloorReactionCard> {
  final _ctrl = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _ctrl.text.trim();
    if (text.isEmpty) return;
    setState(() => _sending = true);
    // `feature_request` rather than `other`: this is a request for the product
    // to be different, which is what the triage queue needs to know to sort it.
    final ok = await ref.read(feedbackNotifierProvider.notifier).submitBug(
          category: 'feature_request',
          title: 'Floor v0.2 reaction',
          steps: text,
          route: '/floor',
        );
    if (!mounted) return;
    // Marked done either way. A send that failed and a card that keeps coming
    // back are two frustrations; the first is ours to see in the logs, and
    // re-asking makes the second the user's problem.
    await markFloorReactionDone();
    if (!mounted) return;
    final l = AppLocalizations.of(context);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(ok ? l.floorReactionThanks : l.floorReactionFailed),
      behavior: SnackBarBehavior.floating,
    ));
    widget.onDone();
  }

  Future<void> _dismiss() async {
    await markFloorReactionDone();
    widget.onDone();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.m),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexPink),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(l.floorReactionPrompt,
                    style: AmiTypography.labelMono
                        .copyWith(fontSize: 11, color: AmiColors.hexPink)),
              ),
              GestureDetector(
                onTap: _dismiss,
                child: const Icon(Icons.close,
                    size: 16, color: AmiColors.textLow),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          TextField(
            controller: _ctrl,
            maxLines: 2,
            style: AmiTypography.body,
            decoration: InputDecoration(
              isDense: true,
              hintText: l.floorReactionHint,
              hintStyle:
                  AmiTypography.body.copyWith(color: AmiColors.textLow),
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: AmiSpacing.s),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: _sending ? null : _send,
              child: Text(
                _sending ? l.floorReactionSending : l.floorReactionSend,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.hexPink),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// CR172 — the path from a Room verdict that carries a structure to a position.
///
/// This is the wiring the CR was carrying as its one user-visible gap: the
/// ticket existed, `Verdict.structure` existed, and nothing on the board opened
/// one — so a user could not consent to a structure the Room had costed for
/// them.
///
/// **The sequence, and why each step is separate:**
///
///   1. **Review** — [OptionProposalTicket] renders the structure the Room
///      priced: legs, net cost, max loss and gain, break-evens, greeks, and the
///      floor's answer. This is what Saiful chose when asked how much the
///      verdict should carry: *"the full structure the Room priced."*
///   2. **Accept** — not an open. The ticket's yes calls
///      `POST /v1/sim/options/reprice`, which costs the same legs against the
///      live chain and returns what moved.
///   3. **Confirm** — [OptionRepriceSheet] shows the drift and takes the real
///      yes. Only this resolves to an open.
///   4. **Open** — `POST /v1/sim/options/open`, which re-prices a THIRD time.
///      That is not redundant with step 2: seconds pass while the user reads
///      the drift, and a route that trusted step 2's answer would be filling at
///      a price it did not take. Step 2 informs; step 4 commits.
///
/// **Why the review and the confirm are two sheets rather than one.** They ask
/// different questions. The ticket asks *"is this the trade you want?"* — a
/// judgement about structure, risk and thesis. The re-price sheet asks *"at
/// this price?"* — a judgement about a number that changed since. Merging them
/// would put a stale figure beside the button that charges, which is the whole
/// failure the re-price exists to prevent.
///
/// **A dismissal is not a decline and neither is an error.** Every await below
/// can leave the widget unmounted, and every branch that survives one re-checks
/// `mounted` before touching a `BuildContext` — a disposed notifier cannot
/// report an error either (DEF332).
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/option_proposal.dart';
import 'package:ami_trade/models/option_reprice.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sim/option_proposal_ticket.dart';
import 'package:ami_trade/widgets/sim/option_reprice_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' hide TextDirection;

final _money = NumberFormat('#,##0.00');

class OptionVerdictCta extends ConsumerStatefulWidget {
  const OptionVerdictCta({
    super.key,
    required this.structure,
    required this.ticker,
    this.verdictRef,
  });

  final OptionProposal structure;
  final String ticker;

  /// The Room run this structure came from, sent to `/open` so the position
  /// carries the verdict that produced it.
  final String? verdictRef;

  @override
  ConsumerState<OptionVerdictCta> createState() => _OptionVerdictCtaState();
}

class _OptionVerdictCtaState extends ConsumerState<OptionVerdictCta> {
  bool _busy = false;
  OptionOpenResult? _opened;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final opened = _opened;

    if (opened != null && opened.accepted) {
      return _OpenedPill(
        label: l.optionOpenedConfirmation(
          widget.structure.strategyLabel,
          '\$${_money.format((opened.netCost ?? 0).abs())}',
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ElevatedButton.icon(
          style: ElevatedButton.styleFrom(
            backgroundColor: AmiColors.hexCyan,
            foregroundColor: AmiColors.slate900,
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
          ),
          icon: _busy
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: AmiColors.slate900),
                )
              : const Icon(Icons.account_tree_outlined),
          label: Text(l.optionVerdictAcceptCta),
          onPressed: _busy ? null : _run,
        ),
        const SizedBox(height: AmiSpacing.xs),
        Text(
          l.optionVerdictCaption,
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }

  Future<void> _run() async {
    final accepted = await OptionProposalTicket.show(context, widget.structure);
    if (accepted != true || !mounted) return;

    setState(() => _busy = true);
    late final OptionRepriceResult repriced;
    try {
      final api = ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      repriced = await api.simOptionReprice(
        userId: userId,
        proposal: widget.structure,
      );
    } catch (_) {
      // A re-price that could not complete is rendered as exactly that — the
      // sheet's "AMI cannot price this right now" state, which carries no
      // confirm button. Deliberately NOT a fall-through to `/open`: the one
      // thing this step exists to prevent is opening at a price nobody checked,
      // and treating a failed check as permission to proceed would invert it.
      repriced = const OptionRepriceResult(
        repriced: false,
        compliance: OptionProposalCompliance(passed: false),
      );
    }
    if (!mounted) return;
    setState(() => _busy = false);

    final confirmed = await OptionRepriceSheet.show(
      context, repriced, ticker: widget.ticker,
    );
    if (confirmed != true || !mounted) return;

    setState(() => _busy = true);
    try {
      final api = ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      // The structure sent to `/open` is the one the RE-PRICE returned, not the
      // one the Room proposed — same legs either way, but reading it off the
      // fresher object keeps "what the user confirmed" and "what is opened" the
      // same object rather than two that happen to agree.
      final result = await api.simOptionOpen(
        userId: userId,
        proposal: repriced.structure ?? widget.structure,
        verdictRef: widget.verdictRef,
      );
      if (!mounted) return;
      setState(() {
        _busy = false;
        _opened = result;
      });
      if (result.accepted) {
        unawaited(ref.read(simNotifierProvider.notifier).refresh());
      } else {
        _showRefusal(result);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() => _busy = false);
      _showRefusal(null);
    }
  }

  /// The server said no, or the call failed. Either way nothing opened.
  ///
  /// The message leads with that fact rather than with the reason: a user who
  /// tapped a money-moving button needs to know first that no money moved, and
  /// the reason second.
  void _showRefusal(OptionOpenResult? result) {
    final l = AppLocalizations.of(context);
    final reason = [
      ...?result?.compliance.violations,
      ...?result?.compliance.notEvaluated,
    ].where((s) => s.trim().isNotEmpty).join(' ');
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: AmiColors.slate700,
        content: Text(
          reason.isEmpty ? l.optionRepriceFailedBody : reason,
          style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
        ),
      ),
    );
  }
}

class _OpenedPill extends StatelessWidget {
  const _OpenedPill({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        vertical: AmiSpacing.s + 4, horizontal: AmiSpacing.m,
      ),
      decoration: BoxDecoration(
        color: AmiColors.hexGreen.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexGreen, width: 1.5),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.check_circle, color: AmiColors.hexGreen, size: 20),
          const SizedBox(width: AmiSpacing.s),
          Flexible(
            child: Text(
              label,
              style: AmiTypography.labelMono.copyWith(
                color: AmiColors.hexGreen,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// CR177 UI — renders a stored `compliance_block` journal payload: the safety
/// floor refused a trade against the user's own mandate, and this card is the
/// durable account of WHY.
///
/// Payload-pure like `FindingSections`: everything shown was composed by the
/// backend at refusal time (`sim_trade_effects.record_compliance_block`), and
/// the widget recomputes nothing. It is a record of a refused decision, never
/// a trade result — the card carries no win/loss chrome, matching CR177 §4
/// ("a block has no win/loss and must never be rendered as either").
///
/// `isRenderable` guards the detail screen's typed branch: a payload without a
/// non-empty `blocked_by` (the load-bearing field — which rule stopped you)
/// falls through to the generic dump instead — raw but visible and honestly
/// labelled (CR040), never a confident card missing its own headline.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sharia.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sharia_verdict_banner.dart';
import 'package:flutter/material.dart';

class ComplianceBlockCard extends StatelessWidget {
  const ComplianceBlockCard({super.key, required this.payload});

  final Map<String, dynamic> payload;

  /// True only when the payload names the rule that refused the trade.
  /// Anything less renders via the generic payload dump.
  static bool isRenderable(Map<String, dynamic> payload) {
    final blockedBy = payload['blocked_by'];
    return blockedBy is String && blockedBy.trim().isNotEmpty;
  }

  static List<String> _stringList(Object? raw) => raw is List
      ? raw.whereType<String>().where((s) => s.trim().isNotEmpty).toList()
      : const [];

  /// `source` is 'ticket' or 'resting_order' — with no request in the sweep's
  /// call stack, the entry itself must say which path refused. An unknown slug
  /// renders raw rather than being guessed into a known label.
  static String? _sourceLabel(AppLocalizations l, Object? source) {
    switch (source) {
      case 'ticket':
        return l.journalBlockedSourceTicket;
      case 'resting_order':
        return l.journalBlockedSourceResting;
    }
    return source is String && source.trim().isNotEmpty ? source : null;
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final blockedBy = (payload['blocked_by'] as String).toUpperCase();
    final violations = _stringList(payload['violations']);
    final advisories = _stringList(payload['advisories']);
    final request = payload['request'];
    final orderType = request is Map ? request['order_type'] : null;
    final sourceLabel = _sourceLabel(l, payload['source']);
    final shariaVerdict = payload['sharia_verdict'] is Map
        ? ShariaVerdict.fromJson(
            (payload['sharia_verdict'] as Map).cast<String, dynamic>())
        : null;
    final classificationVerdicts = payload['classification_verdicts'] is List
        ? (payload['classification_verdicts'] as List).whereType<Map>().toList()
        : const <Map>[];

    final rows = <({String label, String value, bool mono})>[
      (label: l.journalBlockedRuleLabel, value: blockedBy, mono: true),
      if (orderType is String && orderType.trim().isNotEmpty)
        (
          label: l.journalBlockedOrderTypeLabel,
          value: orderType.toUpperCase(),
          mono: false,
        ),
      if (sourceLabel != null)
        (label: l.journalBlockedSourceLabel, value: sourceLabel, mono: false),
    ];

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexRed),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.lock, color: AmiColors.hexRed, size: 16),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  l.journalBlockedHeading,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.hexRed, fontSize: 11),
                ),
              ),
            ],
          ),
          if (violations.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.m),
            Text(l.journalBlockedViolationsLabel,
                style: AmiTypography.labelMono.copyWith(fontSize: 11)),
            const SizedBox(height: AmiSpacing.xs),
            // Backend-composed English sentences, rendered raw — the same
            // treatment the trade ticket's refusal banner gives them.
            for (final v in violations)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text('•  $v', style: AmiTypography.body),
              ),
          ],
          const SizedBox(height: AmiSpacing.m),
          _KVPanel(rows: rows),
          if (shariaVerdict != null) ...[
            const SizedBox(height: AmiSpacing.m),
            ShariaVerdictBanner(verdict: shariaVerdict),
          ],
          // No Dart model exists for classification verdicts — compact
          // provenance lines from the raw maps, absent fields shown as
          // absent rather than invented.
          for (final cv in classificationVerdicts) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              [cv['kind'], cv['status'], cv['source'], cv['as_of']]
                  .whereType<Object>()
                  .map((v) => '$v')
                  .join(' · '),
              style: AmiTypography.caption,
            ),
          ],
          if (advisories.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.m),
            Text(l.journalBlockedAdvisoriesLabel,
                style: AmiTypography.labelMono.copyWith(fontSize: 11)),
            const SizedBox(height: AmiSpacing.xs),
            for (final a in advisories)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(a, style: AmiTypography.caption),
              ),
          ],
        ],
      ),
    );
  }
}

/// Label/value panel matching the detail screen's private `_KVBox` chrome —
/// cloned rather than shared because `_KVBox` is private to the screen and
/// this card must stay pumpable without it.
class _KVPanel extends StatelessWidget {
  const _KVPanel({required this.rows});

  final List<({String label, String value, bool mono})> rows;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final row in rows)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 110,
                    child: Text(row.label.toUpperCase(),
                        style: AmiTypography.labelMono.copyWith(fontSize: 11)),
                  ),
                  Expanded(
                    child: Text(
                      row.value,
                      style: row.mono
                          ? AmiTypography.labelMono
                              .copyWith(color: AmiColors.textHigh)
                          : AmiTypography.body,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

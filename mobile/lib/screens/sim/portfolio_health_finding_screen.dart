/// CR136 M09 — the Finding (SCREEN_DESIGNS 21): POSTs generation, renders the STORED head disclosure + §F1–§F5 via FindingSections. Never recomputes.
///
/// Two hosts, one renderer. This screen shows the POST envelope's `sections`;
/// the Journal detail branch (M08) shows the same keys read back out of the
/// stored entry. Both go through `FindingSections`, so a Finding read from the
/// journal a month later is byte-identical to the one the user saw when it was
/// written — which is the whole point of storing the rendered report rather
/// than the inputs to it.
///
/// The error panels key on the server's own `detail.code`, never on the status
/// code alone: 402 and 429 are different refusals with different remedies, and
/// a client that guessed would eventually offer an upgrade to a subscriber who
/// had merely hit today's cap.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/portfolio_health.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:ami_trade/widgets/journal/finding_sections.dart';
import 'package:ami_trade/widgets/portfolio_health/health_chrome.dart';
import 'package:ami_trade/widgets/paywall/upgrade_paywall.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class PortfolioHealthFindingScreen extends ConsumerWidget {
  const PortfolioHealthFindingScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final async = ref.watch(healthFindingProvider);

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(title: Text(l.findingScreenTitle)),
      body: healthFadeIn(
        context,
        async.when(
          loading: () => const Center(child: HexPulseLoader()),
          error: (e, __) => _FindingErrorPanel(error: e),
          data: (finding) => _findingBody(context, ref, finding),
        ),
      ),
    );
  }

  Widget _findingBody(
    BuildContext context,
    WidgetRef ref,
    HealthFinding finding,
  ) {
    // The stored payload shape, verbatim — the same map the journal host
    // passes, so there is one contract rather than an adapter that could drift.
    final payload = <String, dynamic>{'sections': finding.sections};
    if (!FindingSections.isRenderable(payload)) {
      // Unreachable while M08's write-time validator holds (it refuses an
      // empty head). Defence in depth for F19: a Finding rendered without its
      // disclosures is a report that outlives every caveat that was true when
      // it was written, so it does not render at all.
      return _FindingErrorPanel(error: null);
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: FindingSections(payload: payload),
    );
  }
}

/// The four refusal panels. Amber only for the engine's own 409 refusal —
/// slate for the gate states, which are commercial, not a system fault.
class _FindingErrorPanel extends ConsumerWidget {
  const _FindingErrorPanel({required this.error});

  final Object? error;

  static Map<String, dynamic> _detail(Object? error) {
    if (error is! DioException) return const {};
    final data = error.response?.data;
    if (data is! Map) return const {};
    final detail = data['detail'];
    return detail is Map ? Map<String, dynamic>.from(detail) : const {};
  }

  String _resetDateStr(WidgetRef ref) {
    final r = ref.read(mandateNotifierProvider).mandate?.creditsResetAt;
    if (r == null) return 'the 1st';
    return '${r.year}-${r.month.toString().padLeft(2, '0')}-'
        '${r.day.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final detail = _detail(error);
    final code = detail['code'] as String?;

    switch (code) {
      case 'portfolio_health_unavailable':
        return _Panel(
          accent: AmiColors.hexAmber,
          body: l.findingUnavailableBody,
        );

      case 'portfolio_health_gate_closed':
        return _Panel(
          accent: AmiColors.slate700,
          body: l.portfolioHealthUpgradeBody,
          action: HexButton(
            label: l.portfolioHealthUpgradeCta,
            color: AmiColors.hexBlue,
            variant: HexButtonVariant.outlined,
            onPressed: () => showUpgradeSheet(
              context,
              resetDateLabel: _resetDateStr(ref),
              onPurchased: () => ref.invalidate(healthFindingProvider),
            ),
          ),
        );

      case 'portfolio_health_daily_cap_reached':
        // The numbers come from the server's own gate dict, not from the
        // card's copy of it — the request that was just refused is the
        // authority on why.
        final gate = HealthGateStatus.fromJson(
          (detail['gate'] as Map?)?.cast<String, dynamic>() ?? const {},
        );
        return _Panel(
          accent: AmiColors.slate700,
          body: l.portfolioHealthDailyCapNote(
            '\u2066${gate.dailyUsed}\u2069',
            '\u2066${gate.dailyCap}\u2069',
          ),
        );

      default:
        return _Panel(
          accent: AmiColors.slate700,
          body: l.portfolioHealthErrorBody,
          onTap: () => ref.invalidate(healthFindingProvider),
        );
    }
  }
}

class _Panel extends StatelessWidget {
  const _Panel({
    required this.accent,
    required this.body,
    this.action,
    this.onTap,
  });

  final Color accent;
  final String body;
  final Widget? action;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    // Dashed, like the card's non-populated states: none of these four panels
    // is a report, and the frame says so before the copy does.
    final content = HealthDashedBox(
      borderColor: accent,
      fill: AmiColors.slate800,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(body, style: AmiTypography.body),
          if (action != null) ...[
            const SizedBox(height: AmiSpacing.m),
            SizedBox(width: double.infinity, child: action),
          ],
        ],
      ),
    );

    return Padding(
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: Align(
        alignment: Alignment.topCenter,
        child: onTap == null
            ? content
            : InkWell(
                onTap: onTap,
                borderRadius: BorderRadius.circular(AmiRadii.card),
                child: content,
              ),
      ),
    );
  }
}

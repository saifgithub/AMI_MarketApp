/// Coach Your Agent — version history.
///
/// Lists every saved UserOverlay version with plain-English summary, active
/// marker, and a Rollback button. Floor Pass keeps 5, Trader 20, Floor
/// Manager unlimited (enforced server-side).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/brief.dart';
import 'package:ami_trade/state/brief_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

class BriefHistoryScreen extends ConsumerStatefulWidget {
  const BriefHistoryScreen({super.key, required this.agent});

  final Agent agent;

  @override
  ConsumerState<BriefHistoryScreen> createState() => _BriefHistoryScreenState();
}

class _BriefHistoryScreenState extends ConsumerState<BriefHistoryScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() =>
        ref.read(briefNotifierProvider(widget.agent.id).notifier).loadHistory());
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(briefNotifierProvider(widget.agent.id));
    final history = state.history;

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(agent: widget.agent),
            Expanded(child: _body(state)),
            if (history != null)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AmiSpacing.m),
                color: AmiColors.glassChrome,
                child: Text(
                  history.editsRemaining == null
                      ? AppLocalizations.of(context)
                          .briefHistoryEditsUnlimited(history.editCount)
                      : AppLocalizations.of(context).briefHistoryEditsRemaining(
                          history.editCount, history.editsRemaining!),
                  style: AmiTypography.caption,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _body(BriefState state) {
    final history = state.history;
    if (history == null) {
      return Center(
        child: CircularProgressIndicator(color: widget.agent.color),
      );
    }
    if (history.versions.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.history, color: AmiColors.textLow, size: 48),
            const SizedBox(height: AmiSpacing.m),
            Text(
              AppLocalizations.of(context).briefHistoryEmpty,
              textAlign: TextAlign.center,
              style: AmiTypography.body,
            ),
          ],
        ),
      );
    }

    final reversed = history.versions.reversed.toList();
    return ListView.separated(
      padding: const EdgeInsets.all(AmiSpacing.m),
      itemCount: reversed.length,
      separatorBuilder: (_, __) => const SizedBox(height: AmiSpacing.s),
      itemBuilder: (context, i) {
        final v = reversed[i];
        final isActive = v.version == history.activeVersion;
        return _VersionCard(
          agent: widget.agent,
          overlay: v,
          isActive: isActive,
          onRollback: isActive
              ? null
              : () async {
                  final l = AppLocalizations.of(context);
                  final confirmed = await showDialog<bool>(
                    context: context,
                    builder: (_) => AlertDialog(
                      backgroundColor: AmiColors.slate800,
                      title: Text(l.briefHistoryRollbackTitle(v.version),
                          style: AmiTypography.h4),
                      content: Text(
                        l.briefHistoryRollbackBody(v.version),
                        style: AmiTypography.body,
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.of(context).pop(false),
                          child: Text(l.actionCancel),
                        ),
                        ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: widget.agent.color,
                            foregroundColor: AmiColors.slate900,
                          ),
                          onPressed: () => Navigator.of(context).pop(true),
                          child: Text(l.briefHistoryRollback),
                        ),
                      ],
                    ),
                  );
                  if (confirmed == true && mounted) {
                    await ref
                        .read(briefNotifierProvider(widget.agent.id).notifier)
                        .rollback(v.version);
                  }
                },
        );
      },
    );
  }
}


class _Header extends StatelessWidget {
  const _Header({required this.agent});
  final Agent agent;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 72,
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.s),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back, color: AmiColors.textHigh),
            onPressed: () => Navigator.of(context).pop(),
          ),
          HexAvatar(label: agent.abbreviation, color: agent.color, size: 44),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(AppLocalizations.of(context)
                        .briefHistoryHeading(agent.displayName.toUpperCase()),
                    style: AmiTypography.labelMono.copyWith(color: agent.color)),
                Text(AppLocalizations.of(context).briefHistorySubtitle,
                    style: AmiTypography.caption),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


class _VersionCard extends StatelessWidget {
  const _VersionCard({
    required this.agent,
    required this.overlay,
    required this.isActive,
    required this.onRollback,
  });

  final Agent agent;
  final UserOverlay overlay;
  final bool isActive;
  final VoidCallback? onRollback;

  @override
  Widget build(BuildContext context) {
    final df = DateFormat('MMM d, h:mm a').format(overlay.createdAt.toLocal());
    return Container(
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(
          color: isActive ? agent.color : AmiColors.slate700,
          width: isActive ? 1.5 : 1.0,
        ),
      ),
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('v${overlay.version}',
                  style: AmiTypography.statSmall.copyWith(
                      color: isActive ? agent.color : AmiColors.textHigh)),
              const SizedBox(width: AmiSpacing.s),
              if (isActive)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: agent.color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(AppLocalizations.of(context).briefHistoryActiveBadge,
                      style: AmiTypography.labelMono.copyWith(
                          color: agent.color, fontSize: 10)),
                ),
              const Spacer(),
              Text(df, style: AmiTypography.caption),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(overlay.plainEnglish, style: AmiTypography.body),
          const SizedBox(height: AmiSpacing.s),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AmiSpacing.s),
            decoration: BoxDecoration(
              color: AmiColors.slate900,
              borderRadius: BorderRadius.circular(AmiRadii.card),
              border: Border.all(color: AmiColors.slate700),
            ),
            child: Text(overlay.content, style: AmiTypography.stream),
          ),
          if (!isActive) ...[
            const SizedBox(height: AmiSpacing.s),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                icon: const Icon(Icons.restore, size: 16),
                label: Text(AppLocalizations.of(context).briefHistoryRollbackToThis),
                style: TextButton.styleFrom(foregroundColor: agent.color),
                onPressed: onRollback,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Decision Journal — list view.
///
/// Shows every captured entry (1-on-1, Coach proposal, lesson completion,
/// agent unlock). Filter chips for entry type. Tap → detail screen.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/screens/journal/journal_detail_screen.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

class JournalScreen extends ConsumerWidget {
  const JournalScreen({super.key});

  /// Filter chip definitions. Labels are resolved at render time via
  /// AppLocalizations so the row reacts to locale switches.
  static List<({JournalEntryType? type, String label})> filtersFor(
      AppLocalizations l) {
    return [
      (type: null, label: l.journalFilterAll),
      (type: JournalEntryType.oneOnOne, label: l.journalFilterOneOnOne),
      (type: JournalEntryType.agentCoach, label: l.journalFilterCoach),
      (type: JournalEntryType.lessonComplete, label: l.journalFilterLessons),
      (type: JournalEntryType.agentUnlock, label: l.journalFilterUnlocks),
    ];
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(journalNotifierProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            const _Header(),
            _FilterRow(active: state.filterType),
            if (state.retentionDays != null)
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AmiSpacing.m, vertical: AmiSpacing.xs,
                ),
                child: Text(
                  AppLocalizations.of(context)
                      .journalRetentionWarning(state.retentionDays!),
                  style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
                ),
              ),
            Expanded(child: _body(context, ref, state)),
          ],
        ),
      ),
    );
  }

  Widget _body(BuildContext context, WidgetRef ref, JournalState state) {
    if (state.loading && state.entries.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.error != null && state.entries.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Center(
          child: Text(state.error!, style: AmiTypography.body),
        ),
      );
    }
    if (state.entries.isEmpty) {
      return _EmptyState();
    }
    return RefreshIndicator(
      onRefresh: () => ref
          .read(journalNotifierProvider.notifier)
          .refresh(filterType: state.filterType),
      color: AmiColors.hexBlue,
      child: ListView.separated(
        padding: const EdgeInsets.all(AmiSpacing.m),
        itemCount: state.entries.length,
        separatorBuilder: (_, __) => const SizedBox(height: AmiSpacing.s),
        itemBuilder: (context, i) {
          final e = state.entries[i];
          return _EntryCard(
            entry: e,
            onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
              builder: (_) => JournalDetailScreen(entryId: e.id),
            )),
          );
        },
      ),
    );
  }
}


class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Row(
        children: [
          Text(AppLocalizations.of(context).journalHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
          const Spacer(),
        ],
      ),
    );
  }
}


class _FilterRow extends ConsumerWidget {
  const _FilterRow({this.active});
  final JournalEntryType? active;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m, vertical: AmiSpacing.s),
      child: Row(
        children: [
          for (final f in JournalScreen.filtersFor(l))
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                label: Text(f.label),
                labelStyle: AmiTypography.labelMono.copyWith(
                  fontSize: 11,
                  color: f.type == active ? AmiColors.hexBlue : AmiColors.textMed,
                ),
                selected: f.type == active,
                onSelected: (_) => ref
                    .read(journalNotifierProvider.notifier)
                    .setFilter(f.type),
                backgroundColor: AmiColors.slate800,
                selectedColor: AmiColors.hexBlue.withValues(alpha: 0.2),
                side: BorderSide(
                  color: f.type == active ? AmiColors.hexBlue : AmiColors.slate700,
                ),
              ),
            ),
        ],
      ),
    );
  }
}


class _EmptyState extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.all(AmiSpacing.xl),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.menu_book_outlined, color: AmiColors.textLow, size: 48),
            const SizedBox(height: AmiSpacing.m),
            Text(l.journalEmptyTitle, style: AmiTypography.h4),
            const SizedBox(height: AmiSpacing.xs),
            Text(
              l.journalEmptyBody,
              textAlign: TextAlign.center,
              style: AmiTypography.body.copyWith(color: AmiColors.textLow),
            ),
          ],
        ),
      ),
    );
  }
}


class _EntryCard extends StatelessWidget {
  const _EntryCard({required this.entry, required this.onTap});
  final JournalEntry entry;
  final VoidCallback onTap;

  Color get _accent {
    switch (entry.entryType) {
      case JournalEntryType.oneOnOne:
        return AmiColors.hexBlue;
      case JournalEntryType.agentCoach:
        return AmiColors.hexPurple;
      case JournalEntryType.lessonComplete:
        return AmiColors.hexGreen;
      case JournalEntryType.agentUnlock:
        return AmiColors.hexAmber;
      case JournalEntryType.simTrade:
        return AmiColors.hexCyan;
      case JournalEntryType.mandateEdit:
        return AmiColors.hexPink;
      case JournalEntryType.driftAlert:
        return AmiColors.hexRed;
      case JournalEntryType.roomRun:
        return AmiColors.hexBlue;
    }
  }

  String _label(AppLocalizations l) {
    switch (entry.entryType) {
      case JournalEntryType.oneOnOne:
        return l.journalEntryTypeOneOnOne;
      case JournalEntryType.agentCoach:
        return l.journalEntryTypeCoach;
      case JournalEntryType.lessonComplete:
        return l.journalEntryTypeLesson;
      case JournalEntryType.agentUnlock:
        return l.journalEntryTypeUnlock;
      case JournalEntryType.simTrade:
        return l.journalEntryTypeTrade;
      case JournalEntryType.mandateEdit:
        return l.journalEntryTypeMandate;
      case JournalEntryType.driftAlert:
        return l.journalEntryTypeDrift;
      case JournalEntryType.roomRun:
        return l.journalEntryTypeRoom;
    }
  }

  @override
  Widget build(BuildContext context) {
    final df = DateFormat('MMM d, h:mm a').format(entry.createdAt.toLocal());
    final agentLabels = entry.agentsInvolved
        .map((id) => agentById(id).abbreviation)
        .toList();
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AmiRadii.card),
      child: Container(
        padding: const EdgeInsets.all(AmiSpacing.m),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.slate700),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: _accent.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(_label(AppLocalizations.of(context)),
                      style: AmiTypography.labelMono.copyWith(
                          color: _accent, fontSize: 10)),
                ),
                if (entry.ticker != null) ...[
                  const SizedBox(width: AmiSpacing.s),
                  Text(entry.ticker!,
                      style: AmiTypography.labelMono.copyWith(fontSize: 11)),
                ],
                const Spacer(),
                Text(df, style: AmiTypography.caption),
              ],
            ),
            const SizedBox(height: AmiSpacing.xs),
            Text(entry.title, style: AmiTypography.h4),
            if (entry.summary != null) ...[
              const SizedBox(height: 2),
              Text(
                entry.summary!,
                style: AmiTypography.body.copyWith(color: AmiColors.textLow),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            if (agentLabels.isNotEmpty) ...[
              const SizedBox(height: AmiSpacing.xs),
              Wrap(
                spacing: 4,
                children: agentLabels
                    .map((l) => Text(l,
                        style: AmiTypography.labelMono.copyWith(
                            fontSize: 10, color: AmiColors.textLow)))
                    .toList(),
              ),
            ],
            if (entry.userNote != null && entry.userNote!.isNotEmpty) ...[
              const SizedBox(height: AmiSpacing.xs),
              Container(
                padding: const EdgeInsets.all(AmiSpacing.xs),
                decoration: BoxDecoration(
                  color: AmiColors.slate900,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '💬 ${entry.userNote}',
                  style: AmiTypography.caption,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

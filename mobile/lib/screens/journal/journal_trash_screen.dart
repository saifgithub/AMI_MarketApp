/// Decision Journal — Trash.
///
/// Lists journal entries that were soft-deleted in the last 30 days,
/// most-recently-deleted first. Each row carries a RESTORE button that
/// calls the existing /v1/journal/{u}/entry/{e}/restore endpoint.
///
/// Older soft-deleted rows still exist in Postgres but are never
/// surfaced here — TRASH_VISIBLE_DAYS=30 lives on the backend. Recovery
/// past that point is admin-only (psql or direct API call).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class JournalTrashScreen extends ConsumerStatefulWidget {
  const JournalTrashScreen({super.key});

  @override
  ConsumerState<JournalTrashScreen> createState() => _JournalTrashScreenState();
}

class _JournalTrashScreenState extends ConsumerState<JournalTrashScreen> {
  @override
  void initState() {
    super.initState();
    // Fire the fetch on first paint so we always show fresh data when
    // the user navigates here.
    Future.microtask(
      () => ref.read(journalTrashNotifierProvider.notifier).refresh(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(journalTrashNotifierProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            const _Header(),
            Expanded(child: _body(context, state)),
          ],
        ),
      ),
    );
  }

  Widget _body(BuildContext context, JournalTrashState state) {
    if (state.loading && state.entries.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.error != null && state.entries.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Center(child: Text(state.error!, style: AmiTypography.body)),
      );
    }
    if (state.entries.isEmpty) {
      return _EmptyState();
    }
    final l = AppLocalizations.of(context);
    return RefreshIndicator(
      onRefresh: () =>
          ref.read(journalTrashNotifierProvider.notifier).refresh(),
      color: AmiColors.hexBlue,
      child: ListView.separated(
        padding: const EdgeInsets.all(AmiSpacing.m),
        itemCount: state.entries.length + 1, // +1 for the footer caption
        separatorBuilder: (_, __) => const SizedBox(height: AmiSpacing.s),
        itemBuilder: (context, i) {
          if (i == state.entries.length) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: AmiSpacing.m),
              child: Center(
                child: Text(
                  l.journalTrashWindowNote,
                  style: AmiTypography.caption,
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }
          final e = state.entries[i];
          return _TrashCard(
            entry: e,
            onRestore: () async {
              // Capture the messenger before the async gap so the
              // linter is happy and we don't risk a stale context.
              final messenger = ScaffoldMessenger.of(context);
              final restoredLabel = l.journalEntryRestored;
              await ref
                  .read(journalTrashNotifierProvider.notifier)
                  .restore(e.id);
              if (!mounted) return;
              messenger.showSnackBar(SnackBar(
                content: Text(restoredLabel),
                duration: const Duration(seconds: 2),
              ));
            },
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
          Text(
            AppLocalizations.of(context).journalTrashHeading,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue),
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
            const Icon(Icons.delete_outline,
                color: AmiColors.textLow, size: 48),
            const SizedBox(height: AmiSpacing.m),
            Text(l.journalTrashEmpty,
                style: AmiTypography.body
                    .copyWith(color: AmiColors.textLow),
                textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}


class _TrashCard extends StatelessWidget {
  const _TrashCard({required this.entry, required this.onRestore});
  final JournalEntry entry;
  final VoidCallback onRestore;

  String _ago(DateTime when) {
    final d = DateTime.now().difference(when);
    if (d.inMinutes < 1) return 'just now';
    if (d.inMinutes < 60) return '${d.inMinutes}m ago';
    if (d.inHours < 24) return '${d.inHours}h ago';
    return '${d.inDays}d ago';
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final deletedAgo = entry.deletedAt == null
        ? ''
        : l.journalDeletedAgo(_ago(entry.deletedAt!.toLocal()));
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(entry.title,
                    style: AmiTypography.h4,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis),
                if (entry.summary != null) ...[
                  const SizedBox(height: 2),
                  Text(entry.summary!,
                      style: AmiTypography.body
                          .copyWith(color: AmiColors.textLow),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis),
                ],
                const SizedBox(height: AmiSpacing.xs),
                Text(deletedAgo, style: AmiTypography.caption),
              ],
            ),
          ),
          const SizedBox(width: AmiSpacing.s),
          TextButton(
            onPressed: onRestore,
            style: TextButton.styleFrom(
              foregroundColor: AmiColors.hexGreen,
              padding: const EdgeInsets.symmetric(
                  horizontal: AmiSpacing.s, vertical: 4),
            ),
            child: Text(l.journalRestoreEntry,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.hexGreen, fontSize: 11)),
          ),
        ],
      ),
    );
  }
}

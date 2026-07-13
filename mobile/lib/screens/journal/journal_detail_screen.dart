/// Decision Journal — single entry detail.
///
/// Shows the full payload (1-on-1 transcript, Coach proposal markdown, etc.)
/// and lets the user attach a note + tags + outcome.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

class JournalDetailScreen extends ConsumerStatefulWidget {
  const JournalDetailScreen({super.key, required this.entryId});

  final String entryId;

  @override
  ConsumerState<JournalDetailScreen> createState() => _JournalDetailScreenState();
}

class _JournalDetailScreenState extends ConsumerState<JournalDetailScreen> {
  final _noteCtrl = TextEditingController();
  String? _currentOutcome;
  bool _initialised = false;

  @override
  void dispose() {
    _noteCtrl.dispose();
    super.dispose();
  }

  void _initFrom(JournalEntry entry) {
    if (_initialised) return;
    _initialised = true;
    _noteCtrl.text = entry.userNote ?? '';
    _currentOutcome = entry.outcome;
  }

  Future<void> _save() async {
    await ref.read(journalNotifierProvider.notifier).annotate(
      entryId: widget.entryId,
      note: _noteCtrl.text,
      outcome: _currentOutcome,
    );
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).journalNoteSaved)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(journalNotifierProvider);
    final l = AppLocalizations.of(context);
    final entry =
        state.entries.firstWhere((e) => e.id == widget.entryId, orElse: () =>
            JournalEntry(
              id: widget.entryId,
              userId: '',
              entryType: JournalEntryType.oneOnOne,
              title: l.journalDetailLoading,
              createdAt: DateTime.now(),
              agentsInvolved: const [],
              tags: const [],
            ));
    _initFrom(entry);

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(entry: entry),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(AmiSpacing.m),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(entry.title, style: AmiTypography.h3),
                    const SizedBox(height: AmiSpacing.xs),
                    Text(
                      DateFormat('EEEE, MMM d • h:mm a')
                          .format(entry.createdAt.toLocal()),
                      style: AmiTypography.caption,
                    ),
                    if (entry.agentsInvolved.isNotEmpty) ...[
                      const SizedBox(height: AmiSpacing.s),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final id in entry.agentsInvolved)
                            _AgentPill(agentId: id),
                        ],
                      ),
                    ],
                    const SizedBox(height: AmiSpacing.l),
                    if (entry.summary != null) ...[
                      Text(entry.summary!,
                          style: AmiTypography.body.copyWith(color: AmiColors.textMed)),
                      const SizedBox(height: AmiSpacing.m),
                    ],
                    if (entry.payload.isNotEmpty)
                      _PayloadBlock(payload: entry.payload, entryType: entry.entryType),
                    const SizedBox(height: AmiSpacing.l),
                    _NoteEditor(
                      controller: _noteCtrl,
                      outcome: _currentOutcome,
                      onOutcomeChange: (v) => setState(() => _currentOutcome = v),
                      onSave: _save,
                    ),
                    const SizedBox(height: AmiSpacing.xxl),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}


class _Header extends StatelessWidget {
  const _Header({required this.entry});
  final JournalEntry entry;

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
          Text(AppLocalizations.of(context).journalDetailHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
        ],
      ),
    );
  }
}


class _AgentPill extends StatelessWidget {
  const _AgentPill({required this.agentId});
  final String agentId;

  @override
  Widget build(BuildContext context) {
    final a = agentById(agentId);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: a.color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: a.color),
      ),
      child: Text(a.displayName.toUpperCase(),
          style: AmiTypography.labelMono.copyWith(color: a.color, fontSize: 11)),
    );
  }
}


class _PayloadBlock extends StatelessWidget {
  const _PayloadBlock({required this.payload, required this.entryType});
  final Map<String, dynamic> payload;
  final JournalEntryType entryType;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final children = <Widget>[];
    if (entryType == JournalEntryType.oneOnOne) {
      final user = payload['user_message'] as String?;
      final reply = payload['assistant_reply'] as String?;
      if (user != null) children.add(_Block(label: l.journalDetailBlockYou, body: user));
      if (reply != null) children.add(_Block(label: l.journalDetailBlockAgent, body: reply));
    } else if (entryType == JournalEntryType.agentCoach) {
      final v = payload['version'];
      final overlay = payload['overlay'] as String?;
      if (v != null) {
        final version = v is int ? v : int.tryParse('$v') ?? 0;
        children.add(Text(l.journalDetailSavedAsVersion(version),
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexPurple)));
        children.add(const SizedBox(height: AmiSpacing.s));
      }
      if (overlay != null) children.add(_Block(label: l.journalDetailBlockOverlay, body: overlay));
    } else if (entryType == JournalEntryType.simTrade) {
      final t = (payload['trade'] as Map?)?.cast<String, dynamic>();
      if (t != null) {
        // Show fields the title/summary don't already cover: horizon,
        // status, timestamps, close info, P&L, linked verdict. Skip side,
        // quantity, ticker, entry/stop/target (already in the header).
        final horizonDays = t['horizon_days'];
        final status = (t['status'] as String?)?.toUpperCase();
        final openedAt = _formatJournalTs(t['opened_at'] as String?);
        final closedAt = _formatJournalTs(t['closed_at'] as String?);
        final closedPrice = t['closed_price'];
        final realisedPnl = t['realised_pnl'];
        final verdictRef = t['verdict_ref'] as String?;
        final rows = <_KV>[];
        if (horizonDays != null) rows.add(_KV('Horizon', '$horizonDays days'));
        if (status != null) rows.add(_KV('Status', status));
        if (openedAt != null) rows.add(_KV('Opened at', openedAt));
        if (closedAt != null) rows.add(_KV('Closed at', closedAt));
        if (closedPrice is num) {
          rows.add(_KV('Closed price', '\$${closedPrice.toStringAsFixed(2)}'));
        }
        if (realisedPnl is num && realisedPnl != 0) {
          final sign = realisedPnl >= 0 ? '+' : '';
          rows.add(_KV('Realised P&L', '$sign\$${realisedPnl.toStringAsFixed(2)}'));
        }
        if (verdictRef != null && verdictRef.isNotEmpty) {
          // First 8 chars match the short_id surfaced in the bug-report UI.
          rows.add(_KV('From verdict', verdictRef.substring(0, 8)));
        } else {
          // Bug d5717660: trades placed without a Convene the Room verdict
          // are surfaced so the user (or future self) can distinguish
          // AI-backed decisions from gut trades.
          rows.add(_KV('AI advice', 'Without — manual trade'));
        }
        if (rows.isNotEmpty) {
          children.add(Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AmiSpacing.s),
            decoration: BoxDecoration(
              color: AmiColors.slate800,
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
                          child: Text(row.value, style: AmiTypography.body),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ));
        }
      }
    } else if (entryType == JournalEntryType.roomRun) {
      final v = (payload['verdict'] as Map?)?.cast<String, dynamic>();
      if (v != null) {
        final action = v['action'] as String? ?? '—';
        final verdictColor = action == 'APPROVE'
            ? AmiColors.hexGreen
            : action == 'PASS'
                ? AmiColors.slate500
                : AmiColors.hexAmber;
        children.add(Text(l.journalDetailVerdictLine(action),
            style: AmiTypography.labelMono.copyWith(color: verdictColor)));
        final reason = v['reason'] as String? ?? '';
        if (reason.isNotEmpty) {
          children.add(const SizedBox(height: 4));
          children.add(Text(reason, style: AmiTypography.body));
        }
        children.add(const SizedBox(height: AmiSpacing.s));
      }
      final transcript = (payload['transcript'] as List?) ?? const [];
      for (final m in transcript) {
        final mm = (m as Map).cast<String, dynamic>();
        final agentId = (mm['agent_id'] as String?) ?? '';
        final content = (mm['content'] as String?) ?? '';
        final a = agentById(agentId);
        children.add(Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(a.abbreviation,
                  style: AmiTypography.labelMono.copyWith(color: a.color, fontSize: 11)),
              const SizedBox(height: 2),
              Text(content, style: AmiTypography.body),
            ],
          ),
        ));
      }
    } else {
      payload.forEach((k, v) {
        children.add(_Block(label: k.toUpperCase(), body: '$v'));
      });
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }
}


class _Block extends StatelessWidget {
  const _Block({required this.label, required this.body});
  final String label;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: AmiTypography.labelMono.copyWith(fontSize: 11)),
          const SizedBox(height: 2),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AmiSpacing.s),
            decoration: BoxDecoration(
              color: AmiColors.slate800,
              borderRadius: BorderRadius.circular(AmiRadii.card),
              border: Border.all(color: AmiColors.slate700),
            ),
            child: Text(body, style: AmiTypography.body),
          ),
        ],
      ),
    );
  }
}


class _NoteEditor extends StatelessWidget {
  const _NoteEditor({
    required this.controller,
    required this.outcome,
    required this.onOutcomeChange,
    required this.onSave,
  });

  final TextEditingController controller;
  final String? outcome;
  final ValueChanged<String?> onOutcomeChange;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final outcomeOptions = <(String, String, Color)>[
      ('win', l.journalNoteOutcomeWin, AmiColors.hexGreen),
      ('loss', l.journalNoteOutcomeLoss, AmiColors.hexRed),
      ('pending', l.journalNoteOutcomePending, AmiColors.hexAmber),
    ];
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.journalNoteHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
          const SizedBox(height: AmiSpacing.s),
          TextField(
            controller: controller,
            maxLines: 4,
            style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
            decoration: InputDecoration(
              hintText: l.journalNoteHint,
              hintStyle: AmiTypography.body.copyWith(color: AmiColors.textLow),
              filled: true,
              fillColor: AmiColors.slate900,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AmiRadii.card),
                borderSide: const BorderSide(color: AmiColors.slate700),
              ),
            ),
          ),
          const SizedBox(height: AmiSpacing.m),
          Row(
            children: [
              Text(l.journalNoteOutcome,
                  style: AmiTypography.labelMono.copyWith(fontSize: 11)),
              const SizedBox(width: AmiSpacing.m),
              for (final v in outcomeOptions)
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: ChoiceChip(
                    label: Text(v.$2),
                    labelStyle: AmiTypography.labelMono.copyWith(
                      fontSize: 10,
                      color: outcome == v.$1 ? v.$3 : AmiColors.textMed,
                    ),
                    selected: outcome == v.$1,
                    onSelected: (_) => onOutcomeChange(outcome == v.$1 ? null : v.$1),
                    selectedColor: v.$3.withValues(alpha: 0.2),
                    backgroundColor: AmiColors.slate900,
                    side: BorderSide(
                      color: outcome == v.$1 ? v.$3 : AmiColors.slate700,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AmiSpacing.m),
          Align(
            alignment: Alignment.centerRight,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AmiColors.hexBlue,
                foregroundColor: AmiColors.slate900,
              ),
              onPressed: onSave,
              child: Text(l.journalNoteSave),
            ),
          ),
        ],
      ),
    );
  }
}

class _KV {
  const _KV(this.label, this.value);
  final String label;
  final String value;
}

/// Format an ISO-8601 timestamp (e.g. "2026-05-17T06:40:50.438532+00:00")
/// into a short human-readable string in the device's local timezone.
/// Returns null if the input is null or unparseable.
String? _formatJournalTs(String? iso) {
  if (iso == null || iso.isEmpty) return null;
  try {
    final dt = DateTime.parse(iso).toLocal();
    return DateFormat('MMM d, h:mm a').format(dt);
  } catch (_) {
    return null;
  }
}

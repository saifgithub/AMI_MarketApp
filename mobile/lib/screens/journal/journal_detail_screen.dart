/// Decision Journal — single entry detail.
///
/// Shows the full payload (1-on-1 transcript, Coach proposal markdown, etc.)
/// and lets the user attach a note + tags + outcome.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/room_board_mappers.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/room_view_mode_provider.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/room/room_board.dart';
import 'package:ami_trade/widgets/room/room_transcript_rows.dart';
import 'package:ami_trade/widgets/room/room_view_mode_toggle.dart';
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
                    if (entry.payload.isNotEmpty) _PayloadBlock(entry: entry),
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
  const _PayloadBlock({required this.entry});

  /// The whole entry, not just the payload: a Room replay needs the ticker,
  /// the run date and the mandate version, and none of those are in the
  /// payload — they live on the entry row.
  final JournalEntry entry;

  Map<String, dynamic> get payload => entry.payload;
  JournalEntryType get entryType => entry.entryType;

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
      // CR106 / DEF143 — the Journal now replays a Room run through the SAME
      // widget the live Room renders, via a mapper (T-TWICE).
      //
      // What used to be here was 36 lines of a second, independent renderer
      // that never received CR098: `action == 'APPROVE' ? green : action ==
      // 'PASS' ? slate : amber` put `NO_VERDICT` in the reject bucket and
      // printed the raw enum, so a user could watch the PM's professional
      // refusal render correctly in the Room and then open the same run in the
      // Journal thirty seconds later and be told the thesis was turned down —
      // in the durable copy, which is the one that is wrong. It also never read
      // `opinions_not_included`, so a replay of a partial-roster run silently
      // asserted a full roster, and it emitted a bare `Text(content)` per line,
      // so `_PROSE_FORMAT`'s `**bold**` metrics reached the user as literal
      // asterisks.
      //
      // None of that can recur here, because there is no longer a second
      // renderer to fall behind.
      return _RoomRunReplay(entry: entry);
    } else {
      payload.forEach((k, v) {
        children.add(_Block(label: k.toUpperCase(), body: '$v'));
      });
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }
}


/// CR106 §3.4 — a saved Room run, replayed through the shared board.
///
/// Two things make this a **record**, not a setup, and both are structural
/// rather than a matter of copy:
///
///   - **No trade ticket, ever** (T-STALE). A June entry's `$118.20` entry
///     price is not a live setup; offering a one-tap ticket against it invites
///     a trade at a stale price. The actions are `SEE CHART` +
///     `RE-RUN WITH CURRENT MANDATE`, which is also what `screen_inventory.md`
///     already specifies for this screen.
///   - **The geometry is dated.** `RoomBoard` prints the run date under any
///     board it renders with `isRecord`.
///
/// The board degrades per ENTRY, off the payload the snapshot froze: no
/// `level_provenance` → the metric list and no ribbon; no stances → the comb's
/// one honest sentence. Nothing is inferred to fill a gap (T-BACKFILL).
class _RoomRunReplay extends ConsumerStatefulWidget {
  const _RoomRunReplay({required this.entry});
  final JournalEntry entry;

  @override
  ConsumerState<_RoomRunReplay> createState() => _RoomRunReplayState();
}

class _RoomRunReplayState extends ConsumerState<_RoomRunReplay> {
  /// Per-screen only. The Journal never writes `ami_room_view_mode` — see
  /// T-MODESIDE; only the segmented toggle does, and this screen's toggle is
  /// that same control.
  RoomViewMode? _sessionMode;
  String? _jumpAgentId;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final board = boardFromJournalEntry(widget.entry);
    if (board == null) {
      return Text(l.journalDetailLoading, style: AmiTypography.body);
    }
    final storedMode = ref.watch(roomViewModeProvider);
    final mode = _sessionMode ?? storedMode;
    final meta = board.meta;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // The Room's strip shows `41s · 3 CREDITS`; neither number was ever
        // serialised into the snapshot, so the record shows what it does have.
        RoomSubHeader(
          meta: l.journalStripMeta(
            (meta.modelTier ?? '—').toUpperCase(),
            meta.mandateVersion ?? 0,
          ),
          mode: mode,
          onModeChanged: (m) {
            setState(() => _sessionMode = null);
            ref.read(roomViewModeProvider.notifier).setMode(m);
          },
        ),
        const SizedBox(height: AmiSpacing.m),
        if (mode == RoomViewMode.board)
          RoomBoard(
            data: board,
            onVoiceTap: (voice) => showAgentPeekSheet(
              context,
              voice: voice,
              onReadFullDebate: () => setState(() {
                _sessionMode = RoomViewMode.transcript;
                _jumpAgentId = voice.agentId;
              }),
            ),
            footer: _RecordActions(entry: widget.entry),
          )
        else ...[
          RoomTranscriptRows(
            voices: transcriptVoicesFromJournalEntry(widget.entry),
            expandedAgentId: _jumpAgentId,
            highlightAgentId: _jumpAgentId,
          ),
          const SizedBox(height: AmiSpacing.m),
          _RecordActions(entry: widget.entry),
        ],
      ],
    );
  }
}

class _RecordActions extends StatelessWidget {
  const _RecordActions({required this.entry});
  final JournalEntry entry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final ticker = entry.ticker;
    if (ticker == null || ticker.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        OutlinedButton.icon(
          style: OutlinedButton.styleFrom(
            foregroundColor: AmiColors.hexCyan,
            side: const BorderSide(color: AmiColors.hexCyan),
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
          ),
          icon: const Icon(Icons.show_chart),
          label: Text(l.roomVerdictSeeChart),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => TickerDetailScreen(ticker: ticker),
            ),
          ),
        ),
        const SizedBox(height: AmiSpacing.s),
        // The honest counterpart to a trade ticket on a record: run the room
        // again under today's rules rather than acting on months-old prices.
        ElevatedButton.icon(
          style: ElevatedButton.styleFrom(
            backgroundColor: AmiColors.hexCyan,
            foregroundColor: AmiColors.slate900,
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
          ),
          icon: const Icon(Icons.groups_2_outlined),
          label: Text(l.journalRerunWithMandate),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => RoomScreen(ticker: ticker),
            ),
          ),
        ),
      ],
    );
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

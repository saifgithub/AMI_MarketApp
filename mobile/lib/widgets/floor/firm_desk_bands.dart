/// CR159 — "Your Firm" as desk-banded tiers (View A).
///
/// The 12 agents used to sit in one flat `Wrap`. This is the same roster with a
/// firm's structure: hierarchy by **vertical order and band labels, no drawn
/// connectors** (a real org chart is wide, a phone is narrow, and any tree
/// forces sideways scroll). Top to bottom: YOU, the CIO, the analyst desk,
/// research, execution + risk sharing a band, and the Concierge ("reports to
/// you").
///
/// Every group is derived from `Agent.desk` via [agentsOnDesk] — never from
/// list position (T-SLICE) — so a roster edit cannot silently mis-seat an
/// agent. The band header's count slot is reserved for a standing metric later
/// (hit-rate / override-rate); today it reads `filled/total`.
///
/// [AgentTile] lives here (and is re-exported by `your_firm_screen.dart`) so the
/// bands and the tile they draw are one unit; behaviour on tap is the caller's.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';

/// Hex edge used inside a band. Four tiles at [_tileWidth] fill a 320pt-wide
/// phone's content column exactly, so the analyst desk never wraps to 3 + 1.
const double _bandHexSize = 56;
const double _tileWidth = _bandHexSize + 16;

/// Width the Execution column gets when it shares a band with Risk — wide
/// enough for its header label at default text size.
const double _sharedLeadWidth = 104;
const double _sharedGap = AmiSpacing.m;

typedef AgentTapCallback = void Function(Agent agent, bool unlocked);

class FirmDeskBands extends StatelessWidget {
  const FirmDeskBands({
    super.key,
    required this.unlocked,
    required this.onTapAgent,
  });

  /// Agent ids the user has unlocked. The Concierge is never gated.
  final Set<String> unlocked;
  final AgentTapCallback onTapAgent;

  bool _isUnlocked(Agent a) =>
      a.desk == AgentDesk.concierge || unlocked.contains(a.id);

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final cio = agentsOnDesk(AgentDesk.officeOfCio);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _YouMarker(label: l.firmDeskYou),
        const SizedBox(height: AmiSpacing.s),
        _TileRow(agents: cio, isUnlocked: _isUnlocked, onTap: onTapAgent),
        const _BandRule(),
        _Band(
          desk: AgentDesk.analyst,
          label: l.firmDeskAnalyst,
          isUnlocked: _isUnlocked,
          onTap: onTapAgent,
        ),
        const _BandRule(),
        _Band(
          desk: AgentDesk.research,
          label: l.firmDeskResearch,
          isUnlocked: _isUnlocked,
          onTap: onTapAgent,
        ),
        const _BandRule(),
        _SharedBand(
          lead: AgentDesk.execution,
          leadLabel: l.firmDeskExecution,
          trail: AgentDesk.risk,
          trailLabel: l.firmDeskRisk,
          isUnlocked: _isUnlocked,
          onTap: onTapAgent,
        ),
        const _BandRule(),
        _Band(
          desk: AgentDesk.concierge,
          label: l.firmDeskConcierge,
          note: l.firmDeskConciergeNote,
          isUnlocked: _isUnlocked,
          onTap: onTapAgent,
        ),
      ],
    );
  }
}

class _YouMarker extends StatelessWidget {
  const _YouMarker({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    // The CEO marker is not an agent: no tap, no lock state, no color of any
    // family.
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        HexAvatar(label: 'YOU', color: AmiColors.hexBlue, size: 44),
        const SizedBox(height: 2),
        Text(label,
            textAlign: TextAlign.center,
            style: AmiTypography.labelMono
                .copyWith(fontSize: 10, color: AmiColors.textLow)),
      ],
    );
  }
}

class _BandRule extends StatelessWidget {
  const _BandRule();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: AmiSpacing.m),
        child: Divider(height: 1, thickness: 1, color: AmiColors.slate700),
      );
}

/// Label on the left, standing slot on the right (a `filled/total` count today).
class _BandHeader extends StatelessWidget {
  const _BandHeader({required this.label, required this.count, this.note});

  final String label;
  final String? count;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final style = AmiTypography.labelMono
        .copyWith(fontSize: 10, color: AmiColors.hexCyan);
    return Semantics(
      header: true,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(
              note == null ? label : '$label — $note',
              style: style,
            ),
          ),
          if (count != null) ...[
            const SizedBox(width: AmiSpacing.xs),
            Text(count!,
                style: style.copyWith(color: AmiColors.textMed)),
          ],
        ],
      ),
    );
  }
}

String _countFor(BuildContext context, List<Agent> agents,
    bool Function(Agent) isUnlocked) {
  final filled = agents.where(isUnlocked).length;
  return AppLocalizations.of(context).firmDeskCount(filled, agents.length);
}

class _TileRow extends StatelessWidget {
  const _TileRow({
    required this.agents,
    required this.isUnlocked,
    required this.onTap,
    this.alignment = WrapAlignment.center,
  });

  final List<Agent> agents;
  final bool Function(Agent) isUnlocked;
  final AgentTapCallback onTap;
  final WrapAlignment alignment;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      alignment: alignment,
      runSpacing: AmiSpacing.m,
      children: [
        for (final a in agents)
          AgentTile(
            agent: a,
            unlocked: isUnlocked(a),
            size: _bandHexSize,
            onTap: () => onTap(a, isUnlocked(a)),
          ),
      ],
    );
  }
}

class _Band extends StatelessWidget {
  const _Band({
    required this.desk,
    required this.label,
    required this.isUnlocked,
    required this.onTap,
    this.note,
  });

  final AgentDesk desk;
  final String label;
  final String? note;
  final bool Function(Agent) isUnlocked;
  final AgentTapCallback onTap;

  @override
  Widget build(BuildContext context) {
    final agents = agentsOnDesk(desk);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _BandHeader(
          label: label,
          note: note,
          count: desk == AgentDesk.concierge
              ? null
              : _countFor(context, agents, isUnlocked),
        ),
        const SizedBox(height: AmiSpacing.s),
        _TileRow(agents: agents, isUnlocked: isUnlocked, onTap: onTap),
      ],
    );
  }
}

/// Two desks sharing one band (Execution is a single agent — a full-width band
/// would waste a third of the fold). Side by side when the width allows, stacked
/// as two ordinary bands when it does not (a 320pt phone), so nothing ever
/// scrolls sideways.
class _SharedBand extends StatelessWidget {
  const _SharedBand({
    required this.lead,
    required this.leadLabel,
    required this.trail,
    required this.trailLabel,
    required this.isUnlocked,
    required this.onTap,
  });

  final AgentDesk lead;
  final String leadLabel;
  final AgentDesk trail;
  final String trailLabel;
  final bool Function(Agent) isUnlocked;
  final AgentTapCallback onTap;

  @override
  Widget build(BuildContext context) {
    final leadAgents = agentsOnDesk(lead);
    final trailAgents = agentsOnDesk(trail);
    return LayoutBuilder(builder: (context, c) {
      final needed = _sharedLeadWidth +
          _sharedGap +
          trailAgents.length * _tileWidth;
      if (c.maxWidth < needed) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Band(
                desk: lead,
                label: leadLabel,
                isUnlocked: isUnlocked,
                onTap: onTap),
            const _BandRule(),
            _Band(
                desk: trail,
                label: trailLabel,
                isUnlocked: isUnlocked,
                onTap: onTap),
          ],
        );
      }
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: _sharedLeadWidth,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _BandHeader(
                    label: leadLabel,
                    count: _countFor(context, leadAgents, isUnlocked)),
                const SizedBox(height: AmiSpacing.s),
                _TileRow(
                    agents: leadAgents,
                    isUnlocked: isUnlocked,
                    onTap: onTap),
              ],
            ),
          ),
          const SizedBox(width: _sharedGap),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _BandHeader(
                    label: trailLabel,
                    count: _countFor(context, trailAgents, isUnlocked)),
                const SizedBox(height: AmiSpacing.s),
                _TileRow(
                  agents: trailAgents,
                  isUnlocked: isUnlocked,
                  onTap: onTap,
                  alignment: WrapAlignment.start,
                ),
              ],
            ),
          ),
        ],
      );
    });
  }
}

class AgentTile extends StatelessWidget {
  const AgentTile({
    super.key,
    required this.agent,
    required this.unlocked,
    required this.onTap,
    this.size = 72,
  });

  final Agent agent;
  final bool unlocked;
  final VoidCallback onTap;

  /// Hex edge; the tile is 16pt wider so the caption has room.
  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size + 16,
      child: Column(
        children: [
          Stack(
            alignment: Alignment.center,
            children: [
              Opacity(
                opacity: unlocked ? 1.0 : 0.35,
                child: HexAvatar(
                  label: agent.abbreviation,
                  color: agent.color,
                  size: size,
                  onTap: onTap,
                ),
              ),
              if (!unlocked)
                IgnorePointer(
                  child: Container(
                    width: size,
                    height: size,
                    alignment: Alignment.center,
                    child: const Icon(Icons.lock_outline,
                        color: AmiColors.textLow, size: 22),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            agent.displayName,
            textAlign: TextAlign.center,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: AmiTypography.caption.copyWith(
              fontSize: 10,
              color: unlocked ? AmiColors.textMed : AmiColors.textLow,
            ),
          ),
        ],
      ),
    );
  }
}

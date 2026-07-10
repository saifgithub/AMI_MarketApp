/// Coach Your Agent — the flagship screen.
///
/// Conversation with an agent in "brief mode" + a "Propose change" CTA that
/// asks the agent to crystallise the discussion into a BriefProposal. The
/// proposal renders as a diff card with Accept / Refine / Reject. Accepting
/// persists a new UserOverlay version (server-side) and refreshes history.
///
/// Safety floor: if the proposal touches PM mandate enforcement or any other
/// uncoachable rule, the backend returns a refusal — the UI surfaces it as
/// a banner with the "edit your Mandate" suggestion.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/brief.dart';
import 'package:ami_trade/screens/agent/brief_history_screen.dart';
import 'package:ami_trade/state/brief_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/chat/chat_bubble.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class BriefScreen extends ConsumerStatefulWidget {
  const BriefScreen({super.key, required this.agent});

  final Agent agent;

  @override
  ConsumerState<BriefScreen> createState() => _BriefScreenState();
}

class _BriefScreenState extends ConsumerState<BriefScreen> {
  final _textCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final _composerFocus = FocusNode();

  @override
  void dispose() {
    _textCtrl.dispose();
    _scrollCtrl.dispose();
    _composerFocus.dispose();
    super.dispose();
  }

  /// B4 (Plan A #1 / DEF): "Refine" used to call `.reject()`, which discarded
  /// the proposal and its diff. Now it keeps the diff on screen and seeds the
  /// composer with the proposal text so the CEO can edit it into a follow-up
  /// instruction — no server-side reject.
  void _refine(String proposalText) {
    _textCtrl.text = proposalText;
    _textCtrl.selection =
        TextSelection.collapsed(offset: _textCtrl.text.length);
    _composerFocus.requestFocus();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollCtrl.hasClients) return;
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent + 200,
        duration: AmiMotion.normal,
        curve: AmiMotion.easeOut,
      );
    });
  }

  void _send() {
    final txt = _textCtrl.text;
    if (txt.trim().isEmpty) return;
    _textCtrl.clear();
    ref.read(briefNotifierProvider(widget.agent.id).notifier).send(txt);
  }

  Future<void> _openHistory() async {
    await Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => BriefHistoryScreen(agent: widget.agent),
    ));
    if (!mounted) return;
    // refresh history when returning
    await ref.read(briefNotifierProvider(widget.agent.id).notifier).loadHistory();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(briefNotifierProvider(widget.agent.id));

    ref.listen<int>(
      briefNotifierProvider(widget.agent.id).select((s) => s.messages.length),
      (_, __) => _scrollToBottom(),
    );
    ref.listen<bool>(
      briefNotifierProvider(widget.agent.id).select((s) => s.streaming),
      (_, __) => _scrollToBottom(),
    );
    ref.listen<UserOverlay?>(
      briefNotifierProvider(widget.agent.id).select((s) => s.savedOverlay),
      (_, saved) {
        if (saved != null) {
          HexToast.show(
            context,
            AppLocalizations.of(context)
                .briefProposalSavedSnack(saved.version, saved.plainEnglish),
            accent: AmiColors.hexBlue,
            icon: Icons.check_circle_outline,
          );
          ref
              .read(briefNotifierProvider(widget.agent.id).notifier)
              .clearTransientFlags();
        }
      },
    );

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(agent: widget.agent, onHistory: _openHistory, state: state),
            if (state.currentOverlay != null && state.pendingProposal == null)
              _CurrentOverlayBanner(overlay: state.currentOverlay!),
            if (state.refusal != null)
              _RefusalBanner(refusal: state.refusal!, onDismiss: () {
                ref
                    .read(briefNotifierProvider(widget.agent.id).notifier)
                    .clearTransientFlags();
              }),
            Expanded(child: _body(state)),
            // B4: the composer stays mounted alongside a pending proposal so
            // "Refine" can keep the diff on screen while the CEO edits.
            if (state.pendingProposal != null)
              _DiffCard(
                agent: widget.agent,
                proposal: state.pendingProposal!,
                onAccept: () =>
                    ref.read(briefNotifierProvider(widget.agent.id).notifier).accept(),
                onReject: () =>
                    ref.read(briefNotifierProvider(widget.agent.id).notifier).reject(),
                onRefine: () => _refine(state.pendingProposal!.plainEnglish),
              ),
            _InputBar(
              controller: _textCtrl,
              focusNode: _composerFocus,
              disabled: state.streaming || state.session == null,
              proposing: state.proposing,
              onSend: _send,
              onPropose:
                  (state.pendingProposal == null && state.messages.length >= 2)
                      ? () => ref
                          .read(briefNotifierProvider(widget.agent.id).notifier)
                          .propose()
                      : null,
              agentColor: widget.agent.color,
            ),
          ],
        ),
      ),
    );
  }

  Widget _body(BriefState state) {
    if (state.session == null && state.error == null) {
      return Center(child: CircularProgressIndicator(color: widget.agent.color));
    }
    if (state.error != null && state.session == null) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off, color: AmiColors.hexAmber, size: 48),
            const SizedBox(height: AmiSpacing.m),
            Text(state.error!, textAlign: TextAlign.center, style: AmiTypography.body),
          ],
        ),
      );
    }
    return ListView.builder(
      controller: _scrollCtrl,
      padding: const EdgeInsets.all(AmiSpacing.m),
      itemCount: state.messages.length,
      itemBuilder: (context, i) {
        final m = state.messages[i];
        return ChatBubble(
          content: m.content.isEmpty && m.isStreaming ? '…' : m.content,
          author: m.role == 'user' ? ChatAuthor.user : ChatAuthor.agent,
          agentLabel: widget.agent.abbreviation,
          agentColor: widget.agent.color,
          streaming: m.isStreaming,
        );
      },
    );
  }
}


class _Header extends StatelessWidget {
  const _Header({required this.agent, required this.onHistory, required this.state});
  final Agent agent;
  final VoidCallback onHistory;
  final BriefState state;

  @override
  Widget build(BuildContext context) {
    final version = state.currentOverlay?.version ?? 0;
    final editsLeft = state.history?.editsRemaining;
    final l = AppLocalizations.of(context);
    return Container(
      height: 88,
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
                Text(
                  l.briefHeading(agent.displayName.toUpperCase()),
                  style: AmiTypography.labelMono.copyWith(color: agent.color),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  version == 0
                      ? l.briefNoOverlayYet
                      : l.briefOverlayActive(version),
                  style: AmiTypography.caption,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (editsLeft != null && editsLeft <= 1)
                  Text(
                    editsLeft == 0
                        ? l.briefNoEditsLeft
                        : l.briefOneEditLeft(editsLeft),
                    style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
                  ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.history, color: AmiColors.textMed),
            tooltip: l.briefVersionHistoryTooltip,
            onPressed: onHistory,
          ),
        ],
      ),
    );
  }
}


class _CurrentOverlayBanner extends StatelessWidget {
  const _CurrentOverlayBanner({required this.overlay});
  final UserOverlay overlay;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(AmiSpacing.m, AmiSpacing.s, AmiSpacing.m, 0),
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            AppLocalizations.of(context).briefCurrentOverlayLabel(overlay.version),
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue),
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(overlay.plainEnglish, style: AmiTypography.caption),
        ],
      ),
    );
  }
}


class _RefusalBanner extends StatelessWidget {
  const _RefusalBanner({required this.refusal, required this.onDismiss});
  final CoachRefusal refusal;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(AmiSpacing.m, AmiSpacing.s, AmiSpacing.m, 0),
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.lock_outline, color: AmiColors.hexAmber, size: 18),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  refusal.reason == 'safety_floor'
                      ? l.briefProtectedSafetyFloor
                      : refusal.reason == 'mandate_compliance'
                          ? l.briefProtectedMandate
                          : refusal.reason == 'edit_limit_reached'
                              ? l.briefEditLimitReached
                              : l.briefRefused,
                  style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber),
                ),
                const SizedBox(height: 2),
                Text(refusal.message, style: AmiTypography.caption),
                if (refusal.suggestion != null) ...[
                  const SizedBox(height: AmiSpacing.xs),
                  Text(refusal.suggestion!,
                      style: AmiTypography.caption.copyWith(color: AmiColors.textLow)),
                ],
              ],
            ),
          ),
          IconButton(
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.close, color: AmiColors.textLow, size: 18),
            onPressed: onDismiss,
          ),
        ],
      ),
    );
  }
}


class _DiffCard extends StatelessWidget {
  const _DiffCard({
    required this.agent,
    required this.proposal,
    required this.onAccept,
    required this.onReject,
    required this.onRefine,
  });

  final Agent agent;
  final BriefProposal proposal;
  final VoidCallback onAccept;
  final VoidCallback onReject;
  final VoidCallback onRefine;

  @override
  Widget build(BuildContext context) {
    final isRefused = proposal.refused;
    final l = AppLocalizations.of(context);
    final agentUpper = agent.displayName.toUpperCase();
    return Container(
      margin: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.sheet),
        border: Border.all(
          color: isRefused ? AmiColors.hexAmber : agent.color,
          width: 1.5,
        ),
      ),
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            isRefused
                ? l.briefAgentRefused(agentUpper)
                : l.briefAgentProposal(agentUpper),
            style: AmiTypography.labelMono.copyWith(
              color: isRefused ? AmiColors.hexAmber : agent.color,
            ),
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(l.briefPlainEnglish, style: AmiTypography.caption),
          const SizedBox(height: 2),
          Text(proposal.plainEnglish, style: AmiTypography.body),
          if (!isRefused) ...[
            const SizedBox(height: AmiSpacing.m),
            Text(l.briefOverlayAddition, style: AmiTypography.caption),
            const SizedBox(height: 2),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AmiSpacing.s),
              decoration: BoxDecoration(
                color: AmiColors.slate900,
                borderRadius: BorderRadius.circular(AmiRadii.card),
                border: Border.all(color: AmiColors.slate700),
              ),
              child: Text(
                proposal.overlayAddition,
                style: AmiTypography.stream,
              ),
            ),
          ],
          const SizedBox(height: AmiSpacing.m),
          Row(
            children: [
              if (!isRefused)
                Expanded(
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: agent.color,
                      foregroundColor: AmiColors.slate900,
                    ),
                    onPressed: onAccept,
                    child: Text(l.briefAccept),
                  ),
                ),
              if (!isRefused) const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AmiColors.textMed,
                    side: const BorderSide(color: AmiColors.slate700),
                  ),
                  onPressed: onRefine,
                  child: Text(isRefused ? l.briefDismiss : l.briefRefine),
                ),
              ),
              if (!isRefused) const SizedBox(width: AmiSpacing.s),
              if (!isRefused)
                Expanded(
                  child: TextButton(
                    style: TextButton.styleFrom(foregroundColor: AmiColors.textLow),
                    onPressed: onReject,
                    child: Text(l.briefReject),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}


class _InputBar extends StatelessWidget {
  const _InputBar({
    required this.controller,
    required this.disabled,
    required this.proposing,
    required this.onSend,
    required this.agentColor,
    this.focusNode,
    this.onPropose,
  });

  final TextEditingController controller;
  final bool disabled;
  final bool proposing;
  final VoidCallback onSend;
  final VoidCallback? onPropose;
  final Color agentColor;
  final FocusNode? focusNode;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      decoration: const BoxDecoration(
        color: AmiColors.slate900,
        border: Border(top: BorderSide(color: AmiColors.slate700)),
      ),
      padding: EdgeInsets.fromLTRB(
        AmiSpacing.m,
        AmiSpacing.s,
        AmiSpacing.m,
        AmiSpacing.m + MediaQuery.of(context).viewInsets.bottom / 4,
      ),
      child: Column(
        children: [
          if (onPropose != null)
            Padding(
              padding: const EdgeInsets.only(bottom: AmiSpacing.s),
              child: SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: agentColor,
                    side: BorderSide(color: agentColor),
                  ),
                  icon: proposing
                      ? SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            color: agentColor,
                            strokeWidth: 2,
                          ),
                        )
                      : const Icon(Icons.fact_check_outlined, size: 18),
                  label: Text(proposing ? l.briefDrafting : l.briefProposeChange),
                  onPressed: proposing ? null : onPropose,
                ),
              ),
            ),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  focusNode: focusNode,
                  style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
                  minLines: 1,
                  maxLines: 4,
                  enabled: !disabled,
                  onSubmitted: (_) => onSend(),
                  decoration: InputDecoration(
                    hintText: disabled ? l.oneOnOneStreaming : l.briefInputHint,
                    hintStyle: AmiTypography.body.copyWith(color: AmiColors.textLow),
                    filled: true,
                    fillColor: AmiColors.slate800,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: AmiSpacing.m,
                      vertical: 12,
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(AmiRadii.card),
                      borderSide: const BorderSide(color: AmiColors.slate700),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(AmiRadii.card),
                      borderSide: BorderSide(color: agentColor),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: AmiSpacing.s),
              IconButton(
                onPressed: disabled ? null : onSend,
                icon: Icon(Icons.arrow_upward, color: agentColor),
                style: IconButton.styleFrom(
                  backgroundColor: AmiColors.slate800,
                  shape: const RoundedRectangleBorder(
                    borderRadius: BorderRadius.all(Radius.circular(AmiRadii.card)),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

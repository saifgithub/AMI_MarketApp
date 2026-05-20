/// 1-on-1 chat with a single agent.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/agent/brief_screen.dart';
import 'package:ami_trade/state/one_on_one_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/chat/chat_bubble.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class OneOnOneScreen extends ConsumerStatefulWidget {
  const OneOnOneScreen({super.key, required this.agent});

  final Agent agent;

  @override
  ConsumerState<OneOnOneScreen> createState() => _OneOnOneScreenState();
}

class _OneOnOneScreenState extends ConsumerState<OneOnOneScreen> {
  final _textCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();

  @override
  void dispose() {
    _textCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollCtrl.hasClients) return;
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent + 100,
        duration: AmiMotion.normal,
        curve: AmiMotion.easeOut,
      );
    });
  }

  void _send() {
    final txt = _textCtrl.text;
    if (txt.trim().isEmpty) return;
    _textCtrl.clear();
    ref.read(oneOnOneNotifierProvider(widget.agent.id).notifier).send(txt);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(oneOnOneNotifierProvider(widget.agent.id));

    // Auto-scroll on new content
    ref.listen<int>(
      oneOnOneNotifierProvider(widget.agent.id).select((s) => s.messages.length),
      (_, __) => _scrollToBottom(),
    );
    // Also scroll while streaming as content grows
    ref.listen<bool>(
      oneOnOneNotifierProvider(widget.agent.id).select((s) => s.streaming),
      (_, __) => _scrollToBottom(),
    );

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(agent: widget.agent),
            Expanded(child: _body(state)),
            _InputBar(
              controller: _textCtrl,
              disabled: state.streaming || state.session == null,
              onSend: _send,
            ),
          ],
        ),
      ),
    );
  }

  Widget _body(OneOnOneState state) {
    if (state.session == null && state.error == null) {
      return Center(
        child: CircularProgressIndicator(color: widget.agent.color),
      );
    }

    if (state.error != null && state.session == null) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off, color: AmiColors.hexAmber, size: 48),
            const SizedBox(height: AmiSpacing.m),
            Text(state.error!, textAlign: TextAlign.center,
                style: AmiTypography.body),
          ],
        ),
      );
    }

    if (state.messages.isEmpty) {
      return _EmptyState(agent: widget.agent);
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
  const _Header({required this.agent});
  final Agent agent;

  bool get _coachable => agent.family != AgentFamily.concierge;

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
          HexAvatar(
            label: agent.abbreviation,
            color: agent.color,
            size: 44,
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(agent.displayName.toUpperCase(),
                    style: AmiTypography.labelMono.copyWith(color: agent.color)),
                Text(agent.tagline,
                    style: AmiTypography.caption,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis),
              ],
            ),
          ),
          if (_coachable)
            IconButton(
              icon: Icon(Icons.tune, color: agent.color),
              tooltip: AppLocalizations.of(context).oneOnOneBriefTooltip,
              onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                builder: (_) => BriefScreen(agent: agent),
              )),
            ),
        ],
      ),
    );
  }
}


class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.agent});
  final Agent agent;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            HexAvatar(
              label: agent.abbreviation,
              color: agent.color,
              size: 120,
            ),
            const SizedBox(height: AmiSpacing.l),
            Text(agent.displayName,
                style: AmiTypography.h3,
                textAlign: TextAlign.center),
            const SizedBox(height: AmiSpacing.s),
            Text(agent.tagline,
                style: AmiTypography.body.copyWith(color: AmiColors.textLow),
                textAlign: TextAlign.center),
            const SizedBox(height: AmiSpacing.l),
            Text(
              AppLocalizations.of(context).oneOnOneAskAnything,
              style: AmiTypography.caption,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}


class _InputBar extends StatelessWidget {
  const _InputBar({
    required this.controller,
    required this.disabled,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool disabled;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
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
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
              minLines: 1,
              maxLines: 4,
              enabled: !disabled,
              onSubmitted: (_) => onSend(),
              decoration: InputDecoration(
                hintText: disabled
                    ? AppLocalizations.of(context).oneOnOneStreaming
                    : AppLocalizations.of(context).oneOnOneHint,
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
                  borderSide: const BorderSide(color: AmiColors.hexBlue),
                ),
              ),
            ),
          ),
          const SizedBox(width: AmiSpacing.s),
          IconButton(
            onPressed: disabled ? null : onSend,
            icon: const Icon(Icons.arrow_upward, color: AmiColors.hexBlue),
            style: IconButton.styleFrom(
              backgroundColor: AmiColors.slate800,
              shape: const RoundedRectangleBorder(
                borderRadius: BorderRadius.all(Radius.circular(AmiRadii.card)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

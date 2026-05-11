import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/chat/chat_bubble.dart';
import 'package:ami_trade/widgets/chat/chip_row.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _scrollCtrl = ScrollController();
  final _textCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    // Auto-start onboarding on screen mount
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(onboardingNotifierProvider.notifier).start(
            locale: 'en',
            timezone: DateTime.now().timeZoneName,
          );
    });
  }

  @override
  void dispose() {
    _scrollCtrl.dispose();
    _textCtrl.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollCtrl.hasClients) return;
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent + 200,
        duration: AmiMotion.slow,
        curve: AmiMotion.easeOut,
      );
    });
  }

  void _handleSubmit(String answer) {
    final trimmed = answer.trim();
    if (trimmed.isEmpty) return;
    _textCtrl.clear();
    ref.read(onboardingNotifierProvider.notifier).submitAnswer(trimmed);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(onboardingNotifierProvider);

    // Auto-scroll when lines change
    ref.listen<int>(
      onboardingNotifierProvider.select((s) => s.lines.length),
      (_, __) => _scrollToBottom(),
    );

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _HeaderBar(state: state),
            Expanded(child: _body(state)),
            if (state.phase == OnboardingPhase.readback) _readbackControls(),
            if (state.phase == OnboardingPhase.completed) _completedControls(state),
            if (state.phase == OnboardingPhase.inConversation ||
                state.phase == OnboardingPhase.starting)
              _inputArea(state),
          ],
        ),
      ),
    );
  }

  Widget _body(OnboardingState state) {
    if (state.phase == OnboardingPhase.error) {
      return _ErrorView(
        message: state.errorMessage ?? 'Unknown error',
        onRetry: () => ref.read(onboardingNotifierProvider.notifier).start(
              locale: 'en',
              timezone: DateTime.now().timeZoneName,
            ),
      );
    }
    if (state.phase == OnboardingPhase.notStarted ||
        state.phase == OnboardingPhase.starting) {
      return const Center(
        child: CircularProgressIndicator(color: AmiColors.hexPink),
      );
    }

    return ListView.builder(
      controller: _scrollCtrl,
      padding: const EdgeInsets.symmetric(
        horizontal: AmiSpacing.m,
        vertical: AmiSpacing.m,
      ),
      itemCount: state.lines.length,
      itemBuilder: (context, i) {
        final line = state.lines[i];
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: ChatBubble(
            content: line.content,
            author: line.author,
            streaming: line.streaming,
          ),
        );
      },
    );
  }

  Widget _inputArea(OnboardingState state) {
    final chips = state.currentChips;
    return Container(
      decoration: const BoxDecoration(
        color: AmiColors.slate900,
        border: Border(top: BorderSide(color: AmiColors.slate700)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (chips.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: AmiSpacing.s),
              child: ChipRow(chips: chips, onSelected: _handleSubmit),
            ),
          Padding(
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
                    controller: _textCtrl,
                    style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
                    minLines: 1,
                    maxLines: 4,
                    onSubmitted: _handleSubmit,
                    decoration: InputDecoration(
                      hintText: state.submitting ? 'Sending...' : 'Type your answer…',
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
                  onPressed: state.submitting ? null : () => _handleSubmit(_textCtrl.text),
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
          ),
        ],
      ),
    );
  }

  Widget _readbackControls() {
    return Padding(
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: HexButton(
        label: 'LOOKS RIGHT — CONTINUE',
        color: AmiColors.hexBlue,
        onPressed: () =>
            ref.read(onboardingNotifierProvider.notifier).confirmReadback(),
      ),
    );
  }

  Widget _completedControls(OnboardingState state) {
    return Padding(
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: HexButton(
        label: 'MEET YOUR TEAM',
        color: AmiColors.hexPink,
        onPressed: () => Navigator.of(context).pushReplacementNamed('/floor'),
      ),
    );
  }
}


class _HeaderBar extends StatelessWidget {
  const _HeaderBar({required this.state});
  final OnboardingState state;

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
          const Text('⬢', style: TextStyle(fontSize: 22, color: AmiColors.hexBlue)),
          const SizedBox(width: AmiSpacing.s),
          const Text('AMI TRADE', style: AmiTypography.labelMono),
          const Spacer(),
          if (state.sessionId != null)
            Text(
              'SETUP',
              style: AmiTypography.labelMono.copyWith(
                color: AmiColors.hexPink,
                fontSize: 11,
              ),
            ),
        ],
      ),
    );
  }
}


class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AmiSpacing.l),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.cloud_off, size: 56, color: AmiColors.hexAmber),
          const SizedBox(height: AmiSpacing.m),
          const Text('CAN\'T REACH THE BACKEND',
              style: AmiTypography.labelMono, textAlign: TextAlign.center),
          const SizedBox(height: AmiSpacing.s),
          Text(message, style: AmiTypography.body, textAlign: TextAlign.center),
          const SizedBox(height: AmiSpacing.l),
          HexButton(label: 'TRY AGAIN', onPressed: onRetry),
        ],
      ),
    );
  }
}

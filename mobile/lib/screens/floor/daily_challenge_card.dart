/// Daily challenge — Floor tab card + full-screen detail view.
///
/// The card shows the date, type, and question; tapping opens the
/// full screen where the user picks an option, submits, then sees
/// the explanation + related lesson/agent links.
library;

import 'package:ami_trade/models/daily_challenge.dart';
import 'package:ami_trade/state/daily_challenge_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class DailyChallengeCard extends ConsumerWidget {
  const DailyChallengeCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(dailyChallengeTodayProvider);
    return async.when(
      loading: () => _shell(child: _loading()),
      error: (e, _) => const SizedBox.shrink(),
      data: (data) {
        if (data == null) return const SizedBox.shrink();
        return AccentCard(
          accent: AmiColors.hexAmber,
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => DailyChallengeScreen(data: data),
            ),
          ),
          child: _Body(data: data),
        );
      },
    );
  }

  Widget _shell({required Widget child}) {
    // Loading placeholder — same shape envelope as the loaded card.
    return AccentCard(accent: AmiColors.hexAmber, child: child);
  }

  Widget _loading() => const SizedBox(
        height: 40,
        child: Center(
          child: SizedBox(
            width: 18, height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );
}


class _Body extends StatelessWidget {
  const _Body({required this.data});
  final DailyChallengeWithDate data;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.bolt, color: AmiColors.hexAmber, size: 16),
            const SizedBox(width: 6),
            Text(
              'DAILY CHALLENGE · ${data.date}',
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber),
            ),
            const Spacer(),
            _difficultyDots(data.challenge.difficulty),
          ],
        ),
        const SizedBox(height: AmiSpacing.s),
        Text(
          _humanType(data.challenge.type),
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
        ),
        const SizedBox(height: 4),
        Text(
          data.challenge.question,
          style: AmiTypography.body.copyWith(fontWeight: FontWeight.w600),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: AmiSpacing.xs),
        Row(
          children: [
            Text(
              'Tap to attempt →',
              style: AmiTypography.caption.copyWith(color: AmiColors.hexBlue),
            ),
          ],
        ),
      ],
    );
  }

  Widget _difficultyDots(int n) {
    return Row(
      children: [
        for (int i = 0; i < 5; i++)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 1),
            child: Container(
              width: 6, height: 6,
              decoration: BoxDecoration(
                color: i < n ? AmiColors.hexAmber : AmiColors.slate700,
                shape: BoxShape.circle,
              ),
            ),
          ),
      ],
    );
  }

  String _humanType(String t) => t.replaceAll('_', ' ').toUpperCase();
}


class DailyChallengeScreen extends StatefulWidget {
  const DailyChallengeScreen({super.key, required this.data});
  final DailyChallengeWithDate data;

  @override
  State<DailyChallengeScreen> createState() => _DailyChallengeScreenState();
}

class _DailyChallengeScreenState extends State<DailyChallengeScreen> {
  int? _selected;
  bool _submitted = false;

  @override
  Widget build(BuildContext context) {
    final ch = widget.data.challenge;
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(
        backgroundColor: AmiColors.slate900,
        title: Text('Daily · ${widget.data.date}', style: AmiTypography.labelMono),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AmiSpacing.m),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                ch.type.replaceAll('_', ' ').toUpperCase(),
                style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber),
              ),
              const SizedBox(height: AmiSpacing.s),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AmiSpacing.m),
                decoration: BoxDecoration(
                  color: AmiColors.slate800,
                  borderRadius: BorderRadius.circular(AmiRadii.card),
                  border: Border.all(color: AmiColors.slate700),
                ),
                child: Text(ch.scenario, style: AmiTypography.body),
              ),
              const SizedBox(height: AmiSpacing.l),
              Text(ch.question, style: AmiTypography.body.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: AmiSpacing.m),
              for (int i = 0; i < ch.options.length; i++)
                _OptionTile(
                  index: i,
                  text: ch.options[i],
                  selected: _selected == i,
                  showResult: _submitted,
                  correct: i == ch.answer,
                  onTap: _submitted
                      ? null
                      : () => setState(() => _selected = i),
                ),
              const SizedBox(height: AmiSpacing.l),
              if (!_submitted)
                HexButton(
                  label: 'SUBMIT',
                  onPressed: _selected == null
                      ? null
                      : () => setState(() => _submitted = true),
                )
              else ...[
                Text(
                  _selected == ch.answer ? 'CORRECT' : 'INCORRECT',
                  style: AmiTypography.labelMono.copyWith(
                    color: _selected == ch.answer
                        ? AmiColors.hexGreen
                        : AmiColors.hexRed,
                  ),
                ),
                const SizedBox(height: AmiSpacing.s),
                Text(ch.explanation, style: AmiTypography.body),
                const SizedBox(height: AmiSpacing.m),
                if (ch.relatedLesson != null)
                  Text(
                    'Related lesson: ${ch.relatedLesson}',
                    style: AmiTypography.caption.copyWith(color: AmiColors.hexBlue),
                  ),
                if (ch.relatedAgent != null)
                  Text(
                    'Related agent: ${ch.relatedAgent}',
                    style: AmiTypography.caption.copyWith(color: AmiColors.hexBlue),
                  ),
              ],
              const SizedBox(height: AmiSpacing.xl),
            ],
          ),
        ),
      ),
    );
  }
}


class _OptionTile extends StatelessWidget {
  const _OptionTile({
    required this.index,
    required this.text,
    required this.selected,
    required this.showResult,
    required this.correct,
    required this.onTap,
  });

  final int index;
  final String text;
  final bool selected;
  final bool showResult;
  final bool correct;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    Color borderColor = AmiColors.slate700;
    if (showResult) {
      if (correct) {
        borderColor = AmiColors.hexGreen;
      } else if (selected) {
        borderColor = AmiColors.hexRed;
      }
    } else if (selected) {
      borderColor = AmiColors.hexBlue;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.xs),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AmiSpacing.s),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(color: borderColor),
          ),
          child: Row(
            children: [
              Container(
                width: 24, height: 24,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  border: Border.all(color: borderColor),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  String.fromCharCode(65 + index),
                  style: AmiTypography.labelMono.copyWith(color: borderColor),
                ),
              ),
              const SizedBox(width: AmiSpacing.s),
              Expanded(child: Text(text, style: AmiTypography.body)),
            ],
          ),
        ),
      ),
    );
  }
}

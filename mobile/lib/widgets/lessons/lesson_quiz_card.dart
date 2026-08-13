/// The graded quiz card and the result panel, shared by book mode and the
/// CR174 beat deck.
///
/// Lifted verbatim out of `lesson_reader_screen.dart`. Behaviour is unchanged —
/// acceptance #1 requires book mode's rendered output to be identical, so this
/// is a move rather than a rewrite, and the deck reuses it rather than growing a
/// second quiz card that agrees with this one only until the first fix lands in
/// one of them (DEF098).
///
/// **The grading contract does not change in interactive mode.** CR174's
/// formative/scored rule is that instant feedback belongs to interactions that
/// carry no unlock value — the parameter play, the reveal — while anything that
/// moves an agent gate stays a batch submit answered by the server. So a quiz
/// card in the deck collects a selection and reveals nothing until
/// `LessonReaderNotifier.submit()` returns, exactly as it does in the book.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';

class LessonQuizCard extends StatelessWidget {
  const LessonQuizCard({
    super.key,
    required this.question,
    required this.onSelect,
    required this.selected,
    required this.locked,
    required this.revealResult,
  });

  final QuizQuestion question;
  final int? selected;
  final bool locked;
  final bool revealResult;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexGreen),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(AppLocalizations.of(context).lessonReaderQuiz,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexGreen)),
          const SizedBox(height: AmiSpacing.s),
          Text(question.question, style: AmiTypography.body),
          const SizedBox(height: AmiSpacing.s),
          for (int i = 0; i < question.options.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: InkWell(
                onTap: locked ? null : () => onSelect(i),
                borderRadius: BorderRadius.circular(AmiRadii.card),
                child: Container(
                  padding: const EdgeInsets.all(AmiSpacing.s),
                  decoration: BoxDecoration(
                    color: _bg(i),
                    borderRadius: BorderRadius.circular(AmiRadii.card),
                    border: Border.all(color: _border(i)),
                  ),
                  child: Row(
                    children: [
                      Icon(_icon(i), color: _border(i), size: 18),
                      const SizedBox(width: AmiSpacing.s),
                      Expanded(child: Text(question.options[i],
                          style: AmiTypography.body)),
                    ],
                  ),
                ),
              ),
            ),
          if (revealResult && question.explanation != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Container(
                padding: const EdgeInsets.all(AmiSpacing.s),
                decoration: BoxDecoration(
                  color: AmiColors.slate900,
                  borderRadius: BorderRadius.circular(AmiRadii.card),
                ),
                child: Text(question.explanation!, style: AmiTypography.caption),
              ),
            ),
        ],
      ),
    );
  }

  Color _bg(int i) {
    if (revealResult) {
      if (i == question.answerIndex) return AmiColors.hexGreen.withValues(alpha: 0.15);
      if (i == selected && i != question.answerIndex) {
        return AmiColors.hexRed.withValues(alpha: 0.15);
      }
    }
    if (selected == i) return AmiColors.slate900;
    return AmiColors.slate900;
  }

  Color _border(int i) {
    if (revealResult) {
      if (i == question.answerIndex) return AmiColors.hexGreen;
      if (i == selected && i != question.answerIndex) return AmiColors.hexRed;
    }
    if (selected == i) return AmiColors.hexBlue;
    return AmiColors.slate700;
  }

  IconData _icon(int i) {
    if (revealResult) {
      if (i == question.answerIndex) return Icons.check_circle;
      if (i == selected && i != question.answerIndex) return Icons.cancel;
      return Icons.radio_button_unchecked;
    }
    return selected == i
        ? Icons.radio_button_checked
        : Icons.radio_button_unchecked;
  }
}


class LessonResultPanel extends StatelessWidget {
  const LessonResultPanel({
    super.key,
    required this.result,
    required this.onRetry,
    required this.onDone,
  });

  final QuizResult result;
  final VoidCallback onRetry;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final passed = result.passed;
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(
          color: passed ? AmiColors.hexGreen : AmiColors.hexAmber,
          width: 1.5,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                passed ? Icons.celebration : Icons.replay,
                color: passed ? AmiColors.hexGreen : AmiColors.hexAmber,
                size: 28,
              ),
              const SizedBox(width: AmiSpacing.s),
              Text(passed ? l.lessonReaderPassed : l.lessonReaderNotQuite,
                  style: AmiTypography.labelMono.copyWith(
                      color: passed ? AmiColors.hexGreen : AmiColors.hexAmber)),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(l.lessonReaderCorrectOf(result.correct, result.total),
              style: AmiTypography.statMid),
          if (result.unlockedAgents.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.m),
            Text(l.lessonReaderAgentUnlocked,
                style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber)),
            const SizedBox(height: AmiSpacing.s),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final id in result.unlockedAgents)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      HexAvatar(
                        label: agentById(id).abbreviation,
                        color: agentById(id).color,
                        size: 48,
                      ),
                      const SizedBox(width: 6),
                      Text(agentById(id).displayName,
                          style: AmiTypography.body),
                    ],
                  ),
              ],
            ),
          ],
          const SizedBox(height: AmiSpacing.m),
          Row(
            children: [
              if (!passed)
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AmiColors.hexAmber,
                      side: const BorderSide(color: AmiColors.hexAmber),
                    ),
                    onPressed: onRetry,
                    child: Text(l.lessonReaderTryAgain),
                  ),
                ),
              if (!passed) const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AmiColors.hexGreen,
                    foregroundColor: AmiColors.slate900,
                  ),
                  onPressed: onDone,
                  child: Text(passed ? l.lessonReaderDone : l.lessonReaderBackToLessons),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

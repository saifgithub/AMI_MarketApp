/// Daily challenge — Floor tab card + full-screen detail view.
///
/// The card shows the date, type, and question; tapping opens the
/// full screen where the user picks an option, submits, then sees
/// the explanation + related lesson/agent links.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/daily_challenge.dart';
import 'package:ami_trade/models/league.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/services/celebration.dart';
import 'package:ami_trade/state/daily_challenge_providers.dart';
import 'package:ami_trade/state/league_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/agent_action_sheet.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/streak_chip.dart';
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
        final me = ref.watch(leagueMeProvider).valueOrNull;
        return AccentCard(
          accent: AmiColors.hexAmber,
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => DailyChallengeScreen(data: data),
            ),
          ),
          child: _Body(data: data, streak: me?.streak),
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
  const _Body({required this.data, this.streak});
  final DailyChallengeWithDate data;
  final StreakInfo? streak;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final answered = data.myAttempt != null;
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
            if (answered)
              Text(
                l.challengeTapToReview,
                style: AmiTypography.caption.copyWith(
                  color: data.myAttempt!.correct
                      ? AmiColors.hexGreen
                      : AmiColors.textLow,
                ),
              )
            else
              Text(
                l.challengeTapToAttempt,
                style: AmiTypography.caption.copyWith(color: AmiColors.hexBlue),
              ),
            const Spacer(),
            if (streak != null && streak!.current > 0)
              StreakChip(count: streak!.current, todayFilled: answered),
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


class DailyChallengeScreen extends ConsumerStatefulWidget {
  const DailyChallengeScreen({super.key, required this.data});
  final DailyChallengeWithDate data;

  @override
  ConsumerState<DailyChallengeScreen> createState() =>
      _DailyChallengeScreenState();
}

class _DailyChallengeScreenState extends ConsumerState<DailyChallengeScreen> {
  int? _selected;
  bool _submitted = false;
  bool _submitting = false;
  bool _correct = false;
  Timer? _countdownTimer;
  Duration _untilNext = Duration.zero;

  @override
  void initState() {
    super.initState();
    // B5 server-truth: if today was already answered, open straight into the
    // answered state (survives a tab switch / restart) from `my_attempt`.
    final prior = widget.data.myAttempt;
    if (prior != null) {
      _selected = prior.selectedOption;
      _correct = prior.correct;
      _submitted = true;
      _startCountdown();
    }
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    super.dispose();
  }

  void _startCountdown() {
    _tick();
    _countdownTimer?.cancel();
    _countdownTimer =
        Timer.periodic(const Duration(seconds: 1), (_) => _tick());
  }

  void _tick() {
    // CR010 M1: the backend rolls the daily challenge at Asia/Kuala_Lumpur
    // midnight (DEFAULT_TZ, fixed UTC+8, no DST), NOT the device-local
    // midnight — count to that so "next in HH:MM:SS" is right on any device tz.
    const klOffset = Duration(hours: 8);
    final nowUtc = DateTime.now().toUtc();
    final nowKl = nowUtc.add(klOffset);
    final nextKlMidnight =
        DateTime.utc(nowKl.year, nowKl.month, nowKl.day)
            .add(const Duration(days: 1));
    final remaining = nextKlMidnight.subtract(klOffset).difference(nowUtc);
    if (!mounted) return;
    setState(
        () => _untilNext = remaining.isNegative ? Duration.zero : remaining);
  }

  Future<void> _submit(DailyChallenge ch) async {
    final sel = _selected;
    if (sel == null || _submitting) return;
    setState(() => _submitting = true);
    try {
      final result =
          await ref.read(apiClientProvider).dailyChallengeAttempt(ch.id, sel);
      if (!mounted) return;
      setState(() {
        _selected = result.selectedOption; // stored attempt wins
        _correct = result.correct;
        _submitted = true;
        _submitting = false;
      });
      _startCountdown();
      if (result.correct) {
        Celebrate.micro(context, accent: AmiColors.hexGreen);
      }
      // Streak/points moved — refresh so the chip + card reflect it.
      ref.invalidate(leagueMeProvider);
      ref.invalidate(dailyChallengeTodayProvider);
    } catch (_) {
      if (!mounted) return;
      setState(() => _submitting = false);
    }
  }

  String _fmt(Duration d) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(d.inHours)}:${two(d.inMinutes % 60)}:${two(d.inSeconds % 60)}';
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
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
                  onPressed: (_selected == null || _submitting)
                      ? null
                      : () => _submit(ch),
                )
              else ...[
                Text(
                  _correct ? 'CORRECT' : 'INCORRECT',
                  style: AmiTypography.labelMono.copyWith(
                    color: _correct ? AmiColors.hexGreen : AmiColors.hexRed,
                  ),
                ),
                const SizedBox(height: AmiSpacing.s),
                Text(ch.explanation, style: AmiTypography.body),
                const SizedBox(height: AmiSpacing.m),
                Text(
                  l.challengeNextIn(_fmt(_untilNext)),
                  style:
                      AmiTypography.caption.copyWith(color: AmiColors.textLow),
                ),
                const SizedBox(height: AmiSpacing.m),
                if (ch.relatedLesson != null)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      style: TextButton.styleFrom(
                        foregroundColor: AmiColors.hexBlue,
                        padding: EdgeInsets.zero,
                        visualDensity: VisualDensity.compact,
                      ),
                      icon: const Icon(Icons.menu_book_outlined, size: 16),
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) =>
                              LessonReaderScreen(lessonId: ch.relatedLesson!),
                        ),
                      ),
                      label: Text(AppLocalizations.of(context).challengeRelatedLesson),
                    ),
                  ),
                if (ch.relatedAgent != null)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      style: TextButton.styleFrom(
                        foregroundColor: AmiColors.hexBlue,
                        padding: EdgeInsets.zero,
                        visualDensity: VisualDensity.compact,
                      ),
                      icon: const Icon(Icons.person_outline, size: 16),
                      onPressed: () => AgentActionSheet.show(
                        context, agentById(ch.relatedAgent!)),
                      label: Text(AppLocalizations.of(context).challengeRelatedAgent),
                    ),
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

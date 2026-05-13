/// AI Coach Q&A — searchable help screen over the 280-entry Q&A library.
///
/// Accessed from Settings → Help. Search-as-you-type with debounce;
/// tapping a hit opens a sheet with the long answer + related lessons
/// / agents. Same backend that the Concierge falls back to when the
/// LLM is offline.
library;

import 'dart:async';

import 'package:ami_trade/models/ai_coach.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AICoachScreen extends ConsumerStatefulWidget {
  const AICoachScreen({super.key});

  @override
  ConsumerState<AICoachScreen> createState() => _AICoachScreenState();
}

class _AICoachScreenState extends ConsumerState<AICoachScreen> {
  final _controller = TextEditingController();
  Timer? _debounce;
  List<CoachSearchHit> _hits = const [];
  bool _loading = false;
  String _lastQuery = '';

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String q) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () => _search(q));
  }

  Future<void> _search(String q) async {
    final query = q.trim();
    if (query.length < 2) {
      setState(() {
        _hits = const [];
        _loading = false;
        _lastQuery = query;
      });
      return;
    }
    setState(() {
      _loading = true;
      _lastQuery = query;
    });
    try {
      final api = ref.read(apiClientProvider);
      final hits = await api.aiCoachSearch(query, limit: 8);
      if (!mounted || query != _lastQuery) return;
      setState(() {
        _hits = hits;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _hits = const [];
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(
        backgroundColor: AmiColors.slate900,
        title: Text('AI Coach', style: AmiTypography.labelMono),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(AmiSpacing.m),
              child: TextField(
                controller: _controller,
                onChanged: _onChanged,
                style: AmiTypography.body,
                autofocus: true,
                decoration: InputDecoration(
                  hintText: 'Ask anything — "halal filter", "mandate", "stop loss"',
                  hintStyle:
                      AmiTypography.body.copyWith(color: AmiColors.slate500),
                  prefixIcon:
                      const Icon(Icons.search, color: AmiColors.hexBlue),
                  filled: true,
                  fillColor: AmiColors.slate800,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(AmiRadii.card),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
            Expanded(child: _body()),
          ],
        ),
      ),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_lastQuery.length < 2) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Text(
          '280 questions and answers across platform, psychology, scams, AI '
          'meta, and beginner / intermediate topics. Type to search.',
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
        ),
      );
    }
    if (_hits.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Text(
          'No matches for "$_lastQuery". Try a different phrasing.',
          style: AmiTypography.body.copyWith(color: AmiColors.textLow),
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
      itemCount: _hits.length,
      separatorBuilder: (_, __) => const SizedBox(height: AmiSpacing.s),
      itemBuilder: (_, i) => _HitTile(hit: _hits[i]),
    );
  }
}


Color _accentFor(String category) {
  // Per spec: hit-tile top-border tints the category at a glance.
  switch (category) {
    case 'scam':
      return AmiColors.hexRed;
    case 'psychology':
      return AmiColors.hexPink;
    case 'ai_meta':
      return AmiColors.hexPurple;
    case 'platform':
      return AmiColors.hexCyan;
    case 'beginner':
      return AmiColors.hexGreen;
    case 'intermediate':
    default:
      return AmiColors.hexBlue;
  }
}


class _HitTile extends StatelessWidget {
  const _HitTile({required this.hit});
  final CoachSearchHit hit;

  @override
  Widget build(BuildContext context) {
    final accent = _accentFor(hit.qa.category);
    return AccentCard(
      accent: accent,
      onTap: () => _openSheet(context, hit.qa),
      padding: const EdgeInsets.all(AmiSpacing.s),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: HexChip(
              label: hit.qa.category,
              color: accent,
              variant: HexChipVariant.tinted,
              fontSize: 9,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            hit.qa.question,
            style: AmiTypography.body.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          Text(
            hit.qa.shortAnswer,
            style: AmiTypography.caption,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}


void _openSheet(BuildContext context, CoachQA qa) {
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: AmiColors.slate900,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (_) => _AnswerSheet(qa: qa),
  );
}


class _AnswerSheet extends StatelessWidget {
  const _AnswerSheet({required this.qa});
  final CoachQA qa;

  @override
  Widget build(BuildContext context) {
    final mediaPad = MediaQuery.of(context).viewInsets;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(bottom: mediaPad.bottom),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height * 0.75,
          ),
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(
              AmiSpacing.l, AmiSpacing.m, AmiSpacing.l, AmiSpacing.l,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Center(
                  child: Container(
                    width: 40, height: 4,
                    decoration: BoxDecoration(
                      color: AmiColors.slate700,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: AmiSpacing.m),
                Align(
                  alignment: Alignment.centerLeft,
                  child: HexChip(
                    label: qa.category,
                    color: _accentFor(qa.category),
                    variant: HexChipVariant.tinted,
                    fontSize: 10,
                  ),
                ),
                const SizedBox(height: AmiSpacing.s),
                Text(qa.question, style: AmiTypography.h3),
                const SizedBox(height: AmiSpacing.m),
                Text(qa.longAnswer, style: AmiTypography.body),
                if (qa.relatedLessons.isNotEmpty) ...[
                  const SizedBox(height: AmiSpacing.l),
                  Text('RELATED LESSONS',
                      style: AmiTypography.labelMono
                          .copyWith(color: AmiColors.textLow)),
                  const SizedBox(height: AmiSpacing.xs),
                  Wrap(
                    spacing: 6, runSpacing: 6,
                    children: [
                      for (final lid in qa.relatedLessons)
                        _Pill(text: lid),
                    ],
                  ),
                ],
                if (qa.relatedAgents.isNotEmpty) ...[
                  const SizedBox(height: AmiSpacing.l),
                  Text('RELATED AGENTS',
                      style: AmiTypography.labelMono
                          .copyWith(color: AmiColors.textLow)),
                  const SizedBox(height: AmiSpacing.xs),
                  Wrap(
                    spacing: 6, runSpacing: 6,
                    children: [
                      for (final aid in qa.relatedAgents)
                        _Pill(text: aid.replaceAll('_', ' ')),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}


class _Pill extends StatelessWidget {
  const _Pill({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Text(text, style: AmiTypography.labelMono.copyWith(fontSize: 11)),
    );
  }
}

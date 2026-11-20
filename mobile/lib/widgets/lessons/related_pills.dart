/// Related-content pills shared by the Q&A answer sheet and the glossary term
/// sheet (DEF481 item 5).
///
/// A pill only looks tappable when it has somewhere to go. A lesson reference
/// that resolves against the loaded catalogue opens that lesson's reader; a
/// reference that doesn't resolve, and every related agent (no agent profile
/// screen exists — the only agent surface is the unlock-gated 1-on-1/Brief
/// chooser), renders as a plain caption with no border, fill or button
/// semantics so it never promises an action it cannot perform.
library;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/lesson_markdown.dart'
    show findLessonMetaById;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Resolves a content-authored lesson reference to a catalogue entry.
///
/// Q&A and glossary content cite lessons by their bare number ("065"), the
/// catalogue keys them by the full slug ("065_guaranteed_return_scams"), so an
/// exact-id match alone resolves none of them.
LessonMeta? resolveRelatedLesson(LessonCatalogue? catalogue, String ref) {
  final exact = findLessonMetaById(catalogue, ref);
  if (exact != null || catalogue == null) return exact;
  final n = int.tryParse(ref);
  for (final track in catalogue.tracks) {
    for (final m in track.lessons) {
      if (m.id.startsWith('${ref}_') || (n != null && n > 0 && m.number == n)) {
        return m;
      }
    }
  }
  return null;
}

/// Display name for a related-agent reference, using the CR160 titles.
String relatedAgentLabel(String id) {
  for (final a in kAllAgents) {
    if (a.id == id) return a.displayName;
  }
  return id.replaceAll('_', ' ');
}

/// Non-interactive tag: plain text, no border, no fill, no tap handler.
class RelatedLabel extends StatelessWidget {
  const RelatedLabel({super.key, required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: AmiTypography.labelMono
          .copyWith(fontSize: 11, color: AmiColors.textMed),
    );
  }
}

/// A related-lesson reference: opens the lesson when it resolves, otherwise
/// degrades to a [RelatedLabel].
class RelatedLessonPill extends ConsumerWidget {
  const RelatedLessonPill({
    super.key,
    required this.lessonRef,
    this.identifier = RelatedIds.lessonPill,
    this.beforeOpen,
  });

  final String lessonRef;
  final String identifier;

  /// Runs before navigating — the host sheet closes itself here.
  final VoidCallback? beforeOpen;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meta = resolveRelatedLesson(
        ref.watch(lessonsNotifierProvider).catalogue, lessonRef);
    if (meta == null) return RelatedLabel(text: lessonRef);
    final label =
        meta.code.isNotEmpty ? '${meta.code} · ${meta.title}' : meta.title;
    return Semantics(
      identifier: identifier,
      button: true,
      label: label,
      excludeSemantics: true,
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 40),
        child: InkWell(
          borderRadius: BorderRadius.circular(AmiRadii.card),
          onTap: () {
            final nav = Navigator.of(context);
            beforeOpen?.call();
            nav.push(MaterialPageRoute<void>(
              builder: (_) => LessonReaderScreen(lessonId: meta.id),
            ));
          },
          child: Container(
            alignment: Alignment.center,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AmiColors.slate800,
              borderRadius: BorderRadius.circular(AmiRadii.card),
              border: Border.all(color: AmiColors.hexCyan),
            ),
            child: Text(
              label,
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 11, color: AmiColors.hexCyan),
            ),
          ),
        ),
      ),
    );
  }
}

/// The lesson body renderer, and the two inline chips it emits.
///
/// Lifted verbatim out of `lesson_reader_screen.dart` by CR174 so book mode and
/// the beat deck render prose through **one** renderer. Two copies of a
/// markdown parser is the DEF098 shape at its most predictable: they agree on
/// the day they are forked and drift on the first `{{term:…}}` fix that lands in
/// one of them. Behaviour is unchanged — acceptance #1 requires book mode's
/// output to be identical, so this move is a move, not a rewrite.
///
/// Intentionally lightweight (no third-party dependency). Handles H1/H2/H3,
/// paragraphs, bullet lists, simple pipe tables, blockquotes, inline `**bold**`,
/// `*italic*`, `` `code` ``, and the `{{term:id}}` / `{{lesson:id}}` tokens the
/// server substitutes for `<Term/>` before block extraction.
library;

import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/term_block.dart';
import 'package:ami_trade/widgets/lessons/term_registry.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class LessonMarkdown extends StatelessWidget {
  const LessonMarkdown({super.key, required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final lines = text.split('\n');
    final widgets = <Widget>[];
    final paraBuffer = StringBuffer();
    final listBuffer = <String>[];
    final tableBuffer = <String>[];

    void flushPara() {
      if (paraBuffer.isEmpty) return;
      widgets.add(_inline(paraBuffer.toString().trim(), AmiTypography.body));
      widgets.add(const SizedBox(height: 10));
      paraBuffer.clear();
    }

    void flushList() {
      if (listBuffer.isEmpty) return;
      for (final item in listBuffer) {
        widgets.add(
          Padding(
            padding: const EdgeInsetsDirectional.only(start: 8, bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('• ', style: AmiTypography.body.copyWith(color: AmiColors.hexBlue)),
                Expanded(child: _inline(item, AmiTypography.body)),
              ],
            ),
          ),
        );
      }
      widgets.add(const SizedBox(height: 8));
      listBuffer.clear();
    }

    void flushTable() {
      if (tableBuffer.isEmpty) return;
      // Strip alignment row (e.g. |---|---|)
      final rows = tableBuffer
          .where((r) => !RegExp(r'^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$').hasMatch(r))
          .toList();
      if (rows.isEmpty) {
        tableBuffer.clear();
        return;
      }
      final parsed = rows.map((r) {
        var s = r.trim();
        if (s.startsWith('|')) s = s.substring(1);
        if (s.endsWith('|')) s = s.substring(0, s.length - 1);
        return s.split('|').map((c) => c.trim()).toList();
      }).toList();
      widgets.add(
        Container(
          width: double.infinity,
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(AmiSpacing.s),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(color: AmiColors.slate700),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (int i = 0; i < parsed.length; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final cell in parsed[i])
                        Expanded(
                          child: _inline(
                            cell,
                            i == 0
                                ? AmiTypography.labelMono
                                    .copyWith(color: AmiColors.hexBlue)
                                : AmiTypography.body,
                          ),
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      );
      tableBuffer.clear();
    }

    for (final raw in lines) {
      final l = raw.trimRight();
      if (l.contains('|') && (l.trim().startsWith('|') || l.contains('| '))) {
        flushPara();
        flushList();
        tableBuffer.add(l);
        continue;
      } else if (tableBuffer.isNotEmpty) {
        flushTable();
      }

      if (l.startsWith('# ')) {
        flushPara();
        flushList();
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 4, bottom: 8),
          child: Text(l.substring(2), style: AmiTypography.h2),
        ));
      } else if (l.startsWith('## ')) {
        flushPara();
        flushList();
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 8, bottom: 6),
          child: Text(l.substring(3), style: AmiTypography.h3),
        ));
      } else if (l.startsWith('### ')) {
        flushPara();
        flushList();
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 6, bottom: 4),
          child: Text(l.substring(4), style: AmiTypography.h4),
        ));
      } else if (l.startsWith('- ') || l.startsWith('* ')) {
        flushPara();
        listBuffer.add(l.substring(2));
      } else if (RegExp(r'^\d+\.\s').hasMatch(l)) {
        flushPara();
        listBuffer.add(l.replaceFirst(RegExp(r'^\d+\.\s'), ''));
      } else if (l.startsWith('> ')) {
        flushPara();
        flushList();
        widgets.add(Container(
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: const BoxDecoration(
            // Directional so the accent bar sits on the reading-start edge
            // (left in LTR, right in RTL/Arabic) — CR087.
            border: BorderDirectional(
              start: BorderSide(color: AmiColors.hexBlue, width: 3),
            ),
          ),
          child: _inline(l.substring(2), AmiTypography.body.copyWith(
            fontStyle: FontStyle.italic, color: AmiColors.textMed,
          )),
        ));
      } else if (l.trim().isEmpty) {
        flushPara();
        flushList();
      } else {
        if (paraBuffer.isNotEmpty) paraBuffer.write(' ');
        paraBuffer.write(l);
      }
    }
    flushPara();
    flushList();
    flushTable();

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: widgets);
  }

  /// Tokenise **bold**, *italic*, `code`, `{{term:id}}` and `{{lesson:id}}`
  /// inline. Term tokens render as a tappable inline chip via WidgetSpan;
  /// lesson tokens (CR053) do the same, deep-linking to that lesson's reader.
  Widget _inline(String src, TextStyle base) {
    final spans = <InlineSpan>[];
    final pattern = RegExp(
      r'(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\{\{term:[a-zA-Z0-9_]+\}\}|\{\{lesson:[a-zA-Z0-9_]+\}\})',
    );
    int cursor = 0;
    for (final m in pattern.allMatches(src)) {
      if (m.start > cursor) {
        spans.add(TextSpan(text: src.substring(cursor, m.start), style: base));
      }
      final tok = m.group(0)!;
      if (tok.startsWith('{{term:')) {
        final id = tok.substring(7, tok.length - 2);
        spans.add(WidgetSpan(
          alignment: PlaceholderAlignment.middle,
          child: _InlineTermChip(termId: id, baseStyle: base),
        ));
      } else if (tok.startsWith('{{lesson:')) {
        final id = tok.substring(9, tok.length - 2);
        spans.add(WidgetSpan(
          alignment: PlaceholderAlignment.middle,
          child: _InlineLessonChip(lessonId: id, baseStyle: base),
        ));
      } else if (tok.startsWith('**')) {
        spans.add(TextSpan(
          text: tok.substring(2, tok.length - 2),
          style: base.copyWith(fontWeight: FontWeight.w700),
        ));
      } else if (tok.startsWith('*')) {
        spans.add(TextSpan(
          text: tok.substring(1, tok.length - 1),
          style: base.copyWith(fontStyle: FontStyle.italic),
        ));
      } else if (tok.startsWith('`')) {
        spans.add(TextSpan(
          text: tok.substring(1, tok.length - 1),
          style: base.copyWith(fontFamily: AmiTypography.jetBrains),
        ));
      }
      cursor = m.end;
    }
    if (cursor < src.length) {
      spans.add(TextSpan(text: src.substring(cursor), style: base));
    }
    return Text.rich(TextSpan(children: spans));
  }
}


/// Compact inline term chip — same tap target as TermBlock but sized to
/// flow inline with surrounding prose (no padding around the chip itself
/// so line height stays consistent with the paragraph).
class _InlineTermChip extends StatelessWidget {
  const _InlineTermChip({required this.termId, required this.baseStyle});
  final String termId;
  final TextStyle baseStyle;

  @override
  Widget build(BuildContext context) {
    final entry = TermRegistry.instance.get(termId);
    if (entry == null) {
      // Unknown id → render the prettified id inline as bold text.
      return Text(
        TermBlock.fallbackLabel(termId),
        style: baseStyle.copyWith(fontWeight: FontWeight.w700),
      );
    }
    return GestureDetector(
      onTap: () => showTermSheet(context, termId),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: AmiColors.hexBlue, width: 1),
          ),
        ),
        child: Text(
          entry.term,
          style: baseStyle.copyWith(
            color: AmiColors.hexBlue,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}


/// CR053 — inline chip for a `{{lesson:ID}}` token. Label is the target
/// lesson's CR044 code (matches the tile/meta-bar badge); tap deep-links into
/// that lesson's reader. Distinguished from `_InlineTermChip` by color (cyan,
/// not blue) since it points at a lesson, not a glossary term.
/// Degrades loudly (CR040): an id absent from the catalogue renders as plain
/// text, never a dead tap.
class _InlineLessonChip extends ConsumerWidget {
  const _InlineLessonChip({required this.lessonId, required this.baseStyle});
  final String lessonId;
  final TextStyle baseStyle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final catalogue = ref.watch(lessonsNotifierProvider).catalogue;
    final meta = findLessonMetaById(catalogue, lessonId);
    if (meta == null) {
      return Text(lessonId, style: baseStyle);
    }
    return GestureDetector(
      onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => LessonReaderScreen(lessonId: meta.id),
      )),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
        decoration: const BoxDecoration(
          border: Border(
            bottom: BorderSide(color: AmiColors.hexCyan, width: 1),
          ),
        ),
        child: Text(
          meta.codeLabel,
          style: baseStyle.copyWith(
            color: AmiColors.hexCyan,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

/// Flat scan of the catalogue's tracks for a lesson id. Small enough
/// (hundreds of lessons) that a lookup map isn't worth the extra state.
LessonMeta? findLessonMetaById(LessonCatalogue? catalogue, String id) {
  if (catalogue == null) return null;
  for (final track in catalogue.tracks) {
    for (final m in track.lessons) {
      if (m.id == id) return m;
    }
  }
  return null;
}

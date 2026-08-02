/// CR136 — renders a STORED Portfolio Health Finding (head disclosure + §F1–§F5 markdown) verbatim; shared by the Journal detail branch (M08) and the Finding detail screen (M09). Never recomputes.
///
/// Payload-pure by design: everything shown here was rendered, validated and
/// frozen by the backend at write time. The widget takes no provider, performs
/// no arithmetic, and reformats no number — an archived report has to read
/// exactly as it did when it was filed, and a client that recomputed anything
/// would eventually disagree with its own stored copy.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/room/room_board.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

class FindingSections extends StatelessWidget {
  const FindingSections({super.key, required this.payload});

  final Map<String, dynamic> payload;

  /// §F1–§F5 in the order the report is written. `head` is not in this list
  /// because it is not a section — it is the disclosure block, and it renders
  /// first with its own chrome.
  static const sectionOrder = ['f1', 'f2', 'f3', 'f4', 'f5'];

  static Map<String, dynamic>? _sections(Map<String, dynamic> payload) {
    final raw = payload['sections'];
    return raw is Map ? Map<String, dynamic>.from(raw) : null;
  }

  static String? _disclosure(Map<String, dynamic> payload) {
    final sections = _sections(payload);
    // `sections.head` is the shipped shape (the seam register's pinned payload).
    // A top-level `disclosure` key is read as a fallback so an entry written by
    // an older build still renders its disclosures rather than falling through
    // to the raw dump.
    final candidates = [sections?['head'], payload['disclosure']];
    for (final candidate in candidates) {
      if (candidate is String && candidate.trim().isNotEmpty) return candidate;
    }
    return null;
  }

  /// True only when the stored payload carries what F19 requires: a non-empty
  /// disclosure AND a sections map. Anything less renders via the generic
  /// payload dump instead — degrade loudly, never a disclosure-less report.
  static bool isRenderable(Map<String, dynamic> payload) =>
      _disclosure(payload) != null && _sections(payload) != null;

  @override
  Widget build(BuildContext context) {
    final sections = _sections(payload) ?? const {};
    final disclosure = _disclosure(payload);
    final style = agentMarkdownStyle(AmiColors.textMed);
    final children = <Widget>[];

    if (disclosure != null) {
      // F19 reversed the foot-of-report placement: the caveats come FIRST,
      // because a reader who stops halfway must not have stopped before them.
      children.add(
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AmiSpacing.s),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(color: AmiColors.slate700),
          ),
          child: MarkdownBody(
            data: disclosure,
            shrinkWrap: true,
            styleSheet: style,
          ),
        ),
      );
    }

    for (final key in sectionOrder) {
      final body = sections[key];
      // Skipped, never substituted: a section the backend did not store is one
      // it chose not to write, and inventing a placeholder here would put words
      // in the report that were never validated.
      if (body is! String || body.trim().isEmpty) continue;
      children.add(const SizedBox(height: AmiSpacing.s));
      children.add(
        MarkdownBody(data: body, shrinkWrap: true, styleSheet: style),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    );
  }
}

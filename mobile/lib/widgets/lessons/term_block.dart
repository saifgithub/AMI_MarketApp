/// TermBlock — renders `<Term id="…"/>` inside a lesson body as a small
/// tappable chip. Tapping opens a bottom sheet with the term and
/// definition; related terms surface as quick links to other Term
/// sheets, related lessons surface as labels (no nav wiring yet).
///
/// Unknown ids render as plain bold text — a typo or not-yet-translated
/// reference never crashes the reader.
library;

import 'package:ami_trade/models/glossary.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/term_registry.dart';
import 'package:flutter/material.dart';

class TermBlock extends StatelessWidget {
  const TermBlock({super.key, required this.termId, this.locale = 'en'});

  final String termId;
  final String locale;

  @override
  Widget build(BuildContext context) {
    final entry = TermRegistry.instance.get(termId, locale: locale);
    if (entry == null) {
      return Text(
        fallbackLabel(termId),
        style: AmiTypography.body.copyWith(fontWeight: FontWeight.w700),
      );
    }
    return _TermChip(entry: entry, locale: locale);
  }

  static String fallbackLabel(String id) {
    return id
        .replaceAll('_', ' ')
        .split(' ')
        .where((w) => w.isNotEmpty)
        .map((w) => w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }
}


class _TermChip extends StatelessWidget {
  const _TermChip({required this.entry, required this.locale});

  final GlossaryEntry entry;
  final String locale;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => _openSheet(context, entry, locale),
      borderRadius: BorderRadius.circular(AmiRadii.card),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.hexBlue),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.menu_book_outlined,
                color: AmiColors.hexBlue, size: 14),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                entry.term,
                style: AmiTypography.body.copyWith(
                  color: AmiColors.hexBlue,
                  fontWeight: FontWeight.w600,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}


void _openSheet(BuildContext context, GlossaryEntry entry, String locale) {
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: AmiColors.slate900,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => _TermSheet(entry: entry, locale: locale),
  );
}


class _TermSheet extends StatelessWidget {
  const _TermSheet({required this.entry, required this.locale});

  final GlossaryEntry entry;
  final String locale;

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
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: AmiColors.slate700,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: AmiSpacing.m),
                Row(
                  children: [
                    const Icon(Icons.menu_book_outlined,
                        color: AmiColors.hexBlue, size: 18),
                    const SizedBox(width: 6),
                    Text(
                      entry.category.replaceAll('_', ' ').toUpperCase(),
                      style: AmiTypography.labelMono.copyWith(
                        color: AmiColors.hexBlue,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AmiSpacing.s),
                Text(entry.term, style: AmiTypography.h2),
                const SizedBox(height: AmiSpacing.m),
                Text(entry.definition, style: AmiTypography.body),
                if (entry.seeAlso.isNotEmpty) ...[
                  const SizedBox(height: AmiSpacing.l),
                  Text(
                    'SEE ALSO',
                    style: AmiTypography.labelMono.copyWith(
                      color: AmiColors.textMed,
                    ),
                  ),
                  const SizedBox(height: AmiSpacing.s),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final relId in entry.seeAlso)
                        _RelatedTermChip(
                          termId: relId,
                          locale: locale,
                          onTap: () {
                            Navigator.of(context).pop();
                            final rel = TermRegistry.instance
                                .get(relId, locale: locale);
                            if (rel != null) {
                              _openSheet(context, rel, locale);
                            }
                          },
                        ),
                    ],
                  ),
                ],
                if (entry.relatedLessons.isNotEmpty) ...[
                  const SizedBox(height: AmiSpacing.l),
                  Text(
                    'RELATED LESSONS',
                    style: AmiTypography.labelMono.copyWith(
                      color: AmiColors.textMed,
                    ),
                  ),
                  const SizedBox(height: AmiSpacing.s),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final lid in entry.relatedLessons)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: AmiColors.slate800,
                            borderRadius: BorderRadius.circular(4),
                            border: Border.all(color: AmiColors.slate700),
                          ),
                          child: Text(
                            lid,
                            style: AmiTypography.labelMono
                                .copyWith(fontSize: 11),
                          ),
                        ),
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


class _RelatedTermChip extends StatelessWidget {
  const _RelatedTermChip({
    required this.termId,
    required this.locale,
    required this.onTap,
  });

  final String termId;
  final String locale;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final entry = TermRegistry.instance.get(termId, locale: locale);
    final label = entry?.term ?? TermBlock.fallbackLabel(termId);
    final enabled = entry != null;
    return InkWell(
      onTap: enabled ? onTap : null,
      borderRadius: BorderRadius.circular(AmiRadii.card),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(
            color: enabled ? AmiColors.hexBlue : AmiColors.slate700,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.menu_book_outlined,
              color: enabled ? AmiColors.hexBlue : AmiColors.textMed,
              size: 12,
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: AmiTypography.body.copyWith(
                color: enabled ? AmiColors.hexBlue : AmiColors.textMed,
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

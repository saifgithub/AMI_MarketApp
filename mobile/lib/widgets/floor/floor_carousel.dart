/// CR173 slice 2 — the answer-card carousel that replaced the roster as the
/// Floor's header.
///
/// Five rules, all of them from measured sources (research 09 §9.2), and all
/// five enforced here rather than remembered by whoever adds the next card:
///
///  1. **Never auto-rotates.** There is no `Timer` in this file and there must
///     not be one. On mobile a rotating carousel moves the thing under the
///     thumb between the decision to tap and the tap (NN/g, Baymard).
///  2. **Priority order, portfolio first** — the caller supplies the order;
///     [assertPortfolioFirst] is what makes that a rule instead of a habit.
///  3. **Nothing load-bearing past card 1.** 55–89% of carousel interactions
///     never leave slide 1 (Runyon), so every capability behind cards 2+ has a
///     second home. That one is a content constraint, checked in review.
///  4. **A peek slice, always.** [_viewport] is < 1.0 so the next card's edge
///     is visible at rest — a carousel that looks like a card does not get
///     swiped (Friedman).
///  5. **≤5 frames** (NN/g), asserted.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// Wide enough to read, narrow enough that the next card's edge shows. Rule 4
/// is this number being less than 1.
const double _viewport = 0.88;

const int kMaxFloorCards = 5;

const double kFloorCardHeight = 120;

class FloorCard {
  const FloorCard({required this.id, required this.child, this.onTap});

  /// Stable, locale-independent — used by the priority assertion and by tests,
  /// so neither depends on a translated label.
  final String id;

  final Widget child;

  /// Where the card opens. Null for a card that is its own answer.
  final VoidCallback? onTap;
}

class FloorCarousel extends StatefulWidget {
  const FloorCarousel({super.key, required this.cards});

  final List<FloorCard> cards;

  @override
  State<FloorCarousel> createState() => _FloorCarouselState();
}

class _FloorCarouselState extends State<FloorCarousel> {
  late final PageController _ctrl =
      PageController(viewportFraction: _viewport);
  int _page = 0;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    assert(widget.cards.length <= kMaxFloorCards,
        'rule 5 — at most $kMaxFloorCards cards, got ${widget.cards.length}');
    assert(widget.cards.isNotEmpty, 'card 1 always renders (acceptance #4)');
    assert(assertPortfolioFirst(widget.cards));

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          // Fixed, because a PageView needs a bounded cross-axis extent — so
          // the height is a budget every card has to live inside. Sized for
          // the tallest legitimate content (a label, a big number and two
          // lines of summary) at the longest locale, rather than for English:
          // the first build used the 42pt `statBig` and overflowed by 100px
          // the moment it met a real viewport.
          height: kFloorCardHeight,
          child: PageView.builder(
            controller: _ctrl,
            // No `onPageChanged`-driven timer, no autoplay, no `animateTo` on a
            // clock. The carousel moves under the thumb or not at all (rule 1).
            onPageChanged: (i) => setState(() => _page = i),
            itemCount: widget.cards.length,
            itemBuilder: (context, i) {
              final card = widget.cards[i];
              return Padding(
                padding: const EdgeInsets.only(right: AmiSpacing.s),
                child: _CardShell(card: card),
              );
            },
          ),
        ),
        // Dots inside the surface, not floating over the card below it.
        if (widget.cards.length > 1) ...[
          const SizedBox(height: AmiSpacing.xs),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              for (var i = 0; i < widget.cards.length; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: Semantics(
                    label: 'card ${i + 1} of ${widget.cards.length}',
                    selected: i == _page,
                    child: Container(
                      width: 5,
                      height: 5,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: i == _page
                            ? AmiColors.hexCyan
                            : AmiColors.slate700,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

/// Rule 2. Not a comment: the portfolio is the answer to "how am I doing",
/// which is the question 55–89% of users ask and never swipe past.
bool assertPortfolioFirst(List<FloorCard> cards) {
  assert(cards.isEmpty || cards.first.id == 'portfolio',
      'rule 2 — the portfolio card leads, got "${cards.first.id}"');
  return true;
}

class _CardShell extends StatelessWidget {
  const _CardShell({required this.card});

  final FloorCard card;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: card.onTap,
      child: Container(
        padding: const EdgeInsets.all(AmiSpacing.m),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.slate700),
        ),
        child: card.child,
      ),
    );
  }
}

/// The label above each card's content. One renderer, so the three cards cannot
/// drift into three different heading treatments (DEF098).
class FloorCardLabel extends StatelessWidget {
  const FloorCardLabel({super.key, required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Text(label,
        style: AmiTypography.labelMono.copyWith(fontSize: 10, color: color));
  }
}

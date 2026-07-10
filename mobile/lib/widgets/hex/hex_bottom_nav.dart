/// CR016 (E4/D8 / C2) — HexBottomNav: the AMI signature bottom navigation.
/// Five hex-clipped destination pills; the active pill fills with a purple→blue
/// brand gradient + glow (the "center brand cell" treatment), inactive pills are
/// muted icon+label. Material semantics are preserved — same five destinations,
/// full-cell touch targets, `Semantics(button, selected)` — only the visuals
/// change. Drop-in for the stock `BottomNavigationBar` in `home_shell.dart`.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

class HexNavItem {
  const HexNavItem({required this.icon, required this.label});
  final IconData icon;
  final String label;
}

class HexBottomNav extends StatelessWidget {
  const HexBottomNav({
    super.key,
    required this.currentIndex,
    required this.onTap,
    required this.items,
  });

  final int currentIndex;
  final ValueChanged<int> onTap;
  final List<HexNavItem> items;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 62,
      child: Row(
        children: [
          for (var i = 0; i < items.length; i++)
            Expanded(child: _Cell(
              item: items[i],
              active: i == currentIndex,
              onTap: () => onTap(i),
            )),
        ],
      ),
    );
  }
}

class _Cell extends StatelessWidget {
  const _Cell({required this.item, required this.active, required this.onTap});

  final HexNavItem item;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final content = Column(
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(item.icon,
            size: 22, color: active ? Colors.white : AmiColors.textLow),
        const SizedBox(height: 3),
        Text(
          item.label,
          style: AmiTypography.labelMono.copyWith(
            fontSize: 9,
            color: active ? AmiColors.textHigh : AmiColors.textLow,
          ),
        ),
      ],
    );

    Widget cell;
    if (active) {
      cell = DecoratedBox(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
                color: AmiColors.hexPurple.withValues(alpha: 0.3),
                blurRadius: 16),
            BoxShadow(
                color: AmiColors.hexBlue.withValues(alpha: 0.35),
                blurRadius: 22),
          ],
        ),
        child: ClipPath(
          clipper: const FlatTopHexagonClipper(cornerCut: 12),
          child: Container(
            alignment: Alignment.center,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AmiColors.hexPurple.withValues(alpha: 0.22),
                  AmiColors.hexBlue.withValues(alpha: 0.22),
                ],
              ),
              border: Border.all(color: AmiColors.hexBlue, width: 1),
            ),
            child: content,
          ),
        ),
      );
    } else {
      cell = Center(child: content);
    }

    return Semantics(
      button: true,
      selected: active,
      label: item.label,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
          child: cell,
        ),
      ),
    );
  }
}

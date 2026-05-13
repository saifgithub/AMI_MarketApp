/// HexMeshOverlay — 3% opacity hex tessellation texture for dark surfaces.
///
/// Per spec (README.md "Backgrounds"):
///   "Hex-mesh SVG overlay at 3% opacity (for texture on dark surfaces)"
///
/// Usage: wrap your scaffold body in a Stack and drop a
/// `Positioned.fill(child: const HexMeshOverlay())` above it. Pointer
/// events fall through (`IgnorePointer`) so it never intercepts taps.
library;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

class HexMeshOverlay extends StatelessWidget {
  const HexMeshOverlay({super.key, this.opacity = 0.03});
  final double opacity;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Opacity(
        opacity: opacity,
        child: SvgPicture.asset(
          'assets/hex_mesh.svg',
          fit: BoxFit.cover,
          alignment: Alignment.topCenter,
        ),
      ),
    );
  }
}

/// AMI hex design system — Flutter port of `colors_and_type.css`.
///
/// Source of truth: /Volumes/Extreme Pro/AMI AI Design System/colors_and_type.css
/// Spec doc: docs/05_design/ami_hex_in_flutter.md
library;

import 'package:flutter/material.dart';

// ─────────────────────────────────────────────────────────────────────────
// Colors
// ─────────────────────────────────────────────────────────────────────────

abstract final class AmiColors {
  // Canvas / surfaces
  static const Color slate900 = Color(0xFF0F172A); // primary canvas
  static const Color slate800 = Color(0xFF1E293B); // surface
  static const Color slate700 = Color(0xFF334155); // borders
  static const Color slate600 = Color(0xFF475569); // muted text
  static const Color slate500 = Color(0xFF64748B); // captions

  // Brand
  static const Color hexBlue = Color(0xFF3B82F6); // primary

  // Role accents (6)
  static const Color hexCyan = Color(0xFF06B6D4); // analysts
  static const Color hexAmber = Color(0xFFF59E0B); // risk
  static const Color hexGreen = Color(0xFF10B981); // trader / positive
  static const Color hexRed = Color(0xFFEF4444); // negative / violations
  static const Color hexPurple = Color(0xFFA855F7); // researchers + managers
  static const Color hexPink = Color(0xFFEC4899); // concierge

  // Text on dark
  static const Color textHigh = Colors.white;
  static const Color textMed = Color(0xFFCBD5E1);
  static const Color textLow = Color(0xFF94A3B8);

  // Glass surfaces
  static const Color glass = Color(0xB3111827); // rgba(17,24,39,0.7)
  static const Color glassChrome = Color(0xD90F172A); // rgba(15,23,42,0.85)
}

/// Maps an agent family ("analyst", "risk", "researcher", "manager",
/// "execution", "concierge") to its accent color.
Color agentFamilyColor(String family) {
  switch (family) {
    case 'analyst':
      return AmiColors.hexCyan;
    case 'risk':
      return AmiColors.hexAmber;
    case 'execution':
      return AmiColors.hexGreen;
    case 'researcher':
    case 'manager':
      return AmiColors.hexPurple;
    case 'concierge':
      return AmiColors.hexPink;
    default:
      return AmiColors.hexBlue;
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Typography
// ─────────────────────────────────────────────────────────────────────────

abstract final class AmiTypography {
  static const String inter = 'Inter';
  static const String jetBrains = 'JetBrainsMono';

  // Headers (Inter)
  static const TextStyle h1 = TextStyle(
    fontFamily: inter,
    fontSize: 32,
    fontWeight: FontWeight.w700,
    color: AmiColors.textHigh,
    height: 1.2,
  );
  static const TextStyle h2 = TextStyle(
    fontFamily: inter,
    fontSize: 24,
    fontWeight: FontWeight.w700,
    color: AmiColors.textHigh,
  );
  static const TextStyle h3 = TextStyle(
    fontFamily: inter,
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: AmiColors.textHigh,
  );
  static const TextStyle h4 = TextStyle(
    fontFamily: inter,
    fontSize: 16,
    fontWeight: FontWeight.w600,
    color: AmiColors.textHigh,
  );

  // Body (Inter)
  static const TextStyle body = TextStyle(
    fontFamily: inter,
    fontSize: 14,
    fontWeight: FontWeight.w400,
    color: AmiColors.textMed,
    height: 1.5,
  );
  static const TextStyle caption = TextStyle(
    fontFamily: inter,
    fontSize: 13,
    color: AmiColors.textLow,
  );

  // Mono (JetBrains)
  static const TextStyle labelMono = TextStyle(
    fontFamily: jetBrains,
    fontSize: 13,
    fontWeight: FontWeight.w500,
    letterSpacing: 1.3, // ~0.1em
    color: AmiColors.textHigh,
  );
  static const TextStyle statBig = TextStyle(
    fontFamily: jetBrains,
    fontSize: 42,
    fontWeight: FontWeight.w700,
    color: AmiColors.textHigh,
  );
  static const TextStyle statMid = TextStyle(
    fontFamily: jetBrains,
    fontSize: 24,
    fontWeight: FontWeight.w600,
    color: AmiColors.textHigh,
  );
  static const TextStyle statSmall = TextStyle(
    fontFamily: jetBrains,
    fontSize: 16,
    fontWeight: FontWeight.w500,
    color: AmiColors.textHigh,
  );
  static const TextStyle stream = TextStyle(
    fontFamily: jetBrains,
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: AmiColors.textMed,
    height: 1.5,
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Spacing / radii / motion
// ─────────────────────────────────────────────────────────────────────────

abstract final class AmiSpacing {
  static const double xs = 4.0;
  static const double s = 8.0;
  static const double m = 16.0;
  static const double l = 24.0;
  static const double xl = 32.0;
  static const double xxl = 48.0;
}

abstract final class AmiRadii {
  static const double card = 8.0;
  static const double sheet = 12.0;
  static const double hexCornerMobile = 10.0;
  static const double hexCornerDesktop = 20.0;
}

abstract final class AmiMotion {
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration normal = Duration(milliseconds: 200);
  static const Duration slow = Duration(milliseconds: 350);

  // AMI default easing
  static const Cubic easeOut = Cubic(0.4, 0, 0.2, 1);
}

// ─────────────────────────────────────────────────────────────────────────
// Theme assembly
// ─────────────────────────────────────────────────────────────────────────

ThemeData amiTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AmiColors.slate900,
    fontFamily: AmiTypography.inter,
    colorScheme: const ColorScheme.dark(
      primary: AmiColors.hexBlue,
      secondary: AmiColors.hexCyan,
      surface: AmiColors.slate800,
      onPrimary: AmiColors.textHigh,
      onSurface: AmiColors.textMed,
      error: AmiColors.hexRed,
    ),
    textTheme: const TextTheme(
      headlineLarge: AmiTypography.h1,
      headlineMedium: AmiTypography.h2,
      titleLarge: AmiTypography.h3,
      titleMedium: AmiTypography.h4,
      bodyMedium: AmiTypography.body,
      bodySmall: AmiTypography.caption,
      labelLarge: AmiTypography.labelMono,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AmiColors.glassChrome,
      elevation: 0,
      toolbarHeight: 64,
      iconTheme: IconThemeData(color: AmiColors.textHigh),
      titleTextStyle: AmiTypography.h4,
    ),
    iconTheme: const IconThemeData(color: AmiColors.textMed),
    dividerColor: AmiColors.slate700,
  );
}

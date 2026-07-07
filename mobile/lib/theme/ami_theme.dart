/// AMI hex design system — Flutter port of `colors_and_type.css`.
///
/// Source of truth: /Volumes/Extreme Pro/AMI AI Design System/colors_and_type.css
/// Spec doc: docs/initial_specs/05_design/ami_hex_in_flutter.md
///
/// Typography uses IBM Plex Sans + IBM Plex Mono via the `google_fonts`
/// package — they're the canonical AMI typefaces. Inter and JetBrainsMono
/// are bundled as the explicit fallbacks the spec names; they cover the
/// first paint before Plex resolves on cold launch.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// ─────────────────────────────────────────────────────────────────────────
// Colors
// ─────────────────────────────────────────────────────────────────────────

abstract final class AmiColors {
  // Canvas / surfaces (per colors_and_type.css v2)
  static const Color slate900 = Color(0xFF0F172A); // canvas (--dark-bg)
  static const Color slate800 = Color(0xFF111827); // opaque panel (--panel-bg-solid)
  static const Color slate700 = Color(0xFF374151); // border (--border-color)
  static const Color slate600 = Color(0xFF475569); // muted
  static const Color slate500 = Color(0xFF64748B); // dim
  static const Color cardBg = Color(0xFF152845); // --card-bg
  static const Color cardBgAlt = Color(0xFF121E37); // --card-bg-alt

  // Brand
  static const Color hexBlue = Color(0xFF3B82F6); // --hex-blue
  static const Color hexBlue600 = Color(0xFF2563EB); // hover

  // Role accents (6) — spec values
  static const Color hexCyan = Color(0xFF06B6D4); // --accent-cyan
  static const Color hexAmber = Color(0xFFF59E0B); // --accent-amber
  static const Color hexGreen = Color(0xFF10B981); // --accent-green
  static const Color hexRed = Color(0xFFEF4444); // --accent-red
  static const Color hexPurple = Color(0xFF8B5CF6); // --accent-purple (was #A855F7)
  static const Color hexPink = Color(0xFFEC4899); // --accent-pink

  // Text on dark
  static const Color textHigh = Color(0xFFF3F4F6); // --text-main
  static const Color textMed = Color(0xFF94A3B8); // --text-muted
  static const Color textLow = Color(0xFF64748B); // --text-dim

  // Glass surfaces
  static const Color glass = Color(0xB3111827); // rgba(17,24,39,0.7)
  static const Color glassChrome = Color(0xD90F172A); // rgba(15,23,42,0.85)

  // Brand glow
  static const Color hexGlow = Color(0x803B82F6); // rgba(59,130,246,0.5)

  // Hairline borders (--border-light / --border-subtle)
  static const Color borderLight = Color(0x1AFFFFFF); // rgba(255,255,255,0.10)
  static const Color borderSubtle = Color(0x0DFFFFFF); // rgba(255,255,255,0.05)
}

/// Light-mode token overrides (per AMI AI Design System DEVELOPER_PROMPT_LIGHT_MODE.md).
///
/// These are ONLY used when themeMode resolves to light. Dark is always the
/// default; light is for bright/outdoor conditions (iOS: system preference or
/// manual Settings toggle; no ambient sensor on iOS).
abstract final class AmiColorsLight {
  static const Color canvas = Color(0xFFF1F5F9);    // slate-100
  static const Color panel = Color(0xFFFFFFFF);      // white
  static const Color cardBg = Color(0xFFF8FAFC);
  static const Color cardBgAlt = Color(0xFFEEF2F7);
  static const Color border = Color(0xFFCBD5E1);
  static const Color textHigh = Color(0xFF0F172A);   // slate-900
  static const Color textMed = Color(0xFF475569);    // slate-600
  static const Color textLow = Color(0xFF64748B);

  // AA-safe darkened accent-text variants (≥4.5:1 on white canvas)
  static const Color accentCyan = Color(0xFF0891B2);
  static const Color accentGreen = Color(0xFF047857);
  static const Color accentAmber = Color(0xFFB45309);
  static const Color accentRed = Color(0xFFB91C1C);
  static const Color accentPurple = Color(0xFF6D28D9);
  static const Color accentBlue = Color(0xFF2563EB); // --accent-blue-text (= hexBlue600)
  static const Color accentPink = Color(0xFFBE185D);
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
  // Canonical typefaces (per design v2). Inter / JetBrainsMono live on
  // disk as the spec's named fallbacks for cold-launch paint.
  static const String inter = 'Inter';
  static const String jetBrains = 'JetBrainsMono';
  static const String plexSans = 'IBM Plex Sans';
  static const String plexMono = 'IBM Plex Mono';

  // Headers (IBM Plex Sans)
  static final TextStyle h1 = GoogleFonts.ibmPlexSans(
    fontSize: 32,
    fontWeight: FontWeight.w800,
    color: AmiColors.textHigh,
    height: 1.2,
  );
  static final TextStyle h2 = GoogleFonts.ibmPlexSans(
    fontSize: 24,
    fontWeight: FontWeight.w700,
    color: AmiColors.textHigh,
    height: 1.2,
  );
  static final TextStyle h3 = GoogleFonts.ibmPlexSans(
    fontSize: 18,
    fontWeight: FontWeight.w700,
    color: AmiColors.textHigh,
    height: 1.2,
  );
  static final TextStyle h4 = GoogleFonts.ibmPlexSans(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    color: AmiColors.textHigh,
    height: 1.2,
  );

  // Body (IBM Plex Sans)
  static final TextStyle bodyLg = GoogleFonts.ibmPlexSans(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    color: AmiColors.textMed,
    height: 1.5,
  );
  static final TextStyle body = GoogleFonts.ibmPlexSans(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    color: AmiColors.textMed,
    height: 1.5,
  );
  static final TextStyle bodySm = GoogleFonts.ibmPlexSans(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: AmiColors.textMed,
    height: 1.5,
  );
  static final TextStyle caption = GoogleFonts.ibmPlexSans(
    fontSize: 11,
    fontWeight: FontWeight.w400,
    color: AmiColors.textLow,
  );

  // Mono (IBM Plex Mono) — labels, stats, log streams.
  static final TextStyle labelMono = GoogleFonts.ibmPlexMono(
    fontSize: 12,
    fontWeight: FontWeight.w700,
    letterSpacing: 1.8, // ~0.15em per spec
    color: AmiColors.textHigh,
  );
  static final TextStyle statBig = GoogleFonts.ibmPlexMono(
    fontSize: 42,
    fontWeight: FontWeight.w700,
    color: AmiColors.textHigh,
  );
  static final TextStyle statMid = GoogleFonts.ibmPlexMono(
    fontSize: 24,
    fontWeight: FontWeight.w600,
    color: AmiColors.textHigh,
  );
  static final TextStyle dataMd = GoogleFonts.ibmPlexMono(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    color: AmiColors.textHigh,
  );
  static final TextStyle statSmall = GoogleFonts.ibmPlexMono(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: AmiColors.textHigh,
  );
  static final TextStyle stream = GoogleFonts.ibmPlexMono(
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
  static const double none = 0.0;
  static const double xs = 4.0;
  static const double s = 8.0;
  static const double sm = 12.0; // --sp-3
  static const double m = 16.0;
  static const double l = 24.0;
  static const double xl = 32.0;
  static const double xxl = 48.0;
  static const double xxxl = 64.0; // --sp-8
}

abstract final class AmiRadii {
  static const double sm = 4.0; // --radius-sm
  static const double md = 6.0; // --radius-md
  static const double card = 8.0;
  static const double sheet = 12.0;
  static const double hexCornerMobile = 10.0;
  static const double hexCornerDesktop = 20.0;
}

abstract final class AmiMotion {
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration normal = Duration(milliseconds: 200);
  static const Duration slow = Duration(milliseconds: 300);

  // AMI default easing
  static const Cubic easeOut = Cubic(0.4, 0, 0.2, 1);
}

/// Elevation + glow (per colors_and_type.css --shadow-* / --glow-*).
/// The DS applies these as filters on hex clip-paths; in Flutter they land
/// as BoxShadow lists on the container BEHIND any clipped child.
abstract final class AmiShadow {
  static const List<BoxShadow> card = [
    BoxShadow(color: Color(0x4D000000), offset: Offset(0, 8), blurRadius: 30),
  ];
  static const List<BoxShadow> modal = [
    BoxShadow(color: Color(0x99000000), offset: Offset(0, 25), blurRadius: 60),
  ];
  static const List<BoxShadow> glowBlue = [
    BoxShadow(color: Color(0x663B82F6), blurRadius: 20),
  ];
  static const List<BoxShadow> glowPurple = [
    BoxShadow(color: Color(0x668B5CF6), blurRadius: 30),
  ];
}

// ─────────────────────────────────────────────────────────────────────────
// Theme assembly
// ─────────────────────────────────────────────────────────────────────────

ThemeData amiTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AmiColors.slate900,
    // Author against Plex; Inter is the cold-launch fallback only (DS README).
    fontFamily: GoogleFonts.ibmPlexSans().fontFamily,
    fontFamilyFallback: const [AmiTypography.inter],
    colorScheme: const ColorScheme.dark(
      primary: AmiColors.hexBlue,
      secondary: AmiColors.hexCyan,
      surface: AmiColors.slate800,
      onPrimary: AmiColors.textHigh,
      onSurface: AmiColors.textMed,
      error: AmiColors.hexRed,
    ),
    textTheme: TextTheme(
      headlineLarge: AmiTypography.h1,
      headlineMedium: AmiTypography.h2,
      titleLarge: AmiTypography.h3,
      titleMedium: AmiTypography.h4,
      bodyMedium: AmiTypography.body,
      bodySmall: AmiTypography.caption,
      labelLarge: AmiTypography.labelMono,
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: AmiColors.glassChrome,
      elevation: 0,
      toolbarHeight: 64,
      iconTheme: const IconThemeData(color: AmiColors.textHigh),
      titleTextStyle: AmiTypography.h4,
    ),
    iconTheme: const IconThemeData(color: AmiColors.textMed),
    dividerColor: AmiColors.slate700,
  );
}

ThemeData amiLightTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    scaffoldBackgroundColor: AmiColorsLight.canvas,
    fontFamily: GoogleFonts.ibmPlexSans().fontFamily,
    fontFamilyFallback: const [AmiTypography.inter],
    colorScheme: const ColorScheme.light(
      primary: AmiColorsLight.accentBlue,
      secondary: AmiColorsLight.accentCyan,
      surface: AmiColorsLight.panel,
      onPrimary: AmiColorsLight.textHigh,
      onSurface: AmiColorsLight.textMed,
      error: AmiColorsLight.accentRed,
    ),
    textTheme: TextTheme(
      headlineLarge: AmiTypography.h1.copyWith(color: AmiColorsLight.textHigh),
      headlineMedium: AmiTypography.h2.copyWith(color: AmiColorsLight.textHigh),
      titleLarge: AmiTypography.h3.copyWith(color: AmiColorsLight.textHigh),
      titleMedium: AmiTypography.h4.copyWith(color: AmiColorsLight.textHigh),
      bodyMedium: AmiTypography.body.copyWith(color: AmiColorsLight.textMed),
      bodySmall: AmiTypography.caption.copyWith(color: AmiColorsLight.textLow),
      labelLarge: AmiTypography.labelMono.copyWith(color: AmiColorsLight.textHigh),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: AmiColorsLight.panel,
      elevation: 0,
      toolbarHeight: 64,
      iconTheme: const IconThemeData(color: AmiColorsLight.textHigh),
      titleTextStyle: AmiTypography.h4.copyWith(color: AmiColorsLight.textHigh),
    ),
    iconTheme: const IconThemeData(color: AmiColorsLight.textMed),
    dividerColor: AmiColorsLight.border,
  );
}

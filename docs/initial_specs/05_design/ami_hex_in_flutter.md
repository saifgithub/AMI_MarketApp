# AMI Hex Design in Flutter

How to implement the AMI "Hex-Reinforced Precision" design language in a Flutter codebase.

The source-of-truth AMI design system: `/Volumes/Extreme Pro/AMI AI Design System/`. Read `colors_and_type.css` for the canonical tokens.

## Theme tokens (mirror of `colors_and_type.css`)

Implement in `mobile/lib/theme/ami_theme.dart`:

```dart
class AmiColors {
  // Canvas
  static const slate900 = Color(0xFF0F172A);   // primary canvas
  static const slate800 = Color(0xFF1E293B);   // surface
  static const slate700 = Color(0xFF334155);   // borders
  static const slate600 = Color(0xFF475569);   // muted text
  static const slate500 = Color(0xFF64748B);   // captions

  // Brand (hex-blue primary + 6 accent colors)
  static const hexBlue   = Color(0xFF3B82F6);  // primary
  static const hexCyan   = Color(0xFF06B6D4);  // analysts
  static const hexAmber  = Color(0xFFF59E0B);  // risk / phase 1
  static const hexGreen  = Color(0xFF10B981);  // positive / trader
  static const hexRed    = Color(0xFFEF4444);  // negative
  static const hexPurple = Color(0xFFA855F7);  // researchers / managers
  static const hexPink   = Color(0xFFEC4899);  // concierge / tertiary

  // Text on dark
  static const white      = Color(0xFFFFFFFF);
  static const textHigh   = white;
  static const textMed    = Color(0xFFCBD5E1);
  static const textLow    = Color(0xFF94A3B8);

  // Glass
  static const glass      = Color(0xB3111827);  // rgba(17,24,39,0.7)
  static const glassChrome = Color(0xD90F172A); // header chrome, 0.85
}

class AmiTypography {
  // Inter for body, JetBrains Mono for numerics/labels/buttons
  static const inter      = 'Inter';
  static const jetBrains  = 'JetBrainsMono';

  // Type ramp — sizes per AMI spec
  static const h1     = TextStyle(fontFamily: inter, fontSize: 32, fontWeight: FontWeight.w700, color: AmiColors.textHigh, height: 1.2);
  static const h2     = TextStyle(fontFamily: inter, fontSize: 24, fontWeight: FontWeight.w700, color: AmiColors.textHigh);
  static const h3     = TextStyle(fontFamily: inter, fontSize: 18, fontWeight: FontWeight.w600, color: AmiColors.textHigh);
  static const h4     = TextStyle(fontFamily: inter, fontSize: 16, fontWeight: FontWeight.w600, color: AmiColors.textHigh);

  static const body   = TextStyle(fontFamily: inter, fontSize: 14, fontWeight: FontWeight.w400, color: AmiColors.textMed, height: 1.5);
  static const caption = TextStyle(fontFamily: inter, fontSize: 13, color: AmiColors.textLow);

  // JetBrains Mono — all-caps label / button / stat
  static const labelMono = TextStyle(
    fontFamily: jetBrains,
    fontSize: 13,
    fontWeight: FontWeight.w500,
    letterSpacing: 1.3,    // ~0.1em
    color: AmiColors.textHigh,
  );

  static const statBig = TextStyle(
    fontFamily: jetBrains,
    fontSize: 42,
    fontWeight: FontWeight.w700,
    color: AmiColors.textHigh,
  );

  static const monoBody = TextStyle(
    fontFamily: jetBrains,
    fontSize: 14,
    color: AmiColors.textMed,
  );
}

class AmiSpacing {
  static const xs  = 4.0;
  static const s   = 8.0;
  static const m   = 16.0;
  static const l   = 24.0;
  static const xl  = 32.0;
  static const xxl = 48.0;
}

class AmiRadii {
  static const card = 8.0;
  static const sheet = 12.0;
  static const hexCorner = 10.0;   // corner cut for hex clip-paths (mobile-sized)
}

class AmiMotion {
  static const fast = Duration(milliseconds: 150);
  static const normal = Duration(milliseconds: 200);
  static const slow = Duration(milliseconds: 350);
  
  static const easeOut = Cubic(0.4, 0, 0.2, 1);
}
```

## Hex clip-paths in Flutter

> **CR117 (2026-07-29) — there are THREE shapes, and two of them are not hexagons.**
> This section used to describe two, under names that claimed otherwise. `FlatTopHexagonClipper`
> emitted an **eight**-point path while its own docstring called it a cut-corner octagon; the name
> misled every reader for months, including CR106's spec work, which reasoned about "hex geometry"
> on controls that have none. Saiful found it from the outside, on the ticker-period toggle:
> *"the buttons are octagonal, not hexagonal."*
>
> | Class | Sides | Use |
> |---|---|---|
> | `CutCornerOctagonClipper` | 8 — angled corners all round | `HexButton`, `HexChip`, `GlassPanel` accents, bottom nav, toasts, ticker-period chips. **The app's default control shape**, shipped for months, reads as intentional — not to be swept |
> | `FlatTopHexagonBarClipper` | 6 — angled **ends**, flat top and bottom, any aspect ratio | Segmented bars and wide pills. Built for DEF146's BOARD\|TRANSCRIPT toggle; CR120's Portfolio tabs use it |
> | `FlatTopRegularHexagon` | 6, locked to a 2:√3 box | Agent avatars, honeycomb tessellation |
>
> **`FlatTopHexagonClipper` no longer names anything, deliberately.** The true hexagon could have
> taken the freed name — it is what the name always claimed — but then any unmigrated call site, or
> one written in a lane in flight, would keep compiling and *silently change shape*. Because the
> identifier is gone, a stale reference is a compile error. Degrade loudly, applied to a rename.
> Geometry is pinned by side count in `mobile/test/widgets/hex_geometry_test.dart`.
>
> **Migrate on evidence, not tidiness.** CR117 deliberately leaves open which remaining controls
> become true hexagons: move one when there is a design or a report asking for it. Note CR113
> removes the shape from large CTAs entirely, and CR108 edits `TrackHexButton`, which already uses
> the regular hexagon and must not be caught in any migration.

The flat-topped hexagon is the AMI signature. Implement via `ClipPath`:

```dart
// CR117: renamed. This is the OCTAGON — see the table above.
class CutCornerOctagonClipper extends CustomClipper<Path> {
  final double cornerCut;
  
  CutCornerOctagonClipper({this.cornerCut = 10.0});

  @override
  Path getClip(Size size) {
    final w = size.width;
    final h = size.height;
    final c = cornerCut;

    return Path()
      ..moveTo(c, 0)              // top-left of top edge
      ..lineTo(w - c, 0)          // top-right of top edge
      ..lineTo(w, c)              // right top diagonal end
      ..lineTo(w, h - c)          // right bottom diagonal start
      ..lineTo(w - c, h)          // bottom-right of bottom edge
      ..lineTo(c, h)              // bottom-left of bottom edge
      ..lineTo(0, h - c)          // left bottom diagonal end
      ..lineTo(0, c)              // left top diagonal start
      ..close();
  }

  @override
  bool shouldReclip(covariant CustomClipper<Path> oldClipper) => false;
}
```

This produces an **octagonal-with-cut-corners** shape — what the design system calls a "hex clip-path." For true honeycomb tessellation (the home screen), use a different clipper:

```dart
class FlatTopRegularHexagon extends CustomClipper<Path> {
  // True hexagon, flat-topped, for honeycomb tessellation
  @override
  Path getClip(Size size) {
    final w = size.width;
    final h = size.height;
    final qw = w * 0.25;
    
    return Path()
      ..moveTo(qw, 0)
      ..lineTo(w - qw, 0)
      ..lineTo(w, h * 0.5)
      ..lineTo(w - qw, h)
      ..lineTo(qw, h)
      ..lineTo(0, h * 0.5)
      ..close();
  }

  @override
  bool shouldReclip(covariant CustomClipper<Path> oldClipper) => false;
}
```

For aspect ratio of regular hexagons: `width:height = 2:√3 ≈ 1.155`. Wrap with `AspectRatio(aspectRatio: 2/sqrt(3))`.

## The HexButton widget

```dart
class HexButton extends StatelessWidget {
  final String label;            // typically UPPERCASE
  final VoidCallback onPressed;
  final Color color;             // role color
  final HexVariant variant;      // filled / outlined / glow

  const HexButton({
    required this.label,
    required this.onPressed,
    this.color = AmiColors.hexBlue,
    this.variant = HexVariant.filled,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onPressed,
      child: ClipPath(
        clipper: FlatTopHexagonClipper(),
        child: AnimatedContainer(
          duration: AmiMotion.normal,
          curve: AmiMotion.easeOut,
          padding: EdgeInsets.symmetric(
            horizontal: AmiSpacing.l,
            vertical: AmiSpacing.m,
          ),
          decoration: BoxDecoration(
            color: variant == HexVariant.filled
                ? color
                : Colors.transparent,
            border: variant != HexVariant.filled
                ? Border.all(color: color, width: 1)
                : null,
          ),
          child: Text(
            label,
            style: AmiTypography.labelMono.copyWith(
              color: variant == HexVariant.filled
                  ? Colors.white
                  : color,
            ),
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
```

**Note:** clip-paths cut off `box-shadow` in CSS — same gotcha in Flutter. For "glow" effects on hex elements, use `BackdropFilter` + a colored gradient *inside* the clipped area, or use `filter: DropShadow` (Flutter equivalent) on the parent. Per AMI spec, glow on a hex = a colored radial gradient layered behind the clip.

## Glass panel

The AMI signature surface — a partially-transparent dark panel with backdrop blur:

```dart
class GlassPanel extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? accentColor;       // for the 3px top accent border
  
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700, width: 1),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
          child: Container(
            decoration: BoxDecoration(
              color: AmiColors.glass,
              border: accentColor != null
                  ? Border(top: BorderSide(color: accentColor!, width: 3))
                  : null,
            ),
            padding: padding,
            child: child,
          ),
        ),
      ),
    );
  }
}
```

## Hex mesh background overlay

Per AMI spec — 3%-opacity repeating hex pattern as a texture on dark surfaces.

```dart
Widget hexMeshBackground({required Widget child}) {
  return Stack(
    children: [
      Positioned.fill(
        child: Container(color: AmiColors.slate900),
      ),
      Positioned.fill(
        child: Opacity(
          opacity: 0.03,
          child: SvgPicture.asset(
            'assets/hex_mesh.svg',
            fit: BoxFit.cover,
            repeat: ImageRepeat.repeat,
          ),
        ),
      ),
      // Top-centre radial glow (optional, hero sections)
      Positioned(
        top: -100, left: 0, right: 0,
        height: 400,
        child: IgnorePointer(
          child: Container(
            decoration: BoxDecoration(
              gradient: RadialGradient(
                colors: [
                  AmiColors.hexBlue.withOpacity(0.15),
                  AmiColors.slate900.withOpacity(0),
                ],
              ),
            ),
          ),
        ),
      ),
      child,
    ],
  );
}
```

Copy `hex_mesh.svg` from `/Volumes/Extreme Pro/AMI AI Design System/assets/` to `mobile/assets/`.

## Fonts

| Font | Family name | Where to bundle |
|---|---|---|
| **Inter** (Regular, Medium, SemiBold, Bold) | `Inter` | `mobile/assets/fonts/Inter/` |
| **JetBrains Mono** (Regular, Medium, Bold) | `JetBrainsMono` | `mobile/assets/fonts/JetBrainsMono/` |
| **IBM Plex Sans Arabic** (Regular, Medium, Bold) — v1.0 for AR | `IBMPlexSansArabic` | `mobile/assets/fonts/IBMPlexSansArabic/` |

Add to `pubspec.yaml`:

```yaml
flutter:
  fonts:
    - family: Inter
      fonts:
        - asset: assets/fonts/Inter/Inter-Regular.ttf
        - asset: assets/fonts/Inter/Inter-Medium.ttf
          weight: 500
        - asset: assets/fonts/Inter/Inter-SemiBold.ttf
          weight: 600
        - asset: assets/fonts/Inter/Inter-Bold.ttf
          weight: 700
    - family: JetBrainsMono
      fonts:
        - asset: assets/fonts/JetBrainsMono/JetBrainsMono-Regular.ttf
        - asset: assets/fonts/JetBrainsMono/JetBrainsMono-Medium.ttf
          weight: 500
        - asset: assets/fonts/JetBrainsMono/JetBrainsMono-Bold.ttf
          weight: 700
```

Self-hosting fonts (not Google Fonts API at runtime) is important for offline-first and for non-GMS Android (Huawei).

## ThemeData

```dart
final amiTheme = ThemeData.dark().copyWith(
  scaffoldBackgroundColor: AmiColors.slate900,
  textTheme: const TextTheme(
    headlineLarge: AmiTypography.h1,
    headlineMedium: AmiTypography.h2,
    titleLarge: AmiTypography.h3,
    titleMedium: AmiTypography.h4,
    bodyMedium: AmiTypography.body,
    bodySmall: AmiTypography.caption,
    labelLarge: AmiTypography.labelMono,
  ),
  primaryColor: AmiColors.hexBlue,
  colorScheme: const ColorScheme.dark(
    primary: AmiColors.hexBlue,
    surface: AmiColors.slate800,
    background: AmiColors.slate900,
  ),
  appBarTheme: AppBarTheme(
    backgroundColor: AmiColors.glassChrome,
    elevation: 0,
    toolbarHeight: 64,
  ),
);
```

## Hex avatar widget (for the 12 agents)

```dart
class HexAvatar extends StatelessWidget {
  final String agentId;
  final Color color;              // role color
  final double size;
  final bool active;              // unlocked
  final AgentStatus status;       // idle / signal / attention
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      onLongPress: onLongPress,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Pulsing glow if signal
          if (status == AgentStatus.signal)
            AnimatedBuilder(...),  // Pulsing colored radial behind
          
          // The hex itself
          ClipPath(
            clipper: FlatTopRegularHexagon(),
            child: Container(
              width: size,
              height: size * (sqrt(3) / 2),
              decoration: BoxDecoration(
                color: active ? color : AmiColors.slate700,
                border: Border.all(
                  color: active ? color : AmiColors.slate600,
                  width: 1,
                ),
              ),
              child: Center(
                child: Text(
                  _abbr(agentId),    // "FUND", "BEAR", "PM" etc.
                  style: AmiTypography.labelMono.copyWith(
                    fontSize: size * 0.18,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          ),

          // Lock glyph overlay if locked
          if (!active)
            Positioned(
              top: 4, right: 4,
              child: Icon(Icons.lock, size: 14, color: AmiColors.textLow),
            ),
        ],
      ),
    );
  }
}
```

## Cross-references

- Role colors per agent: [`colors_motion_rtl.md`](colors_motion_rtl.md)
- Full information architecture: [`information_architecture.md`](information_architecture.md)
- AMI design system source: `/Volumes/Extreme Pro/AMI AI Design System/`

#!/usr/bin/env python3
"""Render the AMI Trade app icon ("Diagonal duo" — hexagon bull/bear candles).

Chosen AT:R54 from a 5-option + C×D-mix study. Two candlesticks whose bodies
are the AMI point-up hexagon: green bull (#10B981) rising upper-left, red bear
(#EF4444) falling lower-right, cyan (#06B6D4) wicks from the tips, on the
slate-900 canvas with a soft blue radial glow.

Pillow-only, 4x supersampled — no cairo/SVG dependency (the Mac has neither
librsvg nor a cairo native lib). Requires `pillow` (pip install pillow).

Run from the repo root:
    python3 scripts/render_app_icon.py
Regenerate whenever the artwork changes; commit the outputs.

Writes:
  mobile/assets/icon/ami_icon_hires.png       1024 opaque  (iOS master + FLI image_path)
  mobile/assets/icon/ami_icon_foreground.png  1024 transparent, sized for the adaptive safe zone
  mobile/assets/icon/ami_icon_background.png  1024 opaque   (slate + glow, adaptive background)
  mobile/ios/Runner/Assets.xcassets/AppIcon.appiconset/Icon-App-*.png  (all 15 sizes, RGB)

After running, regenerate the Android set:  (cd mobile && dart run flutter_launcher_icons)
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFilter

SS = 4                      # supersample factor
BASE = 1024
C = BASE * SS

BG = (15, 23, 42)                                  # #0F172A slate900
GREEN, GREEN_D = (16, 185, 129), (14, 158, 112)    # #10B981 -> #0E9E70
RED, RED_D = (239, 68, 68), (220, 47, 47)          # #EF4444 -> #DC2F2F
BLUE = (59, 130, 246)                              # #3B82F6
CYAN = (6, 182, 212)                               # #06B6D4

BULL = (430, 452, 116, 162)   # cx, cy, hw, hh  (point-up hexagon)
BEAR = (594, 572, 116, 162)
HALO = (430, 452, 132, 178)   # bull + 16, carves the bull/bear separation
WICK_W = 24
BULL_WICK = (430, 158, 290)   # x, y_top, y_bottom
BEAR_WICK = (594, 734, 866)

REPO = pathlib.Path(__file__).resolve().parent.parent
ASSETS = REPO / "mobile" / "assets" / "icon"
APPICON = REPO / "mobile" / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"


def s(v):
    return v * SS


def pointy(cx, cy, hw, hh, flat=0.5):
    fy = hh * flat
    return [(cx, cy-hh), (cx+hw, cy-fy), (cx+hw, cy+fy),
            (cx, cy+hh), (cx-hw, cy+fy), (cx-hw, cy-fy)]


def scaled_poly(spec):
    cx, cy, hw, hh = spec
    return [(s(x), s(y)) for x, y in pointy(cx, cy, hw, hh)]


def vgrad_layer(verts, top, bot):
    ys = [p[1] for p in verts]
    y0, y1 = min(ys), max(ys)
    h = max(1, int(y1 - y0))
    strip = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        strip.putpixel((0, y), tuple(int(top[i] + (bot[i]-top[i]) * t) for i in range(3)))
    grad = Image.new("RGB", (C, C), tuple(top))
    grad.paste(strip.resize((C, h)), (0, int(y0)))
    mask = Image.new("L", (C, C), 0)
    ImageDraw.Draw(mask).polygon(verts, fill=255)
    layer = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    layer.paste(grad, (0, 0), mask)
    return layer


def wick_layer(x, y0, y1, w, color):
    layer = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y0, y1, w = s(x), s(y0), s(y1), s(w)
    d.rounded_rectangle([x-w/2, y0, x+w/2, y1], radius=w/2, fill=color + (255,))
    return layer


def glow_layer():
    layer = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    gx, gy, r = s(512), s(430), s(232)
    ImageDraw.Draw(layer).ellipse([gx-r, gy-r, gx+r, gy+r], fill=BLUE + (105,))
    return layer.filter(ImageFilter.GaussianBlur(s(150)))


def draw_motif(canvas, erase_halo):
    canvas.alpha_composite(wick_layer(*BEAR_WICK, WICK_W, CYAN))
    canvas.alpha_composite(vgrad_layer(scaled_poly(BEAR), RED, RED_D))
    halo = scaled_poly(HALO)
    if erase_halo:
        m = Image.new("L", (C, C), 0)
        ImageDraw.Draw(m).polygon(halo, fill=255)
        canvas.paste((0, 0, 0, 0), (0, 0), m)
    else:
        ImageDraw.Draw(canvas).polygon(halo, fill=BG + (255,))
    canvas.alpha_composite(wick_layer(*BULL_WICK, WICK_W, CYAN))
    canvas.alpha_composite(vgrad_layer(scaled_poly(BULL), GREEN, GREEN_D))


def render_full():
    img = Image.new("RGBA", (C, C), BG + (255,))
    img.alpha_composite(glow_layer())
    draw_motif(img, erase_halo=False)
    return img.resize((BASE, BASE), Image.LANCZOS)


def render_background():
    img = Image.new("RGBA", (C, C), BG + (255,))
    img.alpha_composite(glow_layer())
    return img.resize((BASE, BASE), Image.LANCZOS)


def render_foreground(target_frac=0.94):
    """flutter_launcher_icons wraps the foreground in a 16% inset (content →
    central 68% of the cell), so size the motif to fill `target_frac` of THIS
    image → ~target_frac*0.68 of the final cell, keeping wick tips inside the
    66% safe circle. Natural motif span is 708/1024 = 0.691 of the canvas."""
    motif = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    draw_motif(motif, erase_halo=True)
    k = target_frac / (708 / 1024.0)
    big = motif.resize((int(C * k), int(C * k)), Image.LANCZOS)
    canvas = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    off = (C - big.width) // 2
    canvas.alpha_composite(big, (off, off))
    return canvas.resize((BASE, BASE), Image.LANCZOS)


IOS_SIZES = {
    "Icon-App-20x20@1x.png": 20, "Icon-App-20x20@2x.png": 40, "Icon-App-20x20@3x.png": 60,
    "Icon-App-29x29@1x.png": 29, "Icon-App-29x29@2x.png": 58, "Icon-App-29x29@3x.png": 87,
    "Icon-App-40x40@1x.png": 40, "Icon-App-40x40@2x.png": 80, "Icon-App-40x40@3x.png": 120,
    "Icon-App-60x60@2x.png": 120, "Icon-App-60x60@3x.png": 180,
    "Icon-App-76x76@1x.png": 76, "Icon-App-76x76@2x.png": 152,
    "Icon-App-83.5x83.5@2x.png": 167, "Icon-App-1024x1024@1x.png": 1024,
}


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    hires = render_full()
    hires.save(ASSETS / "ami_icon_hires.png")
    render_foreground().save(ASSETS / "ami_icon_foreground.png")
    render_background().save(ASSETS / "ami_icon_background.png")
    print("masters →", ASSETS)

    rgb = hires.convert("RGB")   # iOS icons: opaque, no alpha
    for fn, px in IOS_SIZES.items():
        rgb.resize((px, px), Image.LANCZOS).save(APPICON / fn)
    print(f"{len(IOS_SIZES)} iOS icons →", APPICON)
    print("next:  (cd mobile && dart run flutter_launcher_icons)")


if __name__ == "__main__":
    sys.exit(main())

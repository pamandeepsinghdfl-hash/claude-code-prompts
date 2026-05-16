"""Generate brand assets for the Off Mic channel.

Outputs:
  - data/brand/logo.png       1500x1500 — Google profile picture
  - data/brand/avatar_512.png 512x512   — favicon / social
  - data/brand/banner.png     2560x1440 — YouTube channel banner
  - data/brand/preview.png    combined preview sheet

Uses Montserrat-Black.ttf if present in data/fonts/, otherwise falls
back to DejaVuSans-Bold so the script runs anywhere.

The brand uses:
  - Deep charcoal background (broadcast-studio feel)
  - Red "ON AIR / LIVE" accent — implies hot mic
  - White typography, oversized "MIC" for impact
  - A simple mic silhouette as a visual anchor
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BRAND_DIR = Path(__file__).resolve().parent.parent / "data" / "brand"
BRAND_DIR.mkdir(parents=True, exist_ok=True)

# ─── Visual identity ─────────────────────────────────────────────────────
DARK    = (10, 10, 12)         # near-black background
INK     = (245, 245, 248)      # off-white text
ACCENT  = (220, 30, 50)        # ON AIR red
MUTED   = (160, 160, 168)      # tagline grey

FONT_CANDIDATES = [
    "data/fonts/Montserrat-Black.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def font(size):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ─── Mic silhouette helper ───────────────────────────────────────────────
def draw_mic(img: Image.Image, cx: int, cy: int, scale: float, color=INK, alpha=255):
    """Draw a simple stylized microphone centered at (cx, cy)."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Mic capsule (rounded rectangle)
    w = int(220 * scale)
    h = int(340 * scale)
    x0, y0 = cx - w // 2, cy - h // 2 - int(40 * scale)
    x1, y1 = cx + w // 2, cy + h // 2 - int(40 * scale)
    rad = int(110 * scale)
    d.rounded_rectangle((x0, y0, x1, y1), radius=rad,
                        fill=color + (alpha,))

    # Grille lines
    line_w = int(8 * scale)
    for ly in range(y0 + int(60 * scale), y1 - int(60 * scale), int(30 * scale)):
        d.line((x0 + int(40 * scale), ly, x1 - int(40 * scale), ly),
               fill=(20, 20, 24, alpha), width=line_w)

    # Yoke (U shape)
    yoke_top = y1 + int(20 * scale)
    yoke_bot = yoke_top + int(70 * scale)
    yoke_w = int(280 * scale)
    yt = int(14 * scale)
    d.arc(
        (cx - yoke_w // 2, yoke_top, cx + yoke_w // 2, yoke_bot + int(80 * scale)),
        start=0, end=180, fill=color + (alpha,), width=yt,
    )

    # Stand stem
    stem_top = yoke_bot + int(60 * scale)
    stem_bot = stem_top + int(120 * scale)
    d.line((cx, stem_top, cx, stem_bot),
           fill=color + (alpha,), width=int(20 * scale))

    # Stand base (small ellipse)
    base_w = int(180 * scale)
    base_h = int(28 * scale)
    d.ellipse((cx - base_w // 2, stem_bot - base_h // 2,
               cx + base_w // 2, stem_bot + base_h // 2),
              fill=color + (alpha,))

    img.alpha_composite(overlay)


# ─── Logo / avatar (1500×1500, square, circle-safe) ──────────────────────
def make_logo(size=1500, out: Path = BRAND_DIR / "logo.png"):
    img = Image.new("RGBA", (size, size), DARK + (255,))

    # Subtle red glow behind the mic
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((size * 0.15, size * 0.20, size * 0.85, size * 0.75),
               fill=(80, 18, 28, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    img = Image.alpha_composite(img, glow)

    # Mic silhouette (left-of-center, big)
    draw_mic(img, cx=int(size * 0.32), cy=int(size * 0.48), scale=1.6, color=INK)

    d = ImageDraw.Draw(img)

    # OFF on top, MIC underneath — both right-aligned to the mic
    f_label = font(int(size * 0.13))
    f_main = font(int(size * 0.30))

    label = "ON AIR"
    main_top = "OFF"
    main_bot = "MIC"

    # Red ON AIR badge — top-right
    b_lab = d.textbbox((0, 0), label, font=f_label)
    pad_x, pad_y = 30, 18
    badge_w = (b_lab[2] - b_lab[0]) + 2 * pad_x
    badge_h = (b_lab[3] - b_lab[1]) + 2 * pad_y
    bx = size - badge_w - int(size * 0.06)
    by = int(size * 0.10)
    d.rounded_rectangle((bx, by, bx + badge_w, by + badge_h),
                        radius=24, fill=ACCENT + (255,))
    d.text((bx + pad_x, by + pad_y - 8), label, font=f_label, fill=INK + (255,))

    # OFF MIC — large, stacked, right of the mic
    text_x = int(size * 0.50)
    text_y = int(size * 0.35)
    d.text((text_x, text_y), main_top, font=f_main, fill=INK + (255,),
           stroke_width=6, stroke_fill=DARK + (255,))
    b_top = d.textbbox((0, 0), main_top, font=f_main)
    d.text((text_x, text_y + (b_top[3] - b_top[1]) + 30),
           main_bot, font=f_main, fill=ACCENT + (255,),
           stroke_width=6, stroke_fill=DARK + (255,))

    # Bottom tagline
    tag = "VIRAL PODCAST MOMENTS  ·  IN ENGLISH  ·  DAILY"
    ft = font(int(size * 0.038))
    bt = d.textbbox((0, 0), tag, font=ft)
    wt = bt[2] - bt[0]
    d.text(((size - wt) // 2, int(size * 0.86)),
           tag, font=ft, fill=MUTED + (255,))

    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"  Wrote {out}  ({size}×{size})")
    return img.convert("RGB")


# ─── 512x512 social variant ──────────────────────────────────────────────
def make_avatar_512(logo_img, out: Path = BRAND_DIR / "avatar_512.png"):
    logo_img.resize((512, 512), Image.LANCZOS).save(out, "PNG", optimize=True)
    print(f"  Wrote {out}  (512×512)")


# ─── Banner (2560x1440) ──────────────────────────────────────────────────
def make_banner(out: Path = BRAND_DIR / "banner.png"):
    W, H = 2560, 1440
    img = Image.new("RGBA", (W, H), DARK + (255,))

    # Vertical gradient: charcoal top → near-black bottom
    grad = Image.new("RGB", (1, H))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        t = y / H
        r = int(22 * (1 - t) + 6 * t)
        g = int(22 * (1 - t) + 6 * t)
        b = int(28 * (1 - t) + 10 * t)
        gd.point((0, y), fill=(r, g, b))
    img = grad.resize((W, H)).convert("RGBA")

    # Red ambient glow on the right
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow)
    gd2.ellipse((W * 0.55, -200, W * 1.20, H * 1.20),
                fill=(120, 25, 35, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(200))
    img = Image.alpha_composite(img, glow)

    # Mic silhouette on the right side
    draw_mic(img, cx=int(W * 0.78), cy=int(H * 0.50), scale=1.4, color=INK)

    d = ImageDraw.Draw(img)

    # TV-safe centered text zone (~1546×423)
    safe_w, safe_h = 1546, 423
    safe_x = (W - safe_w) // 2 - 200  # shift left so it doesn't overlap the mic
    safe_y = (H - safe_h) // 2

    f_big = font(220)
    f_med = font(64)
    f_small = font(40)

    # ON AIR pill — sits above the main brand
    f_label = font(50)
    label = "ON AIR  ·  6 SHORTS DAILY"
    b_lab = d.textbbox((0, 0), label, font=f_label)
    pad_x, pad_y = 32, 16
    bw = (b_lab[2] - b_lab[0]) + 2 * pad_x
    bh = (b_lab[3] - b_lab[1]) + 2 * pad_y
    bx, by = safe_x, safe_y - 80
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=28, fill=ACCENT + (255,))
    d.text((bx + pad_x, by + pad_y - 8), label, font=f_label, fill=INK + (255,))

    # OFF MIC headline
    line1 = "OFF MIC"
    d.text((safe_x, safe_y + 40), line1, font=f_big, fill=INK + (255,),
           stroke_width=6, stroke_fill=DARK + (255,))

    # Sub-headline
    line2 = "Viral podcast moments — translated to English."
    d.text((safe_x, safe_y + 280), line2, font=f_med, fill=INK + (255,))

    # Schedule line
    line3 = "NEW SHORTS · 04 · 08 · 12 · 16 · 20 · 00 UTC"
    d.text((safe_x, safe_y + 380), line3, font=f_small, fill=MUTED + (255,))

    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"  Wrote {out}  ({W}×{H})")
    return img.convert("RGB")


# ─── Combined preview sheet ──────────────────────────────────────────────
def make_preview(out: Path = BRAND_DIR / "preview.png"):
    logo = Image.open(BRAND_DIR / "logo.png").resize((600, 600))
    banner = Image.open(BRAND_DIR / "banner.png").resize((1600, 900))

    W, H = 1700, 1700
    sheet = Image.new("RGB", (W, H), (245, 245, 247))
    sheet.paste(banner, (50, 50))
    sheet.paste(logo, (50, 1000))

    d = ImageDraw.Draw(sheet)
    f_label = font(40)
    f_title = font(64)
    d.text((50, 970), "Channel banner — 2560×1440", font=f_label, fill=(50, 50, 60))
    d.text((680, 1050), "Off Mic", font=f_title, fill=(20, 20, 30))
    d.text((680, 1130), "@offmic", font=f_label, fill=(120, 120, 130))
    d.text((680, 1210),
           "Viral podcast moments — translated to English.\n"
           "6 Shorts daily at 04/08/12/16/20/00 UTC.\n"
           "Profile picture — 1500×1500 (shown 600×600 here).",
           font=f_label, fill=(60, 60, 70))

    sheet.save(out, "PNG", optimize=True)
    print(f"  Wrote {out}  ({W}×{H})")


print("Generating Off Mic brand assets…")
logo_img = make_logo()
make_avatar_512(logo_img)
make_banner()
make_preview()
print("Done.")

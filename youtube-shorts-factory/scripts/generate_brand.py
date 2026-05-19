"""Generate brand assets for the Pixel Hours channel.

Outputs:
  - data/brand/logo.png        1500x1500 — channel profile picture
  - data/brand/avatar_512.png  512x512   — social variant
  - data/brand/banner.png      2560x1440 — YouTube banner
  - data/brand/preview.png     combined preview sheet

Uses Montserrat-Black.ttf if present in data/fonts/, otherwise falls back to
DejaVu Sans Bold so the script runs anywhere.

Identity:
  - Deep cozy navy + lamp warm accent
  - Big chunky pixel-style wordmark "PIXEL HOURS"
  - Tiny pixel-art window with city skyline as the brand mark
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import random

BRAND_DIR = Path(__file__).resolve().parent.parent / "data" / "brand"
BRAND_DIR.mkdir(parents=True, exist_ok=True)

# ─── Palette ─────────────────────────────────────────────────────────────
DEEP_NIGHT = (16, 18, 32)
WALL_DARK  = (28, 30, 48)
LAMP_GOLD  = (255, 200, 110)
INK        = (245, 240, 232)
RAIN_BLUE  = (110, 160, 220)
SHADOW     = (8, 9, 16)
WINDOW_BLUE = (40, 60, 110)
CITY_LIT   = (180, 210, 255)

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


def draw_pixel_window(img: Image.Image, x: int, y: int, w: int, h: int, seed: int = 1):
    """Draw a tiny pixel-art window with city skyline and lit cells."""
    rng = random.Random(seed)
    d = ImageDraw.Draw(img)
    # Sky
    d.rectangle((x, y, x + w, y + h), fill=WINDOW_BLUE)
    # Buildings silhouette
    cx = x
    while cx < x + w:
        bw = rng.choice([6, 8, 10, 12, 14])
        bh = rng.choice([30, 50, 80, 110, 70])
        bh = min(bh, h - 10)
        d.rectangle((cx, y + h - bh, min(cx + bw, x + w), y + h), fill=DEEP_NIGHT)
        # Lit windows
        for _ in range(rng.randint(2, 6)):
            wx = cx + rng.randint(1, max(1, bw - 3))
            wy = y + h - bh + rng.randint(3, max(4, bh - 5))
            d.rectangle((wx, wy, wx + 1, wy + 1), fill=CITY_LIT)
        cx += bw
    # Frame
    for thickness in range(3):
        d.rectangle(
            (x - 1 - thickness, y - 1 - thickness,
             x + w + thickness, y + h + thickness),
            outline=(45, 50, 70),
        )
    # Mullion cross
    d.line((x + w // 2, y, x + w // 2, y + h), fill=(45, 50, 70), width=2)
    d.line((x, y + h // 2, x + w, y + h // 2), fill=(45, 50, 70), width=2)


def make_logo(size=1500, out: Path = BRAND_DIR / "logo.png"):
    img = Image.new("RGB", (size, size), DEEP_NIGHT)
    # Soft warm lamp glow lower-left
    glow = Image.new("RGB", (size, size), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-size * 0.2, size * 0.45, size * 0.65, size * 1.05),
               fill=(140, 90, 30))
    glow = glow.filter(ImageFilter.GaussianBlur(180))
    img = Image.blend(img, glow, 0.4)

    # Big pixel window in the center-top
    draw_pixel_window(
        img,
        x=int(size * 0.32), y=int(size * 0.12),
        w=int(size * 0.36), h=int(size * 0.36),
        seed=11,
    )

    # Tiny lamp + base under the window
    d = ImageDraw.Draw(img)
    lx, ly = int(size * 0.66), int(size * 0.30)
    d.rectangle((lx, ly, lx + int(size * 0.025), ly + int(size * 0.08)),
                fill=(60, 65, 80))
    d.ellipse((lx - int(size * 0.025), ly + int(size * 0.08),
               lx + int(size * 0.05), ly + int(size * 0.125)),
              fill=LAMP_GOLD)

    # Wordmark — "PIXEL" + "HOURS" stacked
    f_big = font(int(size * 0.16))
    f_small = font(int(size * 0.06))

    line1 = "PIXEL"
    line2 = "HOURS"
    b1 = d.textbbox((0, 0), line1, font=f_big)
    b2 = d.textbbox((0, 0), line2, font=f_big)
    w1 = b1[2] - b1[0]
    w2 = b2[2] - b2[0]
    h1 = b1[3] - b1[1]

    y0 = int(size * 0.55)
    d.text(((size - w1) // 2, y0), line1, font=f_big, fill=INK,
           stroke_width=8, stroke_fill=SHADOW)
    d.text(((size - w2) // 2, y0 + h1 + 30), line2, font=f_big, fill=LAMP_GOLD,
           stroke_width=8, stroke_fill=SHADOW)

    # Tagline
    tag = "COZY PIXEL LOOPS  ·  EVERY 4 HOURS"
    bt = d.textbbox((0, 0), tag, font=f_small)
    wt = bt[2] - bt[0]
    d.text(((size - wt) // 2, int(size * 0.88)), tag,
           font=f_small, fill=(180, 180, 195))

    img.save(out, "PNG", optimize=True)
    print(f"  Wrote {out} ({size}x{size})")
    return img


def make_avatar_512(logo_img, out: Path = BRAND_DIR / "avatar_512.png"):
    logo_img.resize((512, 512), Image.LANCZOS).save(out, "PNG", optimize=True)
    print(f"  Wrote {out} (512x512)")


def make_banner(out: Path = BRAND_DIR / "banner.png"):
    W, H = 2560, 1440
    img = Image.new("RGB", (W, H), DEEP_NIGHT)
    # Vertical gradient
    grad = Image.new("RGB", (1, H))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        t = y / H
        r = int(28 * (1 - t) + 12 * t)
        g = int(30 * (1 - t) + 14 * t)
        b = int(48 * (1 - t) + 24 * t)
        gd.point((0, y), fill=(r, g, b))
    img = grad.resize((W, H))

    # Lamp glow bottom-right (alternative side to the logo)
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd2 = ImageDraw.Draw(glow)
    gd2.ellipse((W * 0.65, H * 0.40, W * 1.1, H * 1.2),
                fill=(130, 80, 30))
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    img = Image.blend(img, glow, 0.45)

    # Pixel window on the right side
    draw_pixel_window(
        img,
        x=int(W * 0.74), y=int(H * 0.18),
        w=int(W * 0.18), h=int(H * 0.55),
        seed=42,
    )

    d = ImageDraw.Draw(img)

    # TV-safe text centered-left
    safe_x = 350
    safe_y = 480
    f_big = font(220)
    f_med = font(64)
    f_small = font(40)

    d.text((safe_x, safe_y), "PIXEL HOURS", font=f_big, fill=INK,
           stroke_width=8, stroke_fill=SHADOW)

    d.text((safe_x, safe_y + 260),
           "cozy pixel-art loops · every 4 hours",
           font=f_med, fill=(220, 215, 200))

    d.text((safe_x, safe_y + 350),
           "04:00 · 08:00 · 12:00 · 16:00 · 20:00 · 00:00 UTC",
           font=f_small, fill=(170, 170, 190))

    img.save(out, "PNG", optimize=True)
    print(f"  Wrote {out} ({W}x{H})")
    return img


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
    d.text((50, 970), "Channel banner - 2560x1440", font=f_label, fill=(50, 50, 60))
    d.text((680, 1050), "Pixel Hours", font=f_title, fill=(20, 20, 30))
    d.text((680, 1130), "@pixelhours", font=f_label, fill=(120, 120, 130))
    d.text((680, 1210),
           "Cozy pixel-art loops, daily.\n"
           "6 Shorts at 04/08/12/16/20/00 UTC.\n"
           "Profile picture - 1500x1500 (shown 600x600 here).",
           font=f_label, fill=(60, 60, 70))
    sheet.save(out, "PNG", optimize=True)
    print(f"  Wrote {out} ({W}x{H})")


print("Generating Pixel Hours brand assets...")
logo_img = make_logo()
make_avatar_512(logo_img)
make_banner()
make_preview()
print("Done.")

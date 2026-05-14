"""Generate brand assets for the Daily Decoded channel.

Outputs:
  - data/brand/logo.png       1500x1500 — Google profile picture
  - data/brand/banner.png     2560x1440 — YouTube channel banner
  - data/brand/avatar_512.png 512x512  — favicon / social
  - data/brand/preview.png    combined preview sheet

Uses DejaVuSans-Bold as a placeholder. Drop Montserrat-Black.ttf into
data/fonts/ and re-run for the production-grade version (Montserrat is
what the captions use, so the channel branding stays visually consistent
across every Short).
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BRAND_DIR = Path(__file__).resolve().parent.parent / "data" / "brand"
BRAND_DIR.mkdir(parents=True, exist_ok=True)

# ─── Visual identity ─────────────────────────────────────────────────────
PRIMARY = (255, 212, 0)       # #FFD400 — same yellow as caption highlight
DARK    = (10, 10, 12)        # near-black background
WHITE   = (255, 255, 255)
ACCENT  = (255, 60, 60)       # subscribe-CTA red, for the dot

# Use Montserrat if present, otherwise DejaVu Sans Bold.
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


# ─── Logo / avatar (1500×1500, square, circular safe) ────────────────────
def make_logo(size=1500, out: Path = BRAND_DIR / "logo.png"):
    img = Image.new("RGB", (size, size), DARK)
    d = ImageDraw.Draw(img)

    # Subtle yellow vignette in the lower half
    glow = Image.new("RGB", (size, size), DARK)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-size*0.3, size*0.4, size*1.3, size*1.8), fill=(60, 50, 0))
    glow = glow.filter(ImageFilter.GaussianBlur(150))
    img = Image.blend(img, glow, 0.6)
    d = ImageDraw.Draw(img)

    # "DAILY" on top, "DECODED" stacked beneath, with a yellow underline
    f1 = font(int(size * 0.18))
    f2 = font(int(size * 0.22))

    daily = "DAILY"
    decoded = "DECODED"

    # Measure
    b1 = d.textbbox((0, 0), daily, font=f1)
    b2 = d.textbbox((0, 0), decoded, font=f2)
    w1, h1 = b1[2] - b1[0], b1[3] - b1[1]
    w2, h2 = b2[2] - b2[0], b2[3] - b2[1]

    total_h = h1 + h2 + int(size * 0.04)
    y0 = (size - total_h) // 2 - int(size * 0.04)

    # DAILY in white
    d.text(((size - w1) // 2, y0), daily, font=f1, fill=WHITE,
           stroke_width=4, stroke_fill=DARK)

    # DECODED in primary yellow
    y1 = y0 + h1 + int(size * 0.04)
    d.text(((size - w2) // 2, y1), decoded, font=f2, fill=PRIMARY,
           stroke_width=6, stroke_fill=DARK)

    # Red status dot (signals "we publish today")
    dot_r = int(size * 0.04)
    dot_x = (size + w2) // 2 + int(size * 0.02)
    dot_y = y1 + h2 // 2
    d.ellipse(
        (dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r),
        fill=ACCENT,
    )

    # Bottom strip: "GLOBAL · ENGLISH CAPTIONS · 6 SHORTS / DAY"
    tag = "GLOBAL  ·  ENGLISH CAPTIONS  ·  DAILY"
    ft = font(int(size * 0.038))
    bt = d.textbbox((0, 0), tag, font=ft)
    wt = bt[2] - bt[0]
    d.text(((size - wt) // 2, int(size * 0.84)), tag, font=ft,
           fill=(180, 180, 180))

    img.save(out, "PNG", optimize=True)
    print(f"  Wrote {out}  ({size}×{size})")
    return img


# ─── Banner (2560×1440 — YouTube channel banner) ─────────────────────────
def make_banner(out: Path = BRAND_DIR / "banner.png"):
    W, H = 2560, 1440
    img = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(img)

    # Gradient: dark left → very-dark right
    grad = Image.new("RGB", (W, 1))
    gd = ImageDraw.Draw(grad)
    for x in range(W):
        t = x / W
        r = int(20 * (1 - t) + 5 * t)
        g = int(20 * (1 - t) + 5 * t)
        b = int(28 * (1 - t) + 10 * t)
        gd.point((x, 0), fill=(r, g, b))
    img = grad.resize((W, H))
    d = ImageDraw.Draw(img)

    # Yellow ambient glow on the left
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd2 = ImageDraw.Draw(glow)
    gd2.ellipse((-300, 200, 1400, 1900), fill=(70, 55, 0))
    glow = glow.filter(ImageFilter.GaussianBlur(180))
    img = Image.blend(img, glow, 0.55)
    d = ImageDraw.Draw(img)

    # Headline (centered in the "TV-safe" zone ≈ 1546×423 centered)
    safe_w, safe_h = 1546, 423
    safe_x = (W - safe_w) // 2
    safe_y = (H - safe_h) // 2

    f_big = font(180)
    f_med = font(64)
    f_small = font(40)

    line1 = "DAILY DECODED"
    line2 = "The world's viral moments — in English."
    line3 = "NEW SHORTS · 4 AM · 8 AM · 12 PM · 4 PM · 8 PM · 12 AM UTC"

    b1 = d.textbbox((0, 0), line1, font=f_big)
    w1 = b1[2] - b1[0]
    d.text((safe_x + (safe_w - w1) // 2, safe_y - 20),
           line1, font=f_big, fill=PRIMARY,
           stroke_width=6, stroke_fill=DARK)

    b2 = d.textbbox((0, 0), line2, font=f_med)
    w2 = b2[2] - b2[0]
    d.text((safe_x + (safe_w - w2) // 2, safe_y + 215),
           line2, font=f_med, fill=WHITE)

    b3 = d.textbbox((0, 0), line3, font=f_small)
    w3 = b3[2] - b3[0]
    d.text((safe_x + (safe_w - w3) // 2, safe_y + 320),
           line3, font=f_small, fill=(200, 200, 200))

    # Red live-dot in the upper right of the safe zone
    cx, cy = safe_x + safe_w - 60, safe_y + 60
    d.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=ACCENT)
    d.text((cx + 30, cy - 22), "LIVE DAILY",
           font=f_small, fill=(220, 220, 220))

    img.save(out, "PNG", optimize=True)
    print(f"  Wrote {out}  ({W}×{H})")
    return img


# ─── 512×512 social variant ──────────────────────────────────────────────
def make_avatar_512(logo_img, out: Path = BRAND_DIR / "avatar_512.png"):
    img = logo_img.resize((512, 512), Image.LANCZOS)
    img.save(out, "PNG", optimize=True)
    print(f"  Wrote {out}  (512×512)")


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
    f_title = font(60)
    d.text((50, 970), "Channel banner — 2560×1440", font=f_label, fill=(50, 50, 60))
    d.text((680, 1050), "Daily Decoded", font=f_title, fill=(20, 20, 30))
    d.text((680, 1130), "@dailydecoded", font=f_label, fill=(120, 120, 130))
    d.text((680, 1210),
           "Global viral moments, translated to English.\n"
           "6 Shorts daily at 04/08/12/16/20/00 UTC.\n"
           "Profile picture — 1500×1500 (shown 600×600 here).",
           font=f_label, fill=(60, 60, 70))

    sheet.save(out, "PNG", optimize=True)
    print(f"  Wrote {out}  ({W}×{H})")


print("Generating Daily Decoded brand assets…")
logo_img = make_logo()
make_avatar_512(logo_img)
make_banner()
make_preview()
print("Done.")

"""Render a pixel-art Short prototype.

The point: show the user what the FULL pixel-art pipeline produces —
animation, caption overlay, music, watermark, fade — at the cheap tier
($10/mo target).

In the sandbox, the IMAGE itself is procedurally drawn by PIL (cozy
bedroom scene with two character silhouettes + cat + city skyline)
because Pollinations.ai rate-limits this cloud IP. On the user's PC,
the image-generation step will hit Pollinations.ai (free) and produce
much better AI-generated pixel art for the same prompt.

Everything else — parallax, Ken Burns, rain particles, caption animation,
lofi loop, watermark — is the same code that will run in production.
"""
from __future__ import annotations

import math
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "shorts"
WORK = ROOT / "output" / "workdir" / "pixel_art_demo"
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

W, H, FPS = 1080, 1920, 24   # pixel-art looks better at lower fps

# ─── Caption text (would come from LLM on user's PC) ─────────────────────
# Avoid apostrophes in ffmpeg drawtext — they break filter parsing.
CAPTION_LINE = "cant sleep without you"

# ─── 1. Procedural pixel-art bedroom scene ───────────────────────────────
# PIL-drawn at low res then nearest-neighbor upscaled = chunky pixel feel.
SCENE_W, SCENE_H = 180, 320         # internal pixel resolution
SCALE = W // SCENE_W                # × 6 → 1080×1920


def hex_color(s: str) -> tuple:
    s = s.lstrip("#")
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))


# Lofi palette — deep navy + warm lamp glow
NIGHT_SKY    = hex_color("#1a2540")
WINDOW_GLOW  = hex_color("#3b4b78")
CITY_LIT     = hex_color("#a4c4ff")
WALL_DARK    = hex_color("#1f2233")
WALL_LIGHT   = hex_color("#272a40")
FLOOR        = hex_color("#1a1d2e")
BED_SHEET    = hex_color("#2a2f4a")
BED_FRAME    = hex_color("#34384d")
LAMP_GLOW    = hex_color("#ffd07a")
HAIR_BOY     = hex_color("#181818")
HAIR_GIRL    = hex_color("#1d1818")
SKIN         = hex_color("#e8b993")
SHIRT_BOY    = hex_color("#0e0e0e")
SHIRT_GIRL   = hex_color("#e8b8c4")
PILLOW       = hex_color("#bdc4dd")
RAIN         = hex_color("#7a93c6")


def draw_base_scene() -> Image.Image:
    """Static pixel-art bedroom (no rain, no anim — that's added later)."""
    img = Image.new("RGB", (SCENE_W, SCENE_H), WALL_DARK)
    d = ImageDraw.Draw(img)

    # Wall + floor split
    floor_y = int(SCENE_H * 0.78)
    d.rectangle((0, 0, SCENE_W, floor_y), fill=WALL_DARK)
    d.rectangle((0, floor_y, SCENE_W, SCENE_H), fill=FLOOR)

    # Window frame (top-center)
    win_x0, win_y0 = 38, 28
    win_x1, win_y1 = 142, 150
    # Sky behind window
    d.rectangle((win_x0, win_y0, win_x1, win_y1), fill=NIGHT_SKY)
    # City skyline silhouette
    cx = win_x0
    while cx < win_x1:
        bld_w = random.choice([6, 8, 10, 12])
        bld_h = random.choice([24, 32, 44, 56, 38])
        bld_h = min(bld_h, win_y1 - win_y0 - 10)
        d.rectangle((cx, win_y1 - bld_h, min(cx + bld_w, win_x1), win_y1),
                    fill=WINDOW_GLOW)
        # Lit windows
        for _ in range(random.randint(1, 4)):
            wx = cx + random.randint(1, max(1, bld_w - 3))
            wy = win_y1 - bld_h + random.randint(2, max(3, bld_h - 4))
            d.rectangle((wx, wy, wx + 1, wy + 1), fill=CITY_LIT)
        cx += bld_w
    # Window cross frame (mullion)
    d.line([(win_x0, win_y0 + (win_y1 - win_y0) // 2),
            (win_x1, win_y0 + (win_y1 - win_y0) // 2)], fill=BED_FRAME, width=1)
    d.line([((win_x0 + win_x1) // 2, win_y0),
            ((win_x0 + win_x1) // 2, win_y1)], fill=BED_FRAME, width=1)
    # Window outer frame
    for thickness in range(3):
        d.rectangle((win_x0 - 1 - thickness, win_y0 - 1 - thickness,
                     win_x1 + thickness, win_y1 + thickness),
                    outline=BED_FRAME)

    # Lamp on left wall
    lamp_x, lamp_y = 16, 60
    d.rectangle((lamp_x, lamp_y, lamp_x + 6, lamp_y + 14), fill=BED_FRAME)
    d.ellipse((lamp_x - 4, lamp_y + 14, lamp_x + 10, lamp_y + 22),
              fill=LAMP_GLOW)

    # Plant on right side
    plt_x = 156
    d.rectangle((plt_x, 110, plt_x + 14, 130), fill=hex_color("#5b3a25"))
    d.ellipse((plt_x - 2, 95, plt_x + 16, 115),
              fill=hex_color("#3b6b3a"))

    # Bed
    bed_top = floor_y - 30
    d.rectangle((10, bed_top, SCENE_W - 10, floor_y + 10), fill=BED_FRAME)
    d.rectangle((14, bed_top + 6, SCENE_W - 14, floor_y + 6), fill=BED_SHEET)
    # Pillows
    d.rectangle((18, bed_top + 6, 60, bed_top + 22), fill=PILLOW)
    d.rectangle((62, bed_top + 6, 104, bed_top + 22), fill=PILLOW)

    # Two characters cuddling (silhouettes, side view)
    # Girl (right): pink shirt, dark hair
    gx, gy = 80, bed_top - 14
    d.rectangle((gx, gy + 10, gx + 30, gy + 36), fill=SHIRT_GIRL)  # body
    d.rectangle((gx + 8, gy, gx + 26, gy + 14), fill=HAIR_GIRL)    # hair
    d.rectangle((gx + 10, gy + 4, gx + 24, gy + 12), fill=SKIN)    # face

    # Boy (left): dark shirt, dark hair
    bx, by = 60, bed_top - 12
    d.rectangle((bx, by + 12, bx + 28, by + 38), fill=SHIRT_BOY)
    d.rectangle((bx + 6, by, bx + 24, by + 14), fill=HAIR_BOY)
    d.rectangle((bx + 8, by + 4, bx + 22, by + 12), fill=SKIN)
    # Girl's arm draped over boy
    d.rectangle((bx + 14, by + 14, gx + 6, by + 20), fill=SHIRT_GIRL)

    # Tiny black cat at the foot of the bed
    cat_x, cat_y = 130, floor_y - 6
    d.rectangle((cat_x, cat_y - 8, cat_x + 10, cat_y), fill=(0, 0, 0))
    d.rectangle((cat_x + 2, cat_y - 12, cat_x + 4, cat_y - 8), fill=(0, 0, 0))
    d.rectangle((cat_x + 6, cat_y - 12, cat_x + 8, cat_y - 8), fill=(0, 0, 0))
    d.rectangle((cat_x + 10, cat_y - 4, cat_x + 16, cat_y - 2), fill=(0, 0, 0))

    # Soft warm lamp glow overlay
    glow = Image.new("RGB", (SCENE_W, SCENE_H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-30, 30, 100, 200), fill=(80, 50, 0))
    glow = glow.filter(ImageFilter.GaussianBlur(20))
    img = Image.blend(img, glow, 0.18)

    return img


print("[1/4] Generating procedural pixel-art bedroom scene...")
random.seed(7)
scene = draw_base_scene()
# Upscale with nearest-neighbor for crisp chunky pixels.
scene_hi = scene.resize((W, H), Image.NEAREST)
scene_hi.save(WORK / "scene_base.png")
print(f"        wrote {WORK / 'scene_base.png'} ({W}×{H})")


# ─── 2. Generate animated frames: rain + subtle parallax/zoom ────────────
print("[2/4] Animating: rain particles + slow parallax zoom (this is what")
print("        gives the 'pixosly' subtle-motion feel)...")

DURATION = 5.0   # 5-second loop, will be looped in final to ~15s
total_frames = int(DURATION * FPS)

# Pre-make rain drop positions (multiple layers for parallax)
n_drops_far = 40
n_drops_near = 22
rng = random.Random(42)
drops_far = [(rng.uniform(0, SCENE_W), rng.uniform(-SCENE_H, SCENE_H),
              rng.uniform(0.3, 0.6))
             for _ in range(n_drops_far)]
drops_near = [(rng.uniform(0, SCENE_W), rng.uniform(-SCENE_H, SCENE_H),
               rng.uniform(0.8, 1.2))
              for _ in range(n_drops_near)]

frames_dir = WORK / "frames"
frames_dir.mkdir(exist_ok=True)
# Define the window box (so rain only renders inside it)
WIN_X0, WIN_Y0, WIN_X1, WIN_Y1 = 38, 28, 142, 150

for i in range(total_frames):
    t = i / FPS
    # Start from the base scene
    frame = scene.copy()
    d = ImageDraw.Draw(frame)

    # Rain inside the window — falls + loops
    fall_speed_far = 18   # px per second (internal coords)
    fall_speed_near = 36
    for x, y_seed, w in drops_far:
        y = (y_seed + fall_speed_far * t) % (WIN_Y1 - WIN_Y0 + 20) + WIN_Y0 - 10
        if WIN_X0 < x < WIN_X1 and WIN_Y0 < y < WIN_Y1:
            d.line([(x, y), (x, y + 2)], fill=RAIN)
    for x, y_seed, w in drops_near:
        y = (y_seed + fall_speed_near * t) % (WIN_Y1 - WIN_Y0 + 20) + WIN_Y0 - 10
        if WIN_X0 < x < WIN_X1 and WIN_Y0 < y < WIN_Y1:
            d.line([(x, y), (x, y + 3)], fill=hex_color("#a4baea"))

    # Lamp flicker — subtle brightness pulse
    flicker = 0.5 + 0.04 * math.sin(t * 4.0)
    overlay = Image.new("RGB", (SCENE_W, SCENE_H), (0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-20, 35, 80, 140), fill=(140, 90, 30))
    overlay = overlay.filter(ImageFilter.GaussianBlur(14))
    frame = Image.blend(frame, overlay, 0.10 * flicker)

    # Upscale nearest-neighbor
    frame_hi = frame.resize((W, H), Image.NEAREST)

    # Subtle Ken Burns zoom: 1.00 → 1.04 over the duration, centered
    zoom = 1.0 + 0.04 * (t / DURATION)
    cw, ch = int(W / zoom), int(H / zoom)
    left = (W - cw) // 2
    top = (H - ch) // 2
    frame_hi = frame_hi.crop((left, top, left + cw, top + ch)).resize(
        (W, H), Image.NEAREST
    )

    frame_hi.save(frames_dir / f"f_{i:05d}.png")

print(f"        {total_frames} frames written")

# ─── 3. Encode frames + loop to ~15s with audio ──────────────────────────
print("[3/4] Encoding frame sequence + looping to 15s...")
short_loop = WORK / "loop_5s.mp4"
subprocess.run(
    ["ffmpeg", "-y",
     "-framerate", str(FPS),
     "-i", str(frames_dir / "f_%05d.png"),
     "-c:v", "libx264", "-pix_fmt", "yuv420p",
     "-preset", "veryfast", "-crf", "18",
     str(short_loop)],
    check=True, capture_output=True,
)

looped_video = WORK / "looped_15s.mp4"
subprocess.run(
    ["ffmpeg", "-y",
     "-stream_loop", "2", "-i", str(short_loop),
     "-c", "copy", "-t", "15", str(looped_video)],
    check=True, capture_output=True,
)

# ─── 4. Final render: caption + watermark + lofi-ish tone + fade ─────────
print("[4/4] Final render: caption overlay + watermark + fade...")
final = OUT / "sample_pixel_art.mp4"
DURATION_FINAL = 15.0

# Lofi-ish music: generate a soft sine pad with ffmpeg (placeholder; production
# pulls real CC0 lofi from data/music/)
lofi_track = WORK / "lofi.wav"
subprocess.run(
    ["ffmpeg", "-y",
     "-f", "lavfi", "-i",
     "sine=frequency=220:duration=15,"
     "afftfilt=real='hypot(re,im)*sin(0)':imag='hypot(re,im)*cos(0)':win_size=512,"
     "volume=0.15",
     "-ac", "2", "-ar", "44100",
     str(lofi_track)],
    check=True, capture_output=True,
)

font_path = "data/fonts/Montserrat-Black.ttf"
if not Path(font_path).exists():
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Filter chain:
#   - Caption text: bottom-center, soft white, no harsh box (pixosly aesthetic)
#   - @offmic watermark removed — using pix factory brand placeholder
#   - Loop fade tail
filters = [
    # The caption — lowercase, intimate, no all-caps
    f"drawtext=fontfile={font_path}:"
    f"text={CAPTION_LINE}:fontsize=56:fontcolor=white:"
    f"shadowcolor=black@0.7:shadowx=2:shadowy=3:"
    f"x=(w-tw)/2:y=h*0.84",
    # Brand watermark — top-left, lowercase like pixosly
    f"drawtext=fontfile={font_path}:"
    f"text=@yourchannel:fontsize=34:fontcolor=white@0.85:"
    f"box=1:boxcolor=black@0.45:boxborderw=10:x=40:y=60",
    # Loop-perfect fade tail
    f"fade=t=out:st={DURATION_FINAL - 0.4:.2f}:d=0.4:c=black:alpha=1",
]

subprocess.run(
    ["ffmpeg", "-y",
     "-i", str(looped_video),
     "-i", str(lofi_track),
     "-filter_complex", ",".join(filters),
     "-map", "0:v", "-map", "1:a",
     "-c:v", "libx264", "-c:a", "aac",
     "-b:v", "6M", "-b:a", "192k",
     "-pix_fmt", "yuv420p", "-movflags", "+faststart",
     "-r", str(FPS), "-shortest", str(final)],
    check=True, capture_output=True,
)

print(f"\nDone. Pixel-art Short: {final}")
print(f"   Size: {final.stat().st_size/1024/1024:.2f} MB")
print(f"   Note: on your PC, AI image generation will produce a much")
print(f"   richer scene than this PIL-drawn placeholder.")

# Cleanup frame stills
import shutil
shutil.rmtree(frames_dir, ignore_errors=True)

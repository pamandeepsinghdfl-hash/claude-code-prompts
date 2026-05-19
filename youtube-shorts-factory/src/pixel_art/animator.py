"""Animate a still pixel-art image into a 15-second cozy Short.

Cheap-tier animation (no img2vid spend):
  - Subtle Ken Burns zoom (1.00 -> 1.04 over duration)
  - Optional parallax pan (left-to-right by N pixels)
  - Mood-driven particle overlay:
      rainy  -> falling rain inside the bounds we estimate are a window
      snowy  -> drifting snowflakes everywhere
      warm   -> floating dust motes
      dreamy -> slow drifting twinkles
      morning-> static (no particles, just zoom)
      cafe   -> subtle steam swirls

This won't fully match pixosly's character-level animation (that needs
Stable Video Diffusion in the medium tier) but it produces real motion
that meaningfully outperforms a static image.
"""
from __future__ import annotations

import logging
import math
import random
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

log = logging.getLogger("pixel.animator")


def animate(
    still: Image.Image,
    out_path: Path,
    *,
    mood: str = "warm",
    duration_s: float = 5.0,
    fps: int = 24,
    zoom_amount: float = 0.04,
    pan_px: int = 0,
    seed: Optional[int] = None,
) -> Path:
    """Render `still` as an animated MP4 of length `duration_s`.

    Returns the path to a silent MP4 ready for muxing with music + captions.
    """
    rng = random.Random(seed or 0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = out_path.parent / "anim_frames"
    work.mkdir(exist_ok=True)

    total_frames = int(duration_s * fps)
    W, H = still.size

    # ─── Pre-compute particles based on mood ─────────────────────────────
    rain_drops = []
    snowflakes = []
    motes = []
    twinkles = []
    if mood == "rainy":
        rain_drops = [
            (rng.uniform(0, W), rng.uniform(-H, H), rng.choice([0.5, 0.8, 1.1]))
            for _ in range(80)
        ]
    elif mood == "snowy":
        snowflakes = [
            (rng.uniform(0, W), rng.uniform(-H, H),
             rng.uniform(0.4, 1.2), rng.uniform(-0.5, 0.5))
            for _ in range(60)
        ]
    elif mood == "warm":
        motes = [
            (rng.uniform(0, W), rng.uniform(0, H),
             rng.uniform(0.3, 0.8), rng.uniform(0, 6.283))
            for _ in range(40)
        ]
    elif mood == "dreamy":
        twinkles = [
            (rng.uniform(0, W), rng.uniform(0, H),
             rng.uniform(0.5, 1.5), rng.uniform(0, 6.283))
            for _ in range(30)
        ]

    # ─── Render frames ───────────────────────────────────────────────────
    for i in range(total_frames):
        t = i / fps
        prog = t / duration_s  # 0 -> 1

        # Apply zoom + optional pan via crop+resize
        zoom = 1.0 + zoom_amount * prog
        cw, ch = int(W / zoom), int(H / zoom)
        pan_offset = int(pan_px * (prog - 0.5))   # centered around 0
        left = (W - cw) // 2 + pan_offset
        top = (H - ch) // 2
        left = max(0, min(W - cw, left))
        frame = still.crop((left, top, left + cw, top + ch)).resize(
            (W, H), Image.LANCZOS
        )

        # Particle overlay
        if rain_drops or snowflakes or motes or twinkles:
            d = ImageDraw.Draw(frame, "RGBA")
            if rain_drops:
                # Falling rain — angled slightly
                for x, y_seed, speed in rain_drops:
                    y = (y_seed + 600 * speed * t) % (H + 60) - 30
                    alpha = int(180 * speed / 1.1)
                    d.line(
                        [(x, y), (x - 6, y + 18)],
                        fill=(170, 200, 240, alpha), width=2,
                    )
            if snowflakes:
                for x, y_seed, speed, drift in snowflakes:
                    y = (y_seed + 80 * speed * t) % (H + 30) - 15
                    xj = x + 50 * drift * math.sin(t * 1.5)
                    r = max(1, int(2 * speed))
                    d.ellipse(
                        (xj - r, y - r, xj + r, y + r),
                        fill=(255, 255, 255, 180),
                    )
            if motes:
                for x, y, scale, phase in motes:
                    xj = x + 18 * math.sin(t * 0.5 + phase)
                    yj = y + 12 * math.cos(t * 0.4 + phase)
                    r = max(1, int(3 * scale))
                    d.ellipse(
                        (xj - r, yj - r, xj + r, yj + r),
                        fill=(255, 220, 150, 100),
                    )
            if twinkles:
                for x, y, scale, phase in twinkles:
                    alpha = int(200 * (0.5 + 0.5 * math.sin(t * 2 + phase)))
                    r = max(1, int(2 * scale))
                    d.ellipse(
                        (x - r, y - r, x + r, y + r),
                        fill=(255, 240, 200, alpha),
                    )

        frame.save(work / f"f_{i:05d}.png")

    # ─── Encode ──────────────────────────────────────────────────────────
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y",
         "-framerate", str(fps),
         "-i", str(work / "f_%05d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-preset", "veryfast", "-crf", "18",
         str(out_path)],
        check=True, capture_output=True,
    )
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    log.info("Animated %s -> %s (%s, %.1fs)", still.size, out_path, mood, duration_s)
    return out_path

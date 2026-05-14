"""Vertical 9:16 thumbnail generator using Pillow.

YouTube ignores custom thumbnails for true Shorts (they use the first
frame), but we generate one anyway so the channel page looks polished
when the video plays as a standard upload, and so we can use it as a
preview/social-share asset.
"""
from __future__ import annotations

import logging
import textwrap
from pathlib import Path

import ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import ThumbnailCfg

log = logging.getLogger("shorts_factory.thumbnail")


def _grab_frame(video_path: Path, at_seconds: float, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    (
        ffmpeg.input(str(video_path), ss=at_seconds)
        .output(str(out), vframes=1)
        .overwrite_output()
        .run(quiet=True)
    )
    return out


def make_thumbnail(
    *,
    short_video_path: Path,
    title_text: str,
    cfg: ThumbnailCfg,
    fonts_dir: str,
    output_path: Path,
    frame_grab_seconds: float = 1.0,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) Grab a frame for the background
    raw = output_path.with_suffix(".raw.jpg")
    _grab_frame(short_video_path, frame_grab_seconds, raw)

    img = Image.open(raw).convert("RGB").resize((cfg.width, cfg.height))
    # 2) Blur + darken background slightly so text pops.
    bg = img.filter(ImageFilter.GaussianBlur(cfg.background_blur))
    overlay = Image.new("RGB", (cfg.width, cfg.height), (0, 0, 0))
    bg = Image.blend(bg, overlay, 0.35)

    # 3) Big bold title text wrapped onto multiple lines.
    draw = ImageDraw.Draw(bg)
    font_path = Path(fonts_dir) / cfg.title_font
    try:
        font = ImageFont.truetype(str(font_path), cfg.title_font_size)
    except OSError:
        log.warning("Title font %s missing; using default", font_path)
        font = ImageFont.load_default()

    # Wrap by characters then draw line-by-line, centered.
    safe_title = title_text[: cfg.title_max_chars * 3]
    lines = textwrap.wrap(safe_title, width=cfg.title_max_chars)
    if not lines:
        lines = [safe_title]

    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=cfg.title_stroke_width)
        line_heights.append(bbox[3] - bbox[1])
    total_h = sum(line_heights) + (len(lines) - 1) * 30

    y = (cfg.height - total_h) // 2
    for line, lh in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=cfg.title_stroke_width)
        w = bbox[2] - bbox[0]
        x = (cfg.width - w) // 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill="white",
            stroke_width=cfg.title_stroke_width,
            stroke_fill="black",
        )
        y += lh + 30

    bg.save(output_path, "JPEG", quality=92)
    raw.unlink(missing_ok=True)
    log.info("Wrote thumbnail %s", output_path)
    return output_path

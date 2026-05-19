"""Final pixel-art Short renderer.

Inputs:
  - silent video (from animator.py)
  - music track (from music_picker.py)
  - caption text
  - watermark text (channel handle)
  - duration

Output:
  - 1080x1920 H.264/AAC MP4 with caption overlay, watermark, loop fade.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("pixel.renderer")


def _escape_drawtext(s: str) -> str:
    """Make a string safe to embed in ffmpeg drawtext via 'textfile' indirection.

    Apostrophes and special chars in drawtext are tricky. We use a tempfile
    pattern (caller writes the text to a file, we pass `textfile=`).
    """
    return s


def render_short(
    *,
    silent_video: Path,
    music: Path,
    caption: str,
    watermark: str,
    output: Path,
    duration_s: float,
    fonts_dir: str = "data/fonts",
) -> Path:
    """Render the final Short."""
    output.parent.mkdir(parents=True, exist_ok=True)

    # Write caption text to files so we don't fight ffmpeg's quote escaping.
    caption_file = output.parent / "_caption.txt"
    caption_file.write_text(caption, encoding="utf-8")
    watermark_file = output.parent / "_watermark.txt"
    watermark_file.write_text(watermark, encoding="utf-8")

    font_path = f"{fonts_dir}/Montserrat-Black.ttf"
    if not Path(font_path).exists():
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    fade_start = max(duration_s - 0.5, 0.1)

    cap_esc = str(caption_file).replace("\\", "/").replace(":", r"\:")
    wm_esc = str(watermark_file).replace("\\", "/").replace(":", r"\:")
    font_esc = font_path.replace("\\", "/").replace(":", r"\:")

    filters = [
        # Caption — soft white with shadow, bottom-center (pixosly aesthetic)
        f"drawtext=fontfile={font_esc}:textfile={cap_esc}:"
        f"fontsize=58:fontcolor=white:shadowcolor=black@0.75:"
        f"shadowx=2:shadowy=3:x=(w-tw)/2:y=h*0.84",
        # Watermark — top-left lowercase handle
        f"drawtext=fontfile={font_esc}:textfile={wm_esc}:"
        f"fontsize=34:fontcolor=white@0.85:"
        f"box=1:boxcolor=black@0.45:boxborderw=10:x=40:y=60",
        # Loop-perfect fade tail
        f"fade=t=out:st={fade_start:.2f}:d=0.4:c=black:alpha=1",
    ]

    subprocess.run(
        ["ffmpeg", "-y",
         "-i", str(silent_video),
         "-i", str(music),
         "-filter_complex", ",".join(filters),
         "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-c:a", "aac",
         "-b:v", "6M", "-b:a", "192k",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         "-shortest", str(output)],
        check=True, capture_output=True,
    )

    # Tidy up
    caption_file.unlink(missing_ok=True)
    watermark_file.unlink(missing_ok=True)

    log.info("Rendered pixel-art Short: %s (%.1fs)", output, duration_s)
    return output

"""Pick + loop a CC0 lofi track to length.

Production: drop CC0 lofi MP3s into data/music/ (Pixabay Music has hundreds).
Filename convention (optional):
  data/music/rainy_chillhop.mp3
  data/music/warm_jazz_loop.mp3
  data/music/dreamy_pad.mp3
  ...

If the filename starts with a mood ("rainy_…"), we prefer matching tracks.
Otherwise we pick uniformly at random.
"""
from __future__ import annotations

import logging
import random
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger("pixel.music")

MUSIC_EXTS = {".mp3", ".m4a", ".wav", ".ogg"}


def pick_track(music_dir: Path, mood: str = "warm") -> Optional[Path]:
    if not music_dir.exists():
        return None
    tracks = [p for p in music_dir.iterdir() if p.suffix.lower() in MUSIC_EXTS]
    if not tracks:
        return None
    matching = [p for p in tracks if p.stem.lower().startswith(mood.lower())]
    pool = matching or tracks
    return random.choice(pool)


def loop_to_length(track: Path, out_path: Path, length_s: float) -> Path:
    """Loop the track to exactly `length_s` seconds. Soft fades 0.3s in/out."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y",
         "-stream_loop", "-1", "-i", str(track),
         "-af",
         f"afade=t=in:st=0:d=0.4,afade=t=out:st={length_s-0.5:.2f}:d=0.5,volume=0.8",
         "-t", f"{length_s:.2f}",
         "-c:a", "aac", "-b:a", "192k",
         str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def synthesize_silence_with_tone(out_path: Path, length_s: float) -> Path:
    """Fallback when data/music/ is empty: a soft sine pad (production should
    never hit this — drop real CC0 lofi into data/music/)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi",
         "-i", f"sine=frequency=220:duration={length_s},volume=0.12",
         "-ac", "2", "-ar", "44100",
         "-c:a", "aac", "-b:a", "128k",
         str(out_path)],
        check=True, capture_output=True,
    )
    log.warning("No CC0 music found in data/music/ — using sine fallback. "
                "Drop real lofi MP3s in data/music/ for production runs.")
    return out_path

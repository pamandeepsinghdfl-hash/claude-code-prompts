"""Proof-of-concept: download a real video clip from any YouTube URL.

Runs ONE step from the factory — the part that cuts a viral video segment
from YouTube. No API keys needed. No LLM. Just yt-dlp + ffmpeg.

  Usage:
    python scripts/prove_clip_works.py "https://www.youtube.com/watch?v=VIDEO_ID" 60 90

  Arguments:
    1. Any YouTube URL
    2. Start time in seconds (e.g. 60 = 1 minute in)
    3. End time in seconds

  Output:
    output/shorts/clip_<videoid>_<start>_<end>.mp4

This is the EXACT function the factory's pipeline calls. If this works,
the factory works.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.download.downloader import Downloader

if len(sys.argv) != 4:
    print(__doc__)
    sys.exit(1)

url = sys.argv[1]
start = float(sys.argv[2])
end = float(sys.argv[3])

# Extract a fake "video_id" for the filename
video_id = url.split("=")[-1].split("&")[0][:11] or "test"

dl = Downloader(work_dir="output/shorts")
print(f"Downloading segment [{start:.0f}s – {end:.0f}s] from {url}")
print("(uses yt-dlp + ffmpeg; ~10-60 seconds depending on connection)")

path = dl.download_segment(url, video_id, start, end)
print(f"\nReal video clip saved to: {path}")
print(f"Size: {path.stat().st_size / 1024 / 1024:.2f} MB")

# Probe the file so user sees it's real video
import subprocess
probe = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries",
     "stream=codec_type,codec_name,width,height,duration",
     "-of", "default=noprint_wrappers=1", str(path)],
    capture_output=True, text=True, check=True,
)
print("\nffprobe output (proves it's a real video clip):")
print(probe.stdout)

"""Render ONE sample Short end-to-end using the factory's real code.

This script demonstrates the full Daily Decoded pipeline on a public-domain
story so anyone can run it without YouTube/Groq keys. It produces a 9:16
vertical MP4 with:

  - AI narration (edge-tts)
  - Word-level timestamps (faster-whisper tiny)
  - TikTok-style karaoke ASS captions (the factory's real caption writer)
  - Hook overlay at t=0 (Tactic 1)
  - Loop-close echo in the last 1s (Tactic 2)
  - Subscribe CTA at 70% (Tactic 5)
  - Ken Burns motion + procedural animated background
  - Loop-perfect fade tail
"""
from __future__ import annotations

import asyncio
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import load_config
from src.transcription.whisper_transcriber import WhisperTranscriber
from src.video.captions import write_ass_captions

OUT_DIR = Path(__file__).resolve().parent.parent / "output" / "shorts"
WORK = Path(__file__).resolve().parent.parent / "output" / "workdir" / "sample"
WORK.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── 1. Pick a story ─────────────────────────────────────────────────────
stories = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "public_domain_stories.json")
    .read_text(encoding="utf-8")
)
story = next(s for s in stories if s["id"] == "aesop_lion_mouse")

# Hook (first 1.5s) + loop close (last 1s) — what the LLM would normally write.
HOOK = "A LION SPARED A MOUSE."
LOOP_CLOSE = "KINDNESS HAS A MEMORY."

# Narration script — tight, hook-first, payoff at end.
SCRIPT = (
    "A mighty lion caught a tiny mouse, who begged for mercy. "
    "Amused, the lion let her go. "
    "Weeks later, the lion was trapped in a hunter's net. "
    "The same little mouse chewed through the ropes. "
    "The greatest king and the smallest creature... saved each other. "
    "Kindness has a long memory."
)

print(f"Story: {story['title']} ({story['country']}, public domain)")
print(f"Hook: {HOOK}")
print(f"Loop close: {LOOP_CLOSE}")


# ─── 2. Generate narration (offline TTS — espeak-ng) ─────────────────────
print("\n[1/6] Generating narration with espeak-ng (offline TTS)...")
subprocess.run(
    [
        "espeak-ng", "-v", "en-us+f3",
        "-s", "160",        # words per minute
        "-p", "55",         # pitch
        "-g", "5",          # word gap (ms)
        "-w", str(WORK / "narration.wav"),
        SCRIPT,
    ],
    check=True,
)
# Also produce an mp3 for the final mux
(
    ffmpeg.input(str(WORK / "narration.wav"))
    .output(str(WORK / "narration.mp3"), audio_bitrate="192k")
    .overwrite_output().run(quiet=True)
)


# ─── 3. Transcribe with whisper-tiny to get word timestamps ──────────────
print("[2/6] Running whisper-tiny for word-level timestamps...")
w = WhisperTranscriber("tiny", device="cpu", compute_type="int8")
transcript = w.transcribe(str(WORK / "narration.wav"), language="en")

# Probe duration
probe = ffmpeg.probe(str(WORK / "narration.mp3"))
duration = float(probe["format"]["duration"])
print(f"        narration duration: {duration:.2f}s, segments: {len(transcript.segments)}")


# ─── 4. Generate procedural 9:16 background ──────────────────────────────
# A subtle animated gradient with slow drift. Pure ffmpeg so no source video
# is needed. In production this would be the cropped 9:16 source clip.
print("[3/6] Generating animated 9:16 background (1080x1920)...")

W, H = 1080, 1920
FPS = 30
total_frames = int(duration * FPS) + FPS  # +1s for loop tail


def make_frame(t):
    """Animated gradient + drifting particles + subtle vignette."""
    img = Image.new("RGB", (W, H), (8, 8, 14))
    d = ImageDraw.Draw(img)
    # Drifting orange-yellow glow (warm = motivation niche)
    cx = W * (0.5 + 0.12 * math.sin(t * 0.6))
    cy = H * (0.5 + 0.10 * math.cos(t * 0.4))
    rx = W * (0.9 + 0.10 * math.sin(t * 0.3))
    ry = H * (0.55 + 0.06 * math.cos(t * 0.25))
    for i in range(7):
        alpha = int(60 - i * 8)
        color = (180 - i * 12, 110 - i * 8, 0)
        d.ellipse((cx - rx * (1 - i*0.08), cy - ry * (1 - i*0.08),
                   cx + rx * (1 - i*0.08), cy + ry * (1 - i*0.08)),
                  fill=color)
    img = img.filter(ImageFilter.GaussianBlur(80))
    # Particles
    rng = np.random.default_rng(int(t * 1000) % 99999)
    for _ in range(40):
        x = rng.uniform(0, W)
        y = (rng.uniform(0, H) + t * 30) % H
        r = rng.uniform(2, 6)
        c = int(180 + 40 * rng.uniform())
        d2 = ImageDraw.Draw(img)
        d2.ellipse((x-r, y-r, x+r, y+r), fill=(c, c, c))
    # Vignette
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse((-200, -200, W+200, H+200), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(220))
    blackbg = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(img, blackbg, vig)
    return img


# Write frames to a temp dir using ffmpeg's image2 sequence
frames_dir = WORK / "frames"
frames_dir.mkdir(exist_ok=True)
for i, t in enumerate(np.linspace(0, duration, total_frames)):
    if i % 30 == 0:
        print(f"        frame {i}/{total_frames}")
    make_frame(float(t)).save(frames_dir / f"f_{i:05d}.png", optimize=False)

# Encode frames -> mp4
silent_bg = WORK / "silent_bg.mp4"
(
    ffmpeg.input(str(frames_dir / "f_%05d.png"), framerate=FPS)
    .output(str(silent_bg), vcodec="libx264", pix_fmt="yuv420p", r=FPS, crf=18, an=None)
    .overwrite_output().run(quiet=True)
)
print(f"        wrote {silent_bg}")


# ─── 5. Write ASS captions (factory's real caption writer) ───────────────
print("[4/6] Writing karaoke ASS captions with hook overlay + loop close...")
cfg = load_config()
ass_path = WORK / "captions.ass"
write_ass_captions(
    transcript,
    cfg.captions,
    W, H,
    ass_path,
    clip_offset_s=0.0,
    hook_overlay=HOOK,
    loop_close=LOOP_CLOSE,
    clip_duration_s=duration,
)


# ─── 6. Mux audio + render final Short with captions + CTA + fade ───────
print("[5/6] Rendering final Short (captions + subscribe CTA + loop fade)...")

# Combine silent_bg + narration into a single MP4 with audio
v_in = ffmpeg.input(str(silent_bg))
a_in = ffmpeg.input(str(WORK / "narration.mp3"))

# Burn captions
ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
v = v_in.video.filter("ass", f"{ass_escaped}:fontsdir=data/fonts")

# Subtle Ken Burns zoom
v = v.filter(
    "zoompan",
    z="min(zoom+0.0008,1.06)",
    d=1, s=f"{W}x{H}", fps=FPS,
)

# Subscribe CTA at 65-90% (Tactic 5)
cta_start = duration * 0.65
cta_end = duration * 0.92
v = v.filter(
    "drawtext",
    text=" TAP SUBSCRIBE ",
    fontfile="data/fonts/Montserrat-Black.ttf",
    fontsize=58, fontcolor="white",
    box=1, boxcolor="red@0.88", boxborderw=18,
    x="(w-tw)/2", y="h*0.78",
    enable=f"between(t,{cta_start:.2f},{cta_end:.2f})",
)

# Brand watermark top-right
v = v.filter(
    "drawtext",
    text="@dailydecoded",
    fontfile="data/fonts/Montserrat-Black.ttf",
    fontsize=34, fontcolor="white@0.75",
    box=1, boxcolor="black@0.35", boxborderw=10,
    x="w-tw-40", y="60",
)

# Loop-perfect fade tail (Tactic 2 visual half)
v = v.filter(
    "fade", type="out",
    start_time=f"{max(duration-0.3,0.1):.2f}",
    duration=0.3, color="black", alpha=1,
)

final = OUT_DIR / "sample_daily_decoded.mp4"
(
    ffmpeg.output(
        v, a_in.audio, str(final),
        vcodec="libx264", acodec="aac",
        video_bitrate="8M", audio_bitrate="192k",
        pix_fmt="yuv420p", movflags="+faststart",
        r=FPS, shortest=None,
    )
    .overwrite_output().run(quiet=True)
)
print(f"[6/6] Done. Final: {final}")
print(f"        Size: {final.stat().st_size/1024/1024:.2f} MB")

# Tidy up frame stills (not needed anymore)
import shutil
shutil.rmtree(frames_dir, ignore_errors=True)

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


# ─── 4. Generate procedural 9:16 background (pure ffmpeg, fast) ──────────
# In production this is the cropped 9:16 source video. For the demo we
# build an animated gradient via ffmpeg's lavfi filters — no per-frame
# Python work, runs in seconds.
print("[3/6] Generating animated 9:16 background (1080x1920) via ffmpeg lavfi...")
W, H = 1080, 1920
FPS = 30
total_dur = duration + 0.5

silent_bg = WORK / "silent_bg.mp4"
# Two animated gradient layers + grain, blended for a warm "motivation" feel
filter_complex = (
    f"color=c=0x070710:s={W}x{H}:d={total_dur}:r={FPS}[bg];"
    f"gradients=s={W}x{H}:d={total_dur}:r={FPS}:c0=0xB47800:c1=0x1a0a00:"
    f"x0=540:y0=900:x1=200:y1=1500:nb_colors=8,format=yuv420p[grad];"
    f"nullsrc=s={W}x{H}:d={total_dur}:r={FPS},"
    f"geq=lum='128+50*sin(2*PI*(X/{W}+Y/{H}+T*0.15))':cb=128:cr=128"
    f"[wave];"
    f"[bg][grad]blend=all_mode=screen:all_opacity=0.8[mix1];"
    f"[mix1][wave]blend=all_mode=overlay:all_opacity=0.18,"
    f"gblur=sigma=2,"
    f"vignette=PI/4"
    f"[out]"
)
subprocess.run(
    [
        "ffmpeg", "-y",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(FPS), "-t", f"{total_dur}",
        "-preset", "veryfast", "-crf", "20",
        str(silent_bg),
    ],
    check=True, capture_output=True,
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


# ─── 6. Mux audio + render final Short (subprocess ffmpeg, clean escaping)─
print("[5/6] Rendering final Short (captions + subscribe CTA + loop fade)...")
final = OUT_DIR / "sample_daily_decoded.mp4"

cta_start = duration * 0.65
cta_end = duration * 0.92
fade_start = max(duration - 0.3, 0.1)

# ass filter needs `:` escaped as `\:` in the filter spec
ass_arg = f"ass={ass_path}:fontsdir=data/fonts"
filter_chain = (
    f"{ass_arg},"
    f"drawtext=fontfile=data/fonts/Montserrat-Black.ttf:"
    f"text=' TAP SUBSCRIBE ':fontsize=58:fontcolor=white:"
    f"box=1:boxcolor=red@0.88:boxborderw=18:"
    f"x=(w-tw)/2:y=h*0.78:"
    f"enable='between(t\\,{cta_start:.2f}\\,{cta_end:.2f})',"
    f"drawtext=fontfile=data/fonts/Montserrat-Black.ttf:"
    f"text='@dailydecoded':fontsize=34:fontcolor=white@0.75:"
    f"box=1:boxcolor=black@0.35:boxborderw=10:x=w-tw-40:y=60,"
    f"fade=t=out:st={fade_start:.2f}:d=0.3:c=black:alpha=1"
)

subprocess.run(
    [
        "ffmpeg", "-y",
        "-i", str(silent_bg),
        "-i", str(WORK / "narration.mp3"),
        "-vf", filter_chain,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-c:a", "aac",
        "-b:v", "8M", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-r", str(FPS), "-shortest",
        str(final),
    ],
    check=True, capture_output=True,
)
print(f"[6/6] Done. Final: {final}")
print(f"        Size: {final.stat().st_size/1024/1024:.2f} MB")


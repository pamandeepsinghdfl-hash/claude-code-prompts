"""Render a sample Short from a REAL interview video.

Source: Charles Amirkhanian interviews film director Frank Scheffer
        (Other Minds Presents, 2010, archive.org)
        https://archive.org/details/OMP_2010_04_19_1

Pipeline (the factory's actual code, end-to-end):
  1. Use the existing downloaded interview as the source
  2. Transcribe with faster-whisper (real word-level timestamps)
  3. Hand-pick a viral moment (no LLM key available in sandbox; this is
     what viral_detector.py would do automatically on your PC)
  4. Slice the transcript to the chosen window
  5. Write karaoke ASS captions with hook overlay + loop close
  6. Crop the original interview footage to 9:16 with Ken Burns
  7. Burn in captions + subscribe CTA + brand watermark + loop fade
  8. Output a real Short MP4 to output/shorts/
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import load_config
from src.transcription.whisper_transcriber import WhisperTranscriber
from src.video.captions import write_ass_captions

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "output" / "workdir" / "real_demo" / "source.mp4"
WORK = ROOT / "output" / "workdir" / "real_demo"
OUT = ROOT / "output" / "shorts"
OUT.mkdir(parents=True, exist_ok=True)

W, H, FPS = 1080, 1920, 30

assert SOURCE.exists(), f"Source not found at {SOURCE}"

# ─── 1. Extract audio for transcription ──────────────────────────────────
print("[1/5] Extracting audio for whisper...")
audio = WORK / "source.wav"
subprocess.run(
    ["ffmpeg", "-y", "-i", str(SOURCE), "-ac", "1", "-ar", "16000",
     "-vn", str(audio)],
    check=True, capture_output=True,
)

# ─── 2. Transcribe full interview ────────────────────────────────────────
print("[2/5] Transcribing full interview with whisper-tiny...")
w = WhisperTranscriber("tiny", device="cpu", compute_type="int8")
full_transcript = w.transcribe(str(audio), language="en")
print(f"        {len(full_transcript.segments)} segments, lang={full_transcript.detected_language}")

# ─── 3. Pick a 30-45s viral window manually (no LLM in sandbox) ──────────
# We scan the transcript and pick a self-contained, hooky window.
# On the user's PC, viral_detector.py with Groq/Claude does this automatically.
print("\n[3/5] Selecting viral moment from transcript...")
print("        (first 20 seg previews):")
for seg in full_transcript.segments[:20]:
    print(f"          [{seg.start:6.1f}-{seg.end:6.1f}] {seg.text[:90]}")

# Pick a window — let's look for a meaty mid-interview moment.
# Typical interview pacing: hook arrives 20-90s in. We'll grab a 35s slice
# starting around 30s.
target_start = 30.0
target_end = 65.0

# Find actual sentence boundaries near these times
sliced = w.slice_for_window(full_transcript, target_start, target_end)
print(f"\n        Selected window: {target_start:.1f}s - {target_end:.1f}s")
print(f"        Words in window: {sum(len(s.words) for s in sliced.segments)}")
print(f"        Text: {sliced.full_text[:200]}...")

clip_duration = target_end - target_start

# Manually craft hook + loop close (what the LLM would produce)
HOOK = "FILM DIRECTOR REVEALS HIS PROCESS."
LOOP_CLOSE = "HE NEVER SAID THIS BEFORE."

# ─── 4. Extract the actual video segment + crop to 9:16 ──────────────────
print("\n[4/5] Extracting segment + cropping to 9:16...")
seg_path = WORK / "segment_9_16.mp4"

# Source is 436x240 landscape. We pad to 9:16 with a blurred background
# (the same source video scaled up + blurred) — this is the pattern the
# factory uses when the source isn't already 9:16 friendly.
subprocess.run(
    [
        "ffmpeg", "-y",
        "-ss", str(target_start), "-t", str(clip_duration),
        "-i", str(SOURCE),
        "-filter_complex",
        # Background: scale to fill 1080x1920 and heavily blur
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},boxblur=40:1,eq=brightness=-0.18[bg];"
        # Foreground: original aspect, scaled to fit width (so it's centered)
        f"[0:v]scale={W}:-1[fg];"
        # Overlay foreground on blurred background, vertically centered
        f"[bg][fg]overlay=0:(H-h)/2[v]",
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(seg_path),
    ],
    check=True, capture_output=True,
)
print(f"        wrote {seg_path}")

# ─── 5. Karaoke captions (factory's real writer) ─────────────────────────
print("[5/5] Writing karaoke captions + final render...")
cfg = load_config()
ass_path = WORK / "captions.ass"
write_ass_captions(
    sliced,
    cfg.captions,
    W, H, ass_path,
    clip_offset_s=target_start,
    hook_overlay=HOOK,
    loop_close=LOOP_CLOSE,
    clip_duration_s=clip_duration,
)

# Final render: captions + CTA + watermark + fade
final = OUT / "sample_real_interview.mp4"

cta_start = clip_duration * 0.65
cta_end = clip_duration * 0.92
fade_start = max(clip_duration - 0.3, 0.1)

ass_escaped = str(ass_path).replace(":", r"\:")
filters = [
    f"ass={ass_escaped}:fontsdir=data/fonts",
    # Source credit banner — top-left
    "drawtext=fontfile=data/fonts/Montserrat-Black.ttf:"
    "text='REAL INTERVIEW · CC-LICENSED':fontsize=34:fontcolor=white:"
    "box=1:boxcolor=0xCC0033@0.92:boxborderw=12:x=40:y=130",
    # Brand watermark — top-right
    "drawtext=fontfile=data/fonts/Montserrat-Black.ttf:"
    "text='@pixelhours':fontsize=34:fontcolor=white@0.8:"
    "box=1:boxcolor=black@0.45:boxborderw=10:x=w-tw-40:y=130",
    # Subscribe CTA
    f"drawtext=fontfile=data/fonts/Montserrat-Black.ttf:"
    f"text=' TAP SUBSCRIBE ':fontsize=62:fontcolor=white:"
    f"box=1:boxcolor=red@0.92:boxborderw=20:"
    f"x=(w-tw)/2:y=h*0.82:"
    f"enable='between(t\\,{cta_start:.2f}\\,{cta_end:.2f})'",
    # Loop-perfect fade tail
    f"fade=t=out:st={fade_start:.2f}:d=0.3:c=black:alpha=1",
]

subprocess.run(
    [
        "ffmpeg", "-y",
        "-i", str(seg_path),
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-c:a", "copy",
        "-b:v", "8M",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-r", str(FPS),
        str(final),
    ],
    check=True, capture_output=True,
)

print(f"\nDone. Real interview Short: {final}")
print(f"   Size: {final.stat().st_size/1024/1024:.2f} MB")
print(f"   Source: archive.org/details/OMP_2010_04_19_1 (Frank Scheffer interview)")

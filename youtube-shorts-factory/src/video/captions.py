"""TikTok-style English caption renderer.

We render captions with ffmpeg's `drawtext` filter for two reasons:
  1. It's much faster than rendering many MoviePy TextClips.
  2. It's robust on headless servers (no ImageMagick dependency).

Strategy:
  • Split each segment into "phrase chunks" capped at
    `style.max_chars_per_line * style.max_lines` characters.
  • For each chunk, emit a `drawtext` filter with `enable='between(t,start,end)'`.
  • To get the karaoke "active word" effect we render the chunk twice:
    once as the base layer (white-on-black-outline) and once as a smaller
    highlight layer (yellow) gated to the active word's timespan.

The output is a `caption.ass` file (Advanced SubStation Alpha) — we use
ASS instead of plain drawtext for production quality because ASS lets us
do per-word \\k tags and scale animations natively.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from ..config import CaptionsCfg
from ..transcription.whisper_transcriber import Transcript, WordTiming

log = logging.getLogger("shorts_factory.captions")


@dataclass
class CaptionChunk:
    start: float
    end: float
    words: List[WordTiming]

    @property
    def text(self) -> str:
        return " ".join(w.word.strip() for w in self.words if w.word.strip())


def chunk_for_display(
    transcript: Transcript,
    max_chars_per_line: int,
    max_lines: int,
) -> List[CaptionChunk]:
    """Break the transcript into mobile-readable chunks.

    Each chunk is at most `max_chars_per_line * max_lines` chars long and
    never crosses segment boundaries.
    """
    budget = max_chars_per_line * max_lines
    chunks: List[CaptionChunk] = []
    for seg in transcript.segments:
        bucket: List[WordTiming] = []
        bucket_len = 0
        for w in seg.words:
            wlen = len(w.word.strip()) + 1
            if bucket and bucket_len + wlen > budget:
                chunks.append(
                    CaptionChunk(
                        start=bucket[0].start, end=bucket[-1].end, words=bucket
                    )
                )
                bucket = [w]
                bucket_len = wlen
            else:
                bucket.append(w)
                bucket_len += wlen
        if bucket:
            chunks.append(
                CaptionChunk(start=bucket[0].start, end=bucket[-1].end, words=bucket)
            )
    return chunks


# ─── ASS file writer ──────────────────────────────────────────────────────
def _hex_to_ass_color(hex_color: str) -> str:
    """#RRGGBB -> &HAABBGGRR (ASS uses BGR with alpha)."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"&H00{b}{g}{r}".upper()
    return "&H00FFFFFF"


def _format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def write_ass_captions(
    transcript: Transcript,
    cfg: CaptionsCfg,
    video_w: int,
    video_h: int,
    output_path: Path,
    *,
    clip_offset_s: float = 0.0,
    hook_overlay: str = "",
    loop_close: str = "",
    clip_duration_s: float = 0.0,
) -> Path:
    """Write an ASS subtitle file for the clipped window.

    `clip_offset_s` lets you shift all times so they start at 0 when the
    transcript was sliced from a longer original.

    `hook_overlay` is an English line forced onto the screen at t=0 for
    1.4s, BEFORE the voice begins — this is the #1 lever for cutting
    swipe-away rate. `loop_close` is shown for the final 1s and echoes
    the hook so the replay feels seamless.
    """
    style = cfg.style

    # 2 lines minimum margin to clear the YouTube Shorts UI overlay.
    margin_v = max(cfg.safe_margin_px, video_h // 6)

    primary = _hex_to_ass_color(style.fill_color)
    outline = _hex_to_ass_color(style.stroke_color if style.stroke_color.startswith("#") else "#000000")
    highlight = _hex_to_ass_color(style.highlight_color)

    alignment = {"bottom": 2, "center": 5, "top": 8}.get(style.position, 5)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font.replace('.ttf','').replace('-Black','')} Black,{style.font_size},{primary},{highlight},{outline},&H64000000,-1,0,0,0,100,100,0,0,1,{style.stroke_width},2,{alignment},60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    chunks = chunk_for_display(
        transcript,
        max_chars_per_line=style.max_chars_per_line,
        max_lines=style.max_lines,
    )

    events: List[str] = []

    # Tactic 1: HOOK OVERLAY at t=0 (no voice yet). The single biggest
    # lever for cutting swipe-away rate in the first 1.5 seconds.
    if hook_overlay:
        hook_text = hook_overlay.replace("{", "(").replace("}", ")").upper()
        hook_styled = (
            f"{{\\fad(60,120)\\fscx115\\fscy115\\bord{style.stroke_width+2}"
            f"\\1c{highlight}\\3c{outline}}}{hook_text}"
        )
        events.append(
            f"Dialogue: 1,{_format_time(0)},{_format_time(1.4)},Default,,0,0,0,,{hook_styled}"
        )

    # Tactic 2: LOOP CLOSE in the last 1.0s. Echoes the hook so the loop
    # replay feels intentional — boosts rewatch rate.
    if loop_close and clip_duration_s > 1.2:
        close_text = loop_close.replace("{", "(").replace("}", ")").upper()
        close_styled = (
            f"{{\\fad(120,80)\\fscx110\\fscy110\\bord{style.stroke_width+2}"
            f"\\1c{highlight}\\3c{outline}}}{close_text}"
        )
        events.append(
            f"Dialogue: 1,{_format_time(clip_duration_s-1.0)},"
            f"{_format_time(clip_duration_s)},Default,,0,0,0,,{close_styled}"
        )

    for chunk in chunks:
        # Build karaoke string: per-word duration in centiseconds.
        karaoke_parts: List[str] = []
        for w in chunk.words:
            dur_cs = max(int(round((w.end - w.start) * 100)), 5)
            text = w.word.strip().replace("\n", " ").replace("{", "(").replace("}", ")")
            karaoke_parts.append(f"{{\\kf{dur_cs}}}{text} ")
        text = "".join(karaoke_parts).rstrip()

        # Pop animation on entrance for extra TikTok feel.
        text = f"{{\\fad({style.fade_ms},{style.fade_ms})\\t(0,150,\\fscx{int(style.pop_scale*100)}\\fscy{int(style.pop_scale*100)})\\t(150,300,\\fscx100\\fscy100)}}{text}"

        start = max(chunk.start - clip_offset_s, 0)
        end = max(chunk.end - clip_offset_s, start + 0.2)
        events.append(
            f"Dialogue: 0,{_format_time(start)},{_format_time(end)},Default,,0,0,0,,{text}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    log.info("Wrote ASS captions: %s (%d events)", output_path, len(events))
    return output_path


def style_assets(cfg: CaptionsCfg) -> Tuple[str]:
    """Return font path tuple for ffmpeg fontsdir."""
    return ("data/fonts",)

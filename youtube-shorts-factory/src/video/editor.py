"""Vertical (9:16) video assembly pipeline.

Pipeline (all via ffmpeg for speed and headless safety):
  1. Crop+scale the source segment to 1080x1920, preserving the most
     visually informative central column.
  2. Apply subtle Ken Burns zoom (slow centred zoom-in).
  3. Mix royalty-free background music at low volume under original audio.
  4. Burn in the ASS caption file (mandatory English).
  5. Encode to H.264 + AAC at config bitrate.

We use ffmpeg-python to build the filter graph declaratively.
"""
from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Optional

import ffmpeg

from ..config import VideoCfg

log = logging.getLogger("shorts_factory.editor")


def pick_background_music(music_dir: Path) -> Optional[Path]:
    if not music_dir.exists():
        return None
    tracks = [p for p in music_dir.iterdir() if p.suffix.lower() in {".mp3", ".m4a", ".wav", ".ogg"}]
    if not tracks:
        return None
    return random.choice(tracks)


def render_short(
    *,
    source_segment: Path,
    ass_captions: Path,
    output_path: Path,
    cfg: VideoCfg,
    background_music: Optional[Path] = None,
    fonts_dir: str = "data/fonts",
    clip_duration_s: float = 0.0,
    subscribe_cta: bool = True,
) -> Path:
    """Render the final 9:16 Short with burnt-in captions.

    `subscribe_cta=True` overlays a red SUBSCRIBE prompt at the 70% point
    — the single biggest lever for subscribe-rate-from-Short.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ─── Video graph ──────────────────────────────────────────────────────
    v_in = ffmpeg.input(str(source_segment))

    # 1) Letterbox/crop to 9:16. We scale to fill height, then center-crop.
    v = v_in.video.filter(
        "scale",
        f"-2",
        cfg.height,
        force_original_aspect_ratio="increase",
    ).filter("crop", cfg.width, cfg.height)

    # 2) Ken Burns: slow zoom from 1.0 → 1.0+zoom across whole duration.
    if cfg.ken_burns:
        # `zoompan` expects a frame count. We zoom slowly for the whole clip.
        zoom_per_frame = cfg.ken_burns_zoom / (cfg.fps * 30)  # ~30s ramp
        v = v.filter(
            "zoompan",
            z=f"min(zoom+{zoom_per_frame},{1.0 + cfg.ken_burns_zoom})",
            d=1,
            s=f"{cfg.width}x{cfg.height}",
            fps=cfg.fps,
        )

    # 3) Burn in captions (ASS gives us per-word karaoke + animations).
    ass_escaped = str(ass_captions).replace("\\", "/").replace(":", "\\:")
    v = v.filter("ass", f"{ass_escaped}:fontsdir={fonts_dir}")

    # Tactic 5: SUBSCRIBE CTA at the 70% point — biggest lever for
    # subscribe-from-Short rate. Red box, bold white text, mid-screen.
    if subscribe_cta and clip_duration_s > 4:
        cta_start = clip_duration_s * 0.65
        cta_end = min(clip_duration_s * 0.95, clip_duration_s - 0.3)
        v = v.filter(
            "drawtext",
            text=r"\xe2\x86\x93 TAP SUBSCRIBE",
            fontfile=f"{fonts_dir}/Montserrat-Black.ttf",
            fontsize=58,
            fontcolor="white",
            box=1,
            boxcolor="red@0.88",
            boxborderw=14,
            x="(w-tw)/2",
            y="h*0.78",
            enable=f"between(t,{cta_start:.2f},{cta_end:.2f})",
        )

    # Tactic 2 (visual half): loop-perfect tail — short crossfade at the
    # very end so the YouTube replay feels seamless.
    if clip_duration_s > 1.5:
        v = v.filter(
            "fade",
            type="out",
            start_time=f"{max(clip_duration_s - 0.3, 0.1):.2f}",
            duration=0.3,
            color="black",
            alpha=1,
        )

    # Optional watermark/handle
    if cfg.watermark_text:
        v = v.filter(
            "drawtext",
            text=cfg.watermark_text,
            fontfile=f"{fonts_dir}/Montserrat-Black.ttf",
            fontsize=36,
            fontcolor="white@0.7",
            x="w-tw-30",
            y="h-th-30",
            box=1,
            boxcolor="black@0.4",
            boxborderw=10,
        )

    # ─── Audio graph ──────────────────────────────────────────────────────
    if background_music and background_music.exists():
        a_src = v_in.audio.filter("volume", 1.0)
        a_bg = (
            ffmpeg.input(str(background_music))
            .audio.filter("volume", cfg.music_volume)
            .filter("aloop", loop=-1, size=2_147_483_647)
        )
        a = ffmpeg.filter([a_src, a_bg], "amix", inputs=2, dropout_transition=2, normalize=0)
    else:
        a = v_in.audio

    # ─── Encode ───────────────────────────────────────────────────────────
    out = ffmpeg.output(
        v,
        a,
        str(output_path),
        vcodec=cfg.codec,
        acodec=cfg.audio_codec,
        video_bitrate=cfg.bitrate,
        audio_bitrate=cfg.audio_bitrate,
        pix_fmt="yuv420p",
        movflags="+faststart",
        r=cfg.fps,
        shortest=None,  # cut to source length
    ).overwrite_output()

    cmd = " ".join(out.compile())
    log.info("ffmpeg: %s", cmd)
    out.run(quiet=False)
    log.info("Rendered Short → %s", output_path)
    return output_path

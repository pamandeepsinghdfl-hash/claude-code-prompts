"""Fully original Shorts when no copyright-safe source is available.

Inputs:
  • Public-domain global stories (myths, fables, history) from
    `data/public_domain_stories.json`.
  • Optional Pixabay stock footage (CC0) — if PIXABAY_API_KEY is set.
  • Optional edge-tts narration in English.

Outputs the same shape as a sourced Short so the rest of the pipeline
(captions → editor → upload) is unchanged.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import httpx

from ..config import FallbackCfg

log = logging.getLogger("shorts_factory.fallback")


@dataclass
class FallbackStory:
    id: str
    title: str
    country: str
    language: str
    story: str
    moral: str
    source: str


def load_stories(path: str | Path) -> List[FallbackStory]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [FallbackStory(**r) for r in raw]


def pick_story(stories: List[FallbackStory], avoid_ids: set[str]) -> FallbackStory:
    pool = [s for s in stories if s.id not in avoid_ids] or stories
    return random.choice(pool)


# ─── Narration ────────────────────────────────────────────────────────────
async def _tts_async(text: str, voice: str, out_path: Path) -> Path:
    import edge_tts

    communicator = edge_tts.Communicate(text, voice)
    await communicator.save(str(out_path))
    return out_path


def synthesize_voiceover(text: str, voice: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_tts_async(text, voice, out_path))


# ─── Pixabay footage ─────────────────────────────────────────────────────
def fetch_stock_footage(
    keyword: str, pixabay_key: Optional[str], out_dir: Path, count: int = 3
) -> List[Path]:
    if not pixabay_key:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    url = "https://pixabay.com/api/videos/"
    params = {
        "key": pixabay_key,
        "q": keyword,
        "per_page": min(max(count, 3), 50),
        "video_type": "all",
        "orientation": "vertical",
        "safesearch": "true",
    }
    try:
        resp = httpx.get(url, params=params, timeout=30)
        resp.raise_for_status()
        items = resp.json().get("hits", [])
    except Exception as e:  # noqa: BLE001
        log.warning("Pixabay query failed: %s", e)
        return []

    paths: List[Path] = []
    for i, hit in enumerate(items[:count]):
        videos = hit.get("videos", {})
        chosen = videos.get("medium") or videos.get("small")
        if not chosen:
            continue
        try:
            data = httpx.get(chosen["url"], timeout=60).content
            p = out_dir / f"stock_{hit['id']}_{i}.mp4"
            p.write_bytes(data)
            paths.append(p)
        except Exception as e:  # noqa: BLE001
            log.warning("Pixabay download failed: %s", e)
    return paths


def fetch_local_stock(out_dir: Path, count: int = 3) -> List[Path]:
    if not out_dir.exists():
        return []
    pool = [p for p in out_dir.iterdir() if p.suffix.lower() in {".mp4", ".mov", ".webm"}]
    random.shuffle(pool)
    return pool[:count]


# ─── Compose narrated clip from voice + stock footage ────────────────────
def build_fallback_video(
    *,
    voiceover_path: Path,
    footage_paths: List[Path],
    work_dir: Path,
    target_width: int = 1080,
    target_height: int = 1920,
    fps: int = 30,
) -> Path:
    """Concatenate stock clips and overlay narration audio.

    Returns a single MP4 ready for the caption + editor stage. The
    output keeps the narration on the audio track so Whisper can
    re-transcribe and align word timings.
    """
    import ffmpeg

    if not footage_paths:
        raise RuntimeError("No stock footage available for fallback build")

    work_dir.mkdir(parents=True, exist_ok=True)
    concat_list = work_dir / "concat.txt"

    # Normalise each clip to 9:16 before concat (avoids resolution mismatch).
    normalised: List[Path] = []
    for i, p in enumerate(footage_paths):
        out = work_dir / f"norm_{i}.mp4"
        (
            ffmpeg.input(str(p))
            .video.filter("scale", -2, target_height, force_original_aspect_ratio="increase")
            .filter("crop", target_width, target_height)
            .output(str(out), vcodec="libx264", r=fps, pix_fmt="yuv420p", an=None)
            .overwrite_output()
            .run(quiet=True)
        )
        normalised.append(out)

    concat_list.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in normalised), encoding="utf-8"
    )
    concat_out = work_dir / "concat.mp4"
    (
        ffmpeg.input(str(concat_list), format="concat", safe=0)
        .output(str(concat_out), c="copy")
        .overwrite_output()
        .run(quiet=True)
    )

    # Mux narration onto the silent concat.
    out_path = work_dir / "fallback_segment.mp4"
    v = ffmpeg.input(str(concat_out)).video
    a = ffmpeg.input(str(voiceover_path)).audio
    (
        ffmpeg.output(
            v,
            a,
            str(out_path),
            vcodec="libx264",
            acodec="aac",
            pix_fmt="yuv420p",
            shortest=None,
        )
        .overwrite_output()
        .run(quiet=True)
    )
    log.info("Built fallback segment: %s", out_path)
    return out_path


def prepare_fallback(
    cfg: FallbackCfg,
    pixabay_key: Optional[str],
    keyword: str,
    work_dir: Path,
    used_story_ids: set[str],
) -> dict:
    """Returns dict matching the sourced-path output shape."""
    stories = load_stories(cfg.stories_file)
    story = pick_story(stories, used_story_ids)
    log.info("Fallback story selected: %s (%s)", story.id, story.country)

    # 1) Narration
    voice_path = work_dir / f"voice_{story.id}.mp3"
    if cfg.use_ai_voice:
        synthesize_voiceover(story.story + "\n\n" + story.moral, cfg.ai_voice, voice_path)
    else:
        raise RuntimeError("use_ai_voice=False but no recorded narration provided")

    # 2) Footage
    local = fetch_local_stock(Path(cfg.stock_footage_dir), count=4)
    if not local:
        local = fetch_stock_footage(keyword, pixabay_key, work_dir / "stock", count=4)
    if not local:
        raise RuntimeError("No stock footage available — set PIXABAY_API_KEY or seed data/stock_footage")

    # 3) Build the segment (audio + visuals)
    segment = build_fallback_video(
        voiceover_path=voice_path,
        footage_paths=local,
        work_dir=work_dir / story.id,
    )

    return {
        "story": story,
        "segment_path": segment,
        "source_url": "https://en.wikipedia.org/wiki/Public_domain",
        "creator_name": f"Public domain — {story.country}",
        "country": story.country,
        "language": "en",
        "is_fallback": True,
    }

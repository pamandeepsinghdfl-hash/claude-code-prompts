"""Top-level orchestrator for the pixel-art Shorts factory.

Replaces the podcast-sourcing pipeline. Six Shorts per day, each with:
  1. LLM-generated cozy scene prompt + lowercase caption
  2. AI pixel-art still (Pollinations.ai -> fallback chain)
  3. ffmpeg-animated 5-second loop -> 15-second final
  4. CC0 lofi music bed (looped to length)
  5. Soft caption + brand watermark + fade
  6. Upload to YouTube with publishAt schedule

Reuses from the previous pipeline:
  - src.config.load_config / load_secrets
  - src.analysis.llm_client.LLMClient (Groq/Claude/OpenAI failover)
  - src.upload.youtube_uploader.YouTubeUploader (OAuth + scheduling)
  - src.utils.db.Database (dedupe history)
  - src.utils.logger.setup_logger / RunReport
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from ..analysis.llm_client import LLMClient
from ..config import Config, Secrets, load_config, load_secrets
from ..upload.youtube_uploader import YouTubeUploader
from ..utils.db import Database
from ..utils.logger import RunReport, setup_logger
from .animator import animate
from .image_generator import ImageGenerator
from .music_picker import loop_to_length, pick_track, synthesize_silence_with_tone
from .renderer import render_short
from .story_writer import write_story

log = logging.getLogger("pixel.factory")


# ─── Defaults (cheap tier) ───────────────────────────────────────────────
DURATION_S = 15.0
FPS = 24


def _slot_publish_datetime(slot_hhmm: str, now_utc: datetime, slot_index: int) -> datetime:
    h, m = (int(x) for x in slot_hhmm.split(":"))
    target = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now_utc:
        target += timedelta(days=1)
    return target


def produce_one_short(
    *,
    slot_index: int,
    publish_at: datetime,
    cfg: Config,
    secrets: Secrets,
    llm: LLMClient,
    image_gen: ImageGenerator,
    uploader: Optional[YouTubeUploader],
    db: Database,
    work_root: Path,
    report: RunReport,
    recent_moods: List[str],
    channel_handle: str,
) -> Optional[dict]:
    log.info("→ Slot %d / publish_at=%s", slot_index + 1, publish_at)
    work = work_root / f"slot_{slot_index:02d}_{publish_at.strftime('%H%M')}"
    work.mkdir(parents=True, exist_ok=True)

    # 1) Story
    story = write_story(llm, recent_moods=recent_moods)
    log.info("    story: caption=%r mood=%s", story.caption, story.mood)

    # 2) Image
    still = image_gen.generate(story.scene_prompt, save_to=work / "scene.png")

    # 3) Animate
    silent = animate(
        still, work / "silent.mp4",
        mood=story.mood, duration_s=DURATION_S, fps=FPS,
        zoom_amount=0.04,
        pan_px=20 if slot_index % 2 == 0 else -20,  # alternate pan direction
        seed=slot_index,
    )

    # 4) Music
    music_dir = Path(cfg.video.music_dir)
    track = pick_track(music_dir, mood=story.mood)
    music_out = work / "music.aac"
    if track:
        loop_to_length(track, music_out, DURATION_S)
    else:
        synthesize_silence_with_tone(music_out, DURATION_S)

    # 5) Final render
    final = work_root.parent / "shorts" / f"pixel_{publish_at.strftime('%H%M')}.mp4"
    render_short(
        silent_video=silent,
        music=music_out,
        caption=story.caption,
        watermark=channel_handle,
        output=final,
        duration_s=DURATION_S,
    )

    # 6) Description + upload
    description = (
        f"{story.caption}\n\n"
        f"🌙 {channel_handle} — cozy pixel-art loops, daily.\n"
        f"🕒 New Shorts every 4 hours\n\n"
        + " ".join(story.hashtags + ["#PixelHours"])
    )

    record_id = db.record(
        source_video_id=f"pixel_{slot_index}_{publish_at.strftime('%Y%m%d_%H%M')}",
        source_url="ai-generated",
        title=story.title,
        niche=story.mood,
        region="global",
        language="en",
        copyright_score=100.0,
        viral_score=None,
        scheduled_for=publish_at,
    )

    youtube_id = None
    if uploader and not secrets.dry_run:
        youtube_id = uploader.upload(
            video_path=final,
            title=story.title,
            description=description,
            tags=[t.lstrip("#") for t in story.hashtags] + ["pixelhours", "cozy", "lofi", "pixelart"],
            publish_at=publish_at,
            thumbnail_path=None,
        )
        db.update_youtube_id(record_id, youtube_id)
    else:
        log.info("DRY_RUN: skipping upload of %s", final)

    report.add_short({
        "slot": slot_index,
        "publish_at": publish_at.isoformat(),
        "title": story.title,
        "caption": story.caption,
        "mood": story.mood,
        "scene_prompt": story.scene_prompt,
        "video_path": str(final),
        "youtube_video_id": youtube_id,
    })

    # Tidy
    shutil.rmtree(work, ignore_errors=True)
    return report.shorts[-1]


def run_daily(config_path: Optional[str] = None) -> Path:
    cfg = load_config(config_path)
    secrets = load_secrets()
    setup_logger(secrets.log_level, cfg.logging.dir)
    log.info("=== Pixel-art factory — daily run start ===")

    report = RunReport(cfg.logging.dir)
    db = Database(cfg.persistence.db_path)
    llm = LLMClient(secrets)
    image_gen = ImageGenerator(width=cfg.video.width, height=cfg.video.height)

    uploader: Optional[YouTubeUploader] = None
    if not secrets.dry_run:
        try:
            uploader = YouTubeUploader(
                secrets.yt_oauth_client_secret, secrets.yt_oauth_token_path
            )
        except Exception as e:  # noqa: BLE001
            log.error("OAuth init failed; switching to DRY_RUN: %s", e)
            uploader = None

    channel_handle = f"@{secrets.yt_channel_name.lower().replace(' ', '')}"

    now_utc = datetime.now(timezone.utc)
    recent_moods: List[str] = []
    produced = 0

    for slot_idx, slot_hhmm in enumerate(cfg.schedule.publish_slots_utc):
        publish_at = _slot_publish_datetime(slot_hhmm, now_utc, slot_idx)
        try:
            r = produce_one_short(
                slot_index=slot_idx,
                publish_at=publish_at,
                cfg=cfg,
                secrets=secrets,
                llm=llm,
                image_gen=image_gen,
                uploader=uploader,
                db=db,
                work_root=Path("output/workdir"),
                report=report,
                recent_moods=recent_moods[-3:],
                channel_handle=channel_handle,
            )
            if r:
                recent_moods.append(r["mood"])
                produced += 1
        except Exception as e:  # noqa: BLE001
            log.exception("Slot %d failed: %s", slot_idx, e)
            report.add_error(f"slot_{slot_idx}: {e}")

    out = report.write()
    log.info("=== Pixel-art daily run complete: %d Shorts. Report: %s ===", produced, out)
    return out

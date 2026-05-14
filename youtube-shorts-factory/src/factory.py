"""Main orchestrator — turns one daily run into N published, scheduled Shorts.

High-level flow per run:
  1. Discover global candidates (YouTube Data API, last 7 days, many regions).
  2. Score them for viral potential + copyright safety.
  3. For each of N publish slots (rotating through configured niches):
       a. Pick the best UNUSED candidate that passes safety + dedupe.
       b. Download audio, transcribe with multilingual Whisper.
       c. LLM picks the best 18–60s viral moment + writes the English hook.
       d. Translate transcript to natural English (always).
       e. Re-download just the clipped segment.
       f. Render ASS captions (TikTok-style, karaoke).
       g. Render the final 9:16 video with burnt-in captions + music.
       h. Generate thumbnail.
       i. Generate title + summary + hashtags via LLM.
       j. Upload to YouTube with `publishAt = today's UTC slot`.
  4. If no candidate is safe enough, fall back to a public-domain story
     with AI voice + stock footage.
  5. Write a JSON run report to logs/YYYY-MM-DD/report.json.
"""
from __future__ import annotations

import logging
import shutil
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .analysis.llm_client import LLMClient
from .analysis.viral_detector import (
    detect_viral_moments,
    generate_title_and_summary,
)
from .config import Config, Secrets, load_config, load_secrets
from .download.downloader import Downloader, split_audio_for_transcription
from .fallback.public_domain import prepare_fallback
from .sourcing.copyright_check import filter_by_safety, score_copyright_safety
from .sourcing.viral_scorer import attach_hook_score, score_candidates
from .sourcing.youtube_api import VideoCandidate, YouTubeSourcing
from .transcription.translator import Translator
from .transcription.whisper_transcriber import WhisperTranscriber
from .upload.youtube_uploader import YouTubeUploader
from .utils.db import Database
from .utils.logger import RunReport, setup_logger
from .video.captions import write_ass_captions
from .video.editor import pick_background_music, render_short
from .video.thumbnail import make_thumbnail

log = logging.getLogger("shorts_factory.factory")


# ─── Niche → search keywords ─────────────────────────────────────────────
NICHE_KEYWORDS: Dict[str, List[str]] = {
    "motivation_life_lessons": [
        "powerful motivational speech",
        "life lesson interview",
        "best advice ever given",
    ],
    "mind_blowing_facts": [
        "mind blowing facts",
        "did you know facts",
        "incredible science facts",
    ],
    "viral_interviews_podcasts": [
        "viral podcast moment",
        "best interview moments",
        "unforgettable interview",
    ],
    "inspiring_stories": [
        "inspiring true story",
        "incredible human story",
        "real life inspiring",
    ],
    "history_and_myths": [
        "ancient history mystery",
        "world mythology explained",
        "untold history story",
    ],
    "science_breakthroughs": [
        "science breakthrough",
        "new discovery explained",
        "scientists shocked",
    ],
    "global_news_explainers": [
        "world news explained",
        "what happened this week",
        "global story explained",
    ],
}


def _niche_for_slot(niches: List[str], slot_index: int) -> str:
    return niches[slot_index % len(niches)]


def _slot_publish_datetime(slot_hhmm: str, now_utc: datetime, slot_index: int) -> datetime:
    """Resolve a "HH:MM" slot to a concrete UTC datetime for *today's* run.

    If the slot has already passed today, push it to tomorrow. The last
    slot (`00:00`) is always interpreted as next-day midnight.
    """
    h, m = (int(x) for x in slot_hhmm.split(":"))
    target = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)
    if slot_index == 0 and target <= now_utc:
        target = target + timedelta(days=1)
    elif target <= now_utc:
        target = target + timedelta(days=1)
    return target


# ─── Per-Short pipeline ───────────────────────────────────────────────────
def produce_one_short(
    *,
    rank_entry: dict,
    niche: str,
    publish_at: datetime,
    cfg: Config,
    secrets: Secrets,
    llm: LLMClient,
    translator: Translator,
    whisper: WhisperTranscriber,
    downloader: Downloader,
    uploader: Optional[YouTubeUploader],
    db: Database,
    work_root: Path,
    report: RunReport,
) -> Optional[dict]:
    candidate: VideoCandidate = rank_entry["candidate"]
    log.info(
        "→ Building Short for %s (%s, viral=%.1f)",
        candidate.video_id, niche, rank_entry["viral_score"],
    )

    work_dir = work_root / f"{publish_at.strftime('%H%M')}_{candidate.video_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1) Audio-only download for transcription (cheaper than full video).
    audio_path = downloader.download_audio(candidate.url, candidate.video_id)

    # 2) Multilingual transcription.
    transcript = whisper.transcribe(audio_path)

    # 3) Pick best viral window.
    moments = detect_viral_moments(llm, transcript.to_clip_input(), cfg.clip)
    if not moments:
        log.warning("No viable viral moments in %s", candidate.video_id)
        return None
    best = moments[0]
    attach_hook_score(rank_entry, best.viral_score, cfg.viral)
    if rank_entry["viral_score"] < cfg.viral.min_score:
        log.info("Skipping — final viral score %.1f below threshold", rank_entry["viral_score"])
        return None

    # 4) Slice transcript to the chosen window + translate to English.
    sliced = whisper.slice_for_window(transcript, best.start_s, best.end_s)
    english = translator.to_english(sliced)

    # 5) Download just the segment (saves bandwidth on multi-hour podcasts).
    segment_path = downloader.download_segment(
        candidate.url, candidate.video_id, best.start_s, best.end_s
    )

    # 6) Captions (ASS, karaoke style, English ALWAYS).
    ass_path = work_dir / "captions.ass"
    write_ass_captions(
        english,
        cfg.captions,
        cfg.video.width,
        cfg.video.height,
        ass_path,
        clip_offset_s=best.start_s,
    )

    # 7) Render final Short.
    final_path = work_root.parent / "shorts" / f"{candidate.video_id}_{publish_at.strftime('%H%M')}.mp4"
    music = pick_background_music(Path(cfg.video.music_dir))
    render_short(
        source_segment=segment_path,
        ass_captions=ass_path,
        output_path=final_path,
        cfg=cfg.video,
        background_music=music,
        fonts_dir="data/fonts",
    )

    # 8) Title, summary, hashtags from LLM.
    td = generate_title_and_summary(
        llm,
        english_transcript=english.full_text,
        creator_name=candidate.channel_title,
        country=candidate.region,
        language=transcript.detected_language,
        niche=niche,
        max_title_chars=cfg.metadata.title_max_chars,
    )
    title = td["title"]
    summary = td["summary"]
    extra_tags = td.get("hashtags", [])

    # 9) Thumbnail.
    thumb_path = work_root.parent / "thumbnails" / f"{candidate.video_id}_{publish_at.strftime('%H%M')}.jpg"
    try:
        make_thumbnail(
            short_video_path=final_path,
            title_text=title,
            cfg=cfg.thumbnail,
            fonts_dir="data/fonts",
            output_path=thumb_path,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("Thumbnail generation failed: %s", e)
        thumb_path = None

    # 10) Description.
    description = cfg.metadata.description_template.format(
        summary=summary,
        source_url=candidate.url,
        clip_start=f"{int(best.start_s // 60):02d}:{int(best.start_s % 60):02d}",
        clip_end=f"{int(best.end_s // 60):02d}:{int(best.end_s % 60):02d}",
        creator_name=candidate.channel_title,
        country=candidate.region,
        language=transcript.detected_language,
        hashtags=" ".join(set(cfg.metadata.default_hashtags + extra_tags)),
    )

    # 11) Persist + upload.
    record_id = db.record(
        source_video_id=candidate.video_id,
        source_url=candidate.url,
        title=title,
        niche=niche,
        region=candidate.region,
        language=transcript.detected_language,
        copyright_score=rank_entry.get("copyright_score"),
        viral_score=rank_entry["viral_score"],
        scheduled_for=publish_at,
    )

    youtube_video_id = None
    if uploader and not secrets.dry_run:
        youtube_video_id = uploader.upload(
            video_path=final_path,
            title=title,
            description=description,
            tags=[t.lstrip("#") for t in (cfg.metadata.default_hashtags + extra_tags)],
            publish_at=publish_at,
            thumbnail_path=thumb_path,
        )
        db.update_youtube_id(record_id, youtube_video_id)
    else:
        log.info("DRY_RUN: not uploading %s", final_path)

    report.add_short(
        {
            "niche": niche,
            "publish_at": publish_at.isoformat(),
            "source_url": candidate.url,
            "source_creator": candidate.channel_title,
            "source_country_region": candidate.region,
            "source_language": transcript.detected_language,
            "clip_start_s": best.start_s,
            "clip_end_s": best.end_s,
            "title": title,
            "viral_score": rank_entry["viral_score"],
            "copyright_score": rank_entry.get("copyright_score"),
            "video_path": str(final_path),
            "thumbnail_path": str(thumb_path) if thumb_path else None,
            "youtube_video_id": youtube_video_id,
            "is_fallback": False,
        }
    )

    # Tidy intermediate files; keep the final Short + thumbnail.
    try:
        shutil.rmtree(work_dir, ignore_errors=True)
        audio_path.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass

    return report.shorts[-1]


# ─── Fallback path ────────────────────────────────────────────────────────
def produce_fallback_short(
    *,
    niche: str,
    publish_at: datetime,
    cfg: Config,
    secrets: Secrets,
    llm: LLMClient,
    whisper: WhisperTranscriber,
    translator: Translator,
    uploader: Optional[YouTubeUploader],
    db: Database,
    work_root: Path,
    used_story_ids: set[str],
    report: RunReport,
) -> Optional[dict]:
    log.info("Falling back to public-domain pipeline for slot %s", publish_at)
    keyword = niche.replace("_", " ")
    pkg = prepare_fallback(
        cfg.fallback,
        secrets.pixabay_api_key,
        keyword,
        work_root / "fallback",
        used_story_ids,
    )
    used_story_ids.add(pkg["story"].id)

    # Re-transcribe the AI voice so captions are perfectly aligned.
    audio_wav = work_root / "fallback" / f"voice_{pkg['story'].id}.wav"
    split_audio_for_transcription(pkg["segment_path"], audio_wav)
    transcript = whisper.transcribe(audio_wav, language="en")
    english = translator.to_english(transcript)

    ass_path = work_root / "fallback" / pkg["story"].id / "captions.ass"
    write_ass_captions(
        english, cfg.captions, cfg.video.width, cfg.video.height, ass_path
    )

    final_path = work_root.parent / "shorts" / f"fb_{pkg['story'].id}_{publish_at.strftime('%H%M')}.mp4"
    music = pick_background_music(Path(cfg.video.music_dir))
    render_short(
        source_segment=pkg["segment_path"],
        ass_captions=ass_path,
        output_path=final_path,
        cfg=cfg.video,
        background_music=music,
        fonts_dir="data/fonts",
    )

    title = f"🌍 {pkg['story'].title} ({pkg['story'].country})"
    summary = pkg["story"].moral

    thumb_path = work_root.parent / "thumbnails" / f"fb_{pkg['story'].id}_{publish_at.strftime('%H%M')}.jpg"
    try:
        make_thumbnail(
            short_video_path=final_path,
            title_text=title,
            cfg=cfg.thumbnail,
            fonts_dir="data/fonts",
            output_path=thumb_path,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("Thumbnail generation failed: %s", e)
        thumb_path = None

    description = cfg.metadata.description_template.format(
        summary=f"{pkg['story'].story}\n\n💡 {summary}",
        source_url=pkg["source_url"],
        clip_start="00:00",
        clip_end="00:60",
        creator_name=pkg["creator_name"],
        country=pkg["country"],
        language="en",
        hashtags=" ".join(set(cfg.metadata.default_hashtags + ["#Folklore", "#GlobalStories"])),
    )

    record_id = db.record(
        source_video_id=f"fallback_{pkg['story'].id}",
        source_url=pkg["source_url"],
        title=title,
        niche=niche,
        region=pkg["country"],
        language="en",
        copyright_score=100.0,
        viral_score=None,
        scheduled_for=publish_at,
    )

    youtube_video_id = None
    if uploader and not secrets.dry_run:
        youtube_video_id = uploader.upload(
            video_path=final_path,
            title=title,
            description=description,
            tags=[t.lstrip("#") for t in cfg.metadata.default_hashtags + ["Folklore", "GlobalStories"]],
            publish_at=publish_at,
            thumbnail_path=thumb_path,
        )
        db.update_youtube_id(record_id, youtube_video_id)

    report.add_short(
        {
            "niche": niche,
            "publish_at": publish_at.isoformat(),
            "source_url": pkg["source_url"],
            "source_creator": pkg["creator_name"],
            "source_country_region": pkg["country"],
            "source_language": "en",
            "clip_start_s": 0,
            "clip_end_s": None,
            "title": title,
            "viral_score": None,
            "copyright_score": 100,
            "video_path": str(final_path),
            "thumbnail_path": str(thumb_path) if thumb_path else None,
            "youtube_video_id": youtube_video_id,
            "is_fallback": True,
        }
    )
    return report.shorts[-1]


# ─── Top-level entrypoint ─────────────────────────────────────────────────
def run_daily(config_path: Optional[str] = None) -> Path:
    cfg = load_config(config_path)
    secrets = load_secrets()
    setup_logger(secrets.log_level, cfg.logging.dir)
    log.info("=== Global YouTube Shorts Factory — daily run start ===")

    report = RunReport(cfg.logging.dir)

    db = Database(cfg.persistence.db_path)
    llm = LLMClient(secrets)
    translator = Translator(llm)
    whisper = WhisperTranscriber(
        secrets.whisper_model, secrets.whisper_device, secrets.whisper_compute_type
    )
    downloader = Downloader("output/workdir", proxy=secrets.yt_dlp_proxy)
    uploader: Optional[YouTubeUploader] = None
    if not secrets.dry_run:
        try:
            uploader = YouTubeUploader(
                secrets.yt_oauth_client_secret, secrets.yt_oauth_token_path
            )
        except Exception as e:  # noqa: BLE001
            log.error("OAuth init failed; switching to DRY_RUN: %s", e)
            uploader = None

    # 1) Discover.
    sourcing = YouTubeSourcing(secrets.youtube_api_key or "", cfg.sourcing)
    keywords: List[str] = []
    for niche in cfg.niches:
        keywords.extend(NICHE_KEYWORDS.get(niche, [niche.replace("_", " ")]))
    discovered = sourcing.discover(keywords)

    # 2) Filter by copyright safety.
    safe = filter_by_safety(discovered, cfg.copyright.min_safety_score)
    for c, s in safe:
        # mutate to attach the score
        setattr(c, "_copyright_score", s)

    # 3) Score for virality.
    ranked = score_candidates([c for c, _ in safe], cfg.viral)
    for r in ranked:
        r["copyright_score"] = getattr(r["candidate"], "_copyright_score", None)

    # 4) Iterate slots.
    now_utc = datetime.now(timezone.utc)
    used_video_ids: set[str] = set()
    used_story_ids: set[str] = set()
    produced = 0

    for slot_idx, slot_hhmm in enumerate(cfg.schedule.publish_slots_utc):
        niche = _niche_for_slot(cfg.niches, slot_idx)
        publish_at = _slot_publish_datetime(slot_hhmm, now_utc, slot_idx)
        log.info("─── Slot %d/%d %s UTC | niche=%s ───", slot_idx + 1, cfg.schedule.shorts_per_day, slot_hhmm, niche)

        picked = False
        for entry in ranked:
            cand: VideoCandidate = entry["candidate"]
            if cand.video_id in used_video_ids:
                continue
            if db.already_published(cand.video_id, cfg.persistence.dedupe_window_days):
                continue
            try:
                result = produce_one_short(
                    rank_entry=entry,
                    niche=niche,
                    publish_at=publish_at,
                    cfg=cfg,
                    secrets=secrets,
                    llm=llm,
                    translator=translator,
                    whisper=whisper,
                    downloader=downloader,
                    uploader=uploader,
                    db=db,
                    work_root=Path("output/workdir"),
                    report=report,
                )
            except Exception as e:  # noqa: BLE001
                log.error("Short build failed: %s\n%s", e, traceback.format_exc())
                report.add_error(f"{cand.video_id}: {e}")
                continue
            if result is not None:
                used_video_ids.add(cand.video_id)
                picked = True
                produced += 1
                break

        if not picked:
            # Fallback to public-domain pipeline for this slot.
            try:
                produce_fallback_short(
                    niche=niche,
                    publish_at=publish_at,
                    cfg=cfg,
                    secrets=secrets,
                    llm=llm,
                    whisper=whisper,
                    translator=translator,
                    uploader=uploader,
                    db=db,
                    work_root=Path("output/workdir"),
                    used_story_ids=used_story_ids,
                    report=report,
                )
                produced += 1
            except Exception as e:  # noqa: BLE001
                log.error("Fallback failed for slot %d: %s", slot_idx, e)
                report.add_error(f"slot_{slot_idx}_fallback: {e}")

    out = report.write()
    log.info("=== Daily run complete: %d Shorts produced. Report: %s ===", produced, out)
    return out

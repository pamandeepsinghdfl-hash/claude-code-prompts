"""yt-dlp wrapper.

  • Downloads the smallest reasonable mp4 + best audio.
  • Supports proxies for region-locked content (set YT_DLP_PROXY).
  • Returns a dict with `video_path`, `audio_path`, and metadata.

We always download a *trimmed* version when start/end seconds are known
to avoid pulling multi-hour podcasts in full. This is done with yt-dlp's
`download_ranges` option, which uses an ffmpeg post-processor.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

import yt_dlp

log = logging.getLogger("shorts_factory.download")


class Downloader:
    def __init__(self, work_dir: str | Path, proxy: Optional[str] = None):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.proxy = proxy

    # ─── Full video (used when we still need to transcribe) ───────────────
    def download_full(self, url: str, video_id: str) -> Path:
        outtmpl = str(self.work_dir / f"{video_id}.%(ext)s")
        opts = self._base_opts(outtmpl)
        opts.update(
            {
                "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "merge_output_format": "mp4",
            }
        )
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
            log.info("Downloaded %s → %s", url, path)
            return path

    # ─── Trimmed download ────────────────────────────────────────────────
    def download_segment(
        self, url: str, video_id: str, start_s: float, end_s: float
    ) -> Path:
        outtmpl = str(self.work_dir / f"{video_id}_{int(start_s)}_{int(end_s)}.%(ext)s")
        opts = self._base_opts(outtmpl)
        opts.update(
            {
                "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "merge_output_format": "mp4",
                "download_ranges": yt_dlp.utils.download_range_func(
                    None, [(start_s, end_s)]
                ),
                "force_keyframes_at_cuts": True,
            }
        )
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
            log.info("Downloaded segment [%.1f-%.1f]s → %s", start_s, end_s, path)
            return path

    # ─── Audio-only (cheap transcription input) ──────────────────────────
    def download_audio(self, url: str, video_id: str) -> Path:
        outtmpl = str(self.work_dir / f"{video_id}.%(ext)s")
        opts = self._base_opts(outtmpl)
        opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "wav",
                        "preferredquality": "192",
                    }
                ],
            }
        )
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = Path(ydl.prepare_filename(info))
            path = base.with_suffix(".wav")
            log.info("Downloaded audio %s → %s", url, path)
            return path

    # ─── Helpers ─────────────────────────────────────────────────────────
    def _base_opts(self, outtmpl: str) -> dict:
        opts: dict = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 4,
            "ignoreerrors": False,
            "geo_bypass": True,
        }
        if self.proxy:
            opts["proxy"] = self.proxy
        return opts


def split_audio_for_transcription(
    video_path: Path, audio_out: Path
) -> Tuple[Path, float]:
    """Extract a 16k-mono WAV from any video file using ffmpeg.

    Returns (audio_path, duration_seconds).
    """
    import ffmpeg

    audio_out.parent.mkdir(parents=True, exist_ok=True)
    (
        ffmpeg.input(str(video_path))
        .output(str(audio_out), ac=1, ar=16000, format="wav")
        .overwrite_output()
        .run(quiet=True)
    )
    probe = ffmpeg.probe(str(video_path))
    duration = float(probe["format"].get("duration", 0.0))
    return audio_out, duration

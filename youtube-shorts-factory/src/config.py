"""Strongly-typed configuration loader.

Loads `config.yaml` into pydantic models so the rest of the codebase
gets autocomplete + validation instead of dict lookups. Also exposes
the secrets loaded from the `.env` file.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ─── Schema ───────────────────────────────────────────────────────────────
class ScheduleCfg(BaseModel):
    run_at_utc: str
    shorts_per_day: int
    publish_slots_utc: List[str]
    privacy_status: str = "private"

    @field_validator("publish_slots_utc")
    @classmethod
    def slots_match(cls, v, info):
        if "shorts_per_day" in info.data and len(v) != info.data["shorts_per_day"]:
            raise ValueError("publish_slots_utc must match shorts_per_day length")
        return v


class SourcingCfg(BaseModel):
    lookback_days: int = 7
    max_candidates_per_region: int = 25
    region_codes: List[str]
    source_languages: List[str]
    category_ids: List[int]
    min_view_count: int = 50_000
    min_duration_seconds: int = 60
    max_duration_seconds: int = 7200
    exclude_keywords: List[str] = []


class CopyrightCfg(BaseModel):
    min_safety_score: int = 65
    prefer_licenses: List[str] = ["creativeCommon"]
    fallback_below_score: int = 55


class ViralCfg(BaseModel):
    weight_views: float
    weight_engagement_velocity: float
    weight_cross_cultural: float
    weight_hook_strength: float
    min_score: int = 55


class ClipCfg(BaseModel):
    target_duration_seconds: int = 45
    min_duration_seconds: int = 18
    max_duration_seconds: int = 60
    candidates_per_source: int = 3


class CaptionStyleCfg(BaseModel):
    font: str
    font_size: int
    stroke_color: str
    stroke_width: int
    fill_color: str
    highlight_color: str
    position: str
    max_chars_per_line: int
    max_lines: int
    fade_ms: int
    pop_scale: float


class CaptionsCfg(BaseModel):
    language: str = "en"
    translate_if_not_english: bool = True
    style: CaptionStyleCfg
    safe_margin_px: int = 80


class VideoCfg(BaseModel):
    width: int
    height: int
    fps: int
    bitrate: str
    codec: str
    audio_codec: str
    audio_bitrate: str
    ken_burns: bool
    ken_burns_zoom: float
    transition_ms: int
    music_volume: float
    music_dir: str
    watermark_text: str = ""


class ThumbnailCfg(BaseModel):
    width: int
    height: int
    background_blur: int
    title_font: str
    title_font_size: int
    title_max_chars: int
    title_stroke_width: int


class MetadataCfg(BaseModel):
    title_max_chars: int = 90
    title_must_include_emoji: bool = True
    description_template: str
    default_hashtags: List[str]


class FallbackCfg(BaseModel):
    stories_file: str
    use_ai_voice: bool = True
    ai_voice: str = "en-US-AriaNeural"
    stock_footage_dir: str = "data/stock_footage"


class PersistenceCfg(BaseModel):
    db_path: str
    dedupe_window_days: int = 60


class LoggingCfg(BaseModel):
    dir: str = "logs"
    daily_report: bool = True
    json_report: bool = True


class Config(BaseModel):
    schedule: ScheduleCfg
    niches: List[str]
    sourcing: SourcingCfg
    copyright: CopyrightCfg
    viral: ViralCfg
    clip: ClipCfg
    captions: CaptionsCfg
    video: VideoCfg
    thumbnail: ThumbnailCfg
    metadata: MetadataCfg
    fallback: FallbackCfg
    persistence: PersistenceCfg
    logging: LoggingCfg


# ─── Secrets (env) ────────────────────────────────────────────────────────
class Secrets(BaseModel):
    youtube_api_key: Optional[str] = None
    yt_oauth_client_secret: str
    yt_oauth_token_path: str
    yt_channel_name: str = "Global Shorts Factory"

    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-6"
    llm_provider_order: List[str] = Field(default_factory=lambda: ["groq", "openai", "anthropic"])

    deepl_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None

    whisper_model: str = "large-v3"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"

    yt_dlp_proxy: Optional[str] = None
    dry_run: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Secrets":
        order = os.getenv("LLM_PROVIDER_ORDER", "groq,openai,anthropic")
        return cls(
            youtube_api_key=os.getenv("YOUTUBE_API_KEY") or None,
            yt_oauth_client_secret=os.getenv(
                "YOUTUBE_OAUTH_CLIENT_SECRET", "./credentials/client_secret.json"
            ),
            yt_oauth_token_path=os.getenv(
                "YOUTUBE_OAUTH_TOKEN_PATH", "./credentials/token.json"
            ),
            yt_channel_name=os.getenv("YOUTUBE_CHANNEL_NAME", "Global Shorts Factory"),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            llm_provider_order=[p.strip() for p in order.split(",") if p.strip()],
            deepl_api_key=os.getenv("DEEPL_API_KEY") or None,
            pixabay_api_key=os.getenv("PIXABAY_API_KEY") or None,
            whisper_model=os.getenv("WHISPER_MODEL", "large-v3"),
            whisper_device=os.getenv("WHISPER_DEVICE", "auto"),
            whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "auto"),
            yt_dlp_proxy=os.getenv("YT_DLP_PROXY") or None,
            dry_run=os.getenv("DRY_RUN", "0") in {"1", "true", "True"},
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# ─── Loader ───────────────────────────────────────────────────────────────
def load_config(path: Optional[str] = None) -> Config:
    path = path or str(PROJECT_ROOT / "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return Config(**yaml.safe_load(f))


def load_secrets() -> Secrets:
    return Secrets.from_env()

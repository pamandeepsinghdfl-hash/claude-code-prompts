"""LLM-driven viral moment detection.

Given a full transcript (with timestamps), ask the LLM to pick the
N best 15–60s windows that are likely to perform on Shorts.

The returned `ClipCandidate`s include:
  • start / end seconds
  • a 1-line hook (English) that we'll use as the opening caption
  • a viral-strength score (0–100)
  • why it's compelling (used downstream for the description)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List

from ..config import ClipCfg
from .llm_client import LLMClient, parse_json_reply

log = logging.getLogger("shorts_factory.viral")


@dataclass
class ClipCandidate:
    start_s: float
    end_s: float
    hook: str           # short, punchy, English
    reason: str         # why this clip is compelling
    viral_score: float  # 0–100


SYSTEM = """You are a world-class YouTube Shorts producer. You watch trending
clips from podcasts, interviews, news, and motivational videos worldwide and
ruthlessly identify the moments most likely to go viral on vertical short-form
video (TikTok-style). You think in HOOKS, PUNCHLINES, EMOTIONAL PEAKS, and
SURPRISING FACTS. You speak fluent English and translate any non-English line
naturally to crisp, mobile-readable English.""".strip()


def _prompt(transcript: List[dict], cfg: ClipCfg, n: int) -> str:
    """Build the user prompt.

    `transcript` is a list of {"start","end","text"} segments — usually
    output by faster-whisper. We pass them in a compact tabular form to
    save tokens.
    """
    lines = []
    for seg in transcript:
        lines.append(f"[{seg['start']:.2f}-{seg['end']:.2f}] {seg['text'].strip()}")
    transcript_block = "\n".join(lines)

    return f"""
TRANSCRIPT (with timestamps in seconds; original language preserved):
---
{transcript_block}
---

Pick the {n} BEST clip windows from this transcript that will dominate as
vertical Shorts. Hard rules:
  • Each window must be between {cfg.min_duration_seconds} and {cfg.max_duration_seconds} seconds long.
  • Target around {cfg.target_duration_seconds} seconds.
  • The opening line of the window MUST be a hook: a question, a bold claim,
    a startling fact, or an emotional moment.
  • Prefer self-contained moments that make sense to viewers who have no
    context for the full video.
  • Avoid moments whose meaning depends on visuals we don't have.

Respond as STRICT JSON of the shape:
{{
  "clips": [
    {{
      "start": <float seconds>,
      "end": <float seconds>,
      "hook_english": "<one-line English hook for caption overlay>",
      "reason": "<one sentence why this clip will pop>",
      "viral_score": <0-100>
    }}
  ]
}}
Only include the JSON. No extra prose.
""".strip()


def detect_viral_moments(
    llm: LLMClient,
    transcript: List[dict],
    clip_cfg: ClipCfg,
) -> List[ClipCandidate]:
    raw = llm.chat(
        SYSTEM,
        _prompt(transcript, clip_cfg, clip_cfg.candidates_per_source),
        json_mode=True,
        max_tokens=2048,
        temperature=0.7,
    )
    data = parse_json_reply(raw)
    candidates: List[ClipCandidate] = []
    for c in data.get("clips", []):
        try:
            start = float(c["start"])
            end = float(c["end"])
            if end - start < clip_cfg.min_duration_seconds:
                continue
            if end - start > clip_cfg.max_duration_seconds:
                # truncate to max
                end = start + clip_cfg.max_duration_seconds
            candidates.append(
                ClipCandidate(
                    start_s=start,
                    end_s=end,
                    hook=c.get("hook_english", "").strip(),
                    reason=c.get("reason", "").strip(),
                    viral_score=float(c.get("viral_score", 0)),
                )
            )
        except (KeyError, ValueError, TypeError) as e:
            log.warning("Bad clip candidate %s: %s", c, e)
    # Best first
    candidates.sort(key=lambda x: x.viral_score, reverse=True)
    return candidates


# ─── Title / description generator ───────────────────────────────────────
TITLE_DESC_SYSTEM = """You write irresistible, click-worthy YouTube Shorts titles
in English. Your titles are 6-12 words, emoji-rich, never clickbait-deceptive,
and they tease the payoff. You also write tight 2-3 sentence English summaries
of the clip that make people want to watch.""".strip()


def generate_title_and_summary(
    llm: LLMClient,
    *,
    english_transcript: str,
    creator_name: str,
    country: str,
    language: str,
    niche: str,
    max_title_chars: int,
) -> dict:
    user = f"""
Niche: {niche}
Creator: {creator_name} ({country}, original language: {language})

Clip transcript (already translated to English):
\"\"\"
{english_transcript.strip()}
\"\"\"

Return STRICT JSON:
{{
  "title": "<viral English title with 1-2 emojis, <= {max_title_chars} characters>",
  "summary": "<2-3 sentence English description of why viewers should watch>",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}}
""".strip()
    raw = llm.chat(TITLE_DESC_SYSTEM, user, json_mode=True, max_tokens=600, temperature=0.85)
    return parse_json_reply(raw)

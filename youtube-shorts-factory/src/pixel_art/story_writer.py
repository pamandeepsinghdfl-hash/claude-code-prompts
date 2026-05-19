"""LLM-driven cozy scene + caption writer.

Produces one Short's content:
  - scene_prompt: a pixel-art image-gen prompt (cozy, intimate, lofi vibe)
  - caption: 4-7 lowercase words, soft, intimate
  - title: a YouTube Short title (slightly more clickable than the caption)
  - mood: tag for music selection (rainy / warm / morning / dreamy)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

from ..analysis.llm_client import LLMClient, parse_json_reply

log = logging.getLogger("pixel.story")


@dataclass
class PixelStory:
    scene_prompt: str
    caption: str
    title: str
    mood: str          # one of: rainy, warm, morning, dreamy, snowy, cafe
    hashtags: List[str]


SYSTEM = """You are a viral pixel-art Shorts producer in the same lane as
@pixosly, @loomsly, and similar cozy-pixel-loop channels. Your aesthetic:
16-bit/SNES-era pixel art, deeply intimate, lofi nighttime cozy energy.
Couples, single characters, cats, rain, lamps, late-night moments,
small apartments with city windows.

You write short captions that read like a private text message: lowercase,
no punctuation, ALWAYS under 8 words. Examples:
  - "cant sleep without you"
  - "stay a little longer"
  - "morning is hours away"
  - "your favourite song again"
  - "rain doesnt sleep either"

Never use ALL CAPS. Never use emojis in captions (one emoji in hashtags only).
Never use slang like 'fr' or 'lowkey'. The voice is sincere, soft, and slow.

For image-gen prompts: describe ONE pixel-art scene in 25-40 words,
include lighting + atmosphere + setting + characters + style modifiers
(pixel art, 16bit, SNES style, detailed pixelart, lofi atmosphere).
""".strip()


def write_story(llm: LLMClient, recent_moods: List[str] = None) -> PixelStory:
    """Generate one Short's worth of content.

    Pass `recent_moods` to avoid repeating the same mood several days in a row.
    """
    avoid = ""
    if recent_moods:
        avoid = f"\nAvoid these moods (used recently): {', '.join(recent_moods)}"

    user = f"""Generate ONE pixel-art cozy Short. Return STRICT JSON:
{{
  "scene_prompt": "<25-40 words, image-gen prompt for pixel-art still>",
  "caption": "<4-7 lowercase words, intimate, no punctuation, no emoji>",
  "title": "<YouTube Short title, lowercase, 4-8 words, can have one emoji>",
  "mood": "<one of: rainy, warm, morning, dreamy, snowy, cafe>",
  "hashtags": ["#pixelart","#shorts","#lofi","#cozy","#aesthetic"]
}}{avoid}
The scene + caption must feel like the same moment. JSON only, no prose.
""".strip()

    raw = llm.chat(SYSTEM, user, json_mode=True, max_tokens=600, temperature=0.95)
    data = parse_json_reply(raw)
    return PixelStory(
        scene_prompt=data["scene_prompt"].strip(),
        caption=data["caption"].strip().lower(),
        title=data["title"].strip(),
        mood=data.get("mood", "warm").strip().lower(),
        hashtags=data.get("hashtags", []),
    )

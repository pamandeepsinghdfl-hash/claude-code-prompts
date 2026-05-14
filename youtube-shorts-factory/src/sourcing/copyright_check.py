"""Copyright safety scoring (0–100, higher = safer).

We don't claim to be a substitute for ContentID. The score is a
heuristic that biases the pipeline towards public-domain / CC sources
and transformative fair use:

  +35 if YouTube `videoLicense == "creativeCommon"`
  +20 if creator looks like a government / public-broadcaster channel
       (configurable allowlist substrings)
  +15 if the source channel has CC re-uploads anywhere in its title
  +15 if title/desc mention "free to use", "public domain", "CC BY"
  +10 baseline (fair-use transformative short clip)
   -X penalties for known risky publishers (record labels, big studios)

Anything < `min_safety_score` is dropped; below `fallback_below_score`
the factory escalates to the fully-original public-domain pipeline.
"""
from __future__ import annotations

import logging
from typing import List

from .youtube_api import VideoCandidate

log = logging.getLogger("shorts_factory.copyright")


# Channel substrings we treat as inherently safer.
SAFE_CHANNEL_SUBSTRINGS = [
    "nasa", "noaa", "voa", "voice of america", "us army", "us navy",
    "us air force", ".gov", "government of", "european union",
    "united nations", "un news", "wikipedia", "open culture",
    "internet archive", "library of congress", "smithsonian",
    "public domain",
]

# Risky publisher substrings — penalize.
RISKY_CHANNEL_SUBSTRINGS = [
    "vevo", "warner", "sony music", "universal music", "atlantic records",
    "disney", "marvel", "pixar", "netflix", "hbo", "espn", "fox sports",
    "nbc sports", "ufc", "wwe", "nba", "fifa", "premier league",
]

CC_TEXT_HINTS = [
    "creative commons", "cc by", "cc-by", "public domain", "free to use",
    "no copyright", "royalty free", "open source",
]


def score_copyright_safety(c: VideoCandidate) -> int:
    score = 10  # baseline transformative fair-use credit
    license_norm = (c.license or "").lower()
    if license_norm == "creativecommon":
        score += 35

    ch = (c.channel_title or "").lower()
    if any(s in ch for s in SAFE_CHANNEL_SUBSTRINGS):
        score += 25
    if any(s in ch for s in RISKY_CHANNEL_SUBSTRINGS):
        score -= 45

    blob = f"{c.title}\n{c.description}".lower()
    if any(h in blob for h in CC_TEXT_HINTS):
        score += 15

    # Cap to [0, 100]
    return max(0, min(100, score))


def filter_by_safety(
    candidates: List[VideoCandidate], min_score: int
) -> List[tuple[VideoCandidate, int]]:
    rated = [(c, score_copyright_safety(c)) for c in candidates]
    safe = [r for r in rated if r[1] >= min_score]
    log.info(
        "Copyright filter: %d/%d candidates kept (min_score=%d)",
        len(safe), len(rated), min_score,
    )
    return safe

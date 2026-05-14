"""Viral scoring heuristic.

Score = w_views * z(views)
      + w_engagement * z(engagement_velocity)
      + w_cross_cultural * cross_cultural_factor
      + w_hook * hook_strength_from_llm   (added later in the pipeline)

The first three are computed here from YouTube metadata alone.
Hook strength is filled in by `viral_detector` once we have the
transcript and clip candidates.
"""
from __future__ import annotations

import math
from typing import List

from ..config import ViralCfg
from .youtube_api import VideoCandidate


def _zscore_norm(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 50.0
    z = (value - mean) / std
    # squash to 0–100 via logistic
    return 100.0 / (1.0 + math.exp(-z))


def score_candidates(candidates: List[VideoCandidate], cfg: ViralCfg) -> List[dict]:
    if not candidates:
        return []

    views = [c.view_count for c in candidates]
    engagements = [
        (c.like_count + c.comment_count) / c.age_hours for c in candidates
    ]
    v_mean, v_std = _stats(views)
    e_mean, e_std = _stats(engagements)

    out = []
    for c in candidates:
        view_score = _zscore_norm(c.view_count, v_mean, v_std)
        eng_score = _zscore_norm(
            (c.like_count + c.comment_count) / c.age_hours, e_mean, e_std
        )
        cross = min(100.0, len(set(c.appears_in_regions)) * 50.0)  # 1 region=50, 2=100

        base = (
            cfg.weight_views * view_score
            + cfg.weight_engagement_velocity * eng_score
            + cfg.weight_cross_cultural * cross
        )
        # Hook component is unknown at this stage; assume neutral 50.
        base += cfg.weight_hook_strength * 50.0
        out.append(
            {
                "candidate": c,
                "viral_score": round(base, 2),
                "components": {
                    "view": round(view_score, 2),
                    "engagement": round(eng_score, 2),
                    "cross_cultural": round(cross, 2),
                },
            }
        )
    out.sort(key=lambda r: r["viral_score"], reverse=True)
    return out


def _stats(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / n
    return mean, math.sqrt(var)


def attach_hook_score(record: dict, hook_score_0_100: float, cfg: ViralCfg) -> dict:
    """Replace the assumed neutral hook contribution with the real value."""
    # subtract previous neutral 50 contribution, add the real one
    record["viral_score"] = round(
        record["viral_score"] - cfg.weight_hook_strength * 50.0
        + cfg.weight_hook_strength * hook_score_0_100,
        2,
    )
    record.setdefault("components", {})["hook"] = round(hook_score_0_100, 2)
    return record

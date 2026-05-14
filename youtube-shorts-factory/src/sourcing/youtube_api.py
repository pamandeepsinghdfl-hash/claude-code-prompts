"""YouTube Data API v3 client for global sourcing.

Goals:
  • Pull trending videos from the last `lookback_days` days across many
    `regionCode`s for true global coverage (IN, US, BR, ID, MX, JP, KR,
    SA, etc.).
  • Combine trending + search (for niche keywords) + Creative-Commons
    license filter where possible.
  • Respect quota: each call has a cost; we keep things tight.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import SourcingCfg

log = logging.getLogger("shorts_factory.sourcing")


@dataclass
class VideoCandidate:
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    description: str
    published_at: datetime
    region: str               # the region code we discovered it under
    language: Optional[str]   # ISO 2-letter (from defaultAudioLanguage/defaultLanguage)
    license: str              # "youtube" | "creativeCommon"
    duration_seconds: int
    view_count: int
    like_count: int
    comment_count: int
    category_id: Optional[str]
    appears_in_regions: List[str] = field(default_factory=list)  # for cross-cultural score

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def age_hours(self) -> float:
        delta = datetime.now(timezone.utc) - self.published_at
        return max(delta.total_seconds() / 3600.0, 1.0)


# ─── ISO 8601 duration → seconds ─────────────────────────────────────────
_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def _iso_duration_to_seconds(iso: str) -> int:
    m = _DURATION_RE.fullmatch(iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


class YouTubeSourcing:
    def __init__(self, api_key: str, cfg: SourcingCfg):
        if not api_key:
            raise RuntimeError("YOUTUBE_API_KEY is required for sourcing")
        self.cfg = cfg
        self.yt = build("youtube", "v3", developerKey=api_key, cache_discovery=False)

    # ─── Public ──────────────────────────────────────────────────────────
    def discover(self, niche_keywords: Iterable[str]) -> List[VideoCandidate]:
        """Pull a deduped, filtered candidate pool across all regions + niche search."""
        pool: Dict[str, VideoCandidate] = {}

        # 1) Trending by region (chart=mostPopular)
        for region in self.cfg.region_codes:
            try:
                for cat in self.cfg.category_ids:
                    for cand in self._fetch_trending(region, cat):
                        self._merge(pool, cand)
            except HttpError as e:
                log.warning("Trending fetch failed for %s: %s", region, e)

        # 2) Keyword search per niche (CC-licensed first for safety)
        for keyword in niche_keywords:
            try:
                for cand in self._search(keyword, license_cc=True):
                    self._merge(pool, cand)
            except HttpError as e:
                log.warning("CC search failed for '%s': %s", keyword, e)

        # 3) Filter pool
        results = [c for c in pool.values() if self._passes_filters(c)]
        log.info("Discovered %d raw candidates → %d after filtering", len(pool), len(results))
        return results

    # ─── Internals ───────────────────────────────────────────────────────
    def _merge(self, pool: Dict[str, VideoCandidate], cand: VideoCandidate) -> None:
        existing = pool.get(cand.video_id)
        if existing:
            if cand.region not in existing.appears_in_regions:
                existing.appears_in_regions.append(cand.region)
        else:
            cand.appears_in_regions = [cand.region]
            pool[cand.video_id] = cand

    def _passes_filters(self, c: VideoCandidate) -> bool:
        if c.view_count < self.cfg.min_view_count:
            return False
        if not (self.cfg.min_duration_seconds <= c.duration_seconds <= self.cfg.max_duration_seconds):
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.cfg.lookback_days)
        if c.published_at < cutoff:
            return False
        title_l = c.title.lower()
        if any(bad.lower() in title_l for bad in self.cfg.exclude_keywords):
            return False
        if c.language and c.language not in self.cfg.source_languages:
            # don't hard-reject; lots of videos have no language tag set
            return True
        return True

    def _fetch_trending(self, region: str, category_id: int) -> List[VideoCandidate]:
        req = self.yt.videos().list(
            part="snippet,contentDetails,statistics,status",
            chart="mostPopular",
            regionCode=region,
            videoCategoryId=str(category_id),
            maxResults=min(self.cfg.max_candidates_per_region, 50),
        )
        resp = req.execute() or {}
        return [self._to_candidate(item, region) for item in resp.get("items", [])]

    def _search(self, keyword: str, *, license_cc: bool) -> List[VideoCandidate]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.cfg.lookback_days)
        params: dict = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": cutoff.isoformat().replace("+00:00", "Z"),
            "maxResults": 25,
            "videoEmbeddable": "true",
            "safeSearch": "moderate",
        }
        if license_cc:
            params["videoLicense"] = "creativeCommon"
        resp = self.yt.search().list(**params).execute() or {}
        ids = [it["id"]["videoId"] for it in resp.get("items", []) if "videoId" in it.get("id", {})]
        if not ids:
            return []
        details = self.yt.videos().list(
            part="snippet,contentDetails,statistics,status",
            id=",".join(ids),
            maxResults=50,
        ).execute() or {}
        # We don't know which region this came from; tag as "GLOBAL".
        return [self._to_candidate(item, "GLOBAL") for item in details.get("items", [])]

    def _to_candidate(self, item: dict, region: str) -> VideoCandidate:
        sn = item.get("snippet", {})
        st = item.get("statistics", {})
        cd = item.get("contentDetails", {})
        status = item.get("status", {})
        published_at = datetime.fromisoformat(
            sn.get("publishedAt", "1970-01-01T00:00:00Z").replace("Z", "+00:00")
        )
        return VideoCandidate(
            video_id=item["id"],
            title=sn.get("title", ""),
            channel_id=sn.get("channelId", ""),
            channel_title=sn.get("channelTitle", ""),
            description=sn.get("description", ""),
            published_at=published_at,
            region=region,
            language=sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"),
            license=status.get("license", "youtube"),
            duration_seconds=_iso_duration_to_seconds(cd.get("duration", "")),
            view_count=int(st.get("viewCount", 0)),
            like_count=int(st.get("likeCount", 0)),
            comment_count=int(st.get("commentCount", 0)),
            category_id=sn.get("categoryId"),
        )

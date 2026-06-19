"""Build Indeed search URLs and collect matching job postings.

Indeed's markup changes often. Selectors here use several fallbacks and are
isolated in this module so you only have one place to fix when they break.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Iterator

from playwright.sync_api import Page

from .browser import human_delay


@dataclass
class JobPosting:
    job_id: str
    title: str
    company: str
    location: str
    url: str


def build_search_url(search: dict[str, Any], query: str, start: int = 0) -> str:
    """Construct an Indeed search results URL for one query."""
    country = search.get("country", "www")
    base = f"https://{country}.indeed.com/jobs"

    params: dict[str, str] = {
        "q": query,
        "l": search.get("location", ""),
        "radius": str(search.get("radius_miles", 25)),
        "sort": "date",
    }
    if search.get("date_posted_days"):
        params["fromage"] = str(search["date_posted_days"])
    if search.get("salary_min"):
        params["q"] = f"{query} ${search['salary_min']}"
    if start:
        params["start"] = str(start)

    # Indeed filters: sc=0kf:attr_... ; easy apply / remote are encoded there.
    sc_filters: list[str] = []
    if search.get("easy_apply_only"):
        # "indeed apply" attribute
        sc_filters.append("attr(DSQF7)")  # Indeed Apply
    if search.get("remote_only") or str(search.get("location", "")).lower() == "remote":
        sc_filters.append("attr(DSQF7)")  # placeholder; remote handled via l=Remote
    if sc_filters:
        params["sc"] = "0kf:" + "".join(sc_filters) + ";"

    return base + "?" + urllib.parse.urlencode(params)


_JOB_CARD_SELECTORS = [
    "div.job_seen_beacon",
    "a.tapItem",
    "div.cardOutline",
    "[data-testid='slider_item']",
]


def collect_jobs(
    page: Page,
    search: dict[str, Any],
    query: str,
    max_jobs: int,
    action_delay: tuple[float, float],
) -> Iterator[JobPosting]:
    """Yield JobPostings for a query, paginating as needed."""
    seen_ids: set[str] = set()
    start = 0
    yielded = 0

    while yielded < max_jobs:
        url = build_search_url(search, query, start=start)
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        human_delay(*action_delay)
        _dismiss_popups(page)

        cards = _find_cards(page)
        if not cards:
            break

        page_new = 0
        for card in cards:
            if yielded >= max_jobs:
                break
            posting = _parse_card(card, search.get("country", "www"))
            if posting is None or posting.job_id in seen_ids:
                continue
            seen_ids.add(posting.job_id)
            page_new += 1
            yielded += 1
            yield posting

        if page_new == 0:
            break
        start += 10  # Indeed paginates in steps of 10


def _find_cards(page: Page):
    for selector in _JOB_CARD_SELECTORS:
        cards = page.query_selector_all(selector)
        if cards:
            return cards
    return []


def _parse_card(card, country: str):
    # Title + link
    link = (
        card.query_selector("h2 a")
        or card.query_selector("a.jcs-JobTitle")
        or card.query_selector("a[id^='job_']")
        or card.query_selector("a[data-jk]")
    )
    title_el = card.query_selector("h2 span[title]") or card.query_selector("h2")
    company_el = (
        card.query_selector("[data-testid='company-name']")
        or card.query_selector("span.companyName")
        or card.query_selector(".company_location [data-testid='company-name']")
    )
    location_el = (
        card.query_selector("[data-testid='text-location']")
        or card.query_selector("div.companyLocation")
    )

    job_id = None
    href = None
    if link:
        job_id = link.get_attribute("data-jk")
        href = link.get_attribute("href")
    if not job_id:
        # Try to scrape from data attributes on the card.
        job_id = card.get_attribute("data-jk")
    if not job_id and href:
        match = re.search(r"jk=([0-9a-f]+)", href)
        if match:
            job_id = match.group(1)
    if not job_id:
        return None

    url = f"https://{country}.indeed.com/viewjob?jk={job_id}"

    return JobPosting(
        job_id=job_id,
        title=(title_el.inner_text().strip() if title_el else "").strip(),
        company=(company_el.inner_text().strip() if company_el else "").strip(),
        location=(location_el.inner_text().strip() if location_el else "").strip(),
        url=url,
    )


def passes_filters(posting: JobPosting, filters: dict[str, Any]) -> tuple[bool, str]:
    """Return (ok, reason_if_skipped)."""
    title = posting.title.lower()
    company = posting.company.lower()

    for bad in filters.get("title_blocklist", []) or []:
        if bad.lower() in title:
            return False, f"title blocklist: '{bad}'"

    allow = filters.get("title_allowlist", []) or []
    if allow and not any(good.lower() in title for good in allow):
        return False, "title not in allowlist"

    for bad in filters.get("company_blocklist", []) or []:
        if bad.lower() in company:
            return False, f"company blocklist: '{bad}'"

    return True, ""


def _dismiss_popups(page: Page) -> None:
    """Best-effort close of cookie banners / interstitials."""
    for sel in [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept')",
        "button[aria-label='close']",
        "button[aria-label='Close']",
        ".icl-CloseButton",
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=2000)
                page.wait_for_timeout(500)
        except Exception:
            pass

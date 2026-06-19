"""Playwright browser session management.

We use a *persistent* browser context stored under user_data/ so that your
Indeed login (cookies, session) survives between runs. You log in once,
interactively, with `python main.py login`.
"""

from __future__ import annotations

import os
import random
import time
from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import BrowserContext, Page, sync_playwright

# A normal-looking desktop UA. Indeed fingerprints heavily; this is a courtesy,
# not a guarantee. Keeping headless=False is far more important for not tripping
# bot detection.
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class Session:
    """Owns the Playwright lifecycle and a single persistent context."""

    def __init__(self, user_data_dir: str, headless: bool = False) -> None:
        self.user_data_dir = user_data_dir
        self.headless = headless
        self._pw = None
        self._context: BrowserContext | None = None
        os.makedirs(user_data_dir, exist_ok=True)

    def __enter__(self) -> "Session":
        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=self.headless,
            user_agent=DEFAULT_UA,
            viewport={"width": 1366, "height": 900},
            locale="en-US",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
            ],
        )
        # Light stealth: hide the webdriver flag.
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self._context:
                self._context.close()
        finally:
            if self._pw:
                self._pw.stop()

    @property
    def context(self) -> BrowserContext:
        assert self._context is not None, "Session not started"
        return self._context

    def new_page(self) -> Page:
        return self.context.new_page()

    def page(self) -> Page:
        """Reuse the first open page, or create one."""
        pages = self.context.pages
        return pages[0] if pages else self.new_page()


def human_delay(min_s: float, max_s: float) -> None:
    """Sleep a random human-like interval."""
    time.sleep(random.uniform(min_s, max_s))


@contextmanager
def session(user_data_dir: str, headless: bool = False) -> Iterator[Session]:
    with Session(user_data_dir, headless=headless) as sess:
        yield sess

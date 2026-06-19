"""Top-level orchestration: search -> filter -> apply -> record."""

from __future__ import annotations

import logging
import os

from .apply import Applier, Outcome
from .browser import Session, human_delay
from .config import Config
from .questions import QuestionResolver
from .search import collect_jobs, passes_filters
from .tracker import Tracker

log = logging.getLogger("applier")


def login(cfg: Config, user_data_dir: str) -> None:
    """Open Indeed so the user can log in manually; persist the session."""
    country = cfg.search.get("country", "www")
    with Session(user_data_dir, headless=False) as sess:
        page = sess.page()
        page.goto(f"https://{country}.indeed.com/account/login",
                  wait_until="domcontentloaded")
        print("\n" + "=" * 64)
        print(" Log in to Indeed in the opened browser window.")
        print(" Complete any 2FA / CAPTCHA. Your session is saved locally.")
        print(" When you see your account is logged in, press ENTER here.")
        print("=" * 64 + "\n")
        input(" Press ENTER once you're logged in... ")
        print("Session saved to:", user_data_dir)


def run(cfg: Config, user_data_dir: str, dry_run: bool = False) -> dict[str, int]:
    """Execute one full pass over all configured queries."""
    behavior = dict(cfg.behavior)
    if dry_run:
        # Dry run NEVER submits, regardless of config.
        behavior["auto_submit"] = False
        log.info("DRY RUN: forms will be filled but never submitted.")

    base_dir = os.path.dirname(os.path.abspath(cfg.path))
    tracker = Tracker(
        db_path=os.path.join(base_dir, "applications.db"),
        csv_path=os.path.join(base_dir, "applications.csv"),
    )
    resolver = QuestionResolver(cfg.screening_answers, cfg.profile)

    limits = cfg.limits
    max_apps = int(limits.get("max_applications_per_run", 15))
    max_scan = int(limits.get("max_jobs_to_scan_per_query", 50))
    action_delay = (
        float(limits.get("min_action_delay", 1.5)),
        float(limits.get("max_action_delay", 4.0)),
    )
    between = (
        float(limits.get("min_between_applications", 8)),
        float(limits.get("max_between_applications", 20)),
    )

    stats = {o.value: 0 for o in Outcome}
    stats["scanned"] = 0
    stats["filtered"] = 0
    stats["duplicate"] = 0
    applied_count = 0

    with Session(user_data_dir, headless=bool(behavior.get("headless", False))) as sess:
        page = sess.page()
        applier = Applier(
            page=page,
            profile=cfg.profile,
            resolver=resolver,
            behavior=behavior,
            delays=limits,
            screenshot_dir=os.path.join(base_dir, "screenshots"),
        )

        for query in cfg.search["queries"]:
            if applied_count >= max_apps:
                break
            log.info("Searching: %r in %r", query, cfg.search.get("location"))

            for job in collect_jobs(page, cfg.search, query, max_scan, action_delay):
                stats["scanned"] += 1
                if applied_count >= max_apps:
                    break

                if tracker.already_seen(job.job_id):
                    stats["duplicate"] += 1
                    continue

                ok, reason = passes_filters(job, cfg.filters)
                if not ok:
                    stats["filtered"] += 1
                    log.info("  skip [%s] %s — %s", job.job_id, job.title, reason)
                    tracker.record(job_id=job.job_id, title=job.title,
                                   company=job.company, location=job.location,
                                   url=job.url, status="skipped", detail=reason)
                    continue

                log.info("  applying: %s @ %s", job.title, job.company)
                result = applier.apply_to(job)
                stats[result.outcome.value] += 1
                tracker.record(job_id=job.job_id, title=job.title,
                               company=job.company, location=job.location,
                               url=job.url, status=result.outcome.value,
                               detail=result.detail)
                log.info("    -> %s: %s", result.outcome.value, result.detail)

                if result.outcome in (Outcome.SUBMITTED, Outcome.DRAFTED):
                    applied_count += 1

                human_delay(*between)

    tracker.close()
    return stats

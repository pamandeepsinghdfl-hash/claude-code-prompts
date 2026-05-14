"""APScheduler daemon: runs the factory at 00:00 UTC every day.

  python scheduler.py            # daemonise
  python scheduler.py --once     # run immediately, exit (handy for CI / cron)

The scheduler relies on the OS being on UTC time. The Dockerfile sets
TZ=UTC; for VPS deployments set `timedatectl set-timezone UTC`.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import load_config
from src.factory import run_daily
from src.utils.logger import setup_logger


def _run() -> None:
    log = logging.getLogger("shorts_factory.scheduler")
    log.info("Cron trigger fired at %s — kicking daily run.", datetime.now(timezone.utc))
    try:
        run_daily()
    except Exception:  # noqa: BLE001
        log.exception("Daily run crashed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run immediately and exit")
    args = parser.parse_args()

    cfg = load_config()
    setup_logger(log_dir=cfg.logging.dir)
    log = logging.getLogger("shorts_factory.scheduler")

    if args.once:
        _run()
        return 0

    hh, mm = (int(x) for x in cfg.schedule.run_at_utc.split(":"))
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(
        _run,
        CronTrigger(hour=hh, minute=mm),
        id="daily_shorts_factory",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    log.info(
        "Scheduler started. Daily run at %s UTC. Next: %s",
        cfg.schedule.run_at_utc,
        sched.get_jobs()[0].next_run_time,
    )

    def _shutdown(signum, _frame):
        log.info("Signal %s — shutting down scheduler", signum)
        sched.shutdown(wait=False)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    sched.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())

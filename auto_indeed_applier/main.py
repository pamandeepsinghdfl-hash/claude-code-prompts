#!/usr/bin/env python3
"""Auto Indeed Applier — command-line entry point.

Usage:
    python main.py login                 # log in to Indeed once (saves session)
    python main.py run --dry-run         # fill forms but never submit (test it!)
    python main.py run                    # apply for real (uses config auto_submit)
    python main.py run --config my.yaml  # use a different config file

Read the README before your first run.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from applier.config import ConfigError, load_config
from applier.runner import login, run

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "config.yaml")
USER_DATA_DIR = os.path.join(HERE, "user_data")


def _setup_logging(verbose: bool) -> None:
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(HERE, "logs", "applier.log")),
    ]
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auto Indeed Applier")
    parser.add_argument("command", choices=["login", "run"],
                        help="login: authenticate once; run: search & apply")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fill forms but never click submit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    log = logging.getLogger("applier")

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        log.error("Config error: %s", exc)
        return 2

    if args.command == "login":
        login(cfg, USER_DATA_DIR)
        return 0

    # command == run
    if not os.path.exists(USER_DATA_DIR) or not os.listdir(USER_DATA_DIR):
        log.error("No saved session. Run `python main.py login` first.")
        return 2

    if cfg.behavior.get("auto_submit") and not args.dry_run:
        log.warning("auto_submit is ON — applications WILL be submitted for real.")

    stats = run(cfg, USER_DATA_DIR, dry_run=args.dry_run)

    log.info("=" * 50)
    log.info("Run complete. Summary:")
    for key, value in stats.items():
        if value:
            log.info("  %-14s %d", key, value)
    log.info("See applications.csv for the full record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

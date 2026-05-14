"""One-shot runner.

  python main.py             # run today's batch immediately
  python main.py --config x.yaml
  python main.py --dry-run   # build but do not upload
"""
from __future__ import annotations

import argparse
import os
import sys

from src.factory import run_daily


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Global YouTube Shorts Factory once")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Build but skip the upload step")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "1"
    report_path = run_daily(args.config)
    print(f"\nRun report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

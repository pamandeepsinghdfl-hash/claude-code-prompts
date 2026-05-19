"""One-shot runner.

  python main.py                  # pixel-art factory (default since pivot)
  python main.py --legacy         # original podcast-clip pipeline
  python main.py --config x.yaml
  python main.py --dry-run        # build but do not upload
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Pixel Hours Shorts Factory once")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Build but skip the upload step")
    parser.add_argument(
        "--legacy", action="store_true",
        help="Use the original podcast-clip pipeline instead of pixel-art",
    )
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "1"

    if args.legacy:
        from src.factory import run_daily   # original Off Mic / podcast pipeline
    else:
        from src.pixel_art.factory_pixel import run_daily  # default — Pixel Hours

    report_path = run_daily(args.config)
    print(f"\nRun report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

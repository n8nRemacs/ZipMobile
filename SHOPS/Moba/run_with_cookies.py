#!/usr/bin/env python3
"""
Run moba parser with automatic cookie refresh.

1. Validates existing cookies
2. If expired → runs auto_cookies.py to recapture
3. Runs moba_full_parser.py --full

Usage:
    python run_with_cookies.py                           # parse all
    python run_with_cookies.py --twocaptcha KEY          # with 2captcha
    python run_with_cookies.py --category /catalog/url/  # parse one category
    python run_with_cookies.py --dry-run                 # only refresh cookies
"""
import subprocess
import sys
import os
import json
import logging
import argparse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("run_with_cookies")

SCRIPT_DIR = Path(__file__).resolve().parent
COOKIES_FILE = SCRIPT_DIR / "moba_cookies.json"
AUTO_COOKIES = SCRIPT_DIR / "auto_cookies.py"
PARSER = SCRIPT_DIR / "moba_full_parser.py"


def cookies_valid() -> bool:
    """Quick check: do cookies exist and work?"""
    result = subprocess.run(
        [sys.executable, str(AUTO_COOKIES), "--validate"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def refresh_cookies(twocaptcha_key: str = None) -> bool:
    """Run auto_cookies.py to get fresh cookies."""
    cmd = [sys.executable, str(AUTO_COOKIES), "--force"]
    if twocaptcha_key:
        cmd.extend(["--twocaptcha", twocaptcha_key])

    log.info("Refreshing cookies ...")
    result = subprocess.run(cmd, text=True)
    return result.returncode == 0


def run_parser(parser_args: list) -> int:
    """Run moba_full_parser.py with given args."""
    cmd = [sys.executable, str(PARSER)] + parser_args
    log.info("Running parser: %s", " ".join(cmd))
    result = subprocess.run(cmd)
    return result.returncode


def main():
    ap = argparse.ArgumentParser(description="Moba parser with auto cookie refresh")
    ap.add_argument("--twocaptcha", type=str, metavar="KEY", help="2captcha API key")
    ap.add_argument("--dry-run", action="store_true", help="Only refresh cookies, don't parse")
    ap.add_argument("--category", type=str, help="Parse single category URL")
    ap.add_argument("--full", action="store_true", help="Full parse (default)", default=True)
    ap.add_argument("--max-categories", type=int, help="Limit number of categories")
    args = ap.parse_args()

    # Step 1: Check cookies
    log.info("Step 1: Checking cookies ...")
    if cookies_valid():
        log.info("Cookies OK")
    else:
        log.info("Cookies missing or expired")
        if not refresh_cookies(args.twocaptcha):
            log.error("Cookie refresh FAILED — cannot parse")
            sys.exit(1)
        log.info("Cookies refreshed successfully")

    if args.dry_run:
        log.info("Dry run — done")
        sys.exit(0)

    # Step 2: Run parser
    log.info("Step 2: Running parser ...")
    parser_args = []
    if args.category:
        parser_args = ["--category", args.category]
    elif args.max_categories:
        parser_args = ["--full", str(args.max_categories)]
    else:
        parser_args = ["--full"]

    rc = run_parser(parser_args)

    if rc != 0:
        log.error("Parser exited with code %d", rc)
        # Maybe cookies expired mid-parse? Try once more
        log.info("Retrying with fresh cookies ...")
        if refresh_cookies(args.twocaptcha):
            rc = run_parser(parser_args)

    sys.exit(rc)


if __name__ == "__main__":
    main()

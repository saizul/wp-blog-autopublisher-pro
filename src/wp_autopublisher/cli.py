"""Command line interface."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from . import __version__
from .frontmatter import FrontMatterError, load_folder
from .publisher import make_plan, publish_item
from .wp import WPClient, WPError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wp-autopublish",
                                description="Publish Markdown posts to WordPress via the REST API.")
    p.add_argument("folder", help="folder containing .md posts with YAML front matter")
    p.add_argument("--dry-run", action="store_true", help="print the plan; make no network calls")
    p.add_argument("--draft", action="store_true",
                   help="posts without a schedule are created as drafts instead of published")
    p.add_argument("--env-file", default=".env", help="path to .env (default: ./.env)")
    p.add_argument("--timezone", help="IANA timezone for naive publish_at (overrides WP_TIMEZONE)")
    p.add_argument("--version", action="version", version=__version__)
    return p


def _load_env(path: str) -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(path)
    except ImportError:  # pragma: no cover
        pass


def main(argv: Optional[List[str]] = None, client_factory=WPClient) -> int:
    args = build_parser().parse_args(argv)
    _load_env(args.env_file)
    tz = args.timezone or os.environ.get("WP_TIMEZONE", "UTC")
    default_status = "draft" if args.draft else "publish"

    try:
        posts = load_folder(args.folder)
    except FrontMatterError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not posts:
        print("no .md files found in %s" % args.folder, file=sys.stderr)
        return 1
    try:
        plan = make_plan(posts, tz_name=tz, default_status=default_status)
    except ValueError as exc:
        print("error: bad publish_at value: %s" % exc, file=sys.stderr)
        return 2

    if args.dry_run:
        print("DRY RUN: %d post(s), no network calls will be made\n" % len(plan))
        for item in plan:
            print(item.describe())
        return 0

    missing = [k for k in ("WP_URL", "WP_USER", "WP_APP_PASSWORD") if not os.environ.get(k)]
    if missing:
        print("error: missing in environment/.env: %s" % ", ".join(missing), file=sys.stderr)
        return 2
    client = client_factory(os.environ["WP_URL"], os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"])

    failures = 0
    with tempfile.TemporaryDirectory(prefix="wp-autopublish-") as tmp:
        for item in plan:
            try:
                publish_item(client, item, Path(tmp))
            except (WPError, OSError) as exc:
                failures += 1
                print("FAIL  %s: %s" % (item.post.slug, exc), file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

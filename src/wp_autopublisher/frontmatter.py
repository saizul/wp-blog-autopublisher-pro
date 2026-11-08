"""Parse Markdown files with YAML front matter."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

_FM_RE = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", re.DOTALL)


class FrontMatterError(ValueError):
    """Raised when a post file is malformed."""


@dataclass
class Post:
    path: Path
    title: str
    slug: str
    body: str
    excerpt: str = ""
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    seo_title: str = ""
    meta_description: str = ""
    focus_keyword: str = ""
    publish_at: Optional[Union[str, datetime]] = None
    delay_hours: Optional[float] = None
    featured_image: str = ""  # "", "auto", or a path relative to the post file
    featured_image_alt: str = ""  # alt text for the uploaded image; empty = use the title


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "post"


def _as_list(value: Any) -> List[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    raise FrontMatterError("categories/tags must be a list or comma-separated string")


def parse_text(text: str, path: Path = Path("<memory>")) -> Post:
    m = _FM_RE.match(text)
    if not m:
        raise FrontMatterError("%s: missing YAML front matter (--- block)" % path)
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise FrontMatterError("%s: invalid YAML: %s" % (path, exc))
    if not isinstance(meta, dict):
        raise FrontMatterError("%s: front matter must be a mapping" % path)
    title = str(meta.get("title") or "").strip()
    if not title:
        raise FrontMatterError("%s: 'title' is required" % path)
    delay = meta.get("delay_hours")
    if delay is not None:
        try:
            delay = float(delay)
        except (TypeError, ValueError):
            raise FrontMatterError("%s: delay_hours must be a number" % path)
        if delay < 0:
            raise FrontMatterError("%s: delay_hours must be >= 0" % path)
    publish_at = meta.get("publish_at")
    if publish_at is not None and not isinstance(publish_at, (str, datetime)):
        publish_at = str(publish_at)
    return Post(
        path=path,
        title=title,
        slug=slugify(str(meta.get("slug") or title)),
        body=m.group(2).strip() + "\n",
        excerpt=str(meta.get("excerpt") or "").strip(),
        categories=_as_list(meta.get("categories")),
        tags=_as_list(meta.get("tags")),
        seo_title=str(meta.get("seo_title") or "").strip(),
        meta_description=str(meta.get("meta_description") or "").strip(),
        focus_keyword=str(meta.get("focus_keyword") or "").strip(),
        publish_at=publish_at,
        delay_hours=delay,
        featured_image=str(meta.get("featured_image") or "").strip(),
        featured_image_alt=str(meta.get("featured_image_alt") or "").strip(),
    )


def parse_file(path: Union[str, Path]) -> Post:
    p = Path(path)
    return parse_text(p.read_text(encoding="utf-8"), p)


def load_folder(folder: Union[str, Path]) -> List[Post]:
    root = Path(folder)
    if not root.is_dir():
        raise FrontMatterError("not a directory: %s" % root)
    files = sorted(list(root.glob("*.md")) + list(root.glob("*.markdown")))
    return [parse_file(f) for f in files]

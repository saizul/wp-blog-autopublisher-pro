"""Plan and execute publishing of a folder of posts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import markdown

from .frontmatter import Post, slugify
from .images import generate_featured_image
from .scheduling import resolve_schedule
from .wp import WPClient

YOAST_KEYS = {
    "seo_title": "_yoast_wpseo_title",
    "meta_description": "_yoast_wpseo_metadesc",
    "focus_keyword": "_yoast_wpseo_focuskw",
}


def md_to_html(text: str) -> str:
    return markdown.markdown(text, extensions=["extra", "sane_lists", "toc", "tables", "fenced_code"])


def build_meta(post: Post) -> Dict[str, str]:
    return {key: getattr(post, attr) for attr, key in YOAST_KEYS.items() if getattr(post, attr)}


@dataclass
class PlanItem:
    post: Post
    status: str
    date_gmt: Optional[str]
    image: str  # human description

    def describe(self) -> str:
        when = "now" if self.status != "future" else "scheduled for %s UTC" % self.date_gmt
        lines = [
            "- %s  (slug: %s)" % (self.post.title, self.post.slug),
            "    status:     %s (%s)" % (self.status, when),
            "    categories: %s" % (", ".join(self.post.categories) or "-"),
            "    tags:       %s" % (", ".join(self.post.tags) or "-"),
            "    image:      %s" % self.image,
            "    image alt:  %s" % (self.post.featured_image_alt or "(post title)"),
            "    seo meta:   %s" % (", ".join(build_meta(self.post)) or "-"),
        ]
        return "\n".join(lines)


def image_plan(post: Post) -> str:
    fi = post.featured_image
    if not fi or fi.lower() == "auto":
        return "auto-generate 1200x675 PNG"
    return "upload %s" % fi


def make_plan(posts: List[Post], now: Optional[datetime] = None, tz_name: str = "UTC",
              default_status: str = "publish") -> List[PlanItem]:
    items = []
    for p in posts:
        status, date_gmt = resolve_schedule(p, now, tz_name, default_status)
        items.append(PlanItem(p, status, date_gmt, image_plan(p)))
    return items


def publish_item(client: WPClient, item: PlanItem, workdir: Path,
                 log: Callable[[str], None] = print) -> Optional[Dict[str, Any]]:
    post = item.post
    if client.post_exists(post.slug):
        log("SKIP  %s (slug already exists)" % post.slug)
        return None

    cat_ids = [client.ensure_term("categories", n, slugify(n)) for n in post.categories]
    tag_ids = [client.ensure_term("tags", n, slugify(n)) for n in post.tags]

    media_id = None
    fi = post.featured_image
    if not fi or fi.lower() == "auto":
        img_path = generate_featured_image(post.title, workdir / (post.slug + ".png"))
    else:
        img_path = (post.path.parent / fi).resolve()
        if not img_path.is_file():
            raise FileNotFoundError("featured_image not found: %s" % img_path)
    media_id = client.upload_media(img_path, post.title, post.featured_image_alt)

    payload: Dict[str, Any] = {
        "title": post.title,
        "slug": post.slug,
        "content": md_to_html(post.body),
        "excerpt": post.excerpt,
        "status": item.status,
        "categories": cat_ids,
        "tags": tag_ids,
        "featured_media": media_id,
    }
    if item.date_gmt:
        payload["date_gmt"] = item.date_gmt
    meta = build_meta(post)
    if meta:
        payload["meta"] = meta
    created = client.create_post(payload)
    log("OK    %s -> id %s (%s) %s" % (post.slug, created.get("id"), item.status, created.get("link", "")))
    return created

"""Plan and execute publishing of a folder of posts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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


# Statuses whose schedule may still be changed by an update. A post that is already
# live (publish/private) keeps its status and date so an update never unpublishes it.
RESCHEDULABLE = {"draft", "pending", "future"}

CREATED, UPDATED, SKIPPED = "created", "updated", "skipped"


def _explicit_image(post: Post) -> bool:
    fi = post.featured_image
    return bool(fi) and fi.lower() != "auto"


def _resolve_image(post: Post, workdir: Path) -> Path:
    if not _explicit_image(post):
        return generate_featured_image(post.title, workdir / (post.slug + ".png"))
    img_path = (post.path.parent / post.featured_image).resolve()
    if not img_path.is_file():
        raise FileNotFoundError("featured_image not found: %s" % img_path)
    return img_path


def _content_payload(client: WPClient, post: Post) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "title": post.title,
        "content": md_to_html(post.body),
        "excerpt": post.excerpt,
        "categories": [client.ensure_term("categories", n, slugify(n)) for n in post.categories],
        "tags": [client.ensure_term("tags", n, slugify(n)) for n in post.tags],
    }
    meta = build_meta(post)
    if meta:
        payload["meta"] = meta
    return payload


def build_update_payload(client: WPClient, item: PlanItem, existing: Dict[str, Any],
                         workdir: Path) -> Dict[str, Any]:
    """Payload for updating ``existing`` (the post found by slug) from ``item``.

    * Title, content, excerpt, terms and SEO meta always follow the Markdown file.
    * The featured image is replaced only when ``featured_image`` names a file, or when
      the post has none yet; an ``auto`` image is not regenerated on every update.
    * Status and date change only while the post is not live yet (draft, pending or
      scheduled), so a published post is never pulled back or re-dated.
    """
    post = item.post
    payload = _content_payload(client, post)
    if _explicit_image(post) or not existing.get("featured_media"):
        img_path = _resolve_image(post, workdir)
        payload["featured_media"] = client.upload_media(img_path, post.title, post.featured_image_alt)
    if existing.get("status") in RESCHEDULABLE:
        payload["status"] = item.status
        if item.date_gmt:
            payload["date_gmt"] = item.date_gmt
    return payload


def publish_item(client: WPClient, item: PlanItem, workdir: Path,
                 log: Callable[[str], None] = print, update: bool = False) -> Optional[Dict[str, Any]]:
    """Create the post, or update it when ``update`` is true and the slug exists.

    Returns the WordPress response, or None when the post was skipped.
    """
    return publish_item_with_outcome(client, item, workdir, log, update)[1]


def publish_item_with_outcome(client: WPClient, item: PlanItem, workdir: Path,
                              log: Callable[[str], None] = print,
                              update: bool = False) -> Tuple[str, Optional[Dict[str, Any]]]:
    post = item.post
    if update:
        existing = client.find_post(post.slug)
        if existing is not None:
            payload = build_update_payload(client, item, existing, workdir)
            result = client.update_post(int(existing["id"]), payload)
            log("UPD   %s -> id %s (%s) %s" % (post.slug, existing["id"],
                                               result.get("status", existing.get("status")),
                                               result.get("link", existing.get("link", ""))))
            return UPDATED, result
    elif client.post_exists(post.slug):
        log("SKIP  %s (slug already exists; use --update to overwrite)" % post.slug)
        return SKIPPED, None

    payload = _content_payload(client, post)
    img_path = _resolve_image(post, workdir)
    payload["featured_media"] = client.upload_media(img_path, post.title, post.featured_image_alt)
    payload["slug"] = post.slug
    payload["status"] = item.status
    if item.date_gmt:
        payload["date_gmt"] = item.date_gmt
    created = client.create_post(payload)
    log("OK    %s -> id %s (%s) %s" % (post.slug, created.get("id"), item.status, created.get("link", "")))
    return CREATED, created

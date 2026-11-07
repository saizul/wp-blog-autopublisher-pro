"""Turn publish_at / delay_hours into a WordPress status and date_gmt."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Union

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from .frontmatter import Post

GMT_FORMAT = "%Y-%m-%dT%H:%M:%S"


def get_tz(name: str):
    if not name or name.upper() == "UTC":
        return timezone.utc
    if ZoneInfo is None:  # pragma: no cover
        raise RuntimeError("zoneinfo unavailable; use WP_TIMEZONE=UTC")
    return ZoneInfo(name)


def to_utc(value: Union[str, datetime], tz_name: str = "UTC") -> datetime:
    """Parse a value; naive datetimes are interpreted in tz_name."""
    if isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        dt = datetime.fromisoformat(s)
    else:
        dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_tz(tz_name))
    return dt.astimezone(timezone.utc)


def resolve_schedule(
    post: Post,
    now: Optional[datetime] = None,
    tz_name: str = "UTC",
    default_status: str = "publish",
) -> Tuple[str, Optional[str]]:
    """Return (status, date_gmt). date_gmt is None when not scheduling.

    publish_at wins over delay_hours. A moment in the past (or now) publishes
    immediately; a future moment yields status "future" with date_gmt set.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    target = None
    if post.publish_at:
        target = to_utc(post.publish_at, tz_name)
    elif post.delay_hours is not None:
        target = now + timedelta(hours=post.delay_hours)
    if target is not None and target > now:
        return "future", target.strftime(GMT_FORMAT)
    return default_status, None

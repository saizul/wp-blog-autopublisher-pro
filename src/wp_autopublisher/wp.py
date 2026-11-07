"""Minimal WordPress REST client using Application Passwords."""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


class WPError(RuntimeError):
    pass


class WPClient:
    def __init__(self, base_url: str, user: str, app_password: str,
                 session: Optional[requests.Session] = None, timeout: int = 30):
        self.base = base_url.rstrip("/") + "/wp-json/wp/v2"
        self.session = session or requests.Session()
        self.session.auth = (user, app_password)
        self.timeout = timeout

    def _request(self, method: str, path: str, **kw) -> Any:
        resp = self.session.request(method, self.base + path, timeout=self.timeout, **kw)
        if resp.status_code >= 400:
            raise WPError("%s %s -> %s: %s" % (method, path, resp.status_code, resp.text[:300]))
        return resp.json()

    # --- posts -----------------------------------------------------------
    def post_exists(self, slug: str) -> bool:
        # status=any needs auth; includes drafts, scheduled and private posts
        data = self._request("GET", "/posts", params={"slug": slug, "status": "any", "_fields": "id"})
        return bool(data)

    def create_post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/posts", json=payload)

    # --- terms -----------------------------------------------------------
    def ensure_term(self, taxonomy: str, name: str, slug: str) -> int:
        """taxonomy is 'categories' or 'tags'. Lookup by slug, then create."""
        found = self._request("GET", "/" + taxonomy, params={"slug": slug, "_fields": "id,slug"})
        if found:
            return int(found[0]["id"])
        created = self._request("POST", "/" + taxonomy, json={"name": name, "slug": slug})
        return int(created["id"])

    # --- media -----------------------------------------------------------
    def upload_media(self, path: Path, title: str, alt_text: str = "") -> int:
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        headers = {
            "Content-Disposition": 'attachment; filename="%s"' % path.name,
            "Content-Type": ctype,
        }
        resp = self.session.post(self.base + "/media", data=path.read_bytes(),
                                 headers=headers, timeout=self.timeout * 3)
        if resp.status_code >= 400:
            raise WPError("media upload failed: %s %s" % (resp.status_code, resp.text[:300]))
        media_id = int(resp.json()["id"])
        self._request("POST", "/media/%d" % media_id, json={"title": title, "alt_text": alt_text or title})
        return media_id

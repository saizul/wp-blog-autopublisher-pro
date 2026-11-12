from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

from wp_autopublisher import cli
from wp_autopublisher.frontmatter import FrontMatterError, parse_text, load_folder
from wp_autopublisher.scheduling import resolve_schedule
from wp_autopublisher.publisher import build_meta, md_to_html, publish_item, make_plan

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "posts"

DOC = """---
title: Hello World
categories: A, B
tags: [x, y]
focus_keyword: kw
---
Body **text**
"""


def test_parse_basic():
    p = parse_text(DOC)
    assert p.title == "Hello World"
    assert p.slug == "hello-world"
    assert p.categories == ["A", "B"]
    assert p.tags == ["x", "y"]
    assert p.body.strip() == "Body **text**"
    assert build_meta(p) == {"_yoast_wpseo_focuskw": "kw"}


def test_parse_errors():
    with pytest.raises(FrontMatterError):
        parse_text("no front matter")
    with pytest.raises(FrontMatterError):
        parse_text("---\nslug: a\n---\nbody")
    with pytest.raises(FrontMatterError):
        parse_text("---\ntitle: t\ndelay_hours: -1\n---\nb")


def test_examples_load():
    posts = load_folder(EXAMPLES)
    assert len(posts) == 2
    assert posts[1].delay_hours == 48


def test_schedule_future_publish_at_with_timezone():
    p = parse_text("---\ntitle: t\npublish_at: 2026-01-02 09:00\n---\nb")
    status, gmt = resolve_schedule(p, NOW, "Asia/Dhaka")  # UTC+6
    assert (status, gmt) == ("future", "2026-01-02T03:00:00")


def test_schedule_delay_and_past():
    p = parse_text("---\ntitle: t\ndelay_hours: 2.5\n---\nb")
    assert resolve_schedule(p, NOW) == ("future", "2026-01-01T14:30:00")
    past = parse_text("---\ntitle: t\npublish_at: '2025-12-31T00:00:00Z'\n---\nb")
    assert resolve_schedule(past, NOW) == ("publish", None)
    plain = parse_text("---\ntitle: t\n---\nb")
    assert resolve_schedule(plain, NOW, default_status="draft") == ("draft", None)


def test_markdown_html():
    html = md_to_html("## Hi\n\n- a\n- b")
    assert "<h2" in html and "<li>a</li>" in html


def test_dry_run_makes_no_network_calls(capsys):
    factory = mock.Mock()
    with mock.patch("requests.Session.request") as req:
        rc = cli.main([str(EXAMPLES), "--dry-run", "--env-file", "/nonexistent"], client_factory=factory)
    assert rc == 0
    factory.assert_not_called()
    req.assert_not_called()
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "fix-core-web-vitals-wordpress" in out
    assert "scheduled for" in out  # second sample has delay_hours


class FakeClient:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.created = []
        self.media = []

    def post_exists(self, slug):
        return slug in self.existing

    def ensure_term(self, tax, name, slug):
        return len(slug)

    def upload_media(self, path, title, alt_text=""):
        assert path.exists()
        self.media.append(path)
        return 99

    def create_post(self, payload):
        self.created.append(payload)
        return {"id": 1, "link": "https://example.com/x"}


def test_publish_flow_and_skip(tmp_path):
    posts = load_folder(EXAMPLES)
    plan = make_plan(posts, NOW)
    c = FakeClient(existing=["pre-publish-seo-checklist"])
    results = [publish_item(c, i, tmp_path, log=lambda m: None) for i in plan]
    assert results[1] is None
    assert len(c.created) == 1
    payload = c.created[0]
    assert payload["featured_media"] == 99
    assert payload["meta"]["_yoast_wpseo_focuskw"] == "core web vitals wordpress"
    assert payload["status"] == "publish" and "date_gmt" not in payload
    from PIL import Image
    assert Image.open(c.media[0]).size == (1200, 675)


def test_scheduled_payload_has_date_gmt(tmp_path):
    posts = load_folder(EXAMPLES)[1:]
    item = make_plan(posts, NOW)[0]
    c = FakeClient()
    publish_item(c, item, tmp_path, log=lambda m: None)
    assert c.created[0]["status"] == "future"
    assert c.created[0]["date_gmt"] == (NOW + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%S")


def test_featured_image_alt_is_parsed():
    post = parse_text(DOC.replace("focus_keyword: kw", "featured_image_alt: A red bicycle  "))
    assert post.featured_image_alt == "A red bicycle"
    assert parse_text(DOC).featured_image_alt == ""


def test_featured_image_alt_reaches_upload(tmp_path):
    class AltClient(FakeClient):
        def upload_media(self, path, title, alt_text=""):
            self.alts = (title, alt_text)
            return super().upload_media(path, title, alt_text)

    post = parse_text(DOC.replace("focus_keyword: kw", "featured_image_alt: Alt words"))
    post.path = tmp_path / "hello.md"
    c = AltClient()
    publish_item(c, make_plan([post], NOW)[0], tmp_path, log=lambda m: None)
    assert c.alts == ("Hello World", "Alt words")


def test_missing_alt_is_empty_so_client_falls_back_to_title(tmp_path):
    class AltClient(FakeClient):
        def upload_media(self, path, title, alt_text=""):
            self.alts = (title, alt_text)
            return super().upload_media(path, title, alt_text)

    post = parse_text(DOC)
    post.path = tmp_path / "hello.md"
    c = AltClient()
    publish_item(c, make_plan([post], NOW)[0], tmp_path, log=lambda m: None)
    assert c.alts == ("Hello World", "")


def test_dry_run_plan_shows_alt_text():
    post = parse_text(DOC.replace("focus_keyword: kw", "featured_image_alt: Alt words"))
    text = make_plan([post], NOW)[0].describe()
    assert "image alt:  Alt words" in text
    assert "image alt:  (post title)" in make_plan([parse_text(DOC)], NOW)[0].describe()


# --- update mode -------------------------------------------------------------

class UpdatingClient(FakeClient):
    def __init__(self, found=None):
        super().__init__()
        self.found = found or {}
        self.updated = []

    def find_post(self, slug):
        return self.found.get(slug)

    def post_exists(self, slug):
        return slug in self.found

    def update_post(self, post_id, payload):
        self.updated.append((post_id, payload))
        status = next((v.get("status") for v in self.found.values() if v["id"] == post_id), None)
        return {"id": post_id, "status": payload.get("status", status), "link": "https://e.com/u"}


def _item(text=DOC, tmp_path=None, now=NOW):
    post = parse_text(text)
    if tmp_path is not None:
        post.path = tmp_path / "hello.md"
    return make_plan([post], now)[0]


def test_without_update_existing_slug_is_skipped(tmp_path):
    c = UpdatingClient({"hello-world": {"id": 5, "status": "publish", "featured_media": 3}})
    assert publish_item(c, _item(tmp_path=tmp_path), tmp_path, log=lambda m: None) is None
    assert c.updated == [] and c.created == []


def test_update_published_post_keeps_status_date_and_image(tmp_path):
    c = UpdatingClient({"hello-world": {"id": 5, "status": "publish", "featured_media": 3}})
    text = DOC.replace("focus_keyword: kw", "focus_keyword: kw\ndelay_hours: 10")
    result = publish_item(c, _item(text, tmp_path), tmp_path, log=lambda m: None, update=True)
    assert result["id"] == 5 and c.created == []
    post_id, payload = c.updated[0]
    assert post_id == 5
    assert payload["title"] == "Hello World" and "<strong>text</strong>" in payload["content"]
    assert payload["meta"] == {"_yoast_wpseo_focuskw": "kw"}
    assert "status" not in payload and "date_gmt" not in payload
    assert "featured_media" not in payload and c.media == []
    assert "slug" not in payload


def test_update_draft_is_rescheduled(tmp_path):
    c = UpdatingClient({"hello-world": {"id": 7, "status": "draft", "featured_media": 3}})
    text = DOC.replace("focus_keyword: kw", "delay_hours: 2")
    publish_item(c, _item(text, tmp_path), tmp_path, log=lambda m: None, update=True)
    payload = c.updated[0][1]
    assert payload["status"] == "future" and payload["date_gmt"] == "2026-01-01T14:00:00"


def test_update_adds_image_when_post_has_none(tmp_path):
    c = UpdatingClient({"hello-world": {"id": 7, "status": "publish", "featured_media": 0}})
    publish_item(c, _item(tmp_path=tmp_path), tmp_path, log=lambda m: None, update=True)
    assert c.updated[0][1]["featured_media"] == 99 and len(c.media) == 1


def test_update_replaces_explicit_image(tmp_path):
    from PIL import Image
    Image.new("RGB", (10, 10)).save(tmp_path / "cover.png")
    c = UpdatingClient({"hello-world": {"id": 7, "status": "publish", "featured_media": 3}})
    text = DOC.replace("focus_keyword: kw", "featured_image: cover.png")
    publish_item(c, _item(text, tmp_path), tmp_path, log=lambda m: None, update=True)
    assert c.updated[0][1]["featured_media"] == 99
    assert c.media == [(tmp_path / "cover.png").resolve()]


def test_update_mode_creates_missing_post(tmp_path):
    c = UpdatingClient()
    publish_item(c, _item(tmp_path=tmp_path), tmp_path, log=lambda m: None, update=True)
    assert c.updated == [] and c.created[0]["slug"] == "hello-world"


def test_cli_update_flow_and_summary(tmp_path, capsys, monkeypatch):
    for key, value in {"WP_URL": "https://e.com", "WP_USER": "u", "WP_APP_PASSWORD": "p"}.items():
        monkeypatch.setenv(key, value)
    c = UpdatingClient({"pre-publish-seo-checklist": {"id": 3, "status": "future", "featured_media": 1}})
    rc = cli.main([str(EXAMPLES), "--update", "--env-file", "/nonexistent"],
                  client_factory=lambda *a: c)
    assert rc == 0
    assert len(c.created) == 1 and c.updated[0][0] == 3
    assert "1 created, 1 updated, 0 skipped, 0 failed" in capsys.readouterr().out


def test_cli_only_filters_and_rejects_unknown(capsys):
    rc = cli.main([str(EXAMPLES), "--dry-run", "--only", "pre-publish-seo-checklist",
                   "--env-file", "/nonexistent"])
    out = capsys.readouterr().out
    assert rc == 0 and "DRY RUN: 1 post(s)" in out and "create only" in out
    rc = cli.main([str(EXAMPLES), "--dry-run", "--only", "nope", "--env-file", "/nonexistent"])
    assert rc == 2 and "nope" in capsys.readouterr().err


def test_cli_rejects_duplicate_slugs(tmp_path, capsys):
    (tmp_path / "a.md").write_text("---\ntitle: Same\n---\nA", encoding="utf-8")
    (tmp_path / "b.md").write_text("---\ntitle: Other\nslug: same\n---\nB", encoding="utf-8")
    assert cli.main([str(tmp_path), "--dry-run", "--env-file", "/nonexistent"]) == 2
    assert "duplicate slug(s)" in capsys.readouterr().err


def test_wp_client_find_and_update(monkeypatch):
    from wp_autopublisher.wp import WPClient, WPError

    calls = []

    class Resp:
        def __init__(self, code, data):
            self.status_code, self._data, self.text = code, data, str(data)

        def json(self):
            return self._data

    responses = [Resp(200, [{"id": 4, "status": "draft", "featured_media": 0}]),
                 Resp(200, []),
                 Resp(200, {"id": 4, "status": "draft"}),
                 Resp(200, {"oops": 1})]

    def fake_request(method, url, **kw):
        calls.append((method, url, kw))
        return responses.pop(0)

    client = WPClient("https://e.com/", "u", "p")
    monkeypatch.setattr(client.session, "request", fake_request)
    assert client.find_post("a")["id"] == 4
    assert client.post_exists("b") is False
    assert client.update_post(4, {"title": "x"})["id"] == 4
    assert calls[2][0] == "POST" and calls[2][1].endswith("/wp-json/wp/v2/posts/4")
    with pytest.raises(WPError):
        client.find_post("c")

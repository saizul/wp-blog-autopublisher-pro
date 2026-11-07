# WP Blog Autopublisher Pro

Publish a folder of Markdown posts to WordPress through the REST API. Write in Markdown with YAML front matter; the tool converts to HTML, creates categories and tags, uploads a featured image (auto-generated if you do not provide one), schedules posts, and sets Yoast SEO fields.

Built by [Saizul Amin](https://saizul.com). MIT licensed.

## Features

- Markdown to HTML (tables, fenced code, lists, TOC anchors)
- Authentication with WordPress Application Passwords (no plugin needed)
- Featured image: use your own file, or auto-generate a 1200x675 PNG (gradient plus title) with Pillow
- Media upload with title and alt text
- Categories and tags: looked up by slug, created when missing
- Scheduling: `publish_at` or `delay_hours` becomes `status=future` with `date_gmt`
- Idempotent: a post whose slug already exists (any status) is skipped
- Yoast SEO title, meta description and focus keyword through the `meta` field
- `--dry-run` prints the full plan with zero network calls

## Install

Requires Python 3.9+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then edit
```

`.env`:

```
WP_URL=https://example.com
WP_USER=your-wp-username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
WP_TIMEZONE=UTC
```

Create the application password in wp-admin under Users > Profile > Application Passwords. The site should be served over HTTPS. Use a user with at least the Editor role (needs to publish posts and manage categories/tags). Never commit `.env`.

## Usage

```bash
wp-autopublish examples/posts --dry-run     # preview, no network
wp-autopublish examples/posts               # publish
wp-autopublish examples/posts --draft       # unscheduled posts become drafts
wp-autopublish posts/ --timezone Asia/Dhaka # interpret naive publish_at in this zone
```

Exit codes: 0 success, 1 one or more posts failed (or no files), 2 configuration or front matter error.

### Front matter

```yaml
---
title: "Post title"              # required
slug: my-post-slug               # default: slugified title
excerpt: "Short summary"
categories: [WordPress, SEO]     # list or comma-separated
tags: [speed, checklist]
seo_title: "Title for search results"
meta_description: "Snippet under 160 characters"
focus_keyword: "main keyword"
publish_at: 2026-03-01 09:00     # optional; naive values use WP_TIMEZONE
delay_hours: 24                  # optional; used if publish_at is absent
featured_image: auto             # or a path relative to the post file; omitted = auto
---
```

Scheduling rules: `publish_at` wins over `delay_hours`. A time in the future sends `status=future` and `date_gmt` in UTC; a time in the past (or no schedule) publishes immediately (or creates a draft with `--draft`).

## Yoast SEO fields

The REST API only accepts post meta keys that were registered with `show_in_rest`. Yoast does not register its keys this way, so without help the values are silently dropped. Copy `wp/register-yoast-meta.php` into `wp-content/mu-plugins/` on your site. It registers `_yoast_wpseo_title`, `_yoast_wpseo_metadesc` and `_yoast_wpseo_focuskw` for REST with an `auth_callback` that requires `edit_posts`. Review it before installing. If you use another SEO plugin, change the keys in the PHP file and in `YOAST_KEYS` in `src/wp_autopublisher/publisher.py`.

## Tests

```bash
pytest
```

Tests cover front matter parsing, schedule date math, dry-run (asserts no HTTP) and the publish flow against a fake client. No network is used.

## Writing tips for E-E-A-T

Search quality guidelines reward Experience, Expertise, Authoritativeness and Trust. Automation handles publishing; the content still has to earn it.

- Experience: include first-hand detail such as your own screenshots, numbers, configs and mistakes. Say what you tested and when.
- Expertise: explain the why, not just the steps. Name the trade-offs and when the advice does not apply.
- Authoritativeness: link to primary sources (official docs, specs) and keep an author page with real credentials. Add `Person` and `Article` schema.
- Trust: show author name and last-updated date, cite sources, disclose affiliations, keep the site on HTTPS with clear contact details.
- Do not publish unreviewed generated text in bulk. Edit every post, add something only you know, and fact-check claims.
- Match search intent, keep titles honest, and write meta descriptions that describe the page rather than bait.
- Schedule posts with a steady cadence (use `delay_hours`) instead of dumping many at once, then update old posts when facts change.

## Limitations

- Creates posts only; it does not update existing ones (they are skipped by slug).
- Pages and custom post types are not handled.
- Images are uploaded per post; alt text defaults to the title.

## License

MIT, see [LICENSE](LICENSE).

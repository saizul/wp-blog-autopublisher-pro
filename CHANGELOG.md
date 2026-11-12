# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `--update`: posts whose slug already exists are updated in place (title, content,
  excerpt, terms, SEO meta). Published and private posts keep their status and date;
  drafts and scheduled posts follow the new schedule. The featured image is only
  replaced when a file is named in front matter or the post has none.
- `--only SLUG` (repeatable) to process selected posts from a folder.
- End-of-run summary: created, updated, skipped and failed counts.
- `WPClient.find_post()` and `WPClient.update_post()`.

### Changed
- Duplicate slugs inside one folder are now rejected with exit code 2 before any
  request is made, instead of silently skipping the second file.

## [0.1.0]

- Initial release: Markdown to WordPress publishing with scheduling, terms,
  featured images and Yoast meta.

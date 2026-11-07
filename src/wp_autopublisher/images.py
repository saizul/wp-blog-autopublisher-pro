"""Generate a 1200x675 featured image: vertical gradient plus wrapped title."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 675

_PALETTES = [
    ((15, 32, 74), (36, 99, 160)),
    ((38, 20, 71), (125, 61, 142)),
    ((10, 61, 52), (46, 139, 110)),
    ((70, 28, 28), (176, 82, 58)),
    ((24, 24, 38), (66, 84, 120)),
]

_FONT_CANDIDATES = [
    "DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "arialbd.ttf",
]


def _font(size: int):
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size)  # Pillow >= 10.1
    except TypeError:  # pragma: no cover
        return ImageFont.load_default()


def _text_width(draw, text, font) -> float:
    if hasattr(draw, "textlength"):
        return draw.textlength(text, font=font)
    return draw.textsize(text, font=font)[0]  # pragma: no cover


def wrap(draw, text: str, font, max_width: int) -> List[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if _text_width(draw, trial, font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _gradient(top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT))
    px = img.load()
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(WIDTH):
            px[x, y] = row
    return img


def generate_featured_image(title: str, out_path: Path) -> Path:
    """Write a deterministic PNG for the title and return its path."""
    idx = int(hashlib.sha1(title.encode("utf-8")).hexdigest(), 16) % len(_PALETTES)
    img = _gradient(*_PALETTES[idx])
    draw = ImageDraw.Draw(img)
    margin = 90
    max_w = WIDTH - 2 * margin
    size = 76
    while True:
        font = _font(size)
        lines = wrap(draw, title, font, max_w)
        if (len(lines) <= 4 and size * 1.25 * len(lines) <= HEIGHT - 2 * margin) or size <= 36:
            break
        size -= 4
    line_h = int(size * 1.25)
    y = (HEIGHT - line_h * len(lines)) // 2
    for line in lines:
        draw.text((margin, y), line, font=font, fill=(255, 255, 255))
        y += line_h
    draw.rectangle([margin, HEIGHT - margin + 20, margin + 120, HEIGHT - margin + 26], fill=(255, 255, 255))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path

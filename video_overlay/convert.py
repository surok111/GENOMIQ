"""Convert `composition.py` into a video laid over the original recording.

Requires ffmpeg on PATH and Pillow.

    python video_overlay/convert.py --preview
    python video_overlay/convert.py

`--preview` writes stills at the middle of each scene (original frame + overlay).
Without `--preview` the converter streams an overlay track into ffmpeg and
writes an mp4 with the original voice.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from composition import (
    CARD_BOTTOM_MARGIN,
    CARD_MIN_TOP,
    DURATION,
    FPS,
    HEIGHT,
    MARKERS,
    SCENES,
    TONES,
    WALL_BOTTOM,
    WIDTH,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = Path(
    r"C:\Users\adm\Downloads\IMG-0526-1794920141102-wrm8n (online-video-cutter.com).mp4"
)
DEFAULT_OUTPUT = ROOT / "genomiq_pitch.mp4"
PREVIEW_DIR = ROOT / "preview"

FONT_DIR = Path(r"C:\Windows\Fonts")
PAPER = (246, 243, 236, 242)
PAPER_SOLID = (246, 243, 236, 255)
INK = (18, 28, 34, 255)
MUTED = (78, 90, 98, 255)
WHITE = (255, 255, 255, 255)
HAIRLINE = (214, 206, 194, 255)


def load_fonts() -> dict[str, ImageFont.FreeTypeFont]:
    def face(name: str, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(str(FONT_DIR / name), size)

    return {
        "kicker": face("segoeuib.ttf", 18),
        "title": face("segoeuib.ttf", 46),
        "title_sm": face("segoeuib.ttf", 34),
        "subtitle": face("segoeui.ttf", 24),
        "body": face("segoeui.ttf", 26),
        "body_b": face("segoeuib.ttf", 24),
        "speech": face("segoeuii.ttf", 20),
        "num": face("bahnschrift.ttf", 54),
        "num_sm": face("bahnschrift.ttf", 42),
        "chip": face("segoeuib.ttf", 20),
        "section": face("segoeuib.ttf", 18),
        "tiny": face("segoeui.ttf", 16),
        "thanks": face("segoeuib.ttf", 40),
        "stamp": face("segoeuib.ttf", 22),
    }


FONTS: dict[str, ImageFont.FreeTypeFont] = {}
_SHADOW_CACHE: dict[tuple, Image.Image] = {}
_ICON_CACHE: dict[tuple, Image.Image] = {}


def ease_out(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return 1 - (1 - u) ** 3


def phase(t: float, start: float, end: float, enter: float = 0.38, exit: float = 0.30):
    """Return (opacity, enter_progress, local_seconds). Opacity is 0 outside the window."""
    if t < start or t >= end:
        return 0.0, 0.0, 0.0
    local = t - start
    inn = ease_out(local / enter) if enter else 1.0
    if t > end - exit:
        out = max(0.0, (end - t) / exit)
        opacity = out * out
    else:
        opacity = inn
    return opacity, inn, local


def revealed(local: float, at: float, enter: float = 0.32) -> float:
    if local < at:
        return 0.0
    return ease_out((local - at) / enter)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = current + " " + word
            if text_size(draw, trial, font)[0] <= max_w:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def apply_opacity(image: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return image
    out = image.copy()
    alpha = out.getchannel("A")
    alpha = alpha.point(lambda p, o=opacity: int(p * o))
    out.putalpha(alpha)
    return out


def shadow(size: tuple[int, int], radius: int) -> Image.Image:
    key = (size, radius)
    cached = _SHADOW_CACHE.get(key)
    if cached is not None:
        return cached
    pad = 28
    plate = Image.new("RGBA", (size[0] + pad * 2, size[1] + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    draw.rounded_rectangle(
        (pad, pad + 8, pad + size[0], pad + 8 + size[1]),
        radius=radius,
        fill=(12, 16, 20, 78),
    )
    plate = plate.filter(ImageFilter.GaussianBlur(10))
    _SHADOW_CACHE[key] = plate
    return plate


def icon(name: str, size: int, color: tuple[int, int, int, int]) -> Image.Image:
    key = (name, size, color)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    c = color
    cx = cy = size / 2
    m = size * 0.16

    if name == "dna":
        pts_a, pts_b = [], []
        for i in range(size):
            y = 2 + i * (size - 4) / max(1, size - 1)
            ang = (i / size) * math.tau * 1.65
            pts_a.append((cx + math.sin(ang) * size * 0.30, y))
            pts_b.append((cx + math.sin(ang + math.pi) * size * 0.30, y))
        draw.line(pts_a, fill=c, width=max(2, size // 16))
        draw.line(pts_b, fill=c, width=max(2, size // 16))
        step = max(4, size // 7)
        for i in range(step, size - step, step):
            draw.line((pts_a[i], pts_b[i]), fill=(*c[:3], 180), width=max(2, size // 22))
    elif name == "marker":
        r = size * 0.30
        draw.ellipse((cx - r, cy - r - size * 0.06, cx + r, cy + r - size * 0.06), outline=c, width=max(2, size // 14))
        draw.ellipse((cx - r * 0.38, cy - r * 0.38 - size * 0.06, cx + r * 0.38, cy + r * 0.38 - size * 0.06), fill=c)
        draw.polygon([(cx, size - m * 0.2), (cx - size * 0.11, cy + r * 0.55), (cx + size * 0.11, cy + r * 0.55)], fill=c)
    elif name == "pin":
        r = size * 0.26
        draw.ellipse((cx - r, m, cx + r, m + 2 * r), outline=c, width=max(2, size // 12))
        draw.ellipse((cx - r * 0.35, m + r * 0.65, cx + r * 0.35, m + r * 1.35), fill=c)
        draw.line((cx, m + 2 * r, cx, size - m), fill=c, width=max(2, size // 12))
        draw.ellipse((cx - 3, size - m - 3, cx + 3, size - m + 3), fill=c)
    elif name == "people":
        draw.ellipse((cx - size * 0.16, m, cx + size * 0.16, m + size * 0.32), outline=c, width=max(2, size // 14))
        draw.arc((m, cy, size - m, size + size * 0.15), 200, 340, fill=c, width=max(2, size // 14))
    elif name == "calendar":
        draw.rounded_rectangle((m, m + size * 0.08, size - m, size - m), radius=4, outline=c, width=max(2, size // 14))
        draw.line((m, m + size * 0.32, size - m, m + size * 0.32), fill=c, width=max(2, size // 14))
        draw.line((cx - size * 0.16, m, cx - size * 0.16, m + size * 0.16), fill=c, width=max(2, size // 14))
        draw.line((cx + size * 0.16, m, cx + size * 0.16, m + size * 0.16), fill=c, width=max(2, size // 14))
    elif name == "clock":
        draw.ellipse((m, m, size - m, size - m), outline=c, width=max(2, size // 14))
        draw.line((cx, cy, cx, m + size * 0.16), fill=c, width=max(2, size // 14))
        draw.line((cx, cy, cx + size * 0.18, cy + size * 0.08), fill=c, width=max(2, size // 14))
    elif name == "warning":
        draw.polygon([(cx, m), (size - m, size - m), (m, size - m)], outline=c)
        draw.line((cx, m + size * 0.28, cx, cy + size * 0.08), fill=c, width=max(2, size // 12))
        draw.ellipse((cx - 2, size - m - size * 0.16, cx + 2, size - m - size * 0.08), fill=c)
    elif name == "alert":
        draw.ellipse((m, m, size - m, size - m), outline=c, width=max(2, size // 14))
        draw.line((cx, m + size * 0.18, cx, cy + size * 0.06), fill=c, width=max(2, size // 12))
        draw.ellipse((cx - 2.5, cy + size * 0.14, cx + 2.5, cy + size * 0.22), fill=c)
    elif name == "gavel":
        draw.rounded_rectangle((cx - size * 0.28, m + 2, cx + size * 0.08, m + size * 0.28), radius=3, outline=c, width=max(2, size // 16))
        draw.line((cx - size * 0.06, m + size * 0.22, cx + size * 0.22, cy + size * 0.08), fill=c, width=max(2, size // 12))
        draw.line((m + 2, size - m, size - m, size - m), fill=c, width=max(3, size // 10))
    elif name == "user_x":
        draw.ellipse((cx - size * 0.14, m, cx + size * 0.14, m + size * 0.28), outline=c, width=max(2, size // 14))
        draw.arc((m, cy - 2, size * 0.62, size), 200, 340, fill=c, width=max(2, size // 14))
        draw.line((size * 0.62, cy, size - m, size - m), fill=c, width=max(2, size // 14))
        draw.line((size - m, cy, size * 0.62, size - m), fill=c, width=max(2, size // 14))
    elif name == "spark":
        draw.line((cx, m, cx, size - m), fill=c, width=max(2, size // 14))
        draw.line((m, cy, size - m, cy), fill=c, width=max(2, size // 14))
        draw.line((m + 4, m + 4, size - m - 4, size - m - 4), fill=c, width=max(2, size // 18))
        draw.line((m + 4, size - m - 4, size - m - 4, m + 4), fill=c, width=max(2, size // 18))
    elif name == "arrow":
        draw.line((m, cy, size - m - 4, cy), fill=c, width=max(3, size // 10))
        draw.polygon([(size - m + 2, cy), (size - m - size * 0.22, cy - size * 0.16), (size - m - size * 0.22, cy + size * 0.16)], fill=c)
    elif name == "plug":
        draw.rounded_rectangle((cx - size * 0.16, cy, cx + size * 0.16, size - m), radius=3, outline=c, width=max(2, size // 14))
        draw.line((cx - size * 0.08, m, cx - size * 0.08, cy), fill=c, width=max(2, size // 12))
        draw.line((cx + size * 0.08, m, cx + size * 0.08, cy), fill=c, width=max(2, size // 12))
        draw.line((m, cy, size - m, cy), fill=c, width=max(2, size // 14))
    elif name == "check":
        draw.line((m + 2, cy, cx - size * 0.04, size - m - 2), fill=c, width=max(3, size // 10))
        draw.line((cx - size * 0.04, size - m - 2, size - m, m + size * 0.12), fill=c, width=max(3, size // 10))
    elif name == "layers":
        draw.polygon([(cx, m), (size - m, cy - 2), (cx, cy + size * 0.16), (m, cy - 2)], outline=c)
        draw.line((m, cy + 4, cx, size - m), fill=c, width=max(2, size // 16))
        draw.line((size - m, cy + 4, cx, size - m), fill=c, width=max(2, size // 16))
    elif name == "stamp":
        draw.ellipse((m, m, size - m, size - m), outline=c, width=max(3, size // 10))
        draw.ellipse((m + size * 0.12, m + size * 0.12, size - m - size * 0.12, size - m - size * 0.12), outline=c, width=max(2, size // 16))
    elif name == "globe":
        draw.ellipse((m, m, size - m, size - m), outline=c, width=max(2, size // 14))
        draw.ellipse((cx - size * 0.16, m, cx + size * 0.16, size - m), outline=c, width=max(2, size // 16))
        draw.arc((m, cy - size * 0.12, size - m, cy + size * 0.12), 0, 360, fill=c, width=max(2, size // 16))
    elif name == "heart":
        draw.ellipse((cx - size * 0.28, m + 2, cx, cy), fill=c)
        draw.ellipse((cx, m + 2, cx + size * 0.28, cy), fill=c)
        draw.polygon([(m + size * 0.08, cy - 2), (size - m - size * 0.08, cy - 2), (cx, size - m)], fill=c)
    else:
        draw.ellipse((m, m, size - m, size - m), outline=c, width=2)

    _ICON_CACHE[key] = image
    return image


def icon_badge(name: str, diameter: int, tone: str) -> Image.Image:
    tone_rgb = TONES[tone]["bar"]
    plate = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    draw.ellipse((0, 0, diameter - 1, diameter - 1), fill=TONES[tone]["soft"])
    glyph = icon(name, int(diameter * 0.62), tone_rgb)
    plate.alpha_composite(glyph, ((diameter - glyph.width) // 2, (diameter - glyph.height) // 2))
    return plate


def corner_ticks(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color, length: int = 12) -> None:
    x0, y0, x1, y1 = box
    w = 2
    pairs = (
        ((x0, y0, x0 + length, y0), (x0, y0, x0, y0 + length)),
        ((x1 - length, y0, x1, y0), (x1, y0, x1, y0 + length)),
        ((x0, y1, x0 + length, y1), (x0, y1 - length, x0, y1)),
        ((x1 - length, y1, x1, y1), (x1, y1 - length, x1, y1)),
    )
    for a, b in pairs:
        draw.line(a, fill=color, width=w)
        draw.line(b, fill=color, width=w)


def new_card(height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    card = Image.new("RGBA", (WIDTH - 56, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=28, fill=PAPER)
    return card, draw


def paste_shadow_and_card(frame: Image.Image, card: Image.Image, y: int, opacity: float, enter: float) -> None:
    dy = int((1 - enter) * 26)
    y += dy
    shade = shadow(card.size, 28)
    frame.alpha_composite(apply_opacity(shade, opacity), (28 - 28, y - 28))
    frame.alpha_composite(apply_opacity(card, opacity), (28, y))


def draw_kicker(draw, x, y, text, tone) -> int:
    bar = TONES[tone]["bar"]
    draw.rounded_rectangle((x, y + 4, x + 18, y + 8), radius=2, fill=bar)
    draw.text((x + 26, y), text.upper(), font=FONTS["kicker"], fill=bar)
    return y + 32


def draw_speech(draw, card_w, y, text, max_w) -> int:
    lines = wrap(draw, text, FONTS["speech"], max_w)
    draw.rounded_rectangle((28, y, 33, y + 8 + 26 * len(lines)), radius=2, fill=(15, 138, 132, 255))
    for i, line in enumerate(lines):
        draw.text((44, y + i * 26), line, font=FONTS["speech"], fill=MUTED)
    return y + 26 * len(lines) + 8


def render_hero(scene, local) -> Image.Image:
    title_lines = scene["title"].split("\n")
    title_font = FONTS["title"] if len(title_lines) == 1 and len(scene["title"]) < 16 else FONTS["title_sm"]
    line_h = 58 if title_font is FONTS["title"] else 44
    note_h = 64 if scene.get("note") else 0
    height = 36 + 32 + line_h * len(title_lines) + 36 + 8 + 70 + note_h + 24
    card, draw = new_card(height)
    tone = scene["tone"]
    draw.rounded_rectangle((0, 0, 8, height), radius=0, fill=TONES[tone]["bar"])
    y = 28
    y = draw_kicker(draw, 32, y, scene["kicker"], tone)
    badge = icon_badge(scene["icon"], 64, tone)
    # Title block sits left of nothing; icon floats on the right of the first line.
    card.alpha_composite(badge, (card.width - 92, 28))
    for line in title_lines:
        draw.text((32, y), line, font=title_font, fill=INK)
        y += line_h
    y += 4
    draw.text((32, y), scene["subtitle"], font=FONTS["subtitle"], fill=MUTED)
    y += 40
    if scene.get("note"):
        p = revealed(local, scene["note_at"] - scene["start"])
        if p > 0:
            note = scene["note"]
            nw, nh = text_size(draw, note, FONTS["body_b"])
            chip_w = nw + 62
            chip = Image.new("RGBA", (chip_w, 44), (0, 0, 0, 0))
            cd = ImageDraw.Draw(chip)
            cd.rounded_rectangle((0, 0, chip_w - 1, 43), radius=22, fill=TONES[tone]["soft"])
            glyph = icon(scene["note_icon"], 26, TONES[tone]["bar"])
            chip.alpha_composite(glyph, (12, 9))
            cd.text((42, 8), note, font=FONTS["body_b"], fill=TONES[tone]["ink"])
            card.alpha_composite(apply_opacity(chip, p), (32, y))
        y += 56
    draw_speech(draw, card.width, y, scene["speech"], card.width - 80)
    corner_ticks(draw, (16, 16, card.width - 17, height - 17), (*TONES[tone]["bar"][:3], 140))
    return card


def render_stats(scene, local) -> Image.Image:
    height = 300
    card, draw = new_card(height)
    tone = scene["tone"]
    draw.rounded_rectangle((0, 0, 8, height), fill=TONES[tone]["bar"])
    y = draw_kicker(draw, 32, 24, scene["kicker"], tone)
    gap = 12
    tile_w = (card.width - 64 - gap * 2) // 3
    tile_y = y + 8
    for index, item in enumerate(scene["items"]):
        p = revealed(local, item["at"])
        x = 32 + index * (tile_w + gap)
        tile = Image.new("RGBA", (tile_w, 128), (0, 0, 0, 0))
        td = ImageDraw.Draw(tile)
        td.rounded_rectangle((0, 0, tile_w - 1, 127), radius=18, fill=(255, 255, 255, 255))
        td.rounded_rectangle((0, 0, tile_w - 1, 6), radius=0, fill=TONES["teal" if index < 2 else "gold"]["bar"])
        accent = TONES["teal" if index < 2 else "gold"]["bar"]
        glyph = icon(item["icon"], 22, accent)
        tile.alpha_composite(glyph, (tile_w - 34, 12))
        shown = item["text"]
        if isinstance(item["value"], int):
            shown_n = max(0, int(round(item["value"] * p))) if p < 1 else item["value"]
            shown = f"{shown_n} ч" if item["text"].endswith("ч") else str(shown_n)
        td.text((14, 32), shown, font=FONTS["num_sm"], fill=INK)
        label_y = 84
        for line in item["label"].split("\n"):
            td.text((14, label_y), line, font=FONTS["tiny"], fill=MUTED)
            label_y += 18
        card.alpha_composite(apply_opacity(tile, max(0.15, p) if local + 0.01 >= item["at"] else 0.0), (x, tile_y))
        # pop from a slightly lower spot is handled by opacity; add a scale via crop if early
        if 0 < p < 1:
            pass
    draw_speech(draw, card.width, 214, scene["speech"], card.width - 80)
    corner_ticks(draw, (16, 16, card.width - 17, height - 17), (20, 32, 40, 90))
    return card


def render_alert(scene, local) -> Image.Image:
    height = 318
    card, draw = new_card(height)
    tone = scene["tone"]
    draw.rounded_rectangle((0, 0, 8, height), fill=TONES[tone]["bar"])
    badge = icon_badge(scene["icon"], 72, tone)
    pulse = 0.5 + 0.5 * math.sin(local * 5.2)
    ring = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((4, 4, 91, 91), outline=(*TONES[tone]["bar"][:3], int(80 + 120 * pulse)), width=3)
    card.alpha_composite(apply_opacity(ring, 0.9), (card.width - 124, 22))
    card.alpha_composite(badge, (card.width - 112, 34))
    y = draw_kicker(draw, 32, 28, scene["kicker"], tone)
    for line in scene["title"].split("\n"):
        draw.text((32, y), line, font=FONTS["title"], fill=TONES[tone]["ink"])
        y += 54
    draw.text((32, y + 4), scene["subtitle"], font=FONTS["subtitle"], fill=MUTED)
    draw_speech(draw, card.width, y + 48, scene["speech"], card.width - 80)
    corner_ticks(draw, (16, 16, card.width - 17, height - 17), (*TONES[tone]["bar"][:3], 150))
    return card


def chip_image(text: str, icon_name: str, tone: str, filled: bool) -> Image.Image:
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw, _ = text_size(probe, text, FONTS["body_b"])
    width = tw + 64
    chip = Image.new("RGBA", (width, 48), (0, 0, 0, 0))
    draw = ImageDraw.Draw(chip)
    fill = TONES[tone]["bar"] if filled else (255, 255, 255, 255)
    ink = WHITE if filled else TONES[tone]["ink"]
    outline = TONES[tone]["bar"]
    draw.rounded_rectangle((0, 0, width - 1, 47), radius=24, fill=fill, outline=outline, width=2)
    glyph_color = WHITE if filled else TONES[tone]["bar"]
    chip.alpha_composite(icon(icon_name, 24, glyph_color), (14, 12))
    draw.text((44, 10), text, font=FONTS["body_b"], fill=ink)
    return chip


def render_equation(scene, local) -> Image.Image:
    height = 292
    card, draw = new_card(height)
    tone = scene["tone"]
    draw.rounded_rectangle((0, 0, 8, height), fill=TONES[tone]["bar"])
    y = draw_kicker(draw, 32, 22, scene["kicker"], tone)
    x = 32
    for index, item in enumerate(scene["items"]):
        p = revealed(local, item["at"])
        chip = chip_image(item["text"], item["icon"], "ink", False)
        card.alpha_composite(apply_opacity(chip, p), (x, y))
        x += chip.width + 10
        if index == 0:
            plus = Image.new("RGBA", (28, 48), (0, 0, 0, 0))
            ImageDraw.Draw(plus).text((4, 8), "+", font=FONTS["title_sm"], fill=MUTED)
            card.alpha_composite(apply_opacity(plus, p), (x, y - 4))
            x += 32
    y += 62
    # arrow down
    arrow_p = revealed(local, 1.7)
    draw.line((70, y, 70, y + 18), fill=(*TONES[tone]["bar"][:3], int(255 * arrow_p)), width=3)
    if arrow_p > 0:
        draw.polygon([(70, y + 26), (64, y + 16), (76, y + 16)], fill=(*TONES[tone]["bar"][:3], int(255 * arrow_p)))
    y += 36
    x = 32
    for item in scene["results"]:
        p = revealed(local, item["at"])
        chip = chip_image(item["text"], item["icon"], tone, True)
        card.alpha_composite(apply_opacity(chip, p), (x, y))
        x += chip.width + 12
        if x > card.width - 40:
            break
    draw_speech(draw, card.width, height - 72, scene["speech"], card.width - 80)
    corner_ticks(draw, (16, 16, card.width - 17, height - 17), (*TONES[tone]["bar"][:3], 140))
    return card


def render_compare(scene, local) -> Image.Image:
    height = 318
    card, draw = new_card(height)
    tone = scene["tone"]
    draw.rounded_rectangle((0, 0, 8, height), fill=TONES[tone]["bar"])
    badge = icon_badge(scene["icon"], 58, tone)
    card.alpha_composite(badge, (card.width - 86, 22))
    y = draw_kicker(draw, 32, 24, scene["kicker"], tone)
    draw.text((32, y), scene["title"], font=FONTS["title_sm"], fill=INK)
    y += 58
    box_w = (card.width - 64 - 64) // 2
    before_p = revealed(local, scene["before"]["at"])
    after_p = revealed(local, scene["after"]["at"])

    def value_box(text, label, active: bool) -> Image.Image:
        box = Image.new("RGBA", (box_w, 100), (0, 0, 0, 0))
        bd = ImageDraw.Draw(box)
        if active:
            bd.rounded_rectangle((0, 0, box_w - 1, 99), radius=20, fill=TONES["teal"]["bar"])
            main, sub = WHITE, (226, 244, 241, 255)
        else:
            bd.rounded_rectangle((0, 0, box_w - 1, 99), radius=20, fill=(232, 226, 218, 255))
            main, sub = (90, 96, 102, 255), MUTED
        bd.text((16, 14), text, font=FONTS["num"], fill=main)
        bd.text((16, 70), label.upper(), font=FONTS["tiny"], fill=sub)
        return box

    left = value_box(scene["before"]["value"], scene["before"]["label"], False)
    right = value_box(scene["after"]["value"], scene["after"]["label"], True)
    card.alpha_composite(apply_opacity(left, before_p), (32, y))
    # arrow grows between the boxes
    ax = 32 + box_w + 8
    arrow = icon("arrow", 44, TONES["teal"]["bar"])
    card.alpha_composite(apply_opacity(arrow, after_p), (ax, y + 28))
    card.alpha_composite(apply_opacity(right, after_p), (32 + box_w + 64, y))
    draw_speech(draw, card.width, height - 78, scene["speech"], card.width - 80)
    corner_ticks(draw, (16, 16, card.width - 17, height - 17), (*TONES[tone]["bar"][:3], 140))
    return card


def render_checks(scene, local) -> Image.Image:
    height = 36 + 40 + len(scene["items"]) * 78 + 90
    card, draw = new_card(height)
    tone = scene["tone"]
    draw.rounded_rectangle((0, 0, 8, height), fill=TONES[tone]["bar"])
    y = draw_kicker(draw, 32, 24, scene["kicker"], tone)
    for item in scene["items"]:
        p = revealed(local, item["at"])
        row = Image.new("RGBA", (card.width - 64, 66), (0, 0, 0, 0))
        rd = ImageDraw.Draw(row)
        rd.rounded_rectangle((0, 0, row.width - 1, 65), radius=16, fill=(255, 255, 255, 255))
        mark = Image.new("RGBA", (36, 36), (0, 0, 0, 0))
        md = ImageDraw.Draw(mark)
        md.ellipse((0, 0, 35, 35), fill=TONES[tone]["bar"])
        mark.alpha_composite(icon(item["icon"], 22, WHITE), (7, 7))
        row.alpha_composite(mark, (14, 15))
        rd.text((62, 18), item["text"], font=FONTS["body_b"], fill=INK)
        card.alpha_composite(apply_opacity(row, p), (32, y))
        y += 78
    draw_speech(draw, card.width, height - 72, scene["speech"], card.width - 80)
    corner_ticks(draw, (16, 16, card.width - 17, height - 17), (*TONES[tone]["bar"][:3], 140))
    return card


def stamp_image() -> Image.Image:
    size = 118
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    red = (176, 42, 48, 230)
    draw.ellipse((4, 4, size - 5, size - 5), outline=red, width=4)
    draw.ellipse((14, 14, size - 15, size - 15), outline=red, width=2)
    draw.text((22, 46), "ПЕЧАТЬ", font=FONTS["stamp"], fill=red)
    return image.rotate(-14, expand=True, resample=Image.Resampling.BICUBIC)


_STAMP: Image.Image | None = None


def render_flow(scene, local) -> Image.Image:
    height = 360
    card, draw = new_card(height)
    tone = scene["tone"]
    draw.rounded_rectangle((0, 0, 8, height), fill=TONES[tone]["bar"])
    y = draw_kicker(draw, 32, 22, scene["kicker"], tone)
    lead_p = revealed(local, scene["lead_at"])
    lead = Image.new("RGBA", (card.width - 64, 64), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lead)
    ld.rounded_rectangle((0, 0, lead.width - 1, 63), radius=16, fill=TONES["teal"]["soft"])
    lead.alpha_composite(icon("layers", 28, TONES["teal"]["bar"]), (14, 18))
    lines = wrap(ld, scene["lead"], FONTS["body_b"], lead.width - 70)
    for i, line in enumerate(lines):
        ld.text((52, 10 + i * 24), line, font=FONTS["body_b"], fill=TONES["teal"]["ink"])
    card.alpha_composite(apply_opacity(lead, lead_p), (32, y))
    y += 80
    draw.text((32, y), "Врачу остаётся", font=FONTS["subtitle"], fill=MUTED)
    y += 36
    for index, step in enumerate(scene["steps"], start=1):
        p = revealed(local, step["at"])
        row = Image.new("RGBA", (card.width - 210, 40), (0, 0, 0, 0))
        rd = ImageDraw.Draw(row)
        rd.ellipse((0, 4, 28, 32), fill=TONES[tone]["bar"])
        rd.text((8, 6), str(index), font=FONTS["body_b"], fill=WHITE)
        rd.text((40, 6), step["text"], font=FONTS["body_b"], fill=INK)
        card.alpha_composite(apply_opacity(row, p), (32, y))
        y += 44
    stamp_p = revealed(local, scene["stamp_at"], 0.45)
    if stamp_p > 0:
        global _STAMP
        if _STAMP is None:
            _STAMP = stamp_image()
        # scale pop
        scale = 0.72 + 0.28 * stamp_p
        sw = max(1, int(_STAMP.width * scale))
        sh = max(1, int(_STAMP.height * scale))
        stamped = _STAMP.resize((sw, sh), Image.Resampling.BICUBIC)
        card.alpha_composite(apply_opacity(stamped, stamp_p), (card.width - sw - 24, 168))
    draw_speech(draw, card.width, height - 72, scene["speech"], card.width - 80)
    corner_ticks(draw, (16, 16, card.width - 17, height - 17), (*TONES[tone]["bar"][:3], 140))
    return card


def render_trust(scene, local) -> Image.Image:
    height = 286
    card, draw = new_card(height)
    tone = scene["tone"]
    draw.rounded_rectangle((0, 0, 8, height), fill=TONES[tone]["bar"])
    # orbiting dots around the globe — a "different countries" marker
    orbit = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    od = ImageDraw.Draw(orbit)
    for i in range(8):
        ang = local * 0.9 + i * (math.tau / 8)
        ox = 60 + math.cos(ang) * 48
        oy = 60 + math.sin(ang) * 48
        dot_r = 4 if i % 2 == 0 else 3
        od.ellipse((ox - dot_r, oy - dot_r, ox + dot_r, oy + dot_r), fill=TONES[tone]["bar"])
    card.alpha_composite(orbit, (card.width - 140, 16))
    card.alpha_composite(icon_badge(scene["icon"], 72, tone), (card.width - 116, 40))
    y = draw_kicker(draw, 32, 28, scene["kicker"], tone)
    for line in scene["title"].split("\n"):
        draw.text((32, y), line, font=FONTS["title_sm"], fill=INK)
        y += 42
    draw.text((32, y + 4), scene["subtitle"], font=FONTS["subtitle"], fill=TONES[tone]["ink"])
    draw_speech(draw, card.width, height - 76, scene["speech"], card.width - 80)
    corner_ticks(draw, (16, 16, card.width - 17, height - 17), (*TONES[tone]["bar"][:3], 140))
    return card


def render_finale(scene, local) -> Image.Image:
    height = 340
    card, draw = new_card(height)
    tone = scene["tone"]
    draw.rounded_rectangle((0, 0, 8, height), fill=TONES[tone]["bar"])
    y = 28
    for item in scene["items"]:
        p = revealed(local, item["at"])
        if item.get("badge"):
            row = Image.new("RGBA", (card.width - 64, 64), (0, 0, 0, 0))
            rd = ImageDraw.Draw(row)
            rd.rounded_rectangle((0, 0, 250, 63), radius=32, fill=TONES[tone]["bar"])
            row.alpha_composite(icon(item["icon"], 28, WHITE), (18, 18))
            rd.text((56, 16), item["text"], font=FONTS["title_sm"], fill=WHITE)
            card.alpha_composite(apply_opacity(row, p), (32, y))
            y += 78
        else:
            row = Image.new("RGBA", (card.width - 64, 48), (0, 0, 0, 0))
            rd = ImageDraw.Draw(row)
            row.alpha_composite(icon(item["icon"], 28, TONES[tone]["bar"]), (0, 8))
            rd.text((42, 8), item["text"], font=FONTS["body_b"], fill=INK)
            card.alpha_composite(apply_opacity(row, p), (32, y))
            y += 52
    thanks_p = revealed(local, scene["thanks_at"], 0.4)
    if thanks_p > 0:
        draw.text((32, y + 6), scene["thanks"], font=FONTS["thanks"], fill=TONES[tone]["ink"])
    corner_ticks(draw, (16, 16, card.width - 17, height - 17), (*TONES[tone]["bar"][:3], 150))
    return card


RENDERERS = {
    "hero": render_hero,
    "stats": render_stats,
    "alert": render_alert,
    "equation": render_equation,
    "compare": render_compare,
    "checks": render_checks,
    "flow": render_flow,
    "trust": render_trust,
    "finale": render_finale,
}


def render_section(name: str) -> Image.Image:
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw, _ = text_size(probe, name.upper(), FONTS["section"])
    width = tw + 58
    chip = Image.new("RGBA", (width, 44), (0, 0, 0, 0))
    draw = ImageDraw.Draw(chip)
    draw.rounded_rectangle((0, 0, width - 1, 43), radius=22, fill=(16, 24, 30, 214))
    draw.ellipse((14, 16, 26, 28), fill=(232, 184, 109, 255))
    draw.text((36, 10), name.upper(), font=FONTS["section"], fill=WHITE)
    return chip


def render_marker(marker: dict) -> Image.Image:
    tone = marker["tone"]
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw, _ = text_size(probe, marker["text"], FONTS["chip"])
    width = tw + 58
    chip = Image.new("RGBA", (width, 46), (0, 0, 0, 0))
    draw = ImageDraw.Draw(chip)
    draw.rounded_rectangle((0, 0, width - 1, 45), radius=23, fill=(16, 24, 30, 220))
    draw.rounded_rectangle((0, 0, 6, 45), radius=3, fill=TONES[tone]["bar"])
    chip.alpha_composite(icon(marker["icon"], 22, TONES[tone]["bar"]), (16, 12))
    draw.text((44, 10), marker["text"], font=FONTS["chip"], fill=WHITE)
    return chip


def active_section(t: float) -> tuple[str, float, float] | None:
    best = None
    for scene in SCENES:
        opacity, enter, _ = phase(t, scene["start"], scene["end"])
        if opacity <= 0:
            continue
        if best is None or opacity > best[1]:
            best = (scene["section"], opacity, enter)
    return best


def compose_frame(t: float) -> Image.Image:
    frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    # Time rail along the top edge.
    draw.rectangle((0, 0, WIDTH, 6), fill=(16, 24, 30, 90))
    draw.rectangle((0, 0, int(WIDTH * min(1.0, t / DURATION)), 6), fill=(15, 138, 132, 230))

    section = active_section(t)
    if section:
        name, opacity, enter = section
        chip = render_section(name)
        frame.alpha_composite(apply_opacity(chip, opacity), (28, 28 + int((1 - enter) * 16)))

    # Up to two wall markers, newest first. Second chip wraps under the first
    # only when the pair would run off the right edge.
    visible = []
    for marker in MARKERS:
        opacity, enter, _ = phase(t, marker["start"], marker["end"], 0.22, 0.22)
        if opacity <= 0:
            continue
        visible.append((marker, opacity, enter))
    visible.sort(key=lambda item: item[0]["start"])
    x = 28
    y = 86
    row_h = 46
    for marker, opacity, enter in visible[-2:]:
        chip = render_marker(marker)
        if x > 28 and x + chip.width > WIDTH - 28:
            x = 28
            y += row_h + 8
        if y + row_h > WALL_BOTTOM:
            break
        frame.alpha_composite(
            apply_opacity(chip, opacity),
            (x, y + int((1 - enter) * 14)),
        )
        x += chip.width + 8

    cards = []
    for scene in SCENES:
        opacity, enter, local = phase(t, scene["start"], scene["end"])
        if opacity <= 0:
            continue
        card = RENDERERS[scene["kind"]](scene, local)
        cards.append((card, opacity, enter))

    for card, opacity, enter in cards:
        top = HEIGHT - CARD_BOTTOM_MARGIN - card.height
        if top < CARD_MIN_TOP:
            top = CARD_MIN_TOP
        paste_shadow_and_card(frame, card, top, opacity, enter)
    return frame


def extract_source_frame(video: Path, t: float, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(video),
            "-frames:v", "1", str(dest),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def preview(video: Path) -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    times = []
    for scene in SCENES:
        times.append((scene["start"] + scene["end"]) / 2)
    # Extra beats where a number, the stamp, or the thanks line lands.
    times.extend([8.3, 10.4, 19.2, 26.4, 38.8, 49.6])
    for index, t in enumerate(times):
        source_path = PREVIEW_DIR / f"_src_{index:02d}.jpg"
        extract_source_frame(video, min(t, DURATION - 0.05), source_path)
        base = Image.open(source_path).convert("RGBA")
        if base.size != (WIDTH, HEIGHT):
            base = base.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        over = compose_frame(t)
        base.alpha_composite(over)
        out = PREVIEW_DIR / f"frame_{index:02d}_t{t:05.2f}.jpg"
        base.convert("RGB").save(out, quality=90)
        source_path.unlink(missing_ok=True)
        print(f"preview {out.name}")


def render_video(video: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = int(round(DURATION * FPS))
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(FPS),
        "-i", "pipe:0",
        "-i", str(video),
        "-filter_complex", "[1:v][0:v]overlay=0:0:format=auto[v]",
        "-map", "[v]",
        "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ]
    log_path = output.with_suffix(".ffmpeg.log")
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
    assert proc.stdin is not None
    try:
        for index in range(frames):
            t = index / FPS
            frame = compose_frame(t)
            proc.stdin.write(frame.tobytes())
            if index % FPS == 0:
                print(f"frame {index}/{frames}  t={t:.1f}s", flush=True)
    finally:
        proc.stdin.close()
        code = proc.wait()
        log.close()
    if code != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise SystemExit(f"ffmpeg failed ({code})\n{tail}")
    print(f"wrote {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert the GENOMIQ overlay composition into a video.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--preview", action="store_true", help="Write stills instead of an mp4.")
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit(f"Source video not found: {args.input}")
    global FONTS
    FONTS = load_fonts()
    if args.preview:
        preview(args.input)
    else:
        render_video(args.input, args.output)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()

"""
generate_turf_images.py
------------------------
Generates every image TurfHub needs, entirely offline, using Pillow to
draw stylised football-pitch illustrations (mowed stripes, pitch
markings, floodlights) rather than downloading real photography. This
sidesteps licensing entirely and means the whole project — including
images — works with no internet connection, which is what the brief
asked for.

Run once to (re)populate static/images/:

    cd turfhub
    pip install Pillow --break-system-packages   # if not already installed
    python scripts/generate_turf_images.py

Output (all written to static/images/):
    turf-01.jpg .. turf-10.jpg   one per seed turf, matches turfs.id
    turf-gallery-1.jpg .. -4.jpg alternate photos a manager can switch to
    placeholder.jpg               fallback used when an image is missing
"""

import os
import sys
import math
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

from database import TURFS  

OUT_DIR = os.path.join(PROJECT_DIR, "static", "images")
FONT_BOLD = os.path.join(SCRIPT_DIR, "fonts", "BigShoulders-Bold.ttf")

W, H = 900, 560


PALETTES = [
    ((27, 74, 54), (34, 90, 65)),
    ((22, 66, 48), (30, 82, 59)),
    ((31, 79, 59), (40, 95, 71)),
    ((18, 58, 42), (26, 74, 54)),
    ((35, 84, 62), (44, 100, 74)),
]


def font(size):
    try:
        return ImageFont.truetype(FONT_BOLD, size)
    except OSError:
        return ImageFont.load_default()


def draw_stripes(draw, palette, w=W, h=H, band=46):
    light, dark = palette

    i = 0
    x = -h
    while x < w + h:
        color = light if i % 2 == 0 else dark
        draw.polygon(
            [(x, h), (x + h, 0), (x + h + band, 0), (x + band, h)],
            fill=color,
        )
        x += band
        i += 1


def draw_pitch_markings(draw, w=W, h=H, margin=46, alpha_img=None):
    line_color = (255, 255, 255, 130)
    lw = 3
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    
    od.rectangle([margin, margin, w - margin, h - margin], outline=line_color, width=lw)
    
    mid_x = w // 2
    od.line([(mid_x, margin), (mid_x, h - margin)], fill=line_color, width=lw)
    
    r = 70
    od.ellipse([mid_x - r, h // 2 - r, mid_x + r, h // 2 + r], outline=line_color, width=lw)
    od.ellipse([mid_x - 4, h // 2 - 4, mid_x + 4, h // 2 + 4], fill=line_color)
    
    box_w, box_h = 70, 220
    od.rectangle([margin, h // 2 - box_h // 2, margin + box_w, h // 2 + box_h // 2], outline=line_color, width=lw)
    od.rectangle([w - margin - box_w, h // 2 - box_h // 2, w - margin, h // 2 + box_h // 2], outline=line_color, width=lw)
    return overlay


def add_floodlights(base, w=W, h=H):
    draw = ImageDraw.Draw(base, "RGBA")
    positions = [(60, 40), (w - 60, 40)]
    for x, y in positions:
        
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([x - 90, y - 60, x + 90, y + 60], fill=(255, 227, 173, 70))
        glow = glow.filter(ImageFilter.GaussianBlur(30))
        base.alpha_composite(glow)
        draw = ImageDraw.Draw(base, "RGBA")
        
        draw.rectangle([x - 3, y, x + 3, y + 90], fill=(20, 24, 20, 255))
        draw.rectangle([x - 26, y - 14, x + 26, y + 6], fill=(30, 34, 30, 255))
        for lx in range(x - 20, x + 21, 10):
            draw.ellipse([lx - 3, y - 10, lx + 3, y - 4], fill=(255, 236, 190, 255))


def dusk_sky(base, w=W, h=H, band_h=150):
    grad = Image.new("RGBA", (w, band_h), (0, 0, 0, 0))
    top = (56, 40, 74)
    bottom = (20, 30, 30)
    for row in range(band_h):
        t = row / band_h
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        ImageDraw.Draw(grad).line([(0, row), (w, row)], fill=color + (255,))
    base.alpha_composite(grad, (0, 0))


def bottom_label_bar(base, title, subtitle, w=W, h=H):
    bar_h = 150
    grad = Image.new("RGBA", (w, bar_h), (0, 0, 0, 0))
    for row in range(bar_h):
        t = row / bar_h
        alpha = int(0 + t * 195)
        ImageDraw.Draw(grad).line([(0, row), (w, row)], fill=(10, 20, 15, alpha))
    base.alpha_composite(grad, (0, h - bar_h))

    draw = ImageDraw.Draw(base, "RGBA")
    draw.text((34, h - 108), title, font=font(46), fill=(255, 255, 255, 255))
    draw.text((36, h - 56), subtitle, font=font(24), fill=(230, 236, 224, 235))


def vignette(base, w=W, h=H):
    v = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(v)
    vd.ellipse([-w * 0.25, -h * 0.35, w * 1.25, h * 1.35], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(80))
    dark = Image.new("RGBA", (w, h), (5, 15, 10, 90))
    base.paste(Image.composite(Image.new("RGBA", (w, h), (0, 0, 0, 0)), dark, v), (0, 0), Image.new("L", (w, h), 255))


def make_turf_image(name, area, price, evening, palette, path, label=True):
    base = Image.new("RGBA", (W, H), palette[0] + (255,))
    draw = ImageDraw.Draw(base)
    draw_stripes(draw, palette)
    if evening:
        dusk_sky(base)
    markings = draw_pitch_markings(draw)
    base.alpha_composite(markings)
    if evening:
        add_floodlights(base)
    
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle([0, 0, W, H], fill=(0, 0, 0, 0))
    if label:
        bottom_label_bar(base, name, f"{area} · ₹{price}/hour", W, H)
    base.convert("RGB").save(path, "JPEG", quality=87)


def make_placeholder(path):
    palette = ((70, 78, 72), (84, 92, 86))  
    base = Image.new("RGBA", (W, H), palette[0] + (255,))
    draw = ImageDraw.Draw(base)
    draw_stripes(draw, palette, band=60)
    markings = draw_pitch_markings(draw)
    base.alpha_composite(markings)
    
    cx, cy, r = W // 2, H // 2 - 20, 46
    draw = ImageDraw.Draw(base, "RGBA")
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 235), outline=(40, 46, 40, 255), width=3)
    for ang in range(0, 360, 72):
        px = cx + int(r * 0.5 * math.cos(math.radians(ang)))
        py = cy + int(r * 0.5 * math.sin(math.radians(ang)))
        draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(40, 46, 40, 255))
    bottom_label_bar(base, "Image unavailable", "TurfHub could not load a photo for this turf", W, H)
    base.convert("RGB").save(path, "JPEG", quality=87)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    random.seed(7)

    for i, t in enumerate(TURFS, start=1):
        name, area, price = t[0], t[1], t[2]
        palette = PALETTES[(i - 1) % len(PALETTES)]
        evening = (i % 2 == 0)
        out_path = os.path.join(OUT_DIR, f"turf-{i:02d}.jpg")
        make_turf_image(name, area, price, evening, palette, out_path)
        print("wrote", out_path)

    
    for i in range(1, 5):
        palette = PALETTES[(i + 1) % len(PALETTES)]
        evening = (i % 2 == 0)
        out_path = os.path.join(OUT_DIR, f"turf-gallery-{i}.jpg")
        make_turf_image("", "", "", evening, palette, out_path, label=False)
        print("wrote", out_path)

    make_placeholder(os.path.join(OUT_DIR, "placeholder.jpg"))
    print("wrote", os.path.join(OUT_DIR, "placeholder.jpg"))


if __name__ == "__main__":
    main()

"""Render the profile's animated ASCII figure and logo from the source logo.

Usage:
    python3 scripts/render_assets.py path/to/logo.jpeg

Writes:
    assets/zedoox-hacker.gif  - looping ASCII animation (eye pulse, scan line, glyph flicker)
    assets/zedoox-logo.png    - circular-cropped logo for the README / avatar use

Requires Pillow. Uses DejaVu Sans Mono (falls back to Pillow's default font).
"""

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

BG = (8, 8, 8)
PANEL = (17, 17, 17)
BORDER = (41, 32, 32)
CRIMSON = (255, 30, 45)
DEEP_RED = (176, 0, 32)
DIM_RED = (92, 14, 22)
GRAY = (161, 161, 170)
WHITE = (245, 245, 245)

COLS = 76
CELL_W, CELL_H = 6, 11
FONT_SIZE = 10
FRAMES = 40
FRAME_MS = 75
RAMP = " .:-=+*#%@"
FLICKER_GLYPHS = "01<>/\\|#"

PAD_X, TITLE_H, FOOT_H = 14, 30, 30


def load_font(size, bold=False):
    names = ["DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"]
    for name in names:
        for base in ("/usr/share/fonts/truetype/dejavu/", ""):
            try:
                return ImageFont.truetype(base + name, size)
            except OSError:
                continue
    return ImageFont.load_default()


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def build_grid(logo):
    """Sample the logo into a grid of (char, intensity) cells."""
    rows = round(COLS * logo.height / logo.width * CELL_W / CELL_H)
    small = logo.convert("RGB").resize((COLS, rows), Image.LANCZOS)
    grid = []
    for y in range(rows):
        row = []
        for x in range(COLS):
            r, g, b = small.getpixel((x, y))
            # The logo is red-on-black: the red channel minus the others is the figure.
            v = max(0.0, min(1.0, (r - max(g, b) * 0.6 - 12) / 170)) ** 0.8
            ch = RAMP[min(len(RAMP) - 1, int(v * len(RAMP)))] if v > 0.04 else " "
            row.append((ch, v))
        grid.append(row)
    return grid, small


def find_eyes(small):
    """Locate the eye cells: bright red pixels in the face band of the logo."""
    w, h = small.size
    eyes = set()
    for y in range(int(h * 0.36), int(h * 0.44)):
        for x in range(int(w * 0.36), int(w * 0.64)):
            r, g, b = small.getpixel((x, y))
            if r > 150 and g < 80:
                eyes.add((x, y))
    return eyes


def render(logo_path):
    logo = Image.open(logo_path)
    grid, small = build_grid(logo)
    eyes = find_eyes(small)
    rows = len(grid)

    font = load_font(FONT_SIZE)
    font_bold = load_font(FONT_SIZE, bold=True)
    ui_font = load_font(11)

    art_w, art_h = COLS * CELL_W, rows * CELL_H
    W = art_w + PAD_X * 2
    H = TITLE_H + art_h + FOOT_H

    # Deterministic flicker schedule: a few glyphs swap briefly, same every loop.
    rng = random.Random(1337)
    lit = [(x, y) for y in range(rows) for x in range(COLS) if grid[y][x][0] != " " and (x, y) not in eyes]
    flicker = {f: rng.sample(lit, 6) for f in range(FRAMES)}

    prompt = "zedo0x@lab:~$ ./engage --scope authorized"
    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        pulse = 0.5 - 0.5 * math.cos(2 * math.pi * t)  # 0 -> 1 -> 0, seamless
        scan_y = t * (rows + 6) - 3  # scan band sweeps once per loop

        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)

        # Window chrome
        d.rectangle([0, 0, W - 1, H - 1], outline=BORDER)
        d.rectangle([1, 1, W - 2, TITLE_H - 1], fill=PANEL)
        d.line([1, TITLE_H - 1, W - 2, TITLE_H - 1], fill=BORDER)
        for i, c in enumerate((CRIMSON, DEEP_RED, BORDER)):
            cx = 16 + i * 15
            d.ellipse([cx - 4, 11, cx + 4, 19], fill=c)
        title = "zedo0x — tty0"
        tw = d.textlength(title, font=ui_font)
        d.text(((W - tw) / 2, 8), title, fill=GRAY, font=ui_font)

        # Eye glow layer, blurred under the text
        glow = Image.new("RGB", (W, H), (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for (x, y) in eyes:
            px, py = PAD_X + x * CELL_W, TITLE_H + y * CELL_H
            gd.rectangle([px - 3, py - 2, px + CELL_W + 3, py + CELL_H + 2], fill=mix((0, 0, 0), CRIMSON, 0.25 + 0.55 * pulse))
        glow = glow.filter(ImageFilter.GaussianBlur(7))
        img = ImageChops.add(img, glow)
        d = ImageDraw.Draw(img)

        # Scan band background
        band_top = TITLE_H + scan_y * CELL_H
        y0, y1 = max(TITLE_H, band_top), min(TITLE_H + art_h, band_top + CELL_H * 2)
        if y1 > y0:
            d.rectangle([2, y0, W - 3, y1], fill=(20, 10, 11))

        flick = set(flicker[f]) if f % 3 == 0 else set()
        for y, row in enumerate(grid):
            near_scan = abs(y - scan_y) < 1.5
            for x, (ch, v) in enumerate(row):
                if ch == " ":
                    continue
                px, py = PAD_X + x * CELL_W, TITLE_H + y * CELL_H
                if (x, y) in eyes:
                    color = mix(DEEP_RED, (255, 70, 80), pulse)
                    d.text((px, py), "@", fill=color, font=font_bold)
                    continue
                if v > 0.7:
                    color = CRIMSON
                elif v > 0.4:
                    color = mix(DEEP_RED, CRIMSON, (v - 0.4) / 0.3)
                else:
                    color = mix(DIM_RED, DEEP_RED, v / 0.4)
                if near_scan:
                    color = mix(color, WHITE, 0.35)
                if (x, y) in flick:
                    ch = FLICKER_GLYPHS[(x * 7 + y * 3 + f) % len(FLICKER_GLYPHS)]
                    color = mix(color, WHITE, 0.2)
                d.text((px, py), ch, fill=color, font=font)

        # Footer prompt with typed-out text and blinking cursor
        fy = TITLE_H + art_h + 8
        d.line([1, fy - 8, W - 2, fy - 8], fill=BORDER)
        typed = prompt[: min(len(prompt), int(len(prompt) * min(1.0, t / 0.6)))]
        user, _, rest = typed.partition("$")
        d.text((PAD_X, fy), user, fill=CRIMSON, font=ui_font)
        x = PAD_X + d.textlength(user, font=ui_font)
        if "$" in typed:
            d.text((x, fy), "$" + rest, fill=WHITE, font=ui_font)
            x += d.textlength("$" + rest, font=ui_font)
        if (f // 5) % 2 == 0:
            d.rectangle([x + 2, fy + 1, x + 8, fy + 13], fill=CRIMSON)

        frames.append(img)

    # Shared palette keeps frames consistent and the file small.
    palette_src = frames[FRAMES // 2].quantize(colors=64, method=Image.MEDIANCUT)
    pframes = [fr.quantize(palette=palette_src, dither=Image.Dither.NONE) for fr in frames]
    out = ASSETS / "zedoox-hacker.gif"
    pframes[0].save(out, save_all=True, append_images=pframes[1:], duration=FRAME_MS, loop=0, optimize=True, disposal=1)
    return out, (W, H)


def render_logo(logo_path, size=400):
    src = Image.open(logo_path).convert("RGB")
    side = min(src.size)
    src = src.crop(((src.width - side) // 2, (src.height - side) // 2, (src.width + side) // 2, (src.height + side) // 2))
    scale = 4  # supersample for a smooth circular edge
    big = src.resize((size * scale, size * scale), Image.LANCZOS)
    mask = Image.new("L", big.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, big.width - 1, big.height - 1], fill=255)
    ring = ImageDraw.Draw(big)
    ring.ellipse([6, 6, big.width - 7, big.height - 7], outline=DEEP_RED, width=10)
    out_img = Image.new("RGBA", big.size, (0, 0, 0, 0))
    out_img.paste(big, (0, 0), mask)
    out_img = out_img.resize((size, size), Image.LANCZOS)
    out = ASSETS / "zedoox-logo.png"
    out_img.save(out, optimize=True)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ASSETS.mkdir(exist_ok=True)
    gif, dims = render(sys.argv[1])
    logo = render_logo(sys.argv[1])
    print(f"{gif} {dims[0]}x{dims[1]}")
    print(logo)

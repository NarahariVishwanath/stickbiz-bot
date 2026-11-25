"""Illustrated B-roll scenes for the StickBiz Short v2 look (all drawn in code, no stock footage).

scene(name, t) -> RGBA image of PANEL_W x PANEL_H for time t (seconds since the beat started).
Static parts are drawn once at 2x and cached; moving parts are drawn per frame.
"""
import math
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PANEL_W, PANEL_H = 1080, 880
S = 2  # supersampling for the cached static layers

import os
F = os.environ.get("STICKBIZ_FONTS", "C:/Windows/Fonts/").rstrip("/\\") + "/"
def font(name, size):
    try:
        return ImageFont.truetype(F + name, size)
    except OSError:
        alt = {"seguibl.ttf": "ariblk.ttf", "segoeuib.ttf": "arialbd.ttf", "seguisb.ttf": "arialbd.ttf"}.get(name, "arial.ttf")
        return ImageFont.truetype(F + alt, size)
BLACK = lambda s: font("seguibl.ttf", s)
BOLD = lambda s: font("segoeuib.ttf", s)
SEMI = lambda s: font("seguisb.ttf", s)


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def gradient(w, h, top, bot, horizontal=False):
    g = np.linspace(0, 1, w if horizontal else h)
    g = g[None, :, None] if horizontal else g[:, None, None]
    arr = np.array(top)[None, None, :] * (1 - g) + np.array(bot)[None, None, :] * g
    arr = np.broadcast_to(arr, (h, w, 3)).astype(np.uint8)
    return Image.fromarray(np.ascontiguousarray(arr), "RGB")


def glow(img, xy, r, col, alpha=90, steps=8):
    d = ImageDraw.Draw(img, "RGBA")
    x, y = xy
    for i in range(steps, 0, -1):
        rr = r * i / steps
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=col + (int(alpha / steps),))


def text_c(d, cx, y, txt, f, fill, stroke=0, sfill=(0, 0, 0)):
    w = d.textlength(txt, font=f)
    d.text((cx - w / 2, y), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)


# ----------------------------------------------------------------------------
# static layers (2x, cached)
# ----------------------------------------------------------------------------
def _canvas(top, bot):
    return gradient(PANEL_W * S, PANEL_H * S, top, bot)


def _columns_building(d, cx, base_y, w, h, n_cols, stone, shade, sign=None, s=S):
    """A generic classical facade: steps, columns, pediment."""
    x0, x1 = cx - w / 2, cx + w / 2
    top = base_y - h
    for i in range(4):  # steps
        d.rectangle([x0 - 40 * s + i * 12 * s, base_y - (i + 1) * 16 * s, x1 + 40 * s - i * 12 * s, base_y - i * 16 * s],
                    fill=tuple(max(0, c - 10 * i) for c in stone))
    plinth = base_y - 64 * s
    d.rectangle([x0, top + 0.28 * h, x1, plinth], fill=shade)  # dark interior behind columns
    cw = w / (n_cols * 2 - 1)
    for i in range(n_cols):
        xx = x0 + i * 2 * cw
        d.rectangle([xx, top + 0.28 * h, xx + cw, plinth], fill=stone)
        for k in range(1, 4):  # flutes
            d.line([xx + k * cw / 4, top + 0.3 * h, xx + k * cw / 4, plinth - 6 * s], fill=tuple(c - 25 for c in stone), width=2 * s)
        d.rectangle([xx - 8 * s, top + 0.26 * h, xx + cw + 8 * s, top + 0.29 * h], fill=stone)
    d.rectangle([x0 - 30 * s, top + 0.16 * h, x1 + 30 * s, top + 0.27 * h], fill=stone)  # entablature
    d.polygon([(x0 - 50 * s, top + 0.16 * h), (cx, top - 0.05 * h), (x1 + 50 * s, top + 0.16 * h)], fill=stone)
    d.polygon([(x0 + 20 * s, top + 0.14 * h), (cx, top + 0.0 * h), (x1 - 20 * s, top + 0.14 * h)],
              fill=tuple(c - 18 for c in stone))
    if sign:
        f = BLACK(int(0.07 * h))
        text_c(d, cx, top + 0.165 * h, sign, f, (70, 70, 80))


@lru_cache(maxsize=None)
def static(name):
    W, H = PANEL_W * S, PANEL_H * S
    rng = np.random.default_rng(abs(hash(name)) % 1000)
    if name == "exchange":  # Wall Street style exchange building
        im = _canvas((120, 170, 225), (225, 235, 245))
        d = ImageDraw.Draw(im, "RGBA")
        for i in range(9):  # towers behind
            x = rng.integers(0, W)
            w = rng.integers(120, 260) * S / 2
            h = rng.integers(500, 1300)
            d.rectangle([x, H - h - 200 * S, x + w, H], fill=(150, 165, 185, 255))
            for wy in range(int(H - h - 180 * S), H, 40 * S):
                for wx in range(int(x + 14 * S), int(x + w - 14 * S), 34 * S):
                    d.rectangle([wx, wy, wx + 16 * S, wy + 20 * S], fill=(185, 200, 220))
        _columns_building(d, W / 2, H - 40 * S, 760 * S, 700 * S, 6, (232, 226, 214), (60, 58, 66), "STOCK EXCHANGE")
        d.rectangle([0, H - 40 * S, W, H], fill=(120, 118, 115))
        for fx in (W * 0.29, W * 0.71):  # banners
            d.rectangle([fx - 50 * S, H - 520 * S, fx + 50 * S, H - 300 * S], fill=(25, 60, 140))
            for k in range(5):
                d.rectangle([fx - 50 * S, H - 520 * S + k * 44 * S, fx + 50 * S, H - 500 * S + k * 44 * S], fill=(200, 40, 50))
        return im
    if name == "city":  # Indian city skyline at sunrise
        im = _canvas((255, 150, 80), (255, 225, 170))
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([W * 0.62, H * 0.18, W * 0.62 + 260 * S, H * 0.18 + 260 * S], fill=(255, 245, 210))
        for layer, (col, hmin, hmax) in enumerate(((150, 90, 110), (110, 60, 90), (60, 35, 70))):
            x = -50 * S
            while x < W:
                w = rng.integers(90, 200) * S
                h = rng.integers(hmin, hmax) * S
                y = H - h
                d.rectangle([x, y, x + w, H], fill=col)
                if layer == 2:
                    for wy in range(int(y + 20 * S), H - 20 * S, 36 * S):
                        for wx in range(int(x + 14 * S), int(x + w - 20 * S), 30 * S):
                            if rng.random() < 0.45:
                                d.rectangle([wx, wy, wx + 12 * S, wy + 16 * S], fill=(255, 205, 120))
                if rng.random() < 0.25:  # spire / dome
                    d.polygon([(x + w / 2 - 8 * S, y), (x + w / 2, y - 90 * S), (x + w / 2 + 8 * S, y)], fill=col)
                x += w + rng.integers(-20, 25) * S
            hmin, hmax = hmin, hmax
        return im
    if name == "capitol":  # a domed government building (generic)
        im = _canvas((70, 110, 170), (200, 215, 235))
        d = ImageDraw.Draw(im, "RGBA")
        cx = W / 2
        base_y = H - 40 * S
        _columns_building(d, cx, base_y, 900 * S, 420 * S, 8, (238, 236, 230), (70, 70, 85))
        top = base_y - 420 * S
        d.rectangle([cx - 230 * S, top - 170 * S, cx + 230 * S, top], fill=(232, 230, 222))  # drum
        for k in range(9):
            xx = cx - 210 * S + k * 52 * S
            d.rectangle([xx, top - 150 * S, xx + 22 * S, top - 20 * S], fill=(200, 198, 190))
        d.pieslice([cx - 260 * S, top - 430 * S, cx + 260 * S, top - 90 * S], 180, 360, fill=(240, 238, 232))
        d.rectangle([cx - 30 * S, top - 330 * S, cx + 30 * S, top - 260 * S], fill=(232, 230, 222))
        d.polygon([(cx - 22 * S, top - 330 * S), (cx, top - 400 * S), (cx + 22 * S, top - 330 * S)], fill=(232, 230, 222))
        d.rectangle([0, base_y, W, H], fill=(110, 130, 110))
        return im
    if name == "bank":
        im = _canvas((190, 215, 235), (240, 245, 250))
        d = ImageDraw.Draw(im, "RGBA")
        _columns_building(d, W / 2, H - 40 * S, 700 * S, 640 * S, 5, (240, 240, 245), (40, 50, 70), "BANK")
        d.rectangle([0, H - 40 * S, W, H], fill=(130, 135, 145))
        return im
    if name == "boardroom":
        im = _canvas((70, 50, 40), (140, 100, 70))
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, 0, W, H * 0.45], fill=(55, 42, 38))
        for k in range(5):  # window panes
            x = W * 0.1 + k * W * 0.17
            d.rectangle([x, H * 0.06, x + W * 0.14, H * 0.38], fill=(120, 160, 200))
            d.rectangle([x, H * 0.06, x + W * 0.14, H * 0.38], outline=(40, 30, 28), width=10 * S)
        d.polygon([(W * 0.3, H * 0.5), (W * 0.7, H * 0.5), (W * 0.95, H), (W * 0.05, H)], fill=(95, 58, 35))
        d.polygon([(W * 0.31, H * 0.51), (W * 0.69, H * 0.51), (W * 0.92, H * 0.98), (W * 0.08, H * 0.98)], fill=(125, 78, 45))
        for i in range(5):  # chairs both sides
            f = i / 4
            y = H * (0.52 + 0.42 * f)
            r = (40 + 50 * f) * S
            for side in (-1, 1):
                xx = W / 2 + side * (W * (0.22 + 0.28 * f))
                d.rounded_rectangle([xx - r, y - r * 1.6, xx + r, y + r * 0.4], radius=int(r * 0.4), fill=(30, 25, 25))
        return im
    if name == "datacenter":
        im = _canvas((8, 14, 40), (20, 40, 90))
        d = ImageDraw.Draw(im, "RGBA")
        for row in range(4):
            f = row / 3
            y0 = H * (0.12 + 0.12 * f)
            h = H * (0.5 + 0.35 * f)
            w = (90 + 70 * f) * S
            for side in (-1, 1):
                for k in range(3):
                    cx = W / 2 + side * (W * (0.12 + 0.13 * k) * (0.6 + 0.6 * f))
                    d.rectangle([cx - w / 2, y0, cx + w / 2, y0 + h], fill=(28, 36, 60), outline=(60, 80, 130), width=3 * S)
                    for u in range(int(h / (26 * S))):
                        d.rectangle([cx - w / 2 + 8 * S, y0 + u * 26 * S + 6 * S, cx + w / 2 - 8 * S, y0 + u * 26 * S + 20 * S],
                                    fill=(38, 48, 78))
        d.polygon([(W * 0.42, H * 0.3), (W * 0.58, H * 0.3), (W * 0.9, H), (W * 0.1, H)], fill=(14, 22, 50))
        return im
    if name == "game":
        im = _canvas((40, 10, 70), (255, 80, 140))
        d = ImageDraw.Draw(im, "RGBA")
        cx, cy, r = W / 2, H * 0.62, 300 * S
        for k in range(8):  # striped retro sun
            y = cy - r + k * r / 5
            if y > cy:
                break
            half = math.sqrt(max(0, r * r - (cy - y) ** 2))
            d.rectangle([cx - half, y, cx + half, y + r / 7], fill=(255, 200 - k * 14, 90))
        d.rectangle([0, cy, W, H], fill=(25, 5, 45))
        for i in range(-12, 13):  # neon grid floor
            d.line([cx + i * 20 * S, cy, cx + i * 160 * S, H], fill=(255, 60, 200, 160), width=3 * S)
        for j in range(8):
            y = cy + (H - cy) * (j / 8) ** 1.8
            d.line([0, y, W, y], fill=(255, 60, 200, 140), width=3 * S)
        for px in (W * 0.12, W * 0.86):  # palm silhouettes
            d.line([px, H * 0.98, px + 30 * S, cy - 160 * S], fill=(20, 0, 30), width=22 * S)
            for a in range(0, 360, 50):
                ex, ey = px + 30 * S + math.cos(math.radians(a)) * 170 * S, cy - 160 * S + math.sin(math.radians(a)) * 70 * S + 40 * S
                d.line([px + 30 * S, cy - 160 * S, ex, ey], fill=(20, 0, 30), width=18 * S)
        return im
    if name == "chip":
        im = _canvas((6, 20, 40), (10, 50, 70))
        d = ImageDraw.Draw(im, "RGBA")
        for k in range(26):  # circuit traces
            a = k / 26 * math.tau
            x0, y0 = W / 2 + math.cos(a) * 260 * S, H / 2 + math.sin(a) * 260 * S
            x1, y1 = W / 2 + math.cos(a) * 700 * S, H / 2 + math.sin(a) * 520 * S
            mid = (x1, y0) if k % 2 else (x0, y1)
            d.line([x0, y0, *mid, x1, y1], fill=(30, 120, 110), width=5 * S)
            d.ellipse([x1 - 10 * S, y1 - 10 * S, x1 + 10 * S, y1 + 10 * S], fill=(46, 211, 160))
        return im
    if name == "phone":
        return _canvas((60, 30, 120), (20, 120, 160))
    if name == "money":
        return _canvas((8, 60, 40), (20, 120, 80))
    return _canvas((20, 30, 50), (40, 60, 90))


@lru_cache(maxsize=None)
def base(name):
    return static(name).resize((PANEL_W, PANEL_H), Image.LANCZOS)


# ----------------------------------------------------------------------------
# per-frame scene
# ----------------------------------------------------------------------------
def kenburns(img, t, z0=1.0, z1=1.1, dur=7.0, pan=(0.0, -0.02)):
    k = min(1.0, t / dur)
    z = z0 + (z1 - z0) * k
    w, h = int(PANEL_W / z), int(PANEL_H / z)
    cx = PANEL_W / 2 + pan[0] * PANEL_W * k
    cy = PANEL_H / 2 + pan[1] * PANEL_H * k
    box = (int(cx - w / 2), int(cy - h / 2), int(cx - w / 2) + w, int(cy - h / 2) + h)
    return img.crop(box).resize((PANEL_W, PANEL_H), Image.BILINEAR)


def scene(name, t):
    im = kenburns(base(name), t)
    d = ImageDraw.Draw(im, "RGBA")
    if name == "money":  # falling rupee notes
        rng = np.random.default_rng(5)
        for i in range(26):
            x0 = rng.uniform(-60, PANEL_W)
            sp = rng.uniform(140, 260)
            y = (rng.uniform(0, PANEL_H + 200) + t * sp) % (PANEL_H + 200) - 150
            ang = math.sin(t * rng.uniform(1, 2.5) + i) * 25
            note = Image.new("RGBA", (190, 100), (0, 0, 0, 0))
            nd = ImageDraw.Draw(note)
            nd.rounded_rectangle([0, 0, 189, 99], radius=10, fill=(180, 230, 170), outline=(60, 130, 70), width=5)
            nd.ellipse([65, 20, 125, 80], outline=(60, 130, 70), width=5)
            text_c(nd, 95, 18, "₹", BLACK(46), (40, 110, 60))
            note = note.rotate(ang, expand=True, resample=Image.BICUBIC)
            im.paste(note, (int(x0 + math.sin(t + i) * 30), int(y)), note)
    elif name == "chip":
        cx, cy, s = PANEL_W / 2, PANEL_H / 2, 170
        p = 0.5 + 0.5 * math.sin(t * 3)
        glow(im, (cx, cy), 330, (46, 211, 160), alpha=int(60 + 50 * p))
        for i in range(-3, 4):
            for dx, dy in ((i * s * 0.28, -s * 1.12), (i * s * 0.28, s * 1.12), (-s * 1.12, i * s * 0.28), (s * 1.12, i * s * 0.28)):
                d.rounded_rectangle([cx + dx - 11, cy + dy - 11, cx + dx + 11, cy + dy + 11], radius=4, fill=(190, 200, 210))
        d.rounded_rectangle([cx - s, cy - s, cx + s, cy + s], radius=30, fill=(25, 30, 38), outline=(120, 190, 240), width=10)
        d.rounded_rectangle([cx - s * 0.6, cy - s * 0.6, cx + s * 0.6, cy + s * 0.6], radius=14,
                            fill=(int(50 + 40 * p), int(160 + 50 * p), int(120 + 30 * p)))
        text_c(d, cx, cy - 52, "AI", BLACK(86), (10, 28, 48))
        for k in range(8):  # pulses running along the traces
            a = k / 8 * math.tau
            f = (t * 0.6 + k * 0.13) % 1
            r = 260 + 260 * f
            d.ellipse([cx + math.cos(a) * r * 1.3 - 9, cy + math.sin(a) * r - 9, cx + math.cos(a) * r * 1.3 + 9, cy + math.sin(a) * r + 9],
                      fill=(120, 255, 210, int(255 * (1 - f))))
    elif name == "phone":
        cx, cy = PANEL_W / 2, PANEL_H / 2 + 20
        w, h = 360, 700
        d.rounded_rectangle([cx - w / 2 - 14, cy - h / 2 - 14, cx + w / 2 + 14, cy + h / 2 + 14], radius=60, fill=(15, 15, 22))
        d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=48, fill=(245, 247, 252))
        d.rounded_rectangle([cx - 60, cy - h / 2 + 14, cx + 60, cy - h / 2 + 40], radius=13, fill=(15, 15, 22))
        d.text((cx - w / 2 + 30, cy - h / 2 + 70), "US STOCKS", font=BOLD(28), fill=(120, 125, 140))
        d.text((cx - w / 2 + 30, cy - h / 2 + 106), "ANT", font=BLACK(64), fill=(20, 25, 40))
        d.text((cx - w / 2 + 30, cy - h / 2 + 186), "Anthropic", font=SEMI(32), fill=(90, 95, 110))
        pts = []  # mini chart drawing in
        n = int(30 * ease(t / 1.6)) + 2
        for i in range(n):
            x = cx - w / 2 + 30 + i * (w - 60) / 31
            y = cy + 40 - 120 * math.sin(i / 31 * math.pi * 0.9) - 20 * math.sin(i * 1.3)
            pts.append((x, y))
        if len(pts) > 1:
            d.line(pts, fill=(20, 170, 110), width=7, joint="curve")
        pulse = 1 + 0.06 * math.sin(t * 7)
        bw, bh = 260 * pulse, 86 * pulse
        d.rounded_rectangle([cx - bw / 2, cy + h / 2 - 150 - bh / 2, cx + bw / 2, cy + h / 2 - 150 + bh / 2], radius=int(bh / 2),
                            fill=(20, 170, 110))
        text_c(d, cx, cy + h / 2 - 150 - 30 * pulse, "BUY", BLACK(int(52 * pulse)), (255, 255, 255))
        for i in range(5):  # floating "+1" order bubbles
            f = (t * 0.7 + i * 0.2) % 1
            x = cx + (i - 2) * 150 + 220 * (1 if i % 2 else -1)
            y = cy + 200 - 420 * f
            d.rounded_rectangle([x - 60, y - 30, x + 60, y + 30], radius=30, fill=(255, 255, 255, int(230 * (1 - f))))
            text_c(d, x, y - 24, "BUY", BOLD(34), (20, 150, 100, int(255 * (1 - f))))
    elif name == "datacenter":
        rng = np.random.default_rng(9)
        for i in range(70):  # blinking LEDs
            x, y = rng.uniform(120, PANEL_W - 120), rng.uniform(140, PANEL_H - 60)
            on = (math.sin(t * rng.uniform(3, 9) + i) > 0.2)
            col = (46, 211, 160) if i % 3 else (80, 160, 255)
            if on:
                d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=col)
    elif name == "boardroom":
        a = ease((t - 0.3) / 0.8)  # a letter flies onto the table
        x, y = PANEL_W / 2 - 170, 330 + (1 - a) * -500
        ang = (1 - a) * 25 - 4
        env = Image.new("RGBA", (340, 230), (0, 0, 0, 0))
        ed = ImageDraw.Draw(env)
        ed.rectangle([0, 0, 339, 229], fill=(250, 245, 230), outline=(160, 150, 130), width=5)
        ed.polygon([(0, 0), (170, 120), (339, 0)], fill=(235, 228, 205), outline=(160, 150, 130))
        ed.ellipse([145, 95, 195, 145], fill=(190, 30, 40))
        env = env.rotate(ang, expand=True, resample=Image.BICUBIC)
        im.paste(env, (int(x), int(y)), env)
    elif name == "bank":
        a = ease((t - 0.4) / 0.6)  # big rupee coin with a "return" arrow
        cx, cy = PANEL_W - 210, 230
        r = 110 * a
        if r > 1:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(245, 190, 60), outline=(180, 120, 20), width=8)
            text_c(d, cx, cy - r * 0.75, "₹", BLACK(int(r * 1.3) + 1), (130, 80, 10))
            d.arc([cx - r - 50, cy - r - 50, cx + r + 50, cy + r + 50], 200, 340, fill=(230, 50, 50), width=14)
            d.polygon([(cx - r - 70, cy - 20), (cx - r - 20, cy - 30), (cx - r - 50, cy + 25)], fill=(230, 50, 50))
    elif name == "exchange":
        pass
    elif name == "city":
        pass
    return im.convert("RGBA")

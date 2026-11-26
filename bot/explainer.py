"""Explainer look (v3, 2026-11-26): full-screen animated explainer scenes + the mascot walking around them.

Inspired by infographic finance reels: dark glowing backgrounds, glossy 3D icons (Microsoft Fluent Emoji 3D,
MIT), A->B flows with an animated dashed arc and a value chip, big number cards, and a huge two-line condensed
headline (white + gold) with a small spaced kicker. The mascot stands in the scene, walks to a new spot on each
beat and points at the graphic while he talks.

Each beat in script.json carries:
  "head": ["WHITE LINE", "GOLD LINE"], "kicker": "SMALL LINE", "tone": "up|down|neutral",
  "scene": {"type": "flow"|"compare"|"bignum"|"icons"|"clip", ...}, optional "chips": [[label, value, tone], ...]
Run exactly like render2.py (same env vars):  python explainer.py preview 3 10 20 | full | part k n
"""
import math, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
import numpy as np
import render2 as R
from character import draw_presenter

FW, FH, FPS = R.FW, R.FH, R.FPS
MEDIA = R.HERE.parent / "media"
BEBAS = str(MEDIA / "fonts" / "BebasNeue-Regular.ttf")
GOLD = (255, 196, 70)
SOFT = (200, 214, 226)
TONE = {"up": ((10, 60, 44), (46, 220, 150)), "down": ((70, 14, 22), (255, 80, 90)), "neutral": ((18, 26, 70), (110, 150, 255))}
STAGE_Y0, STAGE_Y1 = 170, 1060          # where the graphics live
FLOOR = 1505                            # the mascot's feet
HEAD_Y = 1540                           # headline block top
MASCOT_SCALE = 0.74


def HEADF(s):
    return ImageFont.truetype(BEBAS, int(s))


def ease(x):
    return R.ease(max(0.0, min(1.0, x)))


def pop(lt, delay=0.0, dur=0.45):
    """0 -> 1 with a little overshoot."""
    return R.back(max(0.0, min(1.0, (lt - delay) / dur))) if lt > delay else 0.0


# ---------------------------------------------------------------- backgrounds and assets
_BG = {}


def background(tone):
    if tone not in _BG:
        base, glow = TONE.get(tone, TONE["neutral"])
        yy, xx = np.mgrid[0:FH, 0:FW]
        d = np.sqrt(((xx - FW / 2) / 620.0) ** 2 + ((yy - 620) / 700.0) ** 2)
        g = np.clip(1.15 - d, 0, 1) ** 1.6
        img = np.zeros((FH, FW, 3), np.float32)
        dark = np.array([8, 10, 16], np.float32)
        for c in range(3):
            img[..., c] = dark[c] + (base[c] - dark[c]) * 0.9 + glow[c] * 0.30 * g
        img *= (1 - 0.35 * (yy / FH) ** 2)[..., None]                    # darker towards the bottom
        _BG[tone] = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
    return _BG[tone]


_ICON = {}


def icon(name, size):
    key = (name, int(size))
    if key not in _ICON:
        p = MEDIA / "icons" / f"{name}.png"
        im = Image.open(p).convert("RGBA") if p.exists() else Image.open(MEDIA / "icons" / "red_question_mark.png").convert("RGBA")
        _ICON[key] = im.resize((int(size), int(size)), Image.LANCZOS)
    return _ICON[key]


def glow_under(layer, cx, cy, r, col, a=110):
    g = Image.new("RGBA", (int(r * 2.6), int(r * 2.6)), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([r * 0.3, r * 0.3, r * 2.3, r * 2.3], fill=col + (a,))
    g = g.filter(ImageFilter.GaussianBlur(r * 0.35))
    layer.alpha_composite(g, (int(cx - g.width / 2), int(cy - g.height / 2)))


def put_icon(layer, name, cx, cy, size, k, glow=(255, 200, 90)):
    """Icon popping in (k = 0..1+), floating gently."""
    if k <= 0:
        return
    s = max(1, int(size * k))
    glow_under(layer, cx, cy + size * 0.1, size * 0.55 * k, glow, 90)
    layer.alpha_composite(icon(name, s), (int(cx - s / 2), int(cy - s / 2)))


def chip(d, cx, cy, text, f, fg=GOLD, bg=(14, 18, 28, 235), pad=(26, 12), outline=None):
    w = d.textlength(text, font=f)
    h = f.size
    box = [cx - w / 2 - pad[0], cy - h / 2 - pad[1], cx + w / 2 + pad[0], cy + h / 2 + pad[1] + 4]
    d.rounded_rectangle(box, radius=16, fill=bg, outline=outline or fg + (255,), width=3)
    d.text((cx - w / 2, cy - h / 2), text, font=f, fill=fg)
    return box


def label(d, cx, y, text, size=36, fill=SOFT):
    f = R.fit(d, text, R.BOLD, size, 380)
    R.text_c(d, cx, y, text, f, fill)


# ---------------------------------------------------------------- scenes
def sc_flow(layer, d, sc, lt, tone):
    a, b = sc.get("from", {}), sc.get("to", {})
    y = 640
    ka, kb = pop(lt, 0.0), pop(lt, 0.55)
    for it, x, k in ((a, 250, ka), (b, 830, kb)):
        if k > 0:
            put_icon(layer, it.get("icon", "office_building"), x, y, 310, k)
            if k > 0.6:
                label(d, x, y + 190, it.get("label", ""), 44, (240, 244, 248))
    # dashed arc drawing from A to B
    prog = ease((lt - 0.3) / 0.9)
    if prog > 0:
        pts = []
        for i in range(0, 101):
            u = i / 100
            px = 250 + (830 - 250) * u
            py = y - 175 - math.sin(math.pi * u) * 190
            pts.append((px, py))
        n = int(len(pts) * prog)
        for i in range(0, n - 1, 4):
            d.line([pts[i], pts[min(i + 2, n - 1)]], fill=(130, 230, 200, 255), width=7)
        if n > 2:
            hx, hy = pts[n - 1]
            ang = math.atan2(pts[n - 1][1] - pts[n - 3][1], pts[n - 1][0] - pts[n - 3][0])
            tri = [(hx + 22 * math.cos(ang), hy + 22 * math.sin(ang)),
                   (hx + 18 * math.cos(ang + 2.4), hy + 18 * math.sin(ang + 2.4)),
                   (hx + 18 * math.cos(ang - 2.4), hy + 18 * math.sin(ang - 2.4))]
            d.polygon(tri, fill=(130, 230, 200, 255))
    if sc.get("chip") and lt > 0.9:
        k = pop(lt, 0.9, 0.35)
        f = HEADF(80 * max(0.3, k))
        chip(d, 540, y - 375, sc["chip"], f)


def sc_compare(layer, d, sc, lt, tone):
    if sc.get("icon"):
        put_icon(layer, sc["icon"], 540, 330, 240, pop(lt, 0.0))
    for side, x, delay in (("left", 290, 0.25), ("right", 790, 0.55)):
        it = sc.get(side, {})
        k = pop(lt, delay)
        if k <= 0:
            continue
        col = {"up": (46, 220, 150), "down": (255, 90, 100)}.get(it.get("tone"), GOLD)
        w, h = 400 * k, 380 * k
        cy = 740
        d.rounded_rectangle([x - w / 2, cy - h / 2, x + w / 2, cy + h / 2], radius=34, fill=(255, 255, 255, 236))
        if k > 0.7:
            R.text_c(d, x, cy - 150, it.get("label", ""), R.fit(d, it.get("label", ""), R.BOLD, 36, 360), (60, 66, 80))
            val = it.get("value", "")
            vf = HEADF(150)
            while d.textlength(val, font=vf) > 360 and vf.size > 60:
                vf = HEADF(vf.size - 8)
            R.text_c(d, x, cy - 85, val, vf, col)
            if it.get("note"):
                R.text_c(d, x, cy + 95, it["note"], R.fit(d, it["note"], R.SEMI, 30, 360), (90, 96, 110))
    if sc.get("vs", True) and lt > 0.6:
        R.text_c(d, 540, 705, "VS", HEADF(80), (255, 255, 255))


def sc_bignum(layer, d, sc, lt, tone):
    put_icon(layer, sc.get("icon", "chart_increasing"), 540, 420, 330, pop(lt, 0.0))
    k = pop(lt, 0.35)
    if k > 0:
        col = {"up": (46, 220, 150), "down": (255, 90, 100)}.get(sc.get("tone", tone), GOLD)
        val = sc.get("value", "")
        f = HEADF(230 * min(1.0, 0.6 + 0.4 * k))
        while d.textlength(val, font=f) > 960 and f.size > 90:
            f = HEADF(f.size - 10)
        R.text_c(d, 540, 610, val, f, col)
        if sc.get("label") and k > 0.8:
            label(d, 540, 870, sc["label"], 46, (240, 244, 248))


def sc_icons(layer, d, sc, lt, tone):
    items = sc.get("items", [])[:3]
    n = len(items)
    xs = {1: [540], 2: [300, 780], 3: [200, 540, 880]}[max(1, n)]
    size = {1: 400, 2: 330, 3: 270}[max(1, n)]
    for i, (it, x) in enumerate(zip(items, xs)):
        k = pop(lt, 0.35 * i)
        put_icon(layer, it.get("icon", "red_question_mark"), x, 600, size, k)
        if k > 0.7:
            label(d, x, 600 + size / 2 + 30, it.get("label", ""), 42, (240, 244, 248))
        if sc.get("arrows") and i < n - 1 and lt > 0.35 * i + 0.3:
            ax = (x + xs[i + 1]) / 2
            R.text_c(d, ax, 545, "→", R.BLACK(90), GOLD)


def sc_clip(layer, d, sc, lt, tone):
    k = ease(lt / 0.4)
    W, H = 960, 700
    x0, y0 = (FW - W) // 2, 200 + int(40 * (1 - k))
    if sc.get("video"):
        fdir, n = R.video_frames(f"../media/videos/{sc['video']}.mp4")
        i = (int(sc.get("start", 0) * FPS) + int(lt * FPS)) % max(1, n)
        im = Image.open(fdir / f"{i + 1:04d}.jpg").convert("RGB")
    else:
        im = Image.open(MEDIA / "images" / f"{sc.get('image')}.jpg").convert("RGB")
    s = max(W / im.width, H / im.height) * (1.04 + 0.03 * lt / 6)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H)).convert("RGBA")
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=40, fill=int(255 * k))
    shadow = Image.new("RGBA", (W + 80, H + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([40, 50, W + 40, H + 50], radius=40, fill=(0, 0, 0, int(150 * k)))
    layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22)), (x0 - 40, y0 - 40))
    layer.paste(im, (x0, y0), mask)
    if sc.get("label") and k > 0.9:
        chip(d, FW / 2, y0 + H - 10, sc["label"], R.BOLD(30), fg=(255, 255, 255), bg=(10, 12, 18, 230), outline=(255, 255, 255, 70))
    if sc.get("credit"):
        d.text((x0 + 18, y0 + 14), sc["credit"], font=R.SEMI(20), fill=(255, 255, 255, 200))


def sc_outro(layer, d, sc, lt, tone):
    q = R.SCRIPT.get("quote") or {}
    if q:
        k = ease(lt / 0.5)
        x0, y0, W = 120, 170, 840
        f = R.SEMI(46)
        lines = R.wrap(d, f"“{q.get('text', '')}”", f, W - 80)
        H = 110 + 62 * len(lines) + 80
        d.rounded_rectangle([x0, y0, x0 + W, y0 + H], radius=36, fill=(10, 14, 22, int(220 * k)), outline=(255, 255, 255, int(60 * k)), width=2)
        d.text((x0 + 40, y0 + 34), "THOUGHT OF THE DAY", font=R.BOLD(30), fill=GOLD + (int(255 * k),))
        for i, ln in enumerate(lines):
            d.text((x0 + 40, y0 + 92 + 62 * i), ln, font=f, fill=(244, 248, 250, int(255 * k)))
        d.text((x0 + 40, y0 + 102 + 62 * len(lines)), "— " + q.get("by", ""), font=R.SEMI(34), fill=(150, 205, 200, int(255 * k)))
    pulse = 1 + 0.06 * max(0.0, math.sin(lt * 2 * math.pi / 1.6)) ** 4
    w, h = 520 * pulse, 120 * pulse
    cy = 720
    d.rounded_rectangle([540 - w / 2, cy - h / 2, 540 + w / 2, cy + h / 2], radius=int(h / 2), fill=(230, 33, 23))
    R.text_c(d, 540, cy - 40 * pulse, "SUBSCRIBE", R.BLACK(64 * pulse), (255, 255, 255))


SCENES = {"flow": sc_flow, "compare": sc_compare, "bignum": sc_bignum, "icons": sc_icons, "clip": sc_clip, "outro": sc_outro}


def chips_block(d, chips, x, lt):
    for i, c in enumerate(chips[:3]):
        k = pop(lt, 0.6 + 0.2 * i, 0.35)
        if k <= 0:
            continue
        lab, val, tn = (list(c) + ["", "", ""])[:3]
        col = {"up": (46, 220, 150), "down": (255, 90, 100)}.get(tn, GOLD)
        y = 1140 + i * 112
        w = 380
        d.rounded_rectangle([x - w / 2, y, x + w / 2, y + 92], radius=20, fill=(10, 14, 22, int(215 * min(1, k))),
                            outline=col + (200,), width=3)
        d.text((x - w / 2 + 22, y + 10), lab, font=R.fit(d, lab, R.BOLD, 24, w - 44), fill=SOFT)
        vf = HEADF(52)
        while d.textlength(val, font=vf) > w - 44 and vf.size > 28:
            vf = HEADF(vf.size - 4)
        d.text((x - w / 2 + 22, y + 36), val, font=vf, fill=col)


# ---------------------------------------------------------------- host: in for the headlines, out for the news, back at the end
SEG_T = {s["id"]: (s["start"], s["end"]) for s in R.TL["segments"]}
STORY_IDS = [s["id"] for s in R.SEGS if s["id"] not in ("hook", "outro")]
T_NEWS = SEG_T[STORY_IDS[0]][0] if STORY_IDS else 1e9          # first story starts
T_OUTRO = SEG_T.get("outro", (1e9, 1e9))[0]
HOST_X, OUTRO_X = 300, 540
OFF_R = FW + 260


def host_state(t):
    """(x, walking, facing_left, visible). Fixed spot during the hook; walks off for the news; back for the outro."""
    if t < T_NEWS - 0.2:
        if t < 1.1:
            return -220 + (HOST_X + 220) * ease(t / 1.1), True, False, True
        return HOST_X, False, False, True
    if t < T_OUTRO - 0.6:
        k = (t - (T_NEWS - 0.2)) / 0.9
        if k < 1:
            return HOST_X + (OFF_R - HOST_X) * ease(k), True, False, True
        return OFF_R, False, False, False
    k = (t - (T_OUTRO - 0.6)) / 1.1
    if k < 1:
        return OFF_R + (OUTRO_X - OFF_R) * ease(k), True, True, True
    return OUTRO_X, False, False, True


def draw_host(fr, t):
    x, walking, left, vis = host_state(t)
    if not vis:
        return False
    segs = R.TL["segments"]
    speaking = any(s["start"] <= t <= s["end"] for s in segs)
    mouth = R.mouth_at(t, speaking)
    blink = 1.0 if (t % 3.3) < 0.12 else 0.0
    if walking:
        pose = {"mode": "walk", "sit": 0, "phase": t * 11, "bob": abs(math.sin(t * 11)) * -8, "mouth": mouth, "blink": blink}
    else:
        g = 0.75 + 0.2 * math.sin(t * 1.7) if speaking else 0.35
        pose = {"mode": "stand", "sit": 0, "mouth": mouth, "blink": blink, "gesture": g,
                "wave": 6 * math.sin(t * 5.0) * (1 if speaking else 0.2), "bob": math.sin(t * 2.4) * 3,
                "look": 0.3 * math.sin(t * 0.7), "case": False, "brow": 0.5 if mouth > 0.7 else 0.0}
    im = draw_presenter(pose, MASCOT_SCALE)
    if left:
        im = ImageOps.mirror(im)
    bb = im.getbbox() or (0, 0, im.width, im.height)
    shadow = Image.new("RGBA", (360, 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([0, 0, 360, 60], fill=(0, 0, 0, 110))
    fr.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)), (int(x - 180), FLOOR - 34))
    fr.alpha_composite(im, (int(x - im.width / 2), int(FLOOR - bb[3])))
    return True


# ---------------------------------------------------------------- moving background
_BIG = {}
_rng = np.random.default_rng(7)
DOTS = [(_rng.uniform(0, FW), _rng.uniform(0, FH), _rng.uniform(3, 9), _rng.uniform(8, 26), _rng.uniform(0, 6.28)) for _ in range(46)]


def moving_bg(tone, t):
    """The glow background, bigger than the frame, drifting slowly (Ken Burns), plus soft floating particles."""
    if tone not in _BIG:
        _BIG[tone] = background(tone).resize((FW + 260, FH + 260), Image.LANCZOS)
    big = _BIG[tone]
    ox = 130 + 110 * math.sin(t * 0.21)
    oy = 130 + 110 * math.cos(t * 0.17)
    fr = big.crop((int(ox), int(oy), int(ox) + FW, int(oy) + FH))
    d = ImageDraw.Draw(fr, "RGBA")
    for x, y, r, sp, ph in DOTS:
        yy = (y - t * sp) % FH
        xx = x + 14 * math.sin(t * 0.6 + ph)
        a = int(40 + 30 * math.sin(t * 1.3 + ph))
        d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=(255, 255, 255, max(0, a)))
    return fr


# ---------------------------------------------------------------- explanation note + news scroller
def note_card(fr, text, lt, y, dur=4.0):
    """Explanation card. Words wrapped in *stars* are key words: they get a gold marker swipe, one after
    another while the line is read (each also pops slightly), so the eye keeps moving through the card."""
    if not text:
        return
    d = ImageDraw.Draw(fr, "RGBA")
    k = ease((lt - 0.4) / 0.4)
    if k <= 0:
        return
    f, fb = R.SEMI(40), R.BLACK(40)
    # tokens: (word, is_key, key_index)
    toks, key_i, inkey = [], 0, False
    for w in text.split():
        start, end = w.startswith("*"), w.rstrip(".,;:!?").endswith("*")
        if start:
            inkey = True
        clean = w.replace("*", "")
        toks.append((clean, inkey, key_i if inkey else -1))
        if end:
            inkey = False
            key_i += 1
    nkeys = max(1, key_i)
    # wrap with the right font per word
    maxw, sp = FW - 220, d.textlength(" ", font=f)
    lines, cur, cw = [], [], 0
    for tok in toks:
        tw = d.textlength(tok[0], font=fb if tok[1] else f)
        if cur and cw + sp + tw > maxw:
            lines.append(cur); cur, cw = [], 0
        cur.append((tok, tw)); cw += (sp if len(cur) > 1 else 0) + tw
    if cur:
        lines.append(cur)
    lines = lines[:3]
    lh = 56
    h = 34 + lh * len(lines)
    x0, x1 = 70, FW - 70
    yy = y + int(24 * (1 - k))
    d.rounded_rectangle([x0, yy, x1, yy + h], radius=24, fill=(8, 12, 20, int(210 * k)), outline=(255, 255, 255, int(40 * k)), width=2)
    d.rounded_rectangle([x0, yy, x0 + 12, yy + h], radius=6, fill=GOLD + (int(255 * k),))
    # when each key word lights up: spread over the beat, starting once the card is in
    span = max(1.2, dur - 1.4)
    for li, ln in enumerate(lines):
        ty = yy + 14 + lh * li
        pos, x = [], x0 + 40
        for (word, key, ki), tw in ln:
            pos.append((x, word, key, ki, tw))
            x += tw + sp
        # one marker per key phrase on this line (no gaps between its words)
        groups = {}
        for x, word, key, ki, tw in pos:
            if key:
                g = groups.setdefault(ki, [x, x + tw])
                g[1] = x + tw
        for ki, (gx0, gx1) in groups.items():
            m = ease((lt - (0.9 + span * ki / nkeys)) / 0.35)
            if m > 0:
                d.rounded_rectangle([gx0 - 8, ty + 2, gx0 - 8 + (gx1 - gx0 + 16) * m, ty + 50], radius=10, fill=GOLD + (int(255 * k),))
        for x, word, key, ki, tw in pos:
            if key:
                m = ease((lt - (0.9 + span * ki / nkeys)) / 0.35)
                d.text((x, ty), word, font=fb, fill=((20, 16, 6) if m > 0.6 else GOLD) + (int(255 * k),))
            else:
                d.text((x, ty), word, font=f, fill=(232, 238, 244, int(255 * k)))


TICK_Y = 122                 # just below the StickBiz Brief / SUBSCRIBE bar


def scroller(fr, t):
    items = R.SCRIPT.get("ticker") or [s.get("headline", "") for s in R.SEGS if s["id"] not in ("hook", "outro")]
    d = ImageDraw.Draw(fr, "RGBA")
    d.rectangle([0, TICK_Y, FW, TICK_Y + 70], fill=(6, 8, 14, 235))
    d.line([0, TICK_Y, FW, TICK_Y], fill=GOLD + (200,), width=3)
    f = R.BOLD(32)
    text = "     ●     ".join(x.upper() for x in items) + "     ●     "
    w = d.textlength(text, font=f)
    off = (t * 150) % w
    x = 250 - off
    while x < FW:
        d.text((x, TICK_Y + 14), text, font=f, fill=(240, 244, 248))
        x += w
    d.rectangle([0, TICK_Y, 238, TICK_Y + 70], fill=(225, 30, 45))
    d.text((26, TICK_Y + 13), "TOP NEWS", font=R.BLACK(34), fill=(255, 255, 255))


# ---------------------------------------------------------------- frame
def headline(fr, beat, seg, lt, y0, big=150):
    d = ImageDraw.Draw(fr, "RGBA")
    head = beat.get("head") or [seg.get("headline", "").upper(), ""]
    kick = beat.get("kicker") or seg.get("tag", "")
    k = ease(lt / 0.35)
    dy = int(30 * (1 - k))
    a = int(255 * k)
    kf = R.SEMI(30)
    kt = " ".join(kick.upper())
    w = d.textlength(kt, font=kf)
    y = y0 + dy
    d.text((FW / 2 - w / 2, y), kt, font=kf, fill=SOFT + (a,))
    d.line([FW / 2 - w / 2 - 90, y + 20, FW / 2 - w / 2 - 20, y + 20], fill=SOFT + (int(a * 0.6),), width=2)
    d.line([FW / 2 + w / 2 + 20, y + 20, FW / 2 + w / 2 + 90, y + 20], fill=SOFT + (int(a * 0.6),), width=2)
    for i, (ln, col) in enumerate(zip(head[:2], ((255, 255, 255), GOLD))):
        if not ln:
            continue
        f = HEADF(big)
        while d.textlength(ln, font=f) > FW - 70 and f.size > 70:
            f = HEADF(f.size - 6)
        tw = d.textlength(ln, font=f)
        d.text((FW / 2 - tw / 2 + 4, y + 52 + i * (big - 12) + 5), ln, font=f, fill=(0, 0, 0, int(a * 0.5)))
        d.text((FW / 2 - tw / 2, y + 52 + i * (big - 12)), ln, font=f, fill=col + (a,))


def topbar(fr, t):
    d = ImageDraw.Draw(fr, "RGBA")
    d.rounded_rectangle([34, 40, 330, 104], radius=32, fill=(0, 0, 0, 150))
    f = R.BLACK(34)
    d.text((58, 50), "Stick", font=f, fill=(255, 255, 255))
    x = 58 + d.textlength("Stick", font=f)
    d.text((x, 50), "Biz", font=f, fill=(46, 211, 160))
    d.text((x + d.textlength("Biz", font=f) + 8, 50), "Brief", font=f, fill=(255, 255, 255))
    p = 1 + 0.05 * max(0.0, math.sin(t * 2 * math.pi / 2.6)) ** 6
    w, h = 250 * p, 64 * p
    cx, cy = FW - 34 - 125, 72
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=int(h / 2), fill=(230, 33, 23))
    R.text_c(d, cx, cy - 22 * p, "SUBSCRIBE", R.BLACK(30 * p), (255, 255, 255))
    dl = R.SCRIPT.get("date_label", "")
    if dl:
        R.text_c(d, FW / 2, 58, dl, R.SEMI(26), SOFT)


def scaled(layer, k, anchor_y=150, dy=0):
    """Enlarge the scene layer for the full-screen news part (the host is out of the frame)."""
    if abs(k - 1) < 1e-3 and not dy:
        return layer
    w, h = int(FW * k), int(FH * k)
    big = layer.resize((w, h), Image.BILINEAR)
    out = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    out.alpha_composite(big, (int((FW - w) / 2), int(anchor_y - anchor_y * k + dy)))
    return out


def explainer_frame(t):
    si = R.seg_at(t)
    seg = R.SEGS[si]
    bi, beat, bstart = R.beat_at(si, t)
    lt = t - bstart
    news = seg["id"] not in ("hook", "outro")
    if seg["id"] == "outro":
        beat = dict(beat, scene={"type": "outro"}, head=beat.get("head") or ["SEE YOU", "NEXT TIME"], kicker="STICKBIZ BRIEF")
    tone = beat.get("tone", "neutral")
    fr = moving_bg(tone, t)
    if lt < 0.35 and bi > 0:
        pb = (seg.get("beats") or [{}])[bi - 1]
        if pb.get("tone", "neutral") != tone:
            fr = Image.blend(moving_bg(pb.get("tone", "neutral"), t), fr, ease(lt / 0.35))
    topbar(fr, t)
    layer = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    sc = beat.get("scene") or {"type": "icons", "items": [{"icon": "red_question_mark", "label": ""}]}
    SCENES.get(sc.get("type"), sc_icons)(layer, d, sc, lt, tone)
    if beat.get("chips"):
        chips_block(d, beat["chips"], FW - 230, lt)
    if news:                                   # whole screen for the explanation
        fr.alpha_composite(scaled(layer, 1.12, 150, 10))
        starts = R.beat_starts(si) if seg.get("beats") else [bstart]
        bend = starts[bi + 1] if bi + 1 < len(starts) else R.TL["segments"][si]["end"]
        note_card(fr, beat.get("note", ""), lt, 1200, bend - bstart)
        headline(fr, beat, seg, lt, 1480, 145)
        scroller(fr, t)
        draw_host(fr, t)                       # only while walking off at the start of the news
    else:
        fr.alpha_composite(layer)
        draw_host(fr, t)
        headline(fr, beat, seg, lt, HEAD_Y, 150)
    return fr.convert("RGB")


R.render_frame = explainer_frame       # encode()/preview in render2 now draw this look

if __name__ == "__main__":
    R.main()

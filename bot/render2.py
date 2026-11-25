"""StickBiz Brief Short — v2 look (1080x1920, 30 fps).

Layout (top to bottom):
  B-roll panel (full width, 0-880): changes every sentence ("beat") — illustrated scene, big number,
      animated chart or comparison; LIVE countdown + brand on top; topic tag; synced captions at its foot
  ticker strip (880-940)
  headline banner (white, 955-1150): date + two lines, second line red/green — changes every beat
  studio (1150-1920): the StickBiz presenter on his chair (unchanged character)
Between stories a red "BREAKING · KHABAR 03/09" sting.

Script: script.json (or env STICKBIZ_SCRIPT). Each story may carry "beats": one per sentence of "cap":
  {"banner": ["line 1", "line 2"], "tone": "up|down|neutral", "tag": "TOPIC",
   "v": {"kind": "scene", "name": "exchange|city|money|chip|phone|bank|boardroom|datacenter|game"}
       | {"kind": "bignum", "value": "+898", "label": "SENSEX · 20 NOV", "sub": "POINTS"}
       | {"kind": "chart", "label": "NASDAQ", "end": "−5.3%"}            (tone sets up/down)
       | {"kind": "compare", "left": ["OPENED", "$111.50"], "right": ["CLOSED", "$97.17"]}}
Script-level: "date_label", "ticker": ["SENSEX ▲ 898", ...].

python render2.py preview 0.5 3 10 ...     -> out/v2_preview_XXX.png
python render2.py clip START END NAME      -> out/NAME.mp4 (silent unless out/mix.wav matches the script)
python render2.py video                    -> out/stickbiz_short.mp4 (with out/mix.wav)
Set STICKBIZ_ESTIMATE=1 to time captions from text length instead of the last voiced timeline.
"""
import json, math, os, re, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from character import draw_presenter, draw_chair, briefcase, Pen
import scenes

HERE = Path(__file__).parent
OUT = Path(os.environ["STICKBIZ_OUT"]) if os.environ.get("STICKBIZ_OUT") else HERE / "out"  # separate work folder
OUT.mkdir(exist_ok=True)
FW, FH, FPS = 1080, 1920, 30

MINT = (46, 211, 160)
NAVY = (10, 28, 48)
WHITE = (255, 255, 255)
RED = (225, 30, 45)
GREEN = (12, 160, 90)
AMBER = (245, 180, 60)
INK = (18, 20, 28)

F = os.environ.get("STICKBIZ_FONTS", "C:/Windows/Fonts/").rstrip("/\\") + "/"
def font(name, size):
    try:
        return ImageFont.truetype(F + name, max(8, int(size)))
    except OSError:   # machine without that Segoe UI weight: closest standard font
        alt = {"seguibl.ttf": "ariblk.ttf", "segoeuib.ttf": "arialbd.ttf", "seguisb.ttf": "arialbd.ttf"}.get(name, "arial.ttf")
        return ImageFont.truetype(F + alt, max(8, int(size)))
BLACK = lambda s: font("seguibl.ttf", s)
BOLD = lambda s: font("segoeuib.ttf", s)
SEMI = lambda s: font("seguisb.ttf", s)

SCRIPT_PATH = Path(os.environ.get("STICKBIZ_SCRIPT", HERE / "script.json"))
SCRIPT = json.loads(SCRIPT_PATH.read_text(encoding="utf-8"))
SEGS = SCRIPT["segments"]
STORIES = [s["id"] for s in SEGS if s["id"] not in ("hook", "outro")]

PANEL_H = 880
TICK_Y0, TICK_Y1 = 880, 940
BAN_Y0, BAN_Y1 = 955, 1150
FLOOR_Y = 1890


# ----------------------------------------------------------------------------
# timeline
# ----------------------------------------------------------------------------
def load_timeline():
    tl = OUT / "timeline.json"
    if tl.exists() and not os.environ.get("STICKBIZ_ESTIMATE"):
        data = json.loads(tl.read_text(encoding="utf-8"))
        if [s["id"] for s in data["segments"]] == [s["id"] for s in SEGS]:
            return data
    t, segs = float(SCRIPT.get("lead_in", 1.4)), []
    for s in SEGS:
        d = len(s["cap"]) / 15.5
        segs.append({"id": s["id"], "start": t, "end": t + d})
        t += d + 0.45
    return {"segments": segs, "duration": t + 1.0, "estimated": True}


TL = load_timeline()
DUR = TL["duration"]
ENV = None
if (OUT / "envelope.npy").exists() and not TL.get("estimated"):
    ENV = np.load(OUT / "envelope.npy")


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def back(x):
    x = max(0.0, min(1.0, x))
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(test, font=f) <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_c(d, cx, y, txt, f, fill, stroke=0, sfill=(0, 0, 0)):
    w = d.textlength(txt, font=f)
    d.text((cx - w / 2, y), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)


def fit(d, txt, maker, size, maxw):
    f = maker(size)
    while d.textlength(txt, font=f) > maxw and size > 20:
        size -= 2
        f = maker(size)
    return f


def is_key(word):
    return any(ch.isdigit() for ch in word) or any(c in word for c in "₹$€%")


# ----------------------------------------------------------------------------
# captions and beats
# ----------------------------------------------------------------------------
def caption_chunks(si):
    s, tl = SEGS[si], TL["segments"][si]
    if "chunks" in tl:
        return tl["chunks"]
    words = s["cap"].split()
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 4 or w[-1] in ".,?!:":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    total = sum(len(" ".join(c)) for c in chunks)
    t, out = tl["start"], []
    span = tl["end"] - tl["start"]
    for c in chunks:
        d = span * len(" ".join(c)) / total
        out.append({"text": " ".join(c), "start": t, "end": t + d})
        t += d
    return out


def sentences(cap):
    return [x for x in re.split(r"(?<=[.!?])\s+", cap.strip()) if x]


_BEAT_CACHE = {}


def beat_starts(si):
    """Start time of each beat in segment si. A beat starts at the word given in its "at" snippet
    (a few words copied from the caption); without "at", beats follow the sentences in order."""
    if si in _BEAT_CACHE:
        return _BEAT_CACHE[si]
    seg = SEGS[si]
    cap = seg["cap"]
    beats = seg.get("beats") or [{}]
    # word index where each beat begins
    sent_words, pos = [], 0
    for s in sentences(cap):
        sent_words.append(pos)
        pos += len(s.split())
    word_idx = []
    for i, b in enumerate(beats):
        if b.get("at") and b["at"] in cap:
            word_idx.append(len(cap[:cap.index(b["at"])].split()))
        else:
            word_idx.append(sent_words[min(i, len(sent_words) - 1)] if i < len(sent_words) else 10 ** 6)
    word_idx[0] = 0
    chunks = caption_chunks(si)
    starts = []
    for wi in word_idx:
        wcount, st = 0, None
        for ch in chunks:
            n = len(ch["text"].split())
            if wcount + n > wi:
                # inside this chunk: interpolate by word position
                frac = (wi - wcount) / max(1, n)
                st = ch["start"] + frac * (ch["end"] - ch["start"])
                break
            wcount += n
        starts.append(st if st is not None else 10 ** 6)
    _BEAT_CACHE[si] = starts
    return starts


def beat_at(si, t):
    seg = SEGS[si]
    beats = seg.get("beats") or [{}]
    starts = beat_starts(si)
    bi = 0
    for i, st in enumerate(starts):
        if t >= st - 0.15:
            bi = i
    bi = min(bi, len(beats) - 1)
    bstart = starts[min(bi, len(starts) - 1)] if bi > 0 else TL["segments"][si]["start"] - 0.35
    return bi, beats[bi], bstart


def seg_at(t):
    cur = 0
    for i, s in enumerate(TL["segments"]):
        if t >= s["start"] - 0.35:
            cur = i
    return cur


def mouth_at(t, speaking):
    if ENV is not None:
        i = min(len(ENV) - 1, int(t * FPS))
        return float(min(1.0, ENV[i] * 1.4))
    if not speaking:
        return 0.0
    return max(0.0, 0.5 + 0.5 * math.sin(t * 19) * math.sin(t * 7.3 + 1))


# ----------------------------------------------------------------------------
# B-roll visuals
# ----------------------------------------------------------------------------
def tone_col(tone):
    return GREEN if tone == "up" else RED if tone == "down" else RED


def v_bignum(v, tone, lt):
    im = scenes.gradient(FW, PANEL_H, (250, 250, 252), (228, 232, 240))
    d = ImageDraw.Draw(im, "RGBA")
    for x in range(0, FW, 60):  # faint grid
        d.line([x, 0, x, PANEL_H], fill=(0, 0, 0, 10), width=2)
    for y in range(0, PANEL_H, 60):
        d.line([0, y, FW, y], fill=(0, 0, 0, 10), width=2)
    col = tone_col(tone)
    lab = v.get("label", "")
    lw = d.textlength(lab, font=BOLD(44)) + 50
    d.rounded_rectangle([FW / 2 - lw / 2, 196, FW / 2 + lw / 2, 266], radius=35, fill=(255, 255, 255))
    text_c(d, FW / 2, 202, lab, BOLD(44), (110, 115, 130))
    val = v["value"]
    m = re.match(r"^([^\d]*)([\d,\.]+)(.*)$", val)
    k = ease(lt / 0.9)
    if m:
        pre, num, post = m.groups()
        dec = len(num.split(".")[1]) if "." in num else 0
        n = float(num.replace(",", "")) * k
        s = f"{n:,.{dec}f}" if "," in num else f"{n:.{dec}f}"
        if re.fullmatch(r"(19|20)\d\d", num):  # a year: no count-up
            s = num
        shown = pre + s + post
    else:
        shown = val
    f = fit(d, val, BLACK, 190, FW - 120)
    text_c(d, FW / 2, 290, shown, f, INK)
    sub = v.get("sub")
    if sub:
        a = back((lt - 0.7) / 0.35)
        if a > 0:
            arrow = "▲ " if tone == "up" else "▼ " if tone == "down" else ""
            sf = BLACK(54 * (0.7 + 0.3 * a))
            w = d.textlength(arrow + sub, font=sf) + 60
            d.rounded_rectangle([FW / 2 - w / 2, 560, FW / 2 + w / 2, 560 + 90], radius=16, fill=col)
            text_c(d, FW / 2, 565, arrow + sub, sf, WHITE)
    return im.convert("RGBA")


def v_chart(v, tone, lt):
    up = tone != "down"
    im = scenes.gradient(FW, PANEL_H, (12, 16, 26), (24, 30, 46))
    d = ImageDraw.Draw(im, "RGBA")
    for y in range(160, PANEL_H - 120, 90):
        d.line([60, y, FW - 60, y], fill=(255, 255, 255, 18), width=2)
    rng = np.random.default_rng(4 if up else 8)
    n = 60
    ys, y = [], 0.0
    for i in range(n):
        y += (0.06 if up else -0.06) + rng.normal(0, 0.18)
        ys.append(y)
    lo, hi = min(ys), max(ys)
    shown = max(2, int(n * ease(lt / 1.6)))
    pts = [(80 + i * (FW - 200) / (n - 1), 660 - (ys[i] - lo) / (hi - lo + 1e-6) * 380) for i in range(shown)]
    col = GREEN if up else RED
    poly = pts + [(pts[-1][0], 680), (pts[0][0], 680)]
    d.polygon(poly, fill=col + (55,))
    d.line(pts, fill=col, width=9, joint="curve")
    ex, ey = pts[-1]
    d.ellipse([ex - 14, ey - 14, ex + 14, ey + 14], fill=WHITE, outline=col, width=6)
    d.text((80, 205), v.get("label", ""), font=BLACK(60), fill=WHITE)
    end = v.get("end")
    if end and lt > 1.2:
        a = back((lt - 1.2) / 0.35)
        f = BLACK(80 * (0.6 + 0.4 * a))
        w = d.textlength(end, font=f) + 50
        x = min(FW - 40 - w, ex - w / 2)
        yb = max(220, ey - 150)
        d.rounded_rectangle([x, yb, x + w, yb + 110], radius=18, fill=col)
        text_c(d, x + w / 2, yb + 4, end, f, WHITE)
    return im.convert("RGBA")


def v_compare(v, tone, lt):
    im = scenes.gradient(FW, PANEL_H, (245, 246, 250), (225, 230, 240))
    d = ImageDraw.Draw(im, "RGBA")
    for i, (side, col) in enumerate(((v["left"], GREEN), (v["right"], RED if tone == "down" else GREEN))):
        a = back((lt - 0.15 - i * 0.35) / 0.4)
        if a <= 0:
            continue
        x0 = 60 + i * 500
        yy = 190 + (1 - a) * 80
        d.rounded_rectangle([x0, yy, x0 + 460, yy + 430], radius=36, fill=WHITE, outline=col, width=8)
        text_c(d, x0 + 230, yy + 50, side[0], fit(d, side[0], BOLD, 46, 420), (110, 115, 130))
        f = fit(d, side[1], BLACK, 110, 420)
        text_c(d, x0 + 230, yy + 150, side[1], f, col)
        if len(side) > 2:
            text_c(d, x0 + 230, yy + 320, side[2], BOLD(44), col)
    return im.convert("RGBA")


def v_hook(seg, lt):
    im = scenes.gradient(FW, PANEL_H, (150, 10, 20), (40, 5, 10))
    d = ImageDraw.Draw(im, "RGBA")
    text_c(d, FW / 2, 140, seg.get("hook_title", "AAJ KI TOP NEWS"), fit(d, seg.get("hook_title", "AAJ KI TOP NEWS"), BLACK, 84, FW - 80), WHITE)
    items = seg.get("hook_items", [])
    for i, it in enumerate(items[:3]):
        a = back((lt - 0.25 - i * 1.1) / 0.3)  # all three highlights up within ~3 s
        if a <= 0:
            continue
        y = 250 + i * 128 + (1 - a) * 60
        d.rounded_rectangle([60, y, FW - 60, y + 108], radius=24, fill=WHITE)
        d.ellipse([84, y + 14, 164, y + 94], fill=RED)
        text_c(d, 124, y + 14, str(i + 1), BLACK(54), WHITE)
        f = fit(d, it[0], BLACK, 54, FW - 280)
        d.text((192, y + 22), it[0], font=f, fill=INK)
    return im.convert("RGBA")


def v_outro(lt):
    im = scenes.gradient(FW, PANEL_H, (10, 40, 60), (10, 80, 80))
    d = ImageDraw.Draw(im, "RGBA")
    p = 1 + 0.05 * math.sin(lt * 6)
    w, h = 600 * p, 150 * p
    cx, cy = FW / 2, 330
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=int(h / 2), fill=(230, 33, 23))
    text_c(d, cx, cy - 50 * p, "SUBSCRIBE", BLACK(74 * p), WHITE)
    l1, l2 = SCRIPT.get("outro_lines", ["Comment karo:", "Kaunsi khabar sabse badi?"])
    text_c(d, cx, 470, l1, SEMI(48), (190, 220, 230))
    text_c(d, cx, 535, l2, fit(d, l2, BLACK, 62, FW - 80), WHITE)
    for i, line in enumerate(SCRIPT.get("disclaimer", [])):  # SEBI checklist §8: on-screen disclaimer
        text_c(d, cx, 650 + i * 44, line, fit(d, line, SEMI, 34, FW - 80), (170, 200, 210))
    return im.convert("RGBA")


def panel_visual(si, beat, lt):
    seg = SEGS[si]
    if seg["id"] == "hook" and seg.get("hook_items"):  # the list builds across the whole hook, not per beat
        return v_hook(seg, CUR_T - (TL["segments"][si]["start"] - 0.35))
    if seg["id"] == "outro":
        return v_outro(lt)
    v = beat.get("v") or {"kind": "scene", "name": "city"}
    tone = beat.get("tone", "neutral")
    if v["kind"] == "bignum":
        return v_bignum(v, tone, lt)
    if v["kind"] == "chart":
        return v_chart(v, tone, lt)
    if v["kind"] == "compare":
        return v_compare(v, tone, lt)
    if v["kind"] == "dips":
        return v_dips(v, tone, lt)
    if v["kind"] == "photo":
        return v_photo(v, tone, lt)
    if v["kind"] == "video":
        return v_video(v, tone, lt)
    if v["kind"] == "candle":
        return v_candle(v, tone, lt)
    if v["kind"] == "scale":
        return v_scale(v, tone, lt)
    name = v.get("name", "city")
    shot = broll3d_frame(name, lt)
    return shot if shot is not None else scenes.scene(name, lt)


_SERIES = {}


def sensex_series(path, d0, d1):
    """Real daily closes from a Yahoo chart JSON, thinned to ~400 points (true min/max kept)."""
    import datetime as _dt
    key = (path, d0, d1)
    if key not in _SERIES:
        dd = json.loads(Path(path).read_text(encoding="utf-8"))["chart"]["result"][0]
        rows = [(_dt.datetime.utcfromtimestamp(t + 19800).date(), c)
                for t, c in zip(dd["timestamp"], dd["indicators"]["quote"][0]["close"]) if c]
        a, b = _dt.date.fromisoformat(d0), _dt.date.fromisoformat(d1)
        sel = [r for r in rows if a <= r[0] <= b]
        step = max(1, len(sel) // 400)
        out = sel[::step] + [sel[-1]]
        _SERIES[key] = (sorted(set(out)), dict(rows))
    return _SERIES[key]


def v_dips(v, tone, lt):
    """Real Sensex chart (log scale) with the dips marked: red dots at bottoms, green 'BUY' pins at buy days."""
    import datetime as _dt
    im = scenes.gradient(FW, PANEL_H, (10, 14, 24), (22, 28, 44))
    d = ImageDraw.Draw(im, "RGBA")
    pts, allm = sensex_series(v["data"], v.get("start", "1997-07-01"), v.get("end", "2026-11-20"))
    x0, x1, y0, y1 = 70, FW - 50, 300, 690
    lv = [math.log10(c) for _, c in pts]
    lo, hi = min(lv), max(lv)
    D0, D1 = pts[0][0], pts[-1][0]
    span = (D1 - D0).days

    def X(dt_):
        return x0 + (dt_ - D0).days / span * (x1 - x0)

    def Y(c):
        return y1 - (math.log10(c) - lo) / (hi - lo) * (y1 - y0)
    for yr in range(D0.year + 1, D1.year + 1, 4):
        xx = X(_dt.date(yr, 1, 1))
        d.line([xx, y0 - 10, xx, y1 + 10], fill=(255, 255, 255, 16), width=2)
        text_c(d, xx, y1 + 22, str(yr), BOLD(30), (150, 160, 180))
    prog = ease(lt / v.get("draw", 1.8))
    upto = D0 + _dt.timedelta(days=int(span * prog))
    line = [(X(a), Y(c)) for a, c in pts if a <= upto]
    for s0, s1 in v.get("shade", []):
        a_, b_ = _dt.date.fromisoformat(s0), _dt.date.fromisoformat(s1)
        if a_ <= upto:
            d.rectangle([X(a_), y0 - 10, X(min(b_, upto)), y1 + 10], fill=(225, 30, 45, 46))
    if len(line) > 1:
        d.line(line, fill=MINT, width=7, joint="curve")
    d.text((x0, 208), v.get("label", "SENSEX"), font=BLACK(48), fill=WHITE)
    for i, m in enumerate(v.get("marks", [])):
        md = _dt.date.fromisoformat(m)
        if md > upto or md not in allm:
            continue
        mx, my = X(md), Y(allm[md])
        a = back((lt - v.get("draw", 1.8) * (md - D0).days / span - 0.1) / 0.3)
        if a <= 0:
            continue
        r = 13 * a
        col = RED if v.get("mode", "bottom") == "bottom" else GREEN
        d.ellipse([mx - r, my - r, mx + r, my + r], fill=col, outline=WHITE, width=4)
        if v.get("mode") == "buy":
            pf = BLACK(int(26 * a) + 1)
            w = d.textlength("BUY", font=pf) + 20
            d.rounded_rectangle([mx - w / 2, my + 22, mx + w / 2, my + 58], radius=10, fill=GREEN)
            text_c(d, mx, my + 24, "BUY", pf, WHITE)
    if v.get("end_label") and prog > 0.97:
        ex, ey = line[-1]
        a = back((lt - v.get("draw", 1.8)) / 0.35)
        f = BLACK(int(58 * max(0.2, a)))
        w = d.textlength(v["end_label"], font=f) + 44
        xx = min(FW - 30 - w, ex - w / 2)
        d.rounded_rectangle([xx, ey - 120, xx + w, ey - 40], radius=18, fill=GREEN)
        text_c(d, xx + w / 2, ey - 116, v["end_label"], f, WHITE)
    return im.convert("RGBA")


_CANDLE = {}
_CSYM = {"CNY": "¥", "HKD": "HK$", "USD": "$", "INR": "₹"}


def v_candle(v, tone, lt):
    """Real daily candlesticks from longform/ipo_debuts/data/<slug>.json (Yahoo OHLC).
    v: slug, offer, label, marks (subset of d1/peak/now), days (optional limit), draw (s)."""
    if v["slug"] not in _CANDLE:
        p = HERE.parent / "longform" / "ipo_debuts" / "data" / f"{v['slug']}.json"
        _CANDLE[v["slug"]] = json.loads(p.read_text(encoding="utf-8"))
    dd = _CANDLE[v["slug"]]
    rows = dd["rows"][: v["days"]] if v.get("days") else dd["rows"]
    sym, offer = _CSYM.get(dd["currency"], ""), v["offer"]
    im = scenes.gradient(FW, PANEL_H, (10, 14, 24), (22, 28, 44))
    d = ImageDraw.Draw(im, "RGBA")
    x0, x1, y0, y1 = 60, FW - 40, 300, 690
    lo = min(min(r[3] for r in rows), offer)
    hi = max(max(r[2] for r in rows), offer)
    pad = (hi - lo) * 0.06
    lo, hi = max(0, lo - pad), hi + pad

    def Y(val):
        return y1 - (val - lo) / (hi - lo) * (y1 - y0)
    n = len(rows)
    st = (x1 - x0) / n
    X = lambda i: x0 + (i + 0.5) * st

    def money(val):
        if dd["currency"] == "INR" and val >= 1000:
            return sym + f"{val:,.0f}"
        return sym + (f"{val:,.0f}" if val >= 1000 else f"{val:,.2f}".rstrip("0").rstrip("."))
    oy = Y(offer)
    for xx in range(int(x0), int(x1), 34):
        d.line([xx, oy, xx + 18, oy], fill=AMBER, width=4)
    shown = max(1, int(n * ease(lt / v.get("draw", 1.6))))
    bw = max(2, st * 0.62)
    for i in range(shown):
        _, o, h, l, c, *_ = rows[i]
        col = GREEN if c >= o else RED
        x = X(i)
        d.line([x, Y(h), x, Y(l)], fill=col, width=max(2, int(min(6, st * 0.2))))
        t_, b_ = Y(max(o, c)), max(Y(max(o, c)) + 2, Y(min(o, c)))
        d.rectangle([x - bw / 2, t_, x + bw / 2, b_], fill=col)
    d.text((x0, 196), v.get("label", ""), font=BLACK(52), fill=WHITE)
    of = BOLD(34)
    lab = "IPO " + money(offer)
    w = d.textlength(lab, font=of) + 30
    ly = oy + 12 if oy < 620 else oy - 62
    d.rounded_rectangle([x0, ly, x0 + w, ly + 50], radius=14, fill=AMBER)
    text_c(d, x0 + w / 2, ly + 2, lab, of, INK)
    ip = max(range(n), key=lambda i: rows[i][2])
    for m in v.get("marks", ["d1", "now"]):
        if m == "d1":
            i, val, txt = 0, rows[0][4], "DAY-1"
        elif m == "peak":
            i, val, txt = ip, rows[ip][2], "PEAK"
        else:
            i, val, txt = n - 1, rows[-1][4], "AAJ"
        if i >= shown:
            continue
        a = back((lt - v.get("draw", 1.6) * (i + 1) / n) / 0.3)
        if a <= 0:
            continue
        pc = (val / offer - 1) * 100
        txt = f"{txt} {money(val)} · {'+' if pc >= 0 else '−'}{abs(pc):.0f}%"
        col = AMBER if m == "peak" else (GREEN if pc >= 0 else RED)
        mx, my = X(i), Y(val)
        d.ellipse([mx - 12, my - 12, mx + 12, my + 12], fill=col, outline=WHITE, width=4)
        f = BLACK(int(40 * max(0.2, a)))
        w = d.textlength(txt, font=f) + 36
        tx = min(max(x0, mx - w / 2), x1 - w)
        ty = my - 100 if m != "now" else my + 30
        ty = min(max(ty, 270), y1 + 20)
        d.line([mx, my, tx + w / 2, ty + 30], fill=(255, 255, 255, 170), width=3)
        d.rounded_rectangle([tx, ty, tx + w, ty + 62], radius=16, fill=col)
        text_c(d, tx + w / 2, ty + 4, txt, f, INK if m == "peak" else WHITE)
    return im.convert("RGBA")


def v_scale(v, tone, lt):
    """Hype vs Reality table: rows [[name, subscription_x (float), listing_gain_% (float), note]] ->
    hype bar (log of subscription) + reality bar (listing gain, green/red)."""
    im = scenes.gradient(FW, PANEL_H, (12, 16, 26), (24, 30, 46))
    d = ImageDraw.Draw(im, "RGBA")
    d.text((50, 196), v.get("label", "HYPE vs REALITY"), font=BLACK(52), fill=WHITE)
    rows = v["rows"]
    hi = v.get("hi", -1)
    rh = min(84, 400 / len(rows))
    for i, (name, sub, gain, note) in enumerate(rows):
        a = ease((lt - 0.2 - i * 0.35) / 0.4)
        if a <= 0:
            continue
        y = 300 + i * rh
        if i == hi:
            d.rounded_rectangle([30, y - 6, FW - 30, y + rh - 10], radius=16, fill=(255, 214, 0, 40))
        d.text((50, y), name, font=BLACK(36), fill=WHITE)
        d.text((50, y + 42), note, font=SEMI(22), fill=(150, 160, 180))
        hx0, hx1 = 430, 690
        hw = (hx1 - hx0) * min(1, math.log10(max(1, sub)) / math.log10(300)) * a
        d.rounded_rectangle([hx0, y + 10, hx0 + max(8, hw), y + 46], radius=10, fill=AMBER)
        d.text((hx0, y + 52), f"{sub:g}x", font=BOLD(26), fill=AMBER)
        rx = 860
        gw = 150 * min(1, abs(gain) / 70) * a
        col = GREEN if gain >= 0 else RED
        if gain >= 0:
            d.rounded_rectangle([rx, y + 10, rx + max(8, gw), y + 46], radius=10, fill=col)
        else:
            d.rounded_rectangle([rx - max(8, gw), y + 10, rx, y + 46], radius=10, fill=col)
        d.line([rx, y + 2, rx, y + 56], fill=(255, 255, 255, 120), width=3)
        d.text((rx, y + 52), f"{'+' if gain >= 0 else '−'}{abs(gain):g}%", font=BOLD(26), fill=col, anchor="ma")
    d.text((560, 262), "HYPE · subscription", font=BLACK(24), fill=AMBER, anchor="ma")
    d.text((900, 262), "REALITY · listing", font=BLACK(24), fill=GREEN, anchor="ma")
    return im.convert("RGBA")


_PHOTO = {}


def v_photo(v, tone, lt):
    """Real public-domain photo (Ken Burns push) + quote card + credit line."""
    path = HERE / v["image"]
    if path not in _PHOTO:
        ph = Image.open(path).convert("RGB")
        r = max(FW / ph.width, PANEL_H / ph.height) * 1.12
        _PHOTO[path] = ph.resize((int(ph.width * r), int(ph.height * r)), Image.LANCZOS)
    ph = _PHOTO[path]
    k = ease(lt / 6.0)
    z = 1.0 + 0.06 * k
    cw = int(ph.width / 1.12 / z)
    chh = int(ph.height / 1.12 / z)
    fx, fy = v.get("focus", (0.5, 0.35))
    left = int((ph.width - cw) * fx)
    top = int((ph.height - chh) * fy)
    im = ph.crop((left, top, left + cw, top + chh)).resize((FW, PANEL_H), Image.LANCZOS).convert("RGBA")
    return photo_overlays(im, v, lt)


_VFR = {}


def video_frames(rel):
    """Frames of a free-licence clip (episodes/resources/videos/x.mp4), cover-cropped to the panel once and
    cached in resources/videos/_frames/<name>/0001.jpg... so every episode can reuse them."""
    src = HERE / rel
    d = src.parent / "_frames" / src.stem
    if rel not in _VFR:
        if not (d.is_dir() and any(d.glob("*.jpg"))):
            import imageio_ffmpeg
            d.mkdir(parents=True, exist_ok=True)
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-i", str(src), "-vf",
                            f"fps={FPS},scale={FW}:{PANEL_H}:force_original_aspect_ratio=increase,crop={FW}:{PANEL_H}",
                            "-q:v", "3", str(d / "%04d.jpg")], check=True)
        _VFR[rel] = (d, len(list(d.glob("*.jpg"))))
    return _VFR[rel]


def v_video(v, tone, lt):
    """Free-licence video clip as B-roll (plays from v["start"] s, loops if the beat is longer),
    with the same name tag / fact rows / credit overlays as photos."""
    d, n = video_frames(v["video"])
    i = (int(v.get("start", 0) * FPS) + max(0, int(lt * FPS))) % max(1, n)
    im = Image.open(d / f"{i + 1:04d}.jpg").convert("RGBA")
    return photo_overlays(im, v, lt)


def photo_overlays(im, v, lt):
    shade = Image.new("RGBA", (FW, PANEL_H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(PANEL_H):
        a = int(max(0, (y - 330) / (PANEL_H - 330)) * 215)
        sd.line([0, y, FW, y], fill=(0, 0, 0, a))
    im.alpha_composite(shade)
    d = ImageDraw.Draw(im, "RGBA")
    if v.get("name"):
        a = back((lt - 0.2) / 0.35)
        if a > 0:
            f = BLACK(int(46 * a) + 1)
            w = d.textlength(v["name"], font=f) + 44
            d.rounded_rectangle([40, 230, 40 + w, 300], radius=14, fill=(255, 214, 0))
            d.text((62, 236), v["name"], font=f, fill=INK)
    q = v.get("quote")
    if q:
        a = ease((lt - 0.6) / 0.5)
        f = BLACK(62)
        lines = wrap(d, "“" + q + "”", f, FW - 140)
        y = 330 + (1 - a) * 40
        for ln in lines:
            d.text((70, y), ln, font=f, fill=(255, 255, 255, int(255 * a)), stroke_width=5, stroke_fill=(0, 0, 0, int(220 * a)))
            y += 74
        if v.get("source"):
            d.text((70, y + 8), v["source"], font=BOLD(34), fill=(255, 214, 0, int(255 * a)), stroke_width=3,
                   stroke_fill=(0, 0, 0, int(200 * a)))
    rows = v.get("rows")
    if rows:  # fact card over the photo: [[label, value, "up|down|"], ...]
        y0 = 322
        a0 = ease((lt - 0.35) / 0.4)
        if a0 > 0:
            # no full card: the photo stays visible; only the words get a tight translucent highlight
            for i, r in enumerate(rows):
                a = back((lt - 0.45 - i * 0.28) / 0.3)
                if a <= 0:
                    continue
                al = min(1.0, a)
                yy = y0 + 18 + i * 74
                col = GREEN if (len(r) > 2 and r[2] == "up") else RED if (len(r) > 2 and r[2] == "down") else (255, 214, 0)
                fl = BOLD(36)
                lw = d.textlength(r[0], font=fl)
                d.rounded_rectangle([52, yy + 2, 52 + lw + 36, yy + 58], radius=14, fill=(8, 12, 20, int(165 * al)))
                d.text((70, yy + 7), r[0], font=fl, fill=(235, 240, 248), stroke_width=2, stroke_fill=(0, 0, 0))
                f = fit(d, r[1], BLACK, 48, FW - 420)
                vw = d.textlength(r[1], font=f)
                d.rounded_rectangle([FW - 88 - vw, yy - 4, FW - 52, yy + 62], radius=16, fill=(8, 12, 20, int(175 * al)))
                d.text((FW - 70, yy), r[1], font=f, fill=col, anchor="ra", stroke_width=2, stroke_fill=(0, 0, 0))
    if v.get("credit"):
        cy = (322 + 30 + 74 * len(rows) + 10) if rows else PANEL_H - 300
        d.text((FW - 50, cy), v["credit"], font=SEMI(22), fill=(255, 255, 255, 170), anchor="ra")
    return im


BROLL3D = HERE / "broll3d"
ALIAS3D = {"money": "coins"}
_N3D = {}


def broll3d_frame(name, lt):
    """A frame of a Blender-rendered 3D shot (broll3d/NAME/0001.jpg...), bounced back and forth
    if the beat runs longer than the shot; the still (NAME_still.jpg) with a slow zoom otherwise."""
    name = ALIAS3D.get(name, name)
    d = BROLL3D / name
    if name not in _N3D:
        _N3D[name] = len(list(d.glob("*.jpg"))) if d.is_dir() else 0
    n = _N3D[name]
    if n:
        # shots are 8 s, longer than any beat; play forward once and hold the last frame (never reverse)
        i = min(max(0, int(lt * FPS)), n - 1)
        return Image.open(d / f"{i + 1:04d}.jpg").convert("RGBA")
    still = BROLL3D / f"{name}_still.jpg"
    if still.exists():
        return Image.open(still).convert("RGBA")
    return None


# ----------------------------------------------------------------------------
# static studio layer
# ----------------------------------------------------------------------------
def make_studio():
    bg = scenes.gradient(FW, FH, (9, 24, 44), (10, 62, 66))
    d = ImageDraw.Draw(bg, "RGBA")
    for i, a in enumerate((10, 10, 12, 14)):
        d.ellipse([-200 + i * 70, 1250 + i * 50, 1280 - i * 70, 2400], fill=(46, 211, 160, a))
    rng = np.random.default_rng(7)
    x = 0
    while x < FW:  # faint bar chart wall
        bw = int(rng.integers(60, 100))
        bh = int(rng.integers(120, 420))
        d.rounded_rectangle([x, FLOOR_Y - bh, x + bw, FLOOR_Y], radius=12, fill=(46, 211, 160, 26))
        x += bw + int(rng.integers(25, 60))
    d.rectangle([0, FLOOR_Y, FW, FH], fill=(7, 34, 40, 255))
    d.line([0, FLOOR_Y, FW, FLOOR_Y], fill=(30, 120, 100, 255), width=3)
    return bg.convert("RGBA")


STUDIO = make_studio()
CHAIR = draw_chair(1.0)
CASE = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
briefcase(Pen(CASE, 1), 150, 150)


# ----------------------------------------------------------------------------
# frame
# ----------------------------------------------------------------------------
def story_index(si):
    sid = SEGS[si]["id"]
    return STORIES.index(sid) + 1 if sid in STORIES else 0


def draw_sting(fr, t):
    """Red 'BREAKING · KHABAR 0N/NN' card at the start of each story."""
    for si, s in enumerate(TL["segments"]):
        n = story_index(si)
        if not n:
            continue
        t0, t1 = s["start"] - 0.45, s["start"] + 0.3
        if not (t0 <= t < t1):
            continue
        k = (t - t0) / (t1 - t0)
        if k < 0.22:
            x = FW * (1 - ease(k / 0.22))
        elif k > 0.8:
            x = -FW * ease((k - 0.8) / 0.2)
        else:
            x = 0
        card = Image.new("RGB", (FW, PANEL_H), (205, 18, 32))
        d = ImageDraw.Draw(card, "RGBA")
        for yy in range(0, PANEL_H, 8):
            d.line([0, yy, FW, yy], fill=(255, 255, 255, 10), width=2)
        num = f"{n:02d}"
        text_c(d, FW / 2 + 250, 330, num, BLACK(520), (222, 52, 64))
        st = SCRIPT.get("sting", {})
        pill = f"{st.get('pill', 'KHABAR')} {num} / {len(STORIES):02d}"
        pf = BLACK(40)
        w = d.textlength(pill, font=pf) + 60
        d.rounded_rectangle([FW / 2 - w / 2, 300, FW / 2 + w / 2, 368], radius=34, fill=WHITE)
        text_c(d, FW / 2, 306, pill, pf, (205, 18, 32))
        ttl = st.get("title", "BREAKING")
        text_c(d, FW / 2, 390, ttl, fit(d, ttl, BLACK, 150, FW - 80), WHITE)
        d.line([FW / 2 - 230, 600, FW / 2 + 230, 600], fill=WHITE, width=5)
        fr.paste(card, (int(x), 0))
        return True
    return False


def push(img, lt, amount=0.05, dur=8.0):
    """Slow sub-pixel push-in so no panel ever sits perfectly still (smooth at 30 fps)."""
    k = min(1.0, max(0.0, lt / dur))
    k = k * k * (3 - 2 * k) * 0.6 + k * 0.4
    z = 1.0 + amount * k
    w, h = img.size
    cx, cy = w / 2, h * 0.45
    return img.transform((w, h), Image.AFFINE, (1 / z, 0, cx - cx / z, 0, 1 / z, cy - cy / z), resample=Image.BILINEAR)


def shift(img, dx):
    """Sub-pixel horizontal shift, edges filled from the image itself."""
    if abs(dx) < 0.01:
        return img
    return img.transform(img.size, Image.AFFINE, (1, 0, -dx, 0, 1, 0), resample=Image.BILINEAR, fillcolor=(0, 0, 0, 255))


CUR_T = 0.0


def render_frame(t):
    global CUR_T
    CUR_T = t
    fr = STUDIO.copy()
    segs = TL["segments"]
    si = seg_at(t)
    seg, stl = SEGS[si], segs[si]
    speaking = any(s["start"] <= t <= s["end"] for s in segs)

    # ---------- presenter (unchanged character): walk in, sit, talk ----------
    px, py = 240, FLOOR_Y - 840
    WALK_END, SIT_END = 1.3, 1.75
    fr.alpha_composite(CHAIR, (px, py))
    blink = 1.0 if (t % 3.3) < 0.12 else 0.0
    mouth = mouth_at(t, speaking)
    if t < WALK_END:
        k = ease(t / WALK_END)
        x = int(-520 + (px + 520) * k)
        pose = {"mode": "walk", "sit": 0, "phase": t * 11, "bob": abs(math.sin(t * 11)) * -8,
                "mouth": mouth, "blink": blink}
        fr.alpha_composite(draw_presenter(pose), (x, py - 50))
    else:
        sk = ease((t - WALK_END) / (SIT_END - WALK_END))
        fr.alpha_composite(CASE, (px - 190, FLOOR_Y - 240))
        g = 0.55 + 0.4 * math.sin(t * 1.3 + si) if speaking else 0.25
        pose = {"mode": "sit" if sk > 0.5 else "stand", "sit": sk, "mouth": mouth, "blink": blink,
                "gesture": g, "wave": 8 * math.sin(t * 5.5) * (1 if speaking else 0.2),
                "bob": math.sin(t * 2.4) * 3, "look": 0.3 * math.sin(t * 0.7), "case": False,
                "brow": 0.5 if mouth > 0.7 else 0.0}
        fr.alpha_composite(draw_presenter(pose), (px, py - int(50 * (1 - sk))))

    # ---------- B-roll panel ----------
    bi, beat, bstart = beat_at(si, t)
    lt = t - bstart
    vis = push(panel_visual(si, beat, lt), lt)
    # new beat: short eased slide + crossfade over the previous beat (which keeps moving)
    TR = 0.45
    if lt < TR and bi > 0:
        pbeat = (seg.get("beats") or [{}])[bi - 1]
        pstart = beat_starts(si)[bi - 1] if bi - 1 > 0 else TL["segments"][si]["start"] - 0.35
        plt = t - pstart
        prev = push(panel_visual(si, pbeat, plt), plt)
        k = ease(lt / TR)
        a = min(1.0, max(0.0, lt / (TR * 0.7)))
        a = a * a * (3 - 2 * a)
        base = shift(prev, -0.10 * FW * k)
        top = shift(vis, 0.22 * FW * (1 - k))
        fr.alpha_composite(Image.blend(base, top, a), (0, 0))
    else:
        fr.alpha_composite(vis, (0, 0))
    d = ImageDraw.Draw(fr, "RGBA")
    # foot gradient for captions ("captions": false in the script = no burned-in captions; the user
    # uploads .srt subtitle files instead so YouTube auto-dubbing isn't fighting on-screen text, 2026-11-23)
    show_caps = SCRIPT.get("captions", True)
    if show_caps:
        grad = scenes.gradient(FW, 260, (0, 0, 0), (0, 0, 0))
        mask = Image.fromarray((np.linspace(0, 200, 260)[:, None] * np.ones((1, FW))).astype(np.uint8), "L")
        grad.putalpha(mask)
        fr.alpha_composite(grad, (0, PANEL_H - 260))

    # topic tag (red label on the visual)
    tag = beat.get("tag") or seg.get("tag")
    if tag and seg["id"] not in ("hook", "outro"):
        a = ease((lt - 0.25) / 0.3)
        tf = BLACK(42)
        w = d.textlength(tag, font=tf) + 44
        x = 28 - (1 - a) * (w + 60)
        d.rectangle([x, 122, x + w, 188], fill=(205, 18, 32))
        d.text((x + 22, 125), tag, font=tf, fill=WHITE)

    # captions at the foot of the panel
    for ch in (caption_chunks(si) if show_caps else []):
        if ch["start"] <= t < ch["end"] + 0.05:
            a = back((t - ch["start"]) / 0.18)
            f = BLACK(int(60 * (0.85 + 0.15 * a)))
            lines = wrap(d, ch["text"], f, 980)
            y = 640 if len(lines) > 1 else 705
            for line in lines[:2]:
                total = d.textlength(line, font=f)
                x = FW / 2 - total / 2
                for w in line.split():
                    col = (255, 214, 64) if is_key(w) else WHITE
                    d.text((x, y), w, font=f, fill=col, stroke_width=7, stroke_fill=(0, 0, 0))
                    x += d.textlength(w + " ", font=f)
                y += f.size + 10
            break

    # ---------- ticker strip ----------
    d.rectangle([0, TICK_Y0, FW, TICK_Y1], fill=(14, 16, 22))
    items = SCRIPT.get("ticker") or []
    if items:
        tf = BOLD(34)
        line = "     •     ".join(items) + "     •     "
        lw = d.textlength(line, font=tf)
        off = (t * 120) % lw
        x = 230 - off
        while x < FW:
            for part in re.split(r"(▲[^•]*|▼[^•]*)", line):
                if not part:
                    continue
                col = GREEN if part.startswith("▲") else RED if part.startswith("▼") else (220, 225, 235)
                if x + d.textlength(part, font=tf) > 210:
                    d.text((x, TICK_Y0 + 10), part, font=tf, fill=col)
                x += d.textlength(part, font=tf)
    d.rectangle([0, TICK_Y0, 210, TICK_Y1], fill=(205, 18, 32))
    text_c(d, 105, TICK_Y0 + 11, SCRIPT.get("ticker_label", "MARKETS"), BLACK(32), WHITE)

    # ---------- headline banner ----------
    ban = beat.get("banner") or [seg.get("headline", ""), ""]
    if seg["id"] == "outro":
        ban = SCRIPT.get("outro_banner", ["Kal phir milte hain", "StickBiz Brief ke saath"])
    a = back(lt / 0.3) if bi > 0 or lt < 0.6 else 1
    bx0, bx1 = 36, FW - 36
    by0 = BAN_Y0 + (1 - a) * 30
    d.rounded_rectangle([bx0, by0, bx1, BAN_Y1], radius=24, fill=WHITE)
    date = SCRIPT.get("date_label", "")
    if date:
        text_c(d, FW / 2, by0 + 14, date, BOLD(28), (130, 135, 150))
    l1 = ban[0] if ban else ""
    l2 = ban[1] if len(ban) > 1 else ""
    f1 = fit(d, l1.upper(), BLACK, 58, bx1 - bx0 - 60)
    f2 = fit(d, l2.upper(), BLACK, 58, bx1 - bx0 - 60)
    text_c(d, FW / 2, by0 + 50, l1.upper(), f1, INK)
    text_c(d, FW / 2, by0 + 112, l2.upper(), f2, tone_col(beat.get("tone", "neutral")) if seg["id"] != "hook" else RED)

    # ---------- story sting ----------
    draw_sting(fr, t)
    d = ImageDraw.Draw(fr, "RGBA")

    # ---------- top bar: progress, LIVE countdown, brand ----------
    rem = max(0.0, DUR - t)
    d.rectangle([0, 0, FW, 8], fill=(255, 255, 255, 50))
    d.rectangle([0, 0, FW * (1 - rem / DUR), 8], fill=(205, 18, 32))
    d.rounded_rectangle([28, 34, 268, 104], radius=35, fill=(0, 0, 0, 175))
    on = (t * 2) % 2 < 1.4
    d.ellipse([50, 56, 76, 82], fill=(235, 30, 40) if on else (120, 20, 25))
    d.text((88, 44), "LIVE", font=BLACK(36), fill=WHITE)
    m, s = divmod(int(math.ceil(rem)), 60)
    d.text((178, 44), f"{m}:{s:02d}", font=BLACK(36), fill=(255, 214, 64) if rem <= 10 else WHITE)
    bf = BLACK(40)
    bw = d.textlength("StickBiz Brief", font=bf)
    d.rounded_rectangle([FW - 60 - bw, 34, FW - 28, 104], radius=35, fill=(0, 0, 0, 175))
    bx = FW - 44 - bw
    d.text((bx, 46), "Stick", font=bf, fill=WHITE)
    bx += d.textlength("Stick", font=bf)
    d.text((bx, 46), "Biz", font=bf, fill=MINT)
    bx += d.textlength("Biz", font=bf)
    d.text((bx, 46), " Brief", font=bf, fill=WHITE)

    hit = TL["segments"][0]["start"] - 0.35
    if hit <= t < hit + 0.2:
        d.rectangle([0, 0, FW, FH], fill=(255, 255, 255, int(150 * (1 - (t - hit) / 0.2))))
    return fr.convert("RGB")


def encode(dst, t0, t1, audio=None):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{FW}x{FH}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(audio), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = int(round((t1 - t0) * FPS))
    for i in range(n):
        proc.stdin.write(render_frame(t0 + i / FPS).tobytes())
        if i % 300 == 0:
            print(f"frame {i}/{n}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("wrote", dst)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if mode == "preview":
        ts = [float(x) for x in sys.argv[2:]] or [0.5, 3.0, 12.0]
        for t in ts:
            render_frame(t).save(OUT / f"v2_preview_{t:06.2f}.png")
            print("saved", OUT / f"v2_preview_{t:06.2f}.png")
        print("duration", round(DUR, 1), "estimated" if TL.get("estimated") else "")
    elif mode == "clip":
        t0, t1, name = float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
        audio = OUT / "mix.wav" if not TL.get("estimated") else None
        encode(OUT / f"{name}.mp4", t0, min(t1, DUR), audio)
    elif mode == "part":   # bot: render part k of n (video only, frame-exact) on parallel machines
        k, n = int(sys.argv[2]), int(sys.argv[3])
        total = int(round(DUR * FPS))
        f0, f1 = total * k // n, total * (k + 1) // n
        encode(OUT / f"part_{k}.mp4", f0 / FPS, f1 / FPS, None)
    elif mode == "times":
        for si, s in enumerate(TL["segments"]):
            print(s["id"], round(s["start"], 2), round(s["end"], 2), [round(x, 2) for x in beat_starts(si)])
    else:
        encode(OUT / "stickbiz_short.mp4", 0, DUR, OUT / "mix.wav")


if __name__ == "__main__":
    main()

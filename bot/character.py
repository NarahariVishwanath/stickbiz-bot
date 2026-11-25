"""StickBiz Brief presenter, drawn with Pillow so it can walk, sit, blink and talk.

draw_presenter(pose) returns an RGBA image of size (W, H) * scale.
Design units: canvas 600 x 840, character faces the viewer.
"""
import math
from PIL import Image, ImageDraw

W, H = 600, 840
SS = 2  # supersampling for smooth edges

SKIN = (247, 205, 170)
SKIN_D = (226, 168, 132)
HAIR = (110, 64, 32)
HAIR_D = (82, 46, 22)
SUIT = (44, 58, 104)
SUIT_D = (30, 40, 76)
PANTS = (36, 46, 86)
SHIRT = (250, 250, 252)
TIE = (214, 45, 45)
TIE_D = (170, 28, 32)
MINT = (46, 211, 160)
SHOE = (22, 22, 26)
BRIEF = (150, 92, 52)
BRIEF_D = (112, 66, 36)
GOLD = (240, 200, 80)
EYE_W = (255, 255, 255)
IRIS = (92, 52, 24)
PUPIL = (28, 16, 10)
MOUTH = (140, 30, 44)
TONGUE = (236, 120, 130)
CHEEK = (246, 168, 160)


def bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 3
        b = 3 * (1 - t) ** 2 * t
        c = 3 * (1 - t) * t * t
        d = t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


class Pen:
    def __init__(self, img, s):
        self.d = ImageDraw.Draw(img, "RGBA")
        self.s = s

    def P(self, pts):
        return [(x * self.s, y * self.s) for x, y in pts]

    def ell(self, cx, cy, rx, ry, fill, outline=None, w=0):
        s = self.s
        self.d.ellipse([(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s],
                       fill=fill, outline=outline, width=int(w * s))

    def poly(self, pts, fill):
        self.d.polygon(self.P(pts), fill=fill)

    def rrect(self, x0, y0, x1, y1, r, fill):
        s = self.s
        self.d.rounded_rectangle([x0 * s, y0 * s, x1 * s, y1 * s], radius=r * s, fill=fill)

    def limb(self, pts, width, fill, edge=None):
        s = self.s
        if edge:
            self.limb(pts, width + 8, edge)
        self.d.line(self.P(pts), fill=fill, width=int(width * s), joint="curve")
        for x, y in (pts[0], pts[-1]):
            self.ell(x, y, width / 2, width / 2, fill)

    def arc(self, box, a0, a1, fill, w):
        s = self.s
        self.d.arc([b * s for b in box], a0, a1, fill=fill, width=int(w * s))


def hand(pen, x, y, point_angle=None, r=24):
    """A round hand; if point_angle (degrees, 0 = up) is given, add a pointing finger."""
    if point_angle is not None:
        a = math.radians(point_angle)
        fx, fy = x + math.sin(a) * 40, y - math.cos(a) * 40
        pen.limb([(x, y), (fx, fy)], 15, SKIN)
    pen.ell(x, y, r, r, SKIN)
    pen.ell(x - 5, y + 7, r * 0.5, r * 0.35, (238, 190, 154))


def head(pen, cx, cy, mouth=0.0, blink=0.0, look=0.0, brow=0.0):
    # ears
    for ex in (cx - 148, cx + 148):
        pen.ell(ex, cy + 18, 20, 30, SKIN)
        pen.ell(ex, cy + 18, 10, 17, SKIN_D)
    # back hair
    pen.ell(cx, cy - 22, 162, 140, HAIR)
    # face
    pen.ell(cx, cy + 20, 148, 132, SKIN)
    # fringe with a side part sweeping to the right
    fr = (bez((cx - 158, cy + 10), (cx - 170, cy - 120), (cx - 40, cy - 150), (cx + 60, cy - 140))
          + bez((cx + 60, cy - 140), (cx + 150, cy - 130), (cx + 175, cy - 60), (cx + 150, cy + 5))
          + bez((cx + 150, cy + 5), (cx + 120, cy - 70), (cx + 60, cy - 80), (cx - 10, cy - 70))
          + bez((cx - 10, cy - 70), (cx - 90, cy - 62), (cx - 135, cy - 40), (cx - 158, cy + 10)))
    pen.poly(fr, HAIR)
    # hair shine strands
    pen.arc((cx - 110, cy - 135, cx + 80, cy - 40), 200, 300, HAIR_D, 7)
    pen.arc((cx - 40, cy - 140, cx + 150, cy - 60), 210, 290, (140, 88, 48), 6)
    # eyebrows
    by = cy - 30 - brow * 10
    pen.arc((cx - 100, by, cx - 30, by + 40), 200, 330, HAIR_D, 9)
    pen.arc((cx + 30, by, cx + 100, by + 40), 210, 340, HAIR_D, 9)
    # eyes
    for ex in (cx - 62, cx + 62):
        ey = cy + 22
        ry = 34 * (1 - 0.92 * blink)
        pen.ell(ex, ey, 30, ry, EYE_W, outline=(60, 40, 30), w=3)
        if blink < 0.6:
            ix = ex + look * 8
            pen.ell(ix, ey + 4, 21, min(22, ry), IRIS)
            pen.ell(ix, ey + 5, 12, min(13, ry * 0.6), PUPIL)
            pen.ell(ix + 7, ey - 5, 6, 6, (255, 255, 255))
            pen.ell(ix - 7, ey + 10, 3, 3, (255, 255, 255, 200))
    # nose
    pen.arc((cx - 12, cy + 48, cx + 12, cy + 72), 20, 160, SKIN_D, 5)
    # cheeks
    pen.ell(cx - 98, cy + 72, 30, 17, CHEEK)
    pen.ell(cx + 98, cy + 72, 30, 17, CHEEK)
    # mouth: a smile that opens with `mouth` (0..1)
    my = cy + 92
    hw = 38 + 6 * mouth
    depth = 14 + 38 * mouth
    top = bez((cx - hw, my), (cx - hw / 2, my + 6), (cx + hw / 2, my + 6), (cx + hw, my), 16)
    bot = bez((cx + hw, my), (cx + hw * 0.7, my + depth * 1.3), (cx - hw * 0.7, my + depth * 1.3), (cx - hw, my), 16)
    pen.poly(top + bot, MOUTH)
    if mouth > 0.25:
        pen.ell(cx, my + depth * 0.85, hw * 0.5, depth * 0.3, TONGUE)
        pen.poly(bez((cx - hw * 0.8, my + 3), (cx - hw * 0.4, my + 10), (cx + hw * 0.4, my + 10), (cx + hw * 0.8, my + 3), 10)
                 + [(cx + hw * 0.7, my + 1), (cx - hw * 0.7, my + 1)], SHIRT)


def torso(pen, cx, top):
    """Jacket, shirt, tie. `top` = shoulder line y."""
    # neck
    pen.rrect(cx - 26, top - 30, cx + 26, top + 20, 10, SKIN_D)
    body = (bez((cx - 96, top + 6), (cx - 118, top + 80), (cx - 112, top + 180), (cx - 100, top + 250))
            + bez((cx - 100, top + 250), (cx - 40, top + 262), (cx + 40, top + 262), (cx + 100, top + 250))
            + bez((cx + 100, top + 250), (cx + 112, top + 180), (cx + 118, top + 80), (cx + 96, top + 6))
            + [(cx + 40, top - 6), (cx - 40, top - 6)])
    pen.poly(body, SUIT)
    # shirt V
    pen.poly([(cx - 40, top - 6), (cx + 40, top - 6), (cx, top + 125)], SHIRT)
    # collar points
    pen.poly([(cx - 40, top - 6), (cx - 6, top + 14), (cx - 26, top + 30)], (232, 232, 238))
    pen.poly([(cx + 40, top - 6), (cx + 6, top + 14), (cx + 26, top + 30)], (232, 232, 238))
    # tie
    pen.poly([(cx - 14, top + 6), (cx + 14, top + 6), (cx + 9, top + 28), (cx - 9, top + 28)], TIE_D)
    pen.poly([(cx - 9, top + 28), (cx + 9, top + 28), (cx + 17, top + 108), (cx, top + 126), (cx - 17, top + 108)], TIE)
    # lapels
    pen.poly([(cx - 40, top - 6), (cx - 70, top + 20), (cx - 46, top + 62), (cx - 62, top + 70), (cx, top + 140)], SUIT_D)
    pen.poly([(cx + 40, top - 6), (cx + 70, top + 20), (cx + 46, top + 62), (cx + 62, top + 70), (cx, top + 140)], SUIT_D)
    # pocket square + button
    pen.poly([(cx + 58, top + 92), (cx + 92, top + 88), (cx + 88, top + 104), (cx + 60, top + 106)], MINT)
    pen.ell(cx, top + 182, 7, 7, (18, 22, 40))
    pen.ell(cx, top + 222, 6, 6, (18, 22, 40))


def briefcase(pen, x, y):
    pen.arc((x - 26, y - 34, x + 26, y + 10), 180, 360, BRIEF_D, 8)
    pen.rrect(x - 66, y - 12, x + 66, y + 82, 12, BRIEF)
    pen.rrect(x - 66, y + 24, x + 66, y + 32, 2, BRIEF_D)
    pen.rrect(x - 10, y + 18, x + 10, y + 38, 3, GOLD)


def draw_presenter(pose=None, scale=1.0):
    """pose keys:
       mode: 'walk' | 'sit' | 'stand'
       phase: walk cycle phase (radians)
       sit: 0..1 blend from standing to seated (used for the sit-down move)
       mouth, blink, look, brow: face controls
       gesture: 0..1 pointing arm raise; wave: small wobble in degrees
       bob: vertical body offset in units
    """
    p = dict(mode="sit", phase=0.0, sit=1.0, mouth=0.0, blink=0.0, look=0.0, brow=0.0,
             gesture=0.6, wave=0.0, bob=0.0, case=True)
    if pose:
        p.update(pose)
    s = SS * scale
    img = Image.new("RGBA", (int(W * s), int(H * s)), (0, 0, 0, 0))
    pen = Pen(img, s)
    cx = 300
    sit = p["sit"]
    drop = 70 * sit  # seated body sits lower
    shoulder = 400 + drop + p["bob"]
    hip = shoulder + 245

    # ---- legs ----
    if p["mode"] == "walk" or sit < 0.5:
        ph = p["phase"]
        for side, off in ((-1, 0.0), (1, math.pi)):
            sw = math.sin(ph + off) * 34 * (1 - sit * 2 if sit < 0.5 else 0)
            hx = cx + side * 42
            knee = (hx + sw * 0.5, hip + 90)
            foot = (hx + sw, 800 - max(0, math.cos(ph + off)) * 10 * (p["mode"] == "walk"))
            pen.limb([(hx, hip - 10), knee, foot], 58, PANTS)
            pen.ell(foot[0] + side * 8, foot[1] + 20, 44, 20, SHOE)
            pen.ell(foot[0] + side * 8 - 12, foot[1] + 13, 14, 5, (90, 90, 100))
    else:
        # seated, facing us: short thighs toward the camera, shins down to the floor
        for side in (-1, 1):
            hx = cx + side * 52
            pen.rrect(hx - 40, hip - 30, hx + 40, hip + 52, 30, PANTS)  # thigh (foreshortened)
            pen.limb([(hx, hip + 40), (hx + side * 6, 790)], 60, PANTS)
            pen.ell(hx + side * 10, 808, 46, 21, SHOE)
            pen.ell(hx + side * 10 - 12, 801, 14, 5, (90, 90, 100))
        # knee shading
        pen.ell(cx - 52, hip + 40, 30, 10, (30, 38, 70))
        pen.ell(cx + 52, hip + 40, 30, 10, (30, 38, 70))

    # ---- left arm (viewer's left): carries the case while walking, rests on lap when seated ----
    lsx, lsy = cx - 100, shoulder + 26
    torso(pen, cx, shoulder)
    if p["mode"] == "walk" or sit < 0.5:
        swing = math.sin(p["phase"] + math.pi) * 8 if p["mode"] == "walk" else 0
        lh = (lsx - 30 + swing, shoulder + 225)
        pen.limb([(lsx, lsy), (lsx - 34, shoulder + 120), lh], 50, SUIT, SUIT_D)
        if p["case"]:
            briefcase(pen, lh[0], lh[1] + 40)
        pen.rrect(lh[0] - 20, lh[1] - 26, lh[0] + 20, lh[1] - 12, 5, SHIRT)
        hand(pen, *lh)
    if not (p["mode"] == "walk" or sit < 0.5):
        lh = (cx - 60, hip + 10)
        pen.limb([(lsx, lsy), (lsx - 28, shoulder + 140), lh], 50, SUIT, SUIT_D)
        pen.rrect(lh[0] - 30, lh[1] - 20, lh[0] - 12, lh[1] + 8, 5, SHIRT)
        hand(pen, *lh)

    # ---- right arm (viewer's right): points up while explaining ----
    rsx, rsy = cx + 100, shoulder + 26
    g = p["gesture"]
    if p["mode"] == "walk" or sit < 0.5:
        swing = math.sin(p["phase"]) * 10 if p["mode"] == "walk" else 0
        rh = (rsx + 30 + swing, shoulder + 220)
        relb = (rsx + 34, shoulder + 120)
        pen.limb([(rsx, rsy), relb, rh], 50, SUIT, SUIT_D)
        hand(pen, *rh)
    else:
        ang = math.radians(-20 - 95 * g + p["wave"])  # forearm direction
        relb = (rsx + 40 + 25 * g, shoulder + 125 - 45 * g)
        rh = (relb[0] + math.cos(ang) * 95, relb[1] + math.sin(ang) * 95)
        pen.limb([(rsx, rsy), relb, rh], 50, SUIT, SUIT_D)
        cuff = (relb[0] + math.cos(ang) * 72, relb[1] + math.sin(ang) * 72)
        pen.ell(cuff[0], cuff[1], 20, 20, SHIRT)
        hand(pen, *rh, point_angle=(10 + p["wave"]) if g > 0.35 else None)

    head(pen, cx, shoulder - 175, p["mouth"], p["blink"], p["look"], p["brow"])
    return img.resize((int(W * scale), int(H * scale)), Image.LANCZOS)


def draw_chair(scale=1.0):
    """Brown leather executive office chair seen from the front, drawn behind the seated presenter."""
    s = SS * scale
    img = Image.new("RGBA", (int(W * s), int(H * s)), (0, 0, 0, 0))
    pen = Pen(img, s)
    cx = 300
    RIM = (214, 158, 104)      # warm rim light so it stands off the teal background
    EDGE = (70, 38, 18)
    LEATHER = (128, 76, 40)
    LEATHER_L = (156, 98, 56)
    LEATHER_D = (98, 56, 28)
    METAL = (34, 34, 40)
    CHROME = (190, 196, 206)
    # floor shadow
    pen.ell(cx, 834, 230, 22, (0, 0, 0, 90))
    # five-star base with casters
    for ex, ey in ((cx - 210, 818), (cx + 210, 818), (cx - 110, 832), (cx + 110, 832), (cx, 826)):
        pen.limb([(cx, 800), (ex, ey)], 18, METAL)
        pen.ell(ex, ey + 10, 15, 13, (18, 18, 22))
        pen.ell(ex - 4, ey + 6, 5, 4, (90, 90, 100))
    pen.ell(cx, 800, 26, 14, METAL)
    # gas lift (chrome)
    pen.rrect(cx - 16, 738, cx + 16, 804, 6, CHROME)
    pen.rrect(cx - 16, 738, cx - 6, 804, 4, (236, 240, 246))
    pen.rrect(cx - 60, 728, cx + 60, 750, 8, METAL)  # mechanism
    # tall backrest with headrest wings
    pen.rrect(cx - 196, 214, cx + 196, 712, 96, RIM)
    pen.rrect(cx - 190, 220, cx + 190, 706, 92, EDGE)
    pen.rrect(cx - 180, 230, cx + 180, 696, 86, LEATHER)
    # channel stitching: vertical tufts + horizontal rolls
    for x in (cx - 90, cx + 90):
        pen.d.line(pen.P([(x, 260), (x, 660)]), fill=LEATHER_D, width=int(6 * s))
    for y in (330, 430, 530):
        pen.d.line(pen.P([(cx - 170, y), (cx + 170, y)]), fill=LEATHER_D, width=int(5 * s))
        pen.d.line(pen.P([(cx - 168, y - 8), (cx + 168, y - 8)]), fill=LEATHER_L, width=int(3 * s))
    pen.rrect(cx - 150, 246, cx - 118, 640, 16, LEATHER_L)  # glossy highlight strip
    # seat cushion with a rolled front edge
    pen.rrect(cx - 214, 662, cx + 214, 742, 36, RIM)
    pen.rrect(cx - 208, 668, cx + 208, 736, 32, LEATHER_D)
    pen.rrect(cx - 200, 672, cx + 200, 712, 26, LEATHER)
    pen.rrect(cx - 180, 678, cx + 180, 690, 6, LEATHER_L)
    # armrests: metal supports + padded leather tops
    for side in (-1, 1):
        ax = cx + side * 232
        pen.limb([(ax, 610), (ax, 700)], 22, METAL)
        pen.rrect(ax - 46, 586, ax + 46, 626, 20, RIM)
        pen.rrect(ax - 42, 590, ax + 42, 622, 17, LEATHER_D)
        pen.rrect(ax - 36, 593, ax + 36, 605, 6, LEATHER_L)
    return img.resize((int(W * scale), int(H * scale)), Image.LANCZOS)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "presenter_test.png"
    sheet = Image.new("RGBA", (W * 3, H), (18, 44, 70, 255))
    walk = draw_presenter({"mode": "walk", "sit": 0, "phase": 0.8})
    sheet.alpha_composite(walk, (0, 0))
    sheet.alpha_composite(draw_chair(), (W, 0))
    sheet.alpha_composite(draw_presenter({"mouth": 0.0, "gesture": 0.9}), (W, 0))
    sheet.alpha_composite(draw_chair(), (W * 2, 0))
    sheet.alpha_composite(draw_presenter({"mouth": 0.8, "gesture": 0.2, "blink": 0.0}), (W * 2, 0))
    sheet.save(out)

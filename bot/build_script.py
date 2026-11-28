"""draft.json (written by Claude) -> script.json for the renderer, plus the publishing kit.

    python bot/build_script.py media        # write run/media.md (visual library list for the writer)
    python bot/build_script.py build <slot> # run/draft.json -> run/script.json, run/kit.json, run/description.txt
"""
import datetime as dt, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
RUN, MEDIA = Path(os.environ.get("STICKBIZ_RUN", ROOT / "run")), ROOT / "media"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
sys.path.insert(0, str(HERE))
from hindi_numbers import speak_numbers

SLOT_LABEL = {"am": "Morning", "pm": "Afternoon", "night": "Night"}
MONTHS = "January February March April May June July August September October November December".split()
ORD = {"one": "first", "two": "second", "three": "third", "four": "fourth", "five": "fifth", "six": "sixth",
       "seven": "seventh", "eight": "eighth", "nine": "ninth", "ten": "tenth", "eleven": "eleventh", "twelve": "twelfth",
       "thirteen": "thirteenth", "fourteen": "fourteenth", "fifteen": "fifteenth", "sixteen": "sixteenth",
       "seventeen": "seventeenth", "eighteen": "eighteenth", "nineteen": "nineteenth", "twenty": "twentieth",
       "thirty": "thirtieth"}


def credits():
    return json.loads((MEDIA / "credits.json").read_text(encoding="utf-8"))


def media_list():
    cred = credits()
    rows = []
    for kind, folder, ext in (("video", "videos", "mp4"), ("photo", "images", "jpg")):
        for f in sorted((MEDIA / folder).glob(f"*.{ext}")):
            c = cred.get(f.stem, {})
            rows.append((f.stem, kind, (c.get("title") or "").replace("File:", "").rsplit(".", 1)[0][:70]))
    return rows


def quote_of_the_day(now, slot):
    """A famous quote for the side card, rotating by date and slot (never investment advice)."""
    qs = json.loads((ROOT / "quotes.json").read_text(encoding="utf-8"))
    return qs[(now.toordinal() * 3 + ["am", "pm", "night"].index(slot)) % len(qs)]


def icon_list():
    return sorted(p.stem for p in (MEDIA / "icons").glob("*.png"))


def write_media_md():
    lines = ["# Icons (Fluent 3D; use the slug in scenes)", "", ", ".join(icon_list()), "",
             "# Clips & photos (for `clip` scenes: \"video\" for videos, \"image\" for photos)", "",
             "| slug | kind | what it shows |", "|---|---|---|"]
    lines += [f"| {s} | {k} | {t} |" for s, k, t in media_list()]
    (RUN / "media.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(icon_list())} icons, {len(media_list())} clips/photos listed")


def spoken(cap):
    lang = CONFIG.get("numbers_spoken_in", "en")
    t = speak_numbers(cap, lang=lang)
    if lang == "hi":
        return "[excited] " + re.sub(r"pts", "points", t)
    # "is four December" -> "is the fourth of December"
    t = re.sub(r"\b((?:twenty|thirty)-)?(" + "|".join(ORD) + r") (" + "|".join(MONTHS) + r")\b",
               lambda m: "the " + (m.group(1) or "") + ORD[m.group(2)] + " of " + m.group(3), t)
    # "an eleven thousand crore rupees plan" -> "an eleven thousand crore rupee plan"
    t = re.sub(r"crore rupees (plan|scheme|deal|order|investment|fund|project|package|payout|issue|stake)\b", r"crore rupee \1", t)
    t = re.sub(r"\bpts\b", "points", t)
    return "[excited] " + t


def visual(b, k):
    slug = b["visual"]
    cred = credits().get(slug, {})
    lic = cred.get("license", "")
    who = (cred.get("artist") or "").split("(")[0].strip()[:38]
    credit = "Pexels" if lic == "Pexels License" else ("Public domain" if lic == "Public domain" else f"{who} · {lic}".strip(" ·"))
    if (MEDIA / "videos" / f"{slug}.mp4").exists():
        v = {"kind": "video", "video": f"../media/videos/{slug}.mp4", "start": (k * 4) % 9, "credit": f"Video: {credit}"}
    elif (MEDIA / "images" / f"{slug}.jpg").exists():
        v = {"kind": "photo", "image": f"../media/images/{slug}.jpg", "focus": [0.5, 0.4], "credit": f"Photo: {credit}"}
    else:
        raise SystemExit(f"unknown visual slug: {slug}")
    v["name"] = (b.get("name") or slug.replace("_", " ")).upper()[:44]
    if b.get("rows"):
        v["rows"] = [list(r) + [""] * (3 - len(r)) for r in b["rows"][:3]]
    return v


def build(slot):
    d = json.loads((RUN / "draft.json").read_text(encoding="utf-8"))
    now = dt.datetime.now(IST)
    def scene(sc):
        """Check slugs; give clips a credit line."""
        sc = json.loads(json.dumps(sc or {}))
        for it in [sc.get("from"), sc.get("to"), sc] + list(sc.get("items") or []):
            if isinstance(it, dict) and it.get("icon") and it["icon"] not in icon_list():
                it["icon"] = "red_question_mark"
        if sc.get("type") == "clip":
            slug = sc.get("video") or sc.get("image")
            c = credits().get(slug, {})
            lic = c.get("license", "")
            who = (c.get("artist") or "").split("(")[0].strip()[:34]
            sc["credit"] = ("Video: " if sc.get("video") else "Photo: ") + (
                "Pexels" if lic == "Pexels License" else "Public domain" if lic == "Public domain" else f"{who} · {lic}".strip(" ·"))
        return sc

    h = d["hook"]
    segs = [{"id": "hook", "tag": "TODAY'S TOP NEWS", "headline": " · ".join(s["headline"] for s in d["stories"][:2])[:60],
             "broll": "hook", "cap": h["cap"], "tts": spoken(h["cap"]),
             "beats": [{"head": (h.get("head") or ["TODAY'S", "BIG STORIES"])[:2], "kicker": h.get("kicker", ""), "tone": "neutral",
                        "scene": scene(h.get("scene"))}], "refs": []}]
    for s in d["stories"]:
        beats = []
        for b in s["beats"]:
            bb = {"head": b["head"][:2], "kicker": b.get("kicker", ""), "tone": b.get("tone", "neutral"),
                  "note": b.get("note", ""), "scene": scene(b.get("scene"))}
            if b.get("at"):
                bb["at"] = b["at"]
            if b.get("chips"):
                bb["chips"] = b["chips"][:3]
            beats.append(bb)
        segs.append({"id": s["id"], "tag": s["tag"][:24], "headline": s["headline"][:30], "broll": "stocks",
                     "cap": s["cap"], "tts": spoken(s["cap"]), "beats": beats, "refs": s["sources"]})
    segs.append({"id": "outro", "tag": "STICKBIZ BRIEF", "headline": "See you next time", "broll": "outro",
                 "cap": d["outro"]["cap"], "tts": spoken(d["outro"]["cap"]),
                 "beats": [{"head": ["SEE YOU", "NEXT TIME"], "kicker": "StickBiz Brief", "tone": "neutral"}], "refs": []})
    slot_time = {"am": "8 AM", "pm": "4 PM", "night": "9 PM"}[slot]
    script = {"title": f"{d['titles'][0]} | StickBiz Brief | {now:%d %b %Y}", "voice_provider": "elevenlabs", "look": "explainer",
              "elevenlabs": CONFIG["elevenlabs"], "date_label": f"{now:%d %b %Y}".upper() + f" · {slot_time}",
              "ticker": d.get("ticker", [])[:8], "captions": False, "gap": 0.35, "lead_in": 0.8, "music": CONFIG["music"],
              "quote": quote_of_the_day(now, slot), "segments": segs}
    (RUN / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")

    # publishing kit
    used, cred = [], credits()
    for g in segs:
        for b in g.get("beats", []):
            sc = b.get("scene") or {}
            slug = sc.get("video") or sc.get("image")
            if slug and slug not in used:
                used.append(slug)
    hold = [h for h in CONFIG.get("holdings", []) if any(h.lower() in (s["cap"] + s["headline"]).lower() for s in d["stories"])]

    def make_desc(n_src, links_in_credits):
        out = [d.get("description_intro", ""), "⏱️ Today's market news in under 90 seconds, ✅ every fact checked across 2+ news outlets.", "",
               f"📰 Today's stories ({now:%d %b %Y}):"]
        out += [f"{s['summary']['emoji']} {s['summary']['line']}" for s in d["stories"]]
        out += ["", "🔗 Sources:"]
        for s in d["stories"]:
            out.append(f"{s['summary']['emoji']} {s['headline']}:")
            seen = set()
            for r in s["sources"]:
                if r["link"] not in seen and len(seen) < n_src:
                    seen.add(r["link"])
                    out.append(f"  {r['publisher']}: {r['link']}")
        out += ["", "📷 Photos & videos:"]
        for k in used:
            c = cred.get(k, {})
            name = (c.get("title") or k).replace("File:", "").rsplit(".", 1)[0][:44]
            who = (c.get("artist") or "Unknown").split("(")[0].strip()[:40]
            lic = c.get("license", "")
            page = (c.get("page") or "").replace("https://", "")
            # attribution licences (CC BY / BY-SA) always keep their link; others only when there is room
            keep = page and (links_in_credits or lic.upper().startswith("CC BY"))
            out.append(f"• {name}: {who}, {lic}" + (f" — {page}" if keep else ""))
        out.append("• 3D icons: Microsoft Fluent Emoji (MIT License)")
        out += ["", f"📌 Disclosure: I hold shares of {', '.join(hold)}." if hold else
                "📌 Disclosure: I do not hold shares of any company mentioned in this video.", "",
                "⚠️ For educational purposes only. Not investment advice. I am not a SEBI-registered advisor. "
                "Do your own research or consult a SEBI-registered investment adviser.", "",
                "👉 Follow StickBiz Brief for daily market news! 🔔", "",
                "#StockMarket #Sensex #Nifty #MarketNews #Shorts #StickBizBrief"]
        return "\n".join(out)

    for n_src, links in ((2, True), (2, False), (1, False)):     # shrink until it fits YouTube's 5,000 limit
        desc = make_desc(n_src, links)
        if len(desc) <= 4900:
            break
    else:
        raise SystemExit(f"description too long ({len(desc)} chars)")
    kit = {"slot": slot, "titles": d["titles"][:3], "thumbnail_texts": d["thumbnail_texts"][:3],
           "pinned_comment": d["pinned_comment"], "tags": d["tags"], "description": desc,
           "instagram_caption": f"{d['titles'][0]}\n\n" + "\n".join(f"{s['summary']['emoji']} {s['summary']['line']}" for s in d["stories"])
                                + "\n\n⚠️ Educational only. Not investment advice.\n\n"
                                + " ".join("#" + re.sub(r"[^A-Za-z0-9]", "", t.title()) for t in d["tags"].split(",")[:12]),
           "media_credits": {k: cred.get(k, {}) for k in used}}
    (RUN / "kit.json").write_text(json.dumps(kit, ensure_ascii=False, indent=1), encoding="utf-8")
    head = ["TITLE (pick one):"] + [f"{i}. {x}" for i, x in enumerate(kit["titles"], 1)] + \
           ["", "TAGS:", kit["tags"], "", "PINNED COMMENT:", kit["pinned_comment"], "", "=" * 40, "DESCRIPTION:", ""]
    (RUN / "description.txt").write_text("\n".join(head) + desc, encoding="utf-8")
    chars = sum(len(g["tts"]) for g in segs)
    print(f"script.json: {len(segs) - 2} stories, {chars} voice chars (~{chars / 18:.0f}s); description {len(desc)} chars")


if __name__ == "__main__":
    if sys.argv[1] == "media":
        RUN.mkdir(exist_ok=True)
        write_media_md()
    else:
        build(sys.argv[2] if len(sys.argv) > 2 else "night")

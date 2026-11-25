"""draft.json (written by Claude) -> script.json for the renderer, plus the publishing kit.

    python bot/build_script.py media        # write run/media.md (visual library list for the writer)
    python bot/build_script.py build <slot> # run/draft.json -> run/script.json, run/kit.json, run/description.txt
"""
import datetime as dt, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
RUN, MEDIA = ROOT / "run", ROOT / "media"
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


def write_media_md():
    lines = ["# Visual library (use the slug in `visual`)", "", "| slug | kind | what it shows |", "|---|---|---|"]
    lines += [f"| {s} | {k} | {t} |" for s, k, t in media_list()]
    (RUN / "media.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(lines) - 4} visuals listed")


def spoken(cap):
    t = speak_numbers(cap, lang="en")
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
    segs = [{"id": "hook", "tag": "TODAY'S TOP NEWS", "hook_title": "TODAY'S TOP NEWS",
             "headline": " · ".join(s["headline"] for s in d["stories"][:2])[:60], "broll": "hook",
             "hook_items": d["hook"]["items"][:3], "cap": d["hook"]["cap"], "tts": spoken(d["hook"]["cap"]),
             "beats": [{"banner": d["hook"]["banner"]}], "refs": []}]
    for s in d["stories"]:
        beats = []
        for k, b in enumerate(s["beats"]):
            bb = {"banner": b["banner"][:2], "tone": b.get("tone", "neutral"), "tag": s["tag"][:16], "v": visual(b, k)}
            if b.get("at"):
                bb["at"] = b["at"]
            beats.append(bb)
        segs.append({"id": s["id"], "tag": s["tag"][:16], "headline": s["headline"][:30], "broll": "stocks",
                     "cap": s["cap"], "tts": spoken(s["cap"]), "beats": beats, "refs": s["sources"]})
    segs.append({"id": "outro", "tag": "STICKBIZ BRIEF", "headline": "Follow for daily market news", "broll": "outro",
                 "cap": d["outro"]["cap"], "tts": spoken(d["outro"]["cap"]), "refs": []})
    script = {"title": f"{d['titles'][0]} | StickBiz Brief | {now:%d %b %Y}", "voice_provider": "elevenlabs",
              "elevenlabs": CONFIG["elevenlabs"], "date_label": f"{now:%d %B %Y}".upper(), "ticker": d["ticker"][:8],
              "captions": False, "gap": 0.3, "lead_in": 0.5, "music": CONFIG["music"], "sting": {"pill": "STORY"},
              "outro_lines": ["Comment below:", "Which story mattered most?"],
              "outro_banner": ["Not investment advice", "Educational only · Not SEBI-registered"],
              "disclaimer": ["Educational only. Not investment advice.", "Not a SEBI-registered adviser."],
              "segments": segs}
    (RUN / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")

    # publishing kit
    used, cred = [], credits()
    for g in segs:
        for b in g.get("beats", []):
            v = b.get("v") or {}
            f = v.get("image") or v.get("video")
            if f:
                slug = Path(f).stem
                if slug not in used:
                    used.append(slug)
    desc = [d.get("description_intro", ""), "⏱️ Today's market news in under 90 seconds, ✅ every fact checked across 2+ news outlets.", "",
            f"📰 Today's stories ({now:%d %b %Y}):"]
    desc += [f"{s['summary']['emoji']} {s['summary']['line']}" for s in d["stories"]]
    desc += ["", "🔗 Sources:"]
    for s in d["stories"]:
        desc.append(f"{s['summary']['emoji']} {s['headline']}:")
        seen = set()
        for r in s["sources"]:
            if r["link"] not in seen and len(seen) < 2:
                seen.add(r["link"])
                desc.append(f"  {r['publisher']}: {r['link']}")
    desc += ["", "📷 Photos & videos:"]
    for k in used:
        c = cred.get(k, {})
        name = (c.get("title") or k).replace("File:", "").rsplit(".", 1)[0][:48]
        who = (c.get("artist") or "Unknown").split("(")[0].strip()
        desc.append(f"• {name}: {who}, {c.get('license', '')} — {(c.get('page') or '').replace('https://', '')}")
    hold = [h for h in CONFIG.get("holdings", []) if any(h.lower() in (s["cap"] + s["headline"]).lower() for s in d["stories"])]
    desc += ["", f"📌 Disclosure: I hold shares of {', '.join(hold)}." if hold else
             "📌 Disclosure: I do not hold shares of any company mentioned in this video.", "",
             "⚠️ For educational purposes only. Not investment advice. I am not a SEBI-registered advisor. "
             "Do your own research or consult a SEBI-registered investment adviser.", "",
             "👉 Follow StickBiz Brief for daily market news! 🔔", "",
             "#StockMarket #Sensex #Nifty #MarketNews #Shorts #StickBizBrief"]
    desc = "\n".join(desc)
    if len(desc) > 4900:
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

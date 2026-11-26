"""Code checks on run/draft.json before it reaches the reviewer.

    python bot/checks.py          -> run/checks.md (+ exit code 1 if anything blocks)

1. Format: ids, beats ("at" words appear in the caption), visuals exist, banner lengths, 2+ publishers.
2. Facts: every number/date in captions, banners and card rows is found in 2+ different publishers'
   article texts (research pack) for that story (factcheck_code).
3. Own words: no 7-word run copied from a source article or headline, and no banner/title/headline
   that is a near-copy of a source headline.
4. SEBI: no buy/sell calls, targets, return promises or hype words.
5. Length: spoken text within the Short's range.
"""
import difflib, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
RUN, MEDIA = Path(__import__("os").environ.get("STICKBIZ_RUN", HERE.parent / "run")), HERE.parent / "media"
sys.path.insert(0, str(HERE))
import factcheck_code as FC

SEBI = [r"\bbuy (it|now|this|these|the stock|shares)\b", r"\bsell (it|now|this|these|your)\b", r"\bshould (buy|sell|invest|hold)\b",
        r"\b(accumulate|book profits?|stop[- ]loss|target price|price target|entry level)\b", r"\bguarantee(d)?\b",
        r"\bsure[- ]shot\b", r"\bmultibagger\b", r"\bjackpot\b", r"\bto the moon\b", r"\bdouble your money\b",
        r"\brisk[- ]free\b", r"\bdon'?t miss\b", r"\blast chance\b", r"\binvest (now|today)\b"]
COUNTING = r"\b(first|second|third|fourth|fifth|next|last) story\b"


def words(t):
    return re.findall(r"[a-z0-9]+", t.lower())


def grams(t, n=8, names=frozenset()):
    """Word runs of length n; runs made mostly of names/numbers (unavoidable to repeat) are skipped."""
    w = words(t)
    out = set()
    for i in range(len(w) - n + 1):
        g = w[i:i + n]
        if sum(x in names or x.isdigit() for x in g) >= 3:
            continue
        out.add(" ".join(g))
    return out


SCENE_TYPES = {"flow", "compare", "bignum", "icons", "clip"}


def scene_text(sc):
    sc = sc or {}
    parts = [sc.get("chip", ""), sc.get("value", ""), sc.get("label", "")]
    for k in ("from", "to", "left", "right"):
        it = sc.get(k) or {}
        parts += [it.get("label", ""), it.get("value", ""), it.get("note", "")]
    for it in sc.get("items") or []:
        parts.append(it.get("label", ""))
    return " . ".join(x for x in parts if x)


def scene_icons(sc):
    sc = sc or {}
    out = [sc.get("icon")] + [(sc.get(k) or {}).get("icon") for k in ("from", "to")] + [it.get("icon") for it in sc.get("items") or []]
    return [x for x in out if x]


def beat_text(b):
    """Headline + explanation note (stars removed) + scene values + chips."""
    chips = " . ".join(" ".join(map(str, c[:2])) for c in b.get("chips", []))
    return " . ".join([" ".join(b.get("head", [])), b.get("note", "").replace("*", ""), scene_text(b.get("scene")), chips])


def main():
    d = json.loads((RUN / "draft.json").read_text(encoding="utf-8"))
    res = json.loads((RUN / "research.json").read_text(encoding="utf-8"))
    block, warn, notes = [], [], []
    all_arts = [a for s in res["stories"] for a in s["articles"]]
    by_link = {a["link"]: a for a in all_arts}
    heads = [s["headline"] for s in res["stories"]] + [a["title"] for a in all_arts]
    src_grams = set()
    for a in all_arts:
        src_grams |= grams(a["text"])
    for h in heads:
        src_grams |= grams(h)

    # 1. format
    clips = {p.stem for p in (MEDIA / "videos").glob("*.mp4")} | {p.stem for p in (MEDIA / "images").glob("*.jpg")}
    icons = {p.stem for p in (MEDIA / "icons").glob("*.png")}
    if not 3 <= len(d.get("stories", [])) <= 6:
        block.append(f"Need 3-6 stories, got {len(d.get('stories', []))}.")
    if not (d["hook"].get("scene") and d["hook"].get("head")):
        block.append("hook needs a scene and a head.")
    for s in d["stories"]:
        sid = s.get("id", "?")
        pubs = {FC.publisher(r["publisher"]) for r in s.get("sources", [])}
        if len(pubs) < 2:
            block.append(f"[{sid}] needs sources from 2+ different publishers (has {sorted(pubs)}).")
        for k, b in enumerate(s.get("beats", [])):
            if k and (not b.get("at") or b["at"] not in s["cap"]):
                block.append(f"[{sid}] beat {k + 1}: 'at' words {b.get('at')!r} not found in the caption.")
            sc = b.get("scene") or {}
            if sc.get("type") not in SCENE_TYPES:
                block.append(f"[{sid}] beat {k + 1}: scene type {sc.get('type')!r} is not one of {sorted(SCENE_TYPES)}.")
            for ic in scene_icons(sc):
                if ic not in icons:
                    block.append(f"[{sid}] beat {k + 1}: unknown icon {ic!r}.")
            if sc.get("type") == "clip" and (sc.get("video") or sc.get("image")) not in clips:
                block.append(f"[{sid}] beat {k + 1}: unknown clip {(sc.get('video') or sc.get('image'))!r}.")
            if len(b.get("head", [])) != 2:
                block.append(f"[{sid}] beat {k + 1}: head needs exactly 2 lines.")
            for line in b.get("head", []):
                if len(line) > 22:
                    warn.append(f"[{sid}] headline line is long ({len(line)} chars): {line!r}")
            note = b.get("note", "")
            if not note:
                warn.append(f"[{sid}] beat {k + 1} has no explanation note.")
            elif len(note.replace("*", "")) > 140:
                warn.append(f"[{sid}] beat {k + 1}: note is long ({len(note)} chars).")
            if note and note.count("*") % 2:
                block.append(f"[{sid}] beat {k + 1}: unmatched * in the note.")
        if not s.get("beats"):
            block.append(f"[{sid}] has no beats.")

    # 2. facts: numbers and dates (captions + banners + rows) must be in 2+ publishers -> blocking;
    #    names in the caption -> warning only (English capitalises sentence starts, so name spotting is fuzzy)
    claims = []
    for s in d["stories"]:
        links = {r["link"] for r in s.get("sources", [])}
        cand = [c for c in res["stories"] if any(a["link"] in links for a in c["articles"])]
        pool = {a["link"]: a for c in cand for a in c["articles"]}
        pool.update({l: by_link[l] for l in links if l in by_link})
        arts = [(FC.publisher(a["publisher"]), FC.norm(a["text"])) for a in pool.values()]
        arts = [(p, t, FC.parse_numbers(t)) for p, t in arts]
        extra = " . ".join(beat_text(b) for b in s["beats"])
        facts = [f for f in FC.facts_in(s["cap"]) if f["type"] != "name" or not re.search(r"(^|[.!?]\s+)" + re.escape(f["text"]), s["cap"])]
        facts += [f for f in FC.facts_in(extra) if f["type"] in ("number", "date")]
        seen = set()
        for f in facts:
            key = (f["type"], f["text"].lower())
            if key in seen:
                continue
            seen.add(key)
            pubs = []
            for pub, txt, nums in arts:
                if pub not in pubs and FC.found(f, txt, nums):
                    pubs.append(pub)
            claims.append({"segment_id": s["id"], "claim": f["text"], "type": f["type"], "sources": pubs,
                           "status": "supported" if len(pubs) >= 2 else "weak"})
    for c in claims:
        if c["status"] == "supported":
            notes.append(f"[{c['segment_id']}] ✅ {c['claim']} ({', '.join(c['sources'][:3])})")
        elif c["type"] in ("number", "date"):
            block.append(f"[{c['segment_id']}] {c['type']} “{c['claim']}” is in {len(c['sources'])} publisher(s) "
                         f"({', '.join(c['sources']) or 'none'}) — needs 2+, or remove it.")
        else:
            warn.append(f"[{c['segment_id']}] name “{c['claim']}” found in {len(c['sources'])} publisher(s) — check spelling.")

    # 3. own words
    texts = [("hook", d["hook"]["cap"])] + [(s["id"], s["cap"]) for s in d["stories"]] + \
            [(s["id"] + " headline", " ".join(b.get("head", []))) for s in d["stories"] for b in s["beats"]] + \
            [(s["id"] + " note", b.get("note", "").replace("*", "")) for s in d["stories"] for b in s["beats"]] + \
            [("title", t) for t in d["titles"]] + [(s["id"] + " summary", s["summary"]["line"]) for s in d["stories"]]
    names = frozenset(w.lower() for _, t in texts for w in re.findall(r"\b[A-Z][A-Za-z]+", t)) | {"crore", "lakh", "rs"}
    for where, t in texts:
        hit = grams(t, names=names) & src_grams
        if hit:
            block.append(f"[{where}] copies the source word for word: “{sorted(hit)[0]}…” — rephrase.")
    short = [(s["id"] + " headline", s["headline"]) for s in d["stories"]] + [("title", t) for t in d["titles"]] + \
            [(s["id"] + " headline", " ".join(b.get("head", []))) for s in d["stories"] for b in s["beats"]]
    for where, t in short:
        for h in heads:
            r = difflib.SequenceMatcher(None, t.lower(), h.lower()).ratio()
            if r >= 0.72:
                block.append(f"[{where}] is too close to a source headline ({r:.0%}): {t!r} vs {h[:80]!r}")
                break

    # 4. SEBI + no story counting
    for where, t in texts + [("pinned", d.get("pinned_comment", "")), ("outro", d["outro"]["cap"])]:
        for p in SEBI:
            m = re.search(p, t, re.I)
            if m:
                block.append(f"[{where}] SEBI: advice/hype wording “{m.group(0)}”.")
        m = re.search(COUNTING, t, re.I)
        if m:
            block.append(f"[{where}] says “{m.group(0)}” — don't count stories out loud.")

    # 5. length
    chars = sum(len(x) for _, x in texts[:len(d["stories"]) + 1]) + len(d["outro"]["cap"])
    if not 650 <= chars <= 1500:
        block.append(f"Spoken text is {chars} characters; aim for 900-1,250 (60-80 s).")

    md = ["## Automatic checks", "", f"**{'❌ BLOCKED' if block else '✅ PASSED'}** — {len(block)} blocking, {len(warn)} warnings, "
          f"{sum(1 for c in claims if c['status'] == 'supported')} facts confirmed in 2+ publishers", ""]
    md += [f"- ❌ {x}" for x in block] + [f"- ⚠️ {x}" for x in warn] + ["", "<details><summary>Confirmed facts</summary>", ""] + \
          [f"- {x}" for x in notes] + ["", "</details>"]
    (RUN / "checks.md").write_text("\n".join(md), encoding="utf-8")
    (RUN / "checks.json").write_text(json.dumps({"blocking": block, "warnings": warn}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(md[:3] + [f"- ❌ {x}" for x in block] + [f"- ⚠️ {x}" for x in warn]))
    sys.exit(1 if block else 0)


if __name__ == "__main__":
    main()

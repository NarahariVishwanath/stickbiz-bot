"""Step 1 of a slot: pull the latest news and pack the full article texts for the script writer.

    python bot/research.py <slot>          # slot = am | pm | night

Runs Trend Scout (feeds + verification) and the Story Builder, then opens up to 6 articles per
candidate story so the writer (Claude) can check every fact against 2+ different publishers.
Writes run/research.json (machine) and run/research.md (what Claude reads).
"""
import concurrent.futures, datetime as dt, html, json, re, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
RUN = ROOT / "run"
RUN.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
SLOT_FOCUS = {
    "am": "Morning (8 AM IST): overnight US/global markets and their effect on India, India pre-market news, results and policy news from the evening/night.",
    "pm": "Afternoon (4 PM IST): today's Sensex/Nifty close (always lead with it), sector moves, rupee, the day's biggest India company and policy news.",
    "night": "Night (9 PM IST): evening wrap - policy, regulator (SEBI/RBI), corporate deals, results after hours, and any big global news of the day.",
}


def article_text(url, limit=12000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "en-IN,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read(2_000_000).decode("utf-8", "replace")
    raw = re.sub(r"(?is)<(script|style|noscript|nav|header|footer|aside|form)[^>]*>.*?</\1>", " ", raw)
    paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", raw)
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", p)) for p in paras)
    if len(text) < 600:
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"\s+", " ", text).strip()
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    head = html.unescape(title.group(1)).strip() if title else ""
    return (head + "\n" + text)[:limit]


def main(slot):
    import trend_scout, story_builder
    t0 = dt.datetime.now(IST)
    print(f"[{t0:%H:%M} IST] Trend Scout...", flush=True)
    sys.argv = ["trend_scout.py"]
    trend_scout.main()
    story = story_builder.build(90.0)
    cands = sorted(story["candidates"], key=lambda c: -c.get("score", 0))[:14]

    jobs = []
    for c in cands:
        refs = [{"publisher": c["headline_source"], "title": c["headline"], "link": c["headline_link"]}] + list(c.get("references", []))
        seen = set()
        for r in refs:
            link = (r.get("link") or "").split("?.tsrc")[0]
            if not link or link in seen or "news.google.com" in link:
                continue
            seen.add(link)
            jobs.append((c["n"], {"publisher": r["publisher"], "title": r.get("title", ""), "link": link}))
    arts = {}

    def get(job):
        n, r = job
        try:
            txt = article_text(r["link"])
            return n, dict(r, text=txt) if len(txt) > 400 else None
        except Exception:
            return n, None

    with concurrent.futures.ThreadPoolExecutor(12) as ex:
        for n, a in ex.map(get, jobs):
            if a and len(arts.setdefault(n, [])) < 6:
                arts[n].append(a)

    out = {"slot": slot, "focus": SLOT_FOCUS[slot], "generated_ist": dt.datetime.now(IST).isoformat(timespec="minutes"),
           "stories": []}
    md = [f"# Research pack — {slot.upper()} slot — {dt.datetime.now(IST):%d %b %Y %H:%M} IST", "", f"Slot focus: {SLOT_FOCUS[slot]}", ""]
    for c in cands:
        a = arts.get(c["n"], [])
        pubs = sorted({x["publisher"] for x in a})
        out["stories"].append({"n": c["n"], "segment": c["segment"], "score": c.get("score"), "mark": c.get("mark"),
                               "headline": c["headline"], "brief": c.get("brief", ""), "publishers": pubs, "articles": a})
        md += [f"## Candidate {c['n']} — score {c.get('score')} — {c['segment']} — {c.get('mark')} — {len(pubs)} publishers opened",
               f"Source headline (DO NOT copy): {c['headline']}", f"Brief: {c.get('brief', '')}", ""]
        for x in a:
            md += [f"### [{x['publisher']}] {x['title']}", f"Link: {x['link']}", "", x["text"][:5000], ""]
    (RUN / "research.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (RUN / "research.md").write_text("\n".join(md), encoding="utf-8")
    print(f"{len(cands)} candidates, {sum(len(v) for v in arts.values())} articles opened "
          f"in {(dt.datetime.now(IST) - t0).seconds}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "night")

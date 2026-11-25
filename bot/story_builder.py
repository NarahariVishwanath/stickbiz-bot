"""
StickBiz Story Builder
----------------------
Picks the day's video stories from the verified Trend Scout topics and frames them
with reference links.

Run after trend_scout.py:
    python story_builder.py                 # 60-second Short (default)
    python story_builder.py --seconds 90    # longer video -> more stories
Output: story.html (open in a browser) and story.json (used to write the video script).

How stories are chosen
  1. Candidates: VERIFIED topics (PARTLY VERIFIED only if there are not enough).
  2. Different angles on the same story are merged into one.
  3. Each story gets a MARKET-IMPACT SCORE (see score()):
       coverage (how many outlets) + freshness + verification
       + watchlist boosts (indices, policy/tax, corporate events, large caps — watchlist.json)
       + big figures (₹ crore / $ billion / big % moves)
       + Google Trends India/US search interest
       + India bonus (India-first channel)
       - penalty for off-topic subjects (rockets, games, films ...) unless clearly about money
  4. Length budget: ~11 s for hook + outro, ~8 s per story -> 60 s = 6 stories.
     Highest scores win; at most ~30% of slots go to global stories; stories below a
     minimum impact score are dropped even if there is room.
  5. Order in the video: India first, then global, each by score.
  6. Everything not picked is listed with the reason, so the choice is transparent.
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

import trend_scout as ts

HERE = Path(__file__).parent
HOOK_OUTRO_S = 11.0
PER_STORY_S = 8.0
MIN_SCORE = 12.0          # below this a story is not market news enough for the channel
GLOBAL_SHARE = 0.3

INDIA_MARKERS = ("india", "indian", "sensex", "nifty", "dalal", "rs", "rs.", "crore", "lakh", "sebi", "rbi",
                 "nse", "bse", "finmin", "rupee", "delhi", "mumbai", "bengaluru", "tata", "reliance", "adani",
                 "infosys", "wipro", "hdfc", "icici", "sbi", "coal india", "mahanadi", "lic", "gst", "cbdt", "ltcg")
MONEY_WORDS = ("stock", "share", "market", "ipo", "earnings", "results", "profit", "revenue", "invest", "valuation",
               "fund", "price", "tax", "rate", "bank", "dividend", "deal", "acquire", "ceo", "inflation", "economy")


def wre(words):
    """Whole-word / whole-phrase matcher (so 'lic' does not match 'public')."""
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(w) for w in words) + r")(?![a-z0-9])")


INDIA_RE = wre(INDIA_MARKERS)
MONEY_RE = wre(MONEY_WORDS)
WATCH = json.loads((HERE / "watchlist.json").read_text(encoding="utf-8"))
WATCH_RE = {k: (wre([n.lower() for n in v["names"]]), v.get("boost", 0), v.get("penalty", 0))
            for k, v in WATCH.items() if not k.startswith("_")}
GROUP_LABEL = {"indices": "index / market move", "policy": "policy / tax / macro",
               "corporate_events": "results / IPO / deal", "large_caps_and_watchlist": "large cap / watchlist"}


def esc(s):
    return html.escape(str(s), quote=True)


def text_of(t):
    return f" {t['headline']} {t['brief']} {t['search_terms']} ".lower()


FOREIGN_RE = wre(["us", "u.s.", "america", "american", "fed", "federal reserve", "dollar", "wall street", "nasdaq",
                  "s&p", "dow", "treasury", "china", "chinese", "europe", "european", "uk", "britain", "japan", "yen",
                  "aussie", "euro", "trump", "warsh", "intel", "nvidia", "apple", "microsoft", "google", "alphabet",
                  "amazon", "meta", "tesla", "openai", "anthropic", "jpmorgan", "california", "washington"])


def is_india(t):
    """About India (not merely reported by Indian outlets)."""
    txt = text_of(t)
    if "₹" in t["headline"] + t["brief"] or INDIA_RE.search(txt):
        return True
    # covered only by Indian outlets counts as India unless it is plainly about foreign markets/companies
    return t["regions"] == ["India"] and not FOREIGN_RE.search(txt)


def is_money(t):
    return t["category"] in ("markets", "business") or bool(MONEY_RE.search(text_of(t)))


def big_figures(t):
    """Points for large amounts / big moves in the headline, brief or confirmed figures."""
    txt = (t["headline"] + " " + t["brief"] + " " + " ".join(t["verify"].get("confirmed_figures", []))).lower()
    pts, why = 0, []
    if re.search(r"(₹|rs\.?)\s?[\d,]{4,}(\.\d+)?\s?(crore|cr)|lakh crore|[\d,]+\s?lakh crore", txt):
        pts += 2; why.append("₹1,000 crore+")
    if re.search(r"\$\s?[\d.,]+\s?(billion|bn|trillion)|[\d.,]+\s?(billion|trillion)", txt):
        pts += 2; why.append("$ billion+")
    moves = [float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s?(?:%|per cent)", txt)]
    if any(m >= 5 for m in moves):
        pts += 1; why.append("5%+ move")
    return min(pts, 4), why


def trend_hit(t, trends):
    words = {w for w in ts.tokens(t["headline"] + " " + t["search_terms"]) if len(w) > 3}
    for tr in trends:
        q = {w for w in ts.tokens(tr["query"]) if len(w) > 3}
        if q and (q <= words or len(q & words) >= 2):
            return tr
    return None


def score(t, trends, now):
    parts = []
    cov = min(len(t["sources"]), 20) * 0.5
    parts.append(("coverage", cov, f"{len(t['sources'])} outlets"))
    if t.get("newest"):
        age_h = (now - dt.datetime.fromisoformat(t["newest"])).total_seconds() / 3600
        fr = max(0.0, 4 - age_h / 6)
        parts.append(("freshness", fr, f"{age_h:.0f} h old"))
    mark = t["verify"]["mark"]
    parts.append(("verification", {"verified": 4, "partial": 1}.get(mark, 0), mark))
    txt = text_of(t)
    for g, (rx, boost, penalty) in WATCH_RE.items():
        m = rx.search(txt)
        if not m:
            continue
        if penalty:  # off-topic subject, unless the story is clearly about money
            if g == "avoid_always" or not MONEY_RE.search(txt):
                parts.append(("off-topic", -penalty, m.group(1)))
        else:
            parts.append((GROUP_LABEL.get(g, g), boost, m.group(1)))
    fig, why = big_figures(t)
    if fig:
        parts.append(("big figures", fig, ", ".join(why)))
    tr = trend_hit(t, trends)
    if tr:
        parts.append(("search trend", 3, f"Google Trends {tr['region']}: {tr['query']}"))
    if is_india(t):
        parts.append(("India-first", 3, "Indian market story"))
    total = round(sum(p[1] for p in parts), 1)
    return total, [{"factor": a, "points": round(b, 1), "detail": c} for a, b, c in parts]


def same_story(a, b):
    ta = ts.tokens(a["headline"] + " " + a["search_terms"])
    tb = ts.tokens(b["headline"] + " " + b["search_terms"])
    shared = ta & tb
    if len(shared) >= 2 and len(shared) / min(len(ta), len(tb)) >= 0.34:
        return True
    ka, kb = a["search_terms"].split()[:2], b["search_terms"].split()[:2]
    return bool(set(ka) & set(kb) & shared)


def build(seconds=60.0, max_stories=None):
    data = json.loads((HERE / "topics.json").read_text(encoding="utf-8"))
    now = dt.datetime.fromisoformat(data["generated"])
    trends = data.get("trends", [])
    topics = [t for t in data["topics"] if t.get("verify")]
    slots = max(1, int((seconds - HOOK_OUTRO_S) // PER_STORY_S))
    if max_stories:
        slots = min(slots, max_stories)
    max_global = max(1, round(slots * GLOBAL_SHARE))

    cuts = []
    cands = [t for t in topics if t["verify"]["mark"] == "verified"]
    if len(cands) < slots:
        cands += [t for t in topics if t["verify"]["mark"] == "partial"]
    for t in topics:
        if t not in cands:
            cuts.append({"headline": t["headline"], "reason": f"not verified enough ({t['verify']['mark']})"})

    for t in cands:
        t["_score"], t["_why"] = score(t, trends, now)

    # merge angles: the highest-scoring headline leads the story
    stories = []
    for t in sorted(cands, key=lambda t: -t["_score"]):
        for s in stories:
            if same_story(s["main"], t):
                s["angles"].append(t)
                break
        else:
            stories.append({"main": t, "angles": []})

    picked, n_global = [], 0
    for s in stories:
        m = s["main"]
        if m["_score"] < MIN_SCORE:
            cuts.append({"headline": m["headline"], "score": m["_score"], "reason": "low market impact"})
            continue
        if len(picked) >= slots:
            cuts.append({"headline": m["headline"], "score": m["_score"],
                         "reason": f"no room in a {seconds:.0f}s video ({slots} stories)"})
            continue
        if not is_india(m):
            if n_global >= max_global:
                cuts.append({"headline": m["headline"], "score": m["_score"],
                             "reason": f"global slots full ({max_global})"})
                continue
            n_global += 1
        picked.append(s)
    picked.sort(key=lambda s: (0 if is_india(s["main"]) else 1, -s["main"]["_score"]))

    cut_reason = {c["headline"]: c["reason"] for c in cuts}

    def entry(n, s):
        m = s["main"]
        group = [m] + s["angles"]
        refs, seen = [], set()
        for t in group:
            for r in [{"publisher": t["headline_source"], "title": t["headline"], "link": t["headline_link"]}] \
                    + t["coverage"] + (t["verify"].get("extra_coverage") or []):
                key = (r["publisher"], r["title"])
                if key not in seen and r.get("link"):
                    seen.add(key)
                    refs.append({"publisher": r["publisher"], "title": r["title"], "link": r["link"]})
        confirmed = sorted({f for t in group for f in t["verify"].get("confirmed_figures", [])})
        check = sorted({f for t in group for f in t["verify"].get("unconfirmed_figures", [])} - set(confirmed))
        return {
            "n": n, "segment": "India" if is_india(m) else "Global", "category": m["category"],
            "mark": m["verify"]["mark"], "score": m["_score"], "score_breakdown": m["_why"],
            "headline": m["headline"], "headline_source": m["headline_source"], "headline_link": m["headline_link"],
            "angles": [a["headline"] for a in s["angles"]], "brief": m["brief"],
            "trusted_outlets": m["verify"]["trusted"], "confirmed_figures": confirmed,
            "figures_to_check": check, "references": refs[:12],
        }

    out = [entry(n, s) for n, s in enumerate(picked, 1)]
    # every scored story (picked first), so an app can swap stories in or out
    others = [s for s in stories if s not in picked][:14]
    candidates = [dict(entry(i, s), picked=True) for i, s in enumerate(picked, 1)]
    candidates += [dict(entry(len(picked) + i, s), picked=False,
                        cut_reason=cut_reason.get(s["main"]["headline"], ""))
                   for i, s in enumerate(others, 1)]
    story = {"generated": dt.datetime.now().astimezone().isoformat(timespec="minutes"),
             "news_from": data["generated"], "target_seconds": seconds, "slots": slots,
             "estimated_seconds": round(HOOK_OUTRO_S + PER_STORY_S * len(out)),
             "stories": out, "hook": [s["headline"] for s in sorted(out, key=lambda s: -s["score"])[:3]],
             "cuts": cuts, "candidates": candidates}
    (HERE / "story.json").write_text(json.dumps(story, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "story.html").write_text(render(story), encoding="utf-8")
    return story


def render(story):
    css = ts.CSS + (".seg-h{margin:26px 0 6px;font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;"
                    "letter-spacing:.05em}.score{float:right;font-weight:700;color:var(--accent);font-size:15px}"
                    "table.sb{border-collapse:collapse;font-size:13px;margin:4px 0}table.sb td{padding:1px 10px 1px 0;"
                    "color:var(--muted)}table.sb td.p{text-align:right;font-weight:700;color:var(--text)}")
    p = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
         f"content='width=device-width,initial-scale=1'><title>StickBiz Story Frame</title><style>{css}</style>"
         f"</head><body><main><h1>StickBiz Story Frame</h1>"
         f"<p class='sub'>Built from verified Trend Scout topics · {esc(story['generated'])} · "
         f"target {story['target_seconds']:.0f}s → {story['slots']} story slots, about "
         f"{story['estimated_seconds']}s with hook and outro.</p>"
         f"<p class='sub'>Stories are ranked by a market-impact score (coverage, freshness, verification, "
         f"watchlist names, big figures, search trends, India-first). Edit <b>watchlist.json</b> to change priorities.</p>"]
    p.append("<div class='card'><div class='label'>Hook (first 5 seconds)</div><ul>"
             + "".join(f"<li>{esc(h)}</li>" for h in story["hook"]) + "</ul></div>")
    seg = None
    for s in story["stories"]:
        if s["segment"] != seg:
            seg = s["segment"]
            p.append(f"<div class='seg-h'>{'India first' if seg == 'India' else 'Global'}</div>")
        p.append("<div class='card'>")
        p.append(f"<span class='score'>Impact {s['score']}</span>"
                 f"<h3><span class='rank'>Story {s['n']}</span>{esc(s['headline'])}</h3>")
        p.append(f"<div class='src'>Headline from <b>{esc(s['headline_source'])}</b>: "
                 f"<a href='{esc(s['headline_link'])}' target='_blank' rel='noopener'>open source article</a></div>")
        p.append(f"<span class='vbadge v-{esc(s['mark'])}'>{ts.VERIFY_LABEL[s['mark']]}</span>"
                 f"<span class='small'>Trusted outlets: {esc(', '.join(s['trusted_outlets'][:8]) or 'none')}</span>")
        p.append("<details><summary class='small'>Why this story (score breakdown)</summary><table class='sb'>"
                 + "".join(f"<tr><td>{esc(b['factor'])}</td><td class='p'>{b['points']:+g}</td><td>{esc(b['detail'])}</td></tr>"
                           for b in s["score_breakdown"]) + "</table></details>")
        p.append(f"<div class='label'>What happened</div><p>{esc(s['brief'])}</p>")
        if s["angles"]:
            p.append("<div class='label'>Other angles (merged)</div><ul>"
                     + "".join(f"<li>{esc(a)}</li>" for a in s["angles"]) + "</ul>")
        if s["confirmed_figures"]:
            p.append(f"<div class='label'>Figures confirmed by 2+ outlets</div><p>{esc(', '.join(s['confirmed_figures']))}</p>")
        if s["figures_to_check"]:
            p.append(f"<div class='label'>Figures to double-check before saying them</div>"
                     f"<p class='small'>{esc(', '.join(s['figures_to_check'][:10]))}</p>")
        p.append("<div class='label'>References</div><ul>"
                 + "".join(f"<li><a href='{esc(r['link'])}' target='_blank' rel='noopener'>{esc(r['title'])}</a> "
                           f"<span class='small'>({esc(r['publisher'])})</span></li>" for r in s["references"])
                 + "</ul></div>")
    p.append("<div class='card'><div class='label'>Outro</div><p>Recap the biggest story, ask viewers which "
             "news mattered most to them, subscribe call, and the line: this is not investment advice.</p></div>")
    if story["cuts"]:
        p.append("<h2>Didn't make the cut</h2><div class='card'><ul>"
                 + "".join(f"<li>{esc(c['headline'])} <span class='small'>— {esc(c['reason'])}"
                           f"{' · impact ' + str(c['score']) if 'score' in c else ''}</span></li>"
                           for c in story["cuts"]) + "</ul></div>")
    p.append("</main></body></html>")
    return "".join(p)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Pick and frame the day's video stories.")
    ap.add_argument("max_stories", nargs="?", type=int, help="optional cap on the number of stories")
    ap.add_argument("--seconds", type=float, default=60, help="target video length (default 60)")
    a = ap.parse_args()
    st = build(a.seconds, a.max_stories)
    print(f"{len(st['stories'])} stories for a {a.seconds:.0f}s video (~{st['estimated_seconds']}s) -> story.html / story.json")
    for s in st["stories"]:
        print(f" {s['n']}. [{s['segment']}] impact {s['score']:>5}  {s['headline'][:85]}")
    near = [c for c in st["cuts"] if "score" in c][:6]
    if near:
        print("Next in line (cut):")
        for c in near:
            print(f"    impact {c['score']:>5}  {c['headline'][:70]}  — {c['reason']}")

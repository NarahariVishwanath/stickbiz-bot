"""
StickBiz Trend Scout
--------------------
Collects business and tech headlines from open sources (news RSS feeds,
finance sites, YouTube channel feeds, Hacker News, Reddit, Google Trends),
groups headlines about the same story into topics, ranks topics by how many
different sources are covering them, and writes an HTML report with a short
brief and research links for each topic.

Run:   python trend_scout.py
Output: trend_report.html (next to this script)

No packages to install; it uses only the Python standard library.
X and Threads have no free open feed, so the report links to a live search
on each platform for every topic instead of reading posts directly.
"""

import concurrent.futures
import datetime as dt
import email.utils
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# ----------------------------------------------------------------------------
# Settings you can change
# ----------------------------------------------------------------------------
MAX_AGE_HOURS = 48      # ignore stories older than this
TOP_TOPICS = 40         # how many topics to put in the report
TIMEOUT = 20            # seconds per source

# (name, kind, category, url)
# kind: "rss" = normal feed, "gnews" = Google News feed (titles end with " - Publisher")
FEEDS = [
    # --- news aggregators ---
    ("Google News Business (US)", "gnews", "business",
     "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
    ("Google News Technology (US)", "gnews", "tech",
     "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"),
    ("Google News Business (India)", "gnews", "business",
     "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en"),
    ("Google News Technology (India)", "gnews", "tech",
     "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-IN&gl=IN&ceid=IN:en"),
    # --- finance and business news ---
    ("CNBC Top News", "rss", "business",
     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("CNBC Business", "rss", "business",
     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"),
    ("CNBC Technology", "rss", "tech",
     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"),
    ("Yahoo Finance", "rss", "markets",
     "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US"),
    ("MarketWatch", "rss", "markets", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("BBC Business", "rss", "business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("BBC Technology", "rss", "tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("Economic Times", "rss", "business", "https://economictimes.indiatimes.com/rssfeedstopstories.cms"),
    ("Economic Times Markets", "rss", "markets",
     "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Economic Times Tech", "rss", "tech",
     "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms"),
    ("Mint Companies", "rss", "business", "https://www.livemint.com/rss/companies"),
    ("Mint Markets", "rss", "markets", "https://www.livemint.com/rss/markets"),
    ("Moneycontrol", "rss", "markets", "https://www.moneycontrol.com/rss/business.xml"),
    # --- tech news ---
    ("TechCrunch", "rss", "tech", "https://techcrunch.com/feed/"),
    ("The Verge", "rss", "tech", "https://www.theverge.com/rss/index.xml"),
    ("Ars Technica", "rss", "tech", "https://feeds.arstechnica.com/arstechnica/index"),
    ("Wired", "rss", "tech", "https://www.wired.com/feed/rss"),
    ("MIT Technology Review", "rss", "tech", "https://www.technologyreview.com/feed/"),
    ("Engadget", "rss", "tech", "https://www.engadget.com/rss.xml"),
    ("Inc42", "rss", "tech", "https://inc42.com/feed/"),
    # --- more business news ---
    ("NYT Business", "rss", "business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("NYT Technology", "rss", "tech", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"),
    ("Fortune", "rss", "business", "https://fortune.com/feed/"),
    ("Guardian Business", "rss", "business", "https://www.theguardian.com/uk/business/rss"),
    # --- South China Morning Post (Hong Kong): China / Asia business, economy and tech ---
    ("SCMP Business", "rss", "business", "https://www.scmp.com/rss/92/feed"),
    ("SCMP Global Economy", "rss", "business", "https://www.scmp.com/rss/12/feed"),
    ("SCMP Tech", "rss", "tech", "https://www.scmp.com/rss/36/feed"),
    ("SCMP China", "rss", "business", "https://www.scmp.com/rss/4/feed"),
    ("Hindu BusinessLine", "rss", "business", "https://www.thehindubusinessline.com/feeder/default.rss"),
    ("Business Standard", "rss", "business", "https://www.business-standard.com/rss/latest.rss"),
    ("NDTV Profit", "rss", "markets", "https://feeds.feedburner.com/ndtvprofit-latest"),
    # --- community ---
    ("Reddit", "rss", "community",
     "https://www.reddit.com/r/business+technology+stocks+economy+IndianStockMarket/hot/.rss?limit=50"),
]

# Country of each feed, used by the country toggle in the report.
# Feeds not listed here count as "Global".
FEED_REGION = {
    "Google News Business (US)": "US", "Google News Technology (US)": "US",
    "CNBC Top News": "US", "CNBC Business": "US", "CNBC Technology": "US",
    "Yahoo Finance": "US", "MarketWatch": "US",
    "Google News Business (India)": "India", "Google News Technology (India)": "India",
    "Economic Times": "India", "Economic Times Markets": "India", "Economic Times Tech": "India",
    "Mint Companies": "India", "Mint Markets": "India", "Moneycontrol": "India",
    "NYT Business": "US", "NYT Technology": "US", "Fortune": "US",
    "Hindu BusinessLine": "India", "Business Standard": "India", "NDTV Profit": "India", "Inc42": "India",
}

# YouTube channels (public feeds, no key needed). Add more as (name, channel_id).
# Find a channel id on its page: Share channel -> Copy channel ID.
YOUTUBE_CHANNELS = [
    ("CNBC", "UCvJJ_dzjViJCoLf5uKUTwoA"),
    ("CNBC Television", "UCrp_UI8XtuYfpiqluWLD7Lw"),
    ("Bloomberg Television", "UCIALMKvObZNtJ6AmdCLP7Lg"),
    ("Yahoo Finance", "UCEAZeUIeJs0IjQiqTCdVSIg"),
]

GOOGLE_TRENDS = [
    ("US", "https://trends.google.com/trending/rss?geo=US"),
    ("India", "https://trends.google.com/trending/rss?geo=IN"),
]

HACKER_NEWS = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

STOPWORDS = set("""
a an and are as at be been but by can could did do does for from had has have he her his how if in into is it
its just may might more most new not of on or our out over say says said she should so than that the their them
then there these they this to up was were what when where which who why will with would you your after before
amid about against all also among any back between both day down first get gets here last latest live make
makes many much news now off one only other per report reports set show shows some still take takes today top
two under update updates us use via vs week year years know need here's heres watch video amp
""".split())


# ----------------------------------------------------------------------------
# Fetching
# ----------------------------------------------------------------------------
def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, application/json, */*",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def local(tag):
    """Tag name without its XML namespace."""
    return tag.rsplit("}", 1)[-1].lower()


def child_text(node, *names):
    for child in node:
        if local(child.tag) in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(html.unescape(text))
    return re.sub(r"\s+", " ", text).strip()


def parse_date(text):
    if not text:
        return None
    try:
        d = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def parse_feed(data):
    """Return a list of dicts from an RSS or Atom feed."""
    root = ET.fromstring(data)
    items = []
    for node in root.iter():
        if local(node.tag) not in ("item", "entry"):
            continue
        title = clean(child_text(node, "title"))
        link = child_text(node, "link")
        if not link:  # Atom: <link href="..."/>
            for child in node:
                if local(child.tag) == "link" and child.get("href"):
                    if child.get("rel", "alternate") == "alternate":
                        link = child.get("href")
                        break
        summary = clean(child_text(node, "description", "summary", "content"))
        if not summary:  # YouTube: media:group/media:description
            for child in node.iter():
                if local(child.tag) == "description" and (child.text or "").strip():
                    summary = clean(child.text)
                    break
        date = parse_date(child_text(node, "pubdate", "published", "updated", "date"))
        extra = {local(c.tag): (c.text or "").strip() for c in node if local(c.tag) == "approx_traffic"}
        if title:
            items.append({"title": title, "link": link, "summary": summary, "date": date, **extra})
    return items


def load_feed(name, kind, category, url):
    items = parse_feed(fetch(url))
    out = []
    for it in items:
        publisher = name
        title = it["title"]
        summary = it["summary"]
        if kind == "gnews":
            # "Headline - Publisher": keep the publisher, drop the junk link-list summary
            if " - " in title:
                title, publisher = title.rsplit(" - ", 1)
            summary = ""
        out.append({"title": title.strip(), "link": it["link"], "summary": summary,
                    "date": it["date"], "source": publisher.strip(), "feed": name,
                    "category": category, "region": FEED_REGION.get(name, "Global")})
    return out


def load_hacker_news():
    data = json.loads(fetch(HACKER_NEWS))
    out = []
    for hit in data.get("hits", []):
        if not hit.get("title"):
            continue
        out.append({
            "title": hit["title"],
            "link": hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}",
            "discuss": f"https://news.ycombinator.com/item?id={hit['objectID']}",
            "points": hit.get("points") or 0,
            "comments": hit.get("num_comments") or 0,
            "summary": "", "date": parse_date(hit.get("created_at")),
            "source": "Hacker News", "feed": "Hacker News", "category": "tech", "region": "Global",
        })
    return out


def load_trends(region, url):
    return [{"query": it["title"], "traffic": it.get("approx_traffic", ""), "region": region}
            for it in parse_feed(fetch(url))]


def load_youtube(name, channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    out = []
    for it in parse_feed(fetch(url)):
        out.append({"title": it["title"], "link": it["link"], "summary": "",
                    "date": it["date"], "source": f"YouTube: {name}", "feed": f"YouTube: {name}",
                    "category": "video", "region": "US"})
    return out


# ----------------------------------------------------------------------------
# Grouping headlines into topics
# ----------------------------------------------------------------------------
def tokens(title):
    words = re.findall(r"[a-z0-9][a-z0-9&'.-]*", title.lower())
    out = set()
    for w in words:
        w = w.strip(".'-").replace("'s", "")
        if len(w) > 2 and w not in STOPWORDS and not w.isdigit():
            out.add(w)
    return out


def cluster(items):
    clusters = []
    for it in items:
        tk = tokens(it["title"])
        if len(tk) < 2:
            continue
        it["tokens"] = tk
        best, best_score = None, 0.0
        for c in clusters:
            shared = len(tk & c["tokens"])
            if shared < 2:
                continue
            jaccard = shared / len(tk | c["seed"])
            overlap = len(tk & c["seed"]) / min(len(tk), len(c["seed"]))
            score = max(jaccard, overlap * 0.8)
            if (len(tk & c["seed"]) >= 3 and score >= 0.34) or score >= 0.5:
                if score > best_score:
                    best, best_score = c, score
        if best:
            best["items"].append(it)
            best["tokens"] |= tk
        else:
            clusters.append({"seed": set(tk), "tokens": set(tk), "items": [it]})

    # second pass: merge topics that are different angles on the same story
    # (their first headlines share at least three key words)
    merged = []
    for c in sorted(clusters, key=lambda c: len(c["items"]), reverse=True):
        for m in merged:
            shared = len(c["seed"] & m["seed"])
            if shared >= 3 and shared / min(len(c["seed"]), len(m["seed"])) >= 0.3:
                m["items"].extend(c["items"])
                m["tokens"] |= c["tokens"]
                break
        else:
            merged.append(c)
    return merged


def rank(clusters, now):
    for c in clusters:
        sources = {i["source"] for i in c["items"]}
        dates = [i["date"] for i in c["items"] if i["date"]]
        newest = max(dates) if dates else None
        age_h = (now - newest).total_seconds() / 3600 if newest else MAX_AGE_HOURS
        hn_points = max((i.get("points", 0) for i in c["items"]), default=0)
        c["sources"] = sorted(sources)
        c["newest"] = newest
        c["score"] = (len(sources) * 3 + len(c["items"]) * 0.5
                      + max(0, 6 - age_h / 4) + min(hn_points / 150, 3))
        cats = [i["category"] for i in c["items"] if i["category"] not in ("community", "video")]
        c["category"] = max(set(cats), key=cats.count) if cats else c["items"][0]["category"]
        # every category and country that covers the topic, for the report toggles
        c["cats"] = sorted(set(cats)) or [c["category"]]
        c["regions"] = sorted({i.get("region", "Global") for i in c["items"]
                               if i["category"] != "video"}) or ["Global"]
    return sorted(clusters, key=lambda c: c["score"], reverse=True)


def make_brief(c):
    """Pick the best feed summary for the topic; fall back to the headlines."""
    best = ""
    for it in c["items"]:
        s = it["summary"]
        if len(s) < 60 or s.lower().startswith(it["title"].lower()[:40]) and len(s) < len(it["title"]) + 30:
            continue
        if it["feed"] == "Reddit" or "submitted by" in s:
            continue
        if s.endswith("[…]") or s.endswith("[...]"):
            continue  # a cut-off article intro, not a summary
        # prefer a summary of about two sentences over a long article intro
        if not best or abs(len(s) - 220) < abs(len(best) - 220):
            best = s
    if best:
        if len(best) > 420:
            cut = best[:420]
            best = cut[:cut.rfind(" ")] + "…"
        return best
    others = [i["title"] for i in c["items"][1:3]]
    if others:
        return "No summary in the feeds. Related headlines: " + " | ".join(others)
    return "No summary in the feed. Open the article for details."


def headline_item(c):
    """The item whose title is used as the topic header (so the report can link to it)."""
    # prefer a headline from a named publisher over community posts, and a mid-length one
    cands = [i for i in c["items"] if i["category"] not in ("community", "video")] or c["items"]
    return min(cands, key=lambda i: abs(len(i["title"]) - 75))


def headline(c):
    return headline_item(c)["title"]


def search_terms(c):
    """Up to four words that best describe the topic, for search links."""
    counts = {}
    for it in c["items"]:
        for w in it["tokens"]:
            counts[w] = counts.get(w, 0) + 1
    title_order = [w for w in re.findall(r"[a-z0-9][a-z0-9&'.-]*", headline(c).lower())]
    words = sorted(counts, key=lambda w: (-counts[w], title_order.index(w) if w in title_order else 99))
    return " ".join(words[:4])


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s), quote=True)


def ago(d, now):
    if not d:
        return ""
    h = (now - d).total_seconds() / 3600
    if h < 1:
        return f"{max(1, int(h * 60))} min ago"
    if h < 24:
        return f"{int(h)} h ago"
    return f"{int(h // 24)} d ago"


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#16202e;--muted:#5b6777;--line:#e2e6ec;--accent:#0f766e;--chip:#e6f4f1;--on:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0d1420;--card:#151f2e;--text:#e8edf4;--muted:#9aa7b8;--line:#263347;--accent:#34d399;--chip:#12332f;--on:#06241b}}
:root[data-theme=dark]{--bg:#0d1420;--card:#151f2e;--text:#e8edf4;--muted:#9aa7b8;--line:#263347;--accent:#34d399;--chip:#12332f;--on:#06241b}
[hidden]{display:none!important}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 Segoe UI,Arial,sans-serif}
main{max-width:920px;margin:0 auto;padding:24px 16px 60px}
h1{margin:0 0 4px;font-size:28px}h2{margin:36px 0 12px;font-size:21px}
.sub{color:var(--muted);margin:0 0 8px;font-size:14px}
.bar{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 0;margin:10px 0 4px}
.row{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:4px 0}
.row .name{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;width:74px}
.seg{font:inherit;font-size:14px;font-weight:600;color:var(--text);background:var(--card);border:1px solid var(--line);border-radius:999px;padding:5px 14px;cursor:pointer}
.seg:hover{border-color:var(--accent)}
.seg[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--on)}
.seg:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.spacer{flex:1}
#count{font-size:13px;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.card h3{margin:0 0 6px;font-size:18px;line-height:1.35}
.meta{color:var(--muted);font-size:13px;margin-bottom:8px}
.chip{display:inline-block;background:var(--chip);color:var(--accent);border-radius:999px;padding:1px 10px;font-size:12px;font-weight:600;margin-right:6px}
.rank{color:var(--accent);font-weight:700;margin-right:6px}
p{margin:6px 0}ul{margin:6px 0;padding-left:20px}li{margin:3px 0;font-size:14.5px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.links a{display:inline-block;border:1px solid var(--line);border-radius:8px;padding:2px 10px;margin:4px 6px 0 0;font-size:13px}
.grp{display:flex;flex-wrap:wrap;align-items:baseline;margin-top:2px}
.grp .g{font-size:13px;font-weight:600;color:var(--muted);width:128px;flex:none}
.grp .links{flex:1;min-width:220px}
summary{cursor:pointer}
.label{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:10px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.small{font-size:13px;color:var(--muted)}
.src{font-size:13px;color:var(--muted);margin:-2px 0 8px}
.src a{font-weight:600}
.vbadge{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12.5px;font-weight:700;margin:0 6px 6px 0}
.v-verified{background:#dcfce7;color:#166534}.v-partial{background:#fef3c7;color:#92400e}.v-unverified{background:#fee2e2;color:#991b1b}
:root[data-theme=dark] .v-verified{background:#14532d;color:#bbf7d0}:root[data-theme=dark] .v-partial{background:#78350f;color:#fde68a}:root[data-theme=dark] .v-unverified{background:#7f1d1d;color:#fecaca}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .v-verified{background:#14532d;color:#bbf7d0}:root:not([data-theme=light]) .v-partial{background:#78350f;color:#fde68a}:root:not([data-theme=light]) .v-unverified{background:#7f1d1d;color:#fecaca}}
.vwhy{font-size:13px;color:var(--muted);margin:0 0 6px;padding-left:18px}
.vwhy li{font-size:13px;margin:1px 0}
"""

VERIFY_LABEL = {"verified": "✅ Verified", "partial": "⚠️ Partly verified", "unverified": "❌ Unverified"}

TOOLBAR = """
<div class='bar'>
  <div class='row'><span class='name'>Show</span>
    <button class='seg' data-cat='all' aria-pressed='true'>Overall</button>
    <button class='seg' data-cat='business' aria-pressed='false'>Business</button>
    <button class='seg' data-cat='tech' aria-pressed='false'>Tech</button>
    <button class='seg' data-cat='markets' aria-pressed='false'>Markets</button>
    <span class='spacer'></span>
    <button class='seg' id='theme' aria-pressed='false'>Night mode</button>
  </div>
  <div class='row'><span class='name'>Country</span>
    <button class='seg' data-region='all' aria-pressed='true'>All</button>
    <button class='seg' data-region='US' aria-pressed='false'>US</button>
    <button class='seg' data-region='India' aria-pressed='false'>India</button>
    <button class='seg' data-region='Global' aria-pressed='false'>Global</button>
    <span class='spacer'></span><span id='count'></span>
  </div>
  <div class='row'><span class='name'>Sort by</span>
    <button class='seg' data-sort='rank' aria-pressed='true'>Most covered</button>
    <button class='seg' data-sort='latest' aria-pressed='false'>Latest first</button>
    <button class='seg' data-sort='oldest' aria-pressed='false'>Oldest first</button>
  </div>
  <div class='row'><span class='name'>Checked</span>
    <button class='seg' data-ver='all' aria-pressed='true'>All</button>
    <button class='seg' data-ver='verified' aria-pressed='false'>✅ Verified only</button>
    <button class='seg' data-ver='checked' aria-pressed='false'>✅ + ⚠️</button>
  </div>
</div>
"""

SCRIPT = """
(function () {
  var root = document.documentElement, cat = 'all', region = 'all', sort = 'rank', ver = 'all';
  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); }
    catch (e) { return null; }
  }
  function press(attr, value) {
    document.querySelectorAll('[' + attr + ']').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute(attr) === value ? 'true' : 'false');
    });
  }
  function apply() {
    var n = 0;
    // put the topics in the chosen order: by rank, or by the time of each topic's newest headline
    var box = document.getElementById('topics');
    var els = Array.prototype.slice.call(box.querySelectorAll('.topic'));
    els.sort(function (a, b) {
      var byRank = a.dataset.rank - b.dataset.rank;
      if (sort === 'latest') return (b.dataset.time - a.dataset.time) || byRank;
      if (sort === 'oldest') return (a.dataset.time - b.dataset.time) || byRank;
      return byRank;
    });
    els.forEach(function (el) { box.appendChild(el); });
    document.querySelectorAll('.topic').forEach(function (el) {
      var v = el.dataset.ver || 'unverified';
      var show = (cat === 'all' || el.dataset.cats.split(' ').indexOf(cat) >= 0) &&
                 (region === 'all' || el.dataset.regions.split(' ').indexOf(region) >= 0) &&
                 (ver === 'all' || v === 'verified' || (ver === 'checked' && v === 'partial'));
      el.hidden = !show;
      if (show) { n++; el.querySelector('.rank').textContent = '#' + n; }
    });
    document.querySelectorAll('[data-trend-region]').forEach(function (el) {
      el.hidden = !(region === 'all' || region === 'Global' || el.dataset.trendRegion === region);
    });
    document.getElementById('count').textContent = n + (n === 1 ? ' topic' : ' topics');
    document.getElementById('empty').hidden = n > 0;
    press('data-cat', cat); press('data-region', region); press('data-sort', sort); press('data-ver', ver);
  }
  function isDark() {
    var t = root.getAttribute('data-theme');
    return t ? t === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  function setTheme(t) {
    root.setAttribute('data-theme', t);
    var b = document.getElementById('theme');
    b.textContent = t === 'dark' ? 'Day mode' : 'Night mode';
    b.setAttribute('aria-pressed', t === 'dark' ? 'true' : 'false');
  }
  document.querySelectorAll('[data-cat]').forEach(function (b) {
    b.addEventListener('click', function () { cat = b.dataset.cat; store('ts-cat', cat); apply(); });
  });
  document.querySelectorAll('[data-region]').forEach(function (b) {
    b.addEventListener('click', function () { region = b.dataset.region; store('ts-region', region); apply(); });
  });
  document.querySelectorAll('[data-sort]').forEach(function (b) {
    b.addEventListener('click', function () { sort = b.dataset.sort; store('ts-sort', sort); apply(); });
  });
  document.querySelectorAll('[data-ver]').forEach(function (b) {
    b.addEventListener('click', function () { ver = b.dataset.ver; store('ts-ver', ver); apply(); });
  });
  document.getElementById('theme').addEventListener('click', function () {
    var t = isDark() ? 'light' : 'dark'; setTheme(t); store('ts-theme', t);
  });
  // start from the last choice; a link like trend_report.html#cat=tech&region=India&theme=dark overrides it
  var hash = new URLSearchParams(location.hash.slice(1));
  function has(attr, v) { return v && document.querySelector('[' + attr + '="' + v + '"]'); }
  var c = hash.get('cat') || store('ts-cat'), r = hash.get('region') || store('ts-region');
  var t = hash.get('theme') || store('ts-theme');
  if (has('data-cat', c)) cat = c;
  if (has('data-region', r)) region = r;
  var s = hash.get('sort') || store('ts-sort');
  if (has('data-sort', s)) sort = s;
  var vv = hash.get('ver') || store('ts-ver');
  if (has('data-ver', vv)) ver = vv;
  setTheme(t === 'dark' || t === 'light' ? t : (isDark() ? 'dark' : 'light'));
  apply();
})();
"""


def research_links(terms, regions):
    """Grouped search links for one topic. Each opens a search for the topic's key words."""
    q = urllib.parse.quote_plus
    p = urllib.parse.quote
    groups = [
        ("News", [
            ("Google News", f"https://news.google.com/search?q={q(terms)}"),
            ("Bing News", f"https://www.bing.com/news/search?q={q(terms)}"),
            ("Explainers", f"https://www.google.com/search?q={q(terms + ' explained')}"),
        ]),
        ("Background", [
            ("Wikipedia", f"https://en.wikipedia.org/w/index.php?search={q(terms)}"),
            ("Fact checks", f"https://toolbox.google.com/factcheck/explorer/search/{p(terms)}"),
            ("Search interest", f"https://trends.google.com/trends/explore?date=now%207-d&q={p(terms)}"),
        ]),
        ("Social", [
            ("X (live)", f"https://x.com/search?q={q(terms)}&f=live"),
            ("Threads", f"https://www.threads.net/search?q={q(terms)}"),
            ("Reddit", f"https://www.reddit.com/search/?q={q(terms)}&sort=new"),
            ("Hacker News", f"https://hn.algolia.com/?dateRange=pastWeek&query={q(terms)}"),
        ]),
        ("Video", [
            ("YouTube latest", f"https://www.youtube.com/results?search_query={q(terms)}&sp=CAI%253D"),
            ("YouTube explainers", f"https://www.youtube.com/results?search_query={q(terms + ' explained')}"),
        ]),
    ]
    official = [
        ("Press releases", f"https://www.google.com/search?q={q(terms + ' press release')}"),
        ("Stock price", f"https://www.google.com/search?q={q(terms + ' stock price')}"),
    ]
    if "US" in regions or "Global" in regions:
        official.append(("SEC filings (US)", f"https://www.sec.gov/edgar/search/#/q={p(terms)}"))
    if "India" in regions:
        official.append(("BSE / NSE / SEBI (India)", "https://www.google.com/search?q=" + q(
            terms + " (site:bseindia.com OR site:nseindia.com OR site:sebi.gov.in)")))
    groups.append(("Official and data", official))
    return groups


CHECKLIST = """
<details class='card'><summary><b>Research checklist for a video</b> (click to open)</summary>
<ul>
  <li><b>What happened?</b> Confirm the core facts in at least two outlets under Coverage.</li>
  <li><b>What is the original source?</b> Find the press release, filing or official statement under "Official and data".</li>
  <li><b>What are the numbers?</b> Note amounts, dates and percentages, and where each one comes from.</li>
  <li><b>Why does it matter?</b> Who gains, who loses, and what changes for ordinary people or investors.</li>
  <li><b>What is disputed?</b> Check "Fact checks" and read replies on X, Threads and Reddit for the other side.</li>
  <li><b>What happens next?</b> Look for the next date: a ruling, an earnings call, a launch, a vote.</li>
</ul></details>
"""


def build_report(topics, trends, hn, videos, status, now):
    q = urllib.parse.quote_plus
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>StickBiz Trend Scout</title><style>{CSS}</style></head><body><main>"]
    local_now = now.astimezone()
    ok = [s for s in status if s[1]]
    failed = [s for s in status if not s[1]]
    parts.append("<h1>StickBiz Trend Scout</h1>")
    parts.append(f"<p class='sub'>Business and tech topics trending now. Generated "
                 f"{esc(local_now.strftime('%d %b %Y, %I:%M %p'))}. "
                 f"{len(ok)} of {len(status)} sources loaded; stories from the last {MAX_AGE_HOURS} hours.</p>")
    parts.append("<p class='sub'>Topics are ranked by how many different sources are covering them. "
                 "The briefs come from the publishers' own feed summaries, so check the linked articles "
                 "before you script a video.</p>")

    parts.append(TOOLBAR)
    parts.append("<h2>Top topics</h2>")
    parts.append(CHECKLIST)
    parts.append("<div class='card' id='empty' hidden><p>No topics match this combination right now. "
                 "Try another category or country.</p></div>")
    parts.append("<div id='topics'>")
    for n, c in enumerate(topics, 1):
        terms = search_terms(c)
        v = c.get("verify")
        parts.append(f"<div class='card topic' data-rank='{n}' "
                     f"data-time='{int(c['newest'].timestamp()) if c['newest'] else 0}' "
                     f"data-cats='{esc(' '.join(c['cats']))}' "
                     f"data-regions='{esc(' '.join(c['regions']))}' "
                     f"data-ver='{esc(v['mark']) if v else 'unverified'}'>")
        hi = headline_item(c)
        parts.append(f"<h3><span class='rank'>#{n}</span>{esc(hi['title'])}</h3>")
        # where the header was copied from
        parts.append(f"<div class='src'>Headline from <b>{esc(hi['source'])}</b>"
                     f"{', ' + ago(hi['date'], now) if hi['date'] else ''}: "
                     f"<a href='{esc(hi['link'])}' target='_blank' rel='noopener'>{esc(hi['link'][:90])}"
                     f"{'…' if len(hi['link'] or '') > 90 else ''}</a></div>")
        if v:
            parts.append(f"<span class='vbadge v-{esc(v['mark'])}'>{VERIFY_LABEL[v['mark']]}</span>"
                         f"<ul class='vwhy'>" + "".join(f"<li>{esc(r)}</li>" for r in v["reasons"]) + "</ul>")
        parts.append("<div class='meta'>"
                     + "".join(f"<span class='chip'>{esc(x)}</span>" for x in c["cats"])
                     + f"{esc(' · '.join(c['regions']))} &nbsp;|&nbsp; "
                     f"{len(c['sources'])} source{'s' if len(c['sources']) != 1 else ''}, "
                     f"{len(c['items'])} headline{'s' if len(c['items']) != 1 else ''}"
                     f"{', latest ' + ago(c['newest'], now) if c['newest'] else ''}</div>")
        parts.append(f"<p>{esc(make_brief(c))}</p>")
        parts.append("<div class='label'>Coverage</div><ul>")
        seen = set()
        shown = 0
        for it in sorted(c["items"], key=lambda i: i["date"] or now, reverse=True):
            if it["source"] in seen or shown >= 6:
                continue
            seen.add(it["source"])
            shown += 1
            parts.append(f"<li><a href='{esc(it['link'])}' target='_blank' rel='noopener'>{esc(it['title'])}</a> "
                         f"<span class='small'>({esc(it['source'])}{', ' + ago(it['date'], now) if it['date'] else ''})</span></li>")
        parts.append("</ul>")
        parts.append("<div class='label'>Research more</div>")
        for group, links in research_links(terms, c["regions"]):
            parts.append(f"<div class='grp'><span class='g'>{group}</span><span class='links'>")
            for label, url in links:
                parts.append(f"<a href='{esc(url)}' target='_blank' rel='noopener'>{label}</a>")
            parts.append("</span></div>")
        parts.append(f"<p class='small'>Search words: {esc(terms)}</p></div>")
    parts.append("</div>")

    if trends:
        parts.append("<h2>What people are searching (Google Trends)</h2>"
                     "<p class='sub'>All subjects, not just business. Useful for spotting a crossover story.</p><div class='cols'>")
        for region in dict.fromkeys(t["region"] for t in trends):
            parts.append(f"<div class='card' data-trend-region='{esc(region)}'><h3>{esc(region)}</h3><ul>")
            for t in [t for t in trends if t["region"] == region][:12]:
                url = f"https://www.google.com/search?q={q(t['query'])}&tbm=nws"
                parts.append(f"<li><a href='{esc(url)}' target='_blank' rel='noopener'>{esc(t['query'])}</a>"
                             f"{' <span class=small>' + esc(t['traffic']) + ' searches</span>' if t['traffic'] else ''}</li>")
            parts.append("</ul></div>")
        parts.append("</div>")

    if videos:
        parts.append("<h2>Latest from finance channels on YouTube</h2><div class='cols'>")
        for ch in dict.fromkeys(v["source"] for v in videos):
            parts.append(f"<div class='card'><h3>{esc(ch.replace('YouTube: ', ''))}</h3><ul>")
            for v in [v for v in videos if v["source"] == ch][:5]:
                parts.append(f"<li><a href='{esc(v['link'])}' target='_blank' rel='noopener'>{esc(v['title'])}</a> "
                             f"<span class='small'>{ago(v['date'], now)}</span></li>")
            parts.append("</ul></div>")
        parts.append("</div>")

    if hn:
        parts.append("<h2>Tech community: Hacker News front page</h2><div class='card'><ul>")
        for h in sorted(hn, key=lambda h: h["points"], reverse=True)[:12]:
            parts.append(f"<li><a href='{esc(h['link'])}' target='_blank' rel='noopener'>{esc(h['title'])}</a> "
                         f"<span class='small'>{h['points']} points, "
                         f"<a href='{esc(h['discuss'])}' target='_blank' rel='noopener'>{h['comments']} comments</a></span></li>")
        parts.append("</ul></div>")

    parts.append("<h2>Sources</h2><div class='card'>")
    parts.append("<p class='small'><b>Loaded:</b> " + ", ".join(f"{esc(s[0])} ({s[2]})" for s in ok) + "</p>")
    if failed:
        parts.append("<p class='small'><b>Not loaded this run:</b> "
                     + "; ".join(f"{esc(s[0])}: {esc(s[2])}" for s in failed) + "</p>")
    parts.append("<p class='small'><b>X and Threads:</b> neither offers a free open feed, so this tool does not read "
                 "posts from them. Use the X and Threads buttons on each topic to open a live search there.</p></div>")
    parts.append("</main><script>" + SCRIPT + "</script></body></html>")
    return "".join(parts)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    now = dt.datetime.now(dt.timezone.utc)
    jobs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for name, kind, cat, url in FEEDS:
            jobs[pool.submit(load_feed, name, kind, cat, url)] = ("news", name)
        for name, cid in YOUTUBE_CHANNELS:
            jobs[pool.submit(load_youtube, name, cid)] = ("video", f"YouTube: {name}")
        for region, url in GOOGLE_TRENDS:
            jobs[pool.submit(load_trends, region, url)] = ("trends", f"Google Trends {region}")
        jobs[pool.submit(load_hacker_news)] = ("hn", "Hacker News")

        news, videos, trends, hn, status = [], [], [], [], []
        for fut in concurrent.futures.as_completed(jobs):
            kind, name = jobs[fut]
            try:
                result = fut.result()
            except Exception as e:  # one failing source must not stop the run
                status.append((name, False, f"{type(e).__name__}: {str(e)[:80]}"))
                print(f"  [failed] {name}: {type(e).__name__}: {str(e)[:80]}")
                continue
            status.append((name, bool(result), len(result) if result else "no items"))
            print(f"  [ok] {name}: {len(result)} items")
            {"news": news, "video": videos, "trends": trends, "hn": hn}[kind].extend(result)

    cutoff = now - dt.timedelta(hours=MAX_AGE_HOURS)
    fresh = lambda it: it["date"] is None or it["date"] >= cutoff
    news = [i for i in news if fresh(i)]
    videos = sorted([v for v in videos if fresh(v)], key=lambda v: v["date"] or now, reverse=True)
    hn = [h for h in hn if fresh(h)]

    # drop exact duplicate headlines from the same publisher
    seen, unique = set(), []
    for it in news + hn + videos:
        key = (it["source"], it["title"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(it)

    topics = rank(cluster(unique), now)
    # a topic needs at least one real news or tech item, not only videos
    topics = [c for c in topics if any(i["category"] != "video" for i in c["items"])][:TOP_TOPICS]

    if "--no-verify" not in sys.argv:
        import verify
        print("\nVerifying topics (opening sources, re-searching, checking figures)...")
        counts = verify.verify_all(topics)
        print(f"  ✅ {counts['verified']} verified, ⚠️ {counts['partial']} partly verified, "
              f"❌ {counts['unverified']} unverified")

    status.sort(key=lambda s: s[0])
    report = build_report(topics, trends, hn, videos, status, now)
    out = Path(__file__).with_name("trend_report.html")
    out.write_text(report, encoding="utf-8")
    save_topics(topics, now, trends, status)

    print(f"\n{len(unique)} headlines -> {len(topics)} topics in the report")
    for n, c in enumerate(topics[:10], 1):
        mark = {"verified": "✅", "partial": "⚠️", "unverified": "❌"}.get(c.get("verify", {}).get("mark"), " ")
        print(f" {n:>2}. {mark} [{len(c['sources'])} sources] {headline(c)[:95]}")
    print(f"\nReport written to: {out}")


def save_topics(topics, now, trends=(), status=()):
    """topics.json: everything the story builder needs (headline + its source link, brief,
    coverage links, verification)."""
    out = []
    for n, c in enumerate(topics, 1):
        hi = headline_item(c)
        cover, seen = [], set()
        for it in sorted(c["items"], key=lambda i: i["date"] or now, reverse=True):
            if it["source"] in seen or it["category"] == "video":
                continue
            seen.add(it["source"])
            cover.append({"publisher": it["source"], "title": it["title"], "link": it["link"],
                          "date": it["date"].isoformat() if it["date"] else None})
        out.append({"rank": n, "headline": hi["title"], "headline_source": hi["source"],
                    "headline_link": hi["link"], "brief": make_brief(c), "category": c["category"],
                    "cats": c["cats"], "regions": c["regions"], "sources": c["sources"],
                    "newest": c["newest"].isoformat() if c["newest"] else None,
                    "search_terms": search_terms(c), "coverage": cover[:8], "verify": c.get("verify")})
    Path(__file__).with_name("topics.json").write_text(
        json.dumps({"generated": now.isoformat(), "topics": out,
                    "trends": [{"query": t["query"], "region": t["region"], "traffic": t.get("traffic", "")}
                               for t in trends],
                    "sources_status": [{"name": n, "ok": bool(ok), "detail": str(d)} for n, ok, d in status]},
                   indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()

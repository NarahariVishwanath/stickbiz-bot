"""
StickBiz Verify Bot
-------------------
Re-checks every topic Trend Scout found and gives it a verification mark.

For each topic it:
  1. Opens the source article(s) and checks the page title matches the headline
     (proves the headline was really published there and the link works).
  2. Runs a fresh, independent Google News search (last 2 days) and counts how many
     *different* outlets carry the same story.
  3. Counts how many of all those outlets are well-known, trusted newsrooms.
  4. Looks for an official source (SEBI, BSE, NSE, RBI, PIB, SEC, company IR pages).
  5. Pulls the key figures (₹ / $ / € / % / crore / million ...) from every headline and
     summary and checks which ones are reported by at least two different outlets.

Marks:
  VERIFIED          - 3+ independent outlets incl. 2+ trusted ones, plus an opened source page
                      whose title matches (or an official source).
  PARTLY VERIFIED   - 2+ independent outlets, but not enough for a full verified mark.
  UNVERIFIED        - a single outlet, or only community posts (Reddit / Hacker News).

This is corroboration, not a fact-check by a human: a verified story is one that several
independent, reputable newsrooms are reporting the same way. Always read the linked
articles before stating numbers in a video.

Used automatically by trend_scout.py. Uses only the Python standard library.
"""

import concurrent.futures
import re
import urllib.parse

import trend_scout as ts

TRUSTED = [
    # global
    "reuters", "bloomberg", "associated press", "ap news", "cnbc", "bbc", "financial times", "wall street journal",
    "wsj", "new york times", "nyt", "the guardian", "guardian", "fortune", "the economist", "axios", "marketwatch",
    "yahoo finance", "barron", "forbes", "business insider", "cnn", "al jazeera", "nikkei", "the verge", "techcrunch",
    "ars technica", "wired", "engadget", "mit technology review", "the information", "politico", "npr", "abc news",
    "cbs news", "nbc news", "washington post", "time", "south china morning post", "scmp",
    # india
    "economic times", "the economic times", "livemint", "mint", "business standard", "moneycontrol", "ndtv",
    "ndtv profit", "hindu businessline", "the hindu", "times of india", "hindustan times", "indian express",
    "financial express", "cnbc tv18", "cnbctv18", "business today", "india today", "zee business", "inc42",
    "news on air", "press trust of india", "pti", "ani", "the print", "scroll", "inshorts",
]
COMMUNITY = {"reddit", "hacker news"}
OFFICIAL_HOSTS = ("sebi.gov.in", "bseindia.com", "nseindia.com", "rbi.org.in", "pib.gov.in", "sec.gov",
                  "federalreserve.gov", "mca.gov.in", "investor.", "ir.", "/investor", "newsroom.", "press.")

NUM_RE = re.compile(
    r"(?:(?:₹|rs\.?|inr|\$|us\$|€|£)\s?\d[\d,]*(?:\.\d+)?\s?(?:lakh crore|crore|cr|lakh|trillion|billion|bn|million|mn|m|k)?"
    r"|\d[\d,]*(?:\.\d+)?\s?(?:%|per cent|percent|lakh crore|crore|lakh|trillion|billion|million|bps|basis points))",
    re.I)


SECTION_WORDS = re.compile(r"\s+(technology|tech|business|markets?|companies|top news|news|economy|global economy|"
                           r"india|china|world|money|finance|politics)$", re.I)
NEWSROOM_ALIAS = {"livemint": "Mint", "businessline": "Hindu BusinessLine", "the hindu businessline": "Hindu BusinessLine",
                  "moneycontrol.com": "Moneycontrol", "yahoo": "Yahoo Finance", "scmp": "South China Morning Post",
                  "south china morning post": "South China Morning Post"}


def newsroom(name):
    """Feed sections of one newsroom count as one outlet (BBC Business = BBC Technology = BBC;
    SCMP Business = SCMP Tech = South China Morning Post)."""
    n = (name or "").strip()
    for _ in range(2):
        n = SECTION_WORDS.sub("", n).strip()
    n = re.sub(r"^the\s+", "", n, flags=re.I)
    return NEWSROOM_ALIAS.get(n.lower(), n)


def is_trusted(name):
    n = name.lower()
    return any(t == n or t in n for t in TRUSTED)


def norm_num(s):
    s = s.lower().replace(",", "").replace(" ", "")
    s = s.replace("rs.", "₹").replace("rs", "₹").replace("inr", "₹").replace("us$", "$")
    s = s.replace("percent", "%").replace("percent", "%").replace("bn", "billion").replace("mn", "million")
    s = re.sub(r"(\d)cr$", r"\1crore", s)
    return s


def similarity(a, b):
    ta, tb = ts.tokens(a), ts.tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def page_title(url):
    """Open an article and return its <title> / og:title (None if it cannot be opened)."""
    host = urllib.parse.urlparse(url).netloc
    if not url or "news.google.com" in host:
        return None  # Google News links redirect with JavaScript; check the publisher link instead
    try:
        req = ts.urllib.request.Request(url, headers={"User-Agent": ts.USER_AGENT, "Accept": "text/html,*/*"})
        with ts.urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read(400_000).decode("utf-8", "replace")
    except Exception:
        return None
    for pat in (r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title',
                r"<title[^>]*>(.*?)</title>"):
        m = re.search(pat, raw, re.I | re.S)
        if m:
            return ts.clean(m.group(1))
    return ""


def fresh_search(terms, headline):
    """Independent Google News search (India + US editions, last 2 days). Returns matching outlets."""
    out = {}
    for hl, gl in (("en-IN", "IN"), ("en-US", "US")):
        url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote_plus(terms + " when:2d")
               + f"&hl={hl}&gl={gl}&ceid={gl}:en")
        try:
            items = ts.parse_feed(ts.fetch(url))
        except Exception:
            continue
        for it in items[:40]:
            title, pub = it["title"], ""
            if " - " in title:
                title, pub = title.rsplit(" - ", 1)
            if pub and similarity(title, headline) >= 0.5:
                out.setdefault(pub.strip(), {"title": title.strip(), "link": it["link"]})
    return out


def verify_topic(c):
    head_item = ts.headline_item(c)
    head = head_item["title"]
    terms = ts.search_terms(c)
    publishers = {i["source"] for i in c["items"] if i["category"] != "video"}

    # 1) open the source page(s) and compare titles
    source_check = None
    tried = sorted(c["items"], key=lambda i: (i is not head_item, "news.google.com" in (i.get("link") or "")))
    for it in tried[:4]:
        t = page_title(it.get("link"))
        if t is None:
            continue
        sim = similarity(t, it["title"]) if t else 0.0
        source_check = {"publisher": it["source"], "link": it["link"], "page_title": t[:200],
                        "match": sim >= 0.5}
        if source_check["match"]:
            break

    # 2) independent re-search
    extra = fresh_search(terms, head)
    all_outlets = publishers | set(extra)
    independent = {newsroom(p) for p in all_outlets if p.lower() not in COMMUNITY}
    trusted = sorted(p for p in independent if is_trusted(p))

    # 4) official sources
    links = [i.get("link") or "" for i in c["items"]] + [v["link"] for v in extra.values()]
    official = any(any(h in l.lower() for h in OFFICIAL_HOSTS) for l in links)

    # 5) figures reported by 2+ outlets
    seen = {}
    texts = [(i["source"], i["title"] + " " + (i.get("summary") or "")) for i in c["items"]]
    texts += [(p, v["title"]) for p, v in extra.items()]
    for pub, txt in texts:
        for m in NUM_RE.findall(txt):
            seen.setdefault(norm_num(m), set()).add(pub)
    confirmed = sorted(n for n, pubs in seen.items() if len(pubs) >= 2)
    single = sorted(n for n, pubs in seen.items() if len(pubs) == 1)

    # wire copies (PTI/Reuters republished word for word) are one report, not several:
    # count distinct headline wordings
    wordings = []
    for t in [i["title"] for i in c["items"] if i["category"] != "video"] + [v["title"] for v in extra.values()]:
        if all(similarity(t, w) < 0.85 for w in wordings):
            wordings.append(t)

    src_ok = bool(source_check and source_check["match"])
    if (len(independent) >= 3 and len(trusted) >= 2 and len(wordings) >= 2 and len(extra) >= 2
            and (src_ok or official)):
        mark = "verified"
    elif len(independent) >= 2:
        mark = "partial"
    else:
        mark = "unverified"

    reasons = [f"{len(independent)} independent outlet{'s' if len(independent) != 1 else ''}"
               f" ({len(trusted)} trusted)",
               f"{len(extra)} found again in a fresh news search",
               f"{len(wordings)} differently-worded report{'s' if len(wordings) != 1 else ''}"
               + (" (looks like one wire story copied)" if len(wordings) < 2 else "")]
    if source_check:
        reasons.append(("source page opened, title matches" if src_ok else "source page opened, title differs")
                       + f" ({source_check['publisher']})")
    else:
        reasons.append("source pages could not be opened (blocked or paywalled)")
    if official:
        reasons.append("official source linked")
    if confirmed:
        reasons.append("figures confirmed by 2+ outlets: " + ", ".join(confirmed[:6]))
    if single:
        reasons.append("figures seen in only one outlet (double-check): " + ", ".join(single[:6]))
    if not independent - {p for p in independent if p.lower() in COMMUNITY} and publishers <= COMMUNITY:
        reasons.append("community posts only")

    return {"mark": mark, "reasons": reasons, "trusted": trusted, "independent": sorted(independent),
            "source_check": source_check, "official": official, "confirmed_figures": confirmed,
            "unconfirmed_figures": single,
            "extra_coverage": [{"publisher": p, **v} for p, v in list(extra.items())[:8]]}


def verify_all(topics, workers=8):
    """Adds c['verify'] to every topic. Returns counts per mark."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(verify_topic, c): c for c in topics}
        for f in concurrent.futures.as_completed(futs):
            c = futs[f]
            try:
                c["verify"] = f.result()
            except Exception as e:  # one failure must not stop the run
                c["verify"] = {"mark": "unverified", "reasons": [f"check failed: {type(e).__name__}"],
                               "trusted": [], "independent": [], "source_check": None, "official": False,
                               "confirmed_figures": [], "unconfirmed_figures": [], "extra_coverage": []}
    counts = {"verified": 0, "partial": 0, "unverified": 0}
    for c in topics:
        counts[c["verify"]["mark"]] += 1
    return counts

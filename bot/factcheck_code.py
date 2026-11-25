"""Fact-check without any AI: every number, date and name in the captions must appear in the
article text of 2+ different publishers.

check(segments, articles) -> list of claims shaped like
  {"segment_id", "claim", "status": supported|partly|unsupported|manual, "sources", "evidence", "fix"}
"""
import re

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
MON3 = {m[:3]: m for m in MONTHS}
UNIT_MULT = {"lakh crore": 1e12, "crore": 1e7, "cr": 1e7, "lakh": 1e5, "thousand": 1e3, "k": 1e3,
             "million": 1e6, "mn": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "trillion": 1e12, "tn": 1e12}
APPROX_WORDS = ("lagbhag", "kareeb", "kareeban", "about", "around", "nearly", "over", "se zyada", "zyada", "~", "up to")
NUM_RE = re.compile(r"(₹|rs\.?\s?|inr\s?|\$|us\$|€|£)?\s?(\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)\s?-?\s?"
                    r"(lakh crore|crore|cr\b|lakh|thousand|million|mn\b|billion|bn\b|trillion|tn\b|%|per cent|percent)?", re.I)
DATE_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r"|" + "|".join(MON3) + r")\b", re.I)
# words that start Hinglish sentences or are not names
NOT_NAMES = set("""First Next Story Today Here The And But After Under Until Remember Follow Which Tell Your Another Both Shares Investors Pehli Agli Aaj Ek Bas Chalo Dhyan Sabse Ab Aur Global Toh Ye Yeh Isi Is Iss Aapko Comment Subscribe Market Stocks Dividend Big Saath
Lekin Matlab Date Price Valuation Record Panel Supreme Court Claim Goal Reviews Message Demand This Also India Indian Pehle Company Block Agle Phir Kyunki Wajah
""".split())
try:  # common Hinglish words (Pehla, Naye, Lagataar...) are never names
    from hindi_voice import HINDI as _HI
    HINGLISH = set(_HI)
except Exception:
    HINGLISH = set()
ACRONYMS_SKIP = {"IPO", "FPO", "QIP", "CEO", "AI", "OFS", "US", "UK"}


SECTION_WORDS = r"\s+(technology|tech|business|markets?|companies|top news|news|global economy|economy|india|china|world|money|finance|politics)$"


def publisher(name):
    """Feed sections of one newsroom count as one publisher (BBC Technology = BBC Business = BBC)."""
    n = (name or "").strip()
    for _ in range(2):
        n = re.sub(SECTION_WORDS, "", n, flags=re.I).strip()
    n = re.sub(r"^the\s+", "", n, flags=re.I)
    n = {"Livemint": "Mint", "BusinessLine": "Hindu BusinessLine", "The Hindu BusinessLine": "Hindu BusinessLine",
         "Moneycontrol.com": "Moneycontrol", "Yahoo": "Yahoo Finance", "SCMP": "South China Morning Post"}.get(n, n)
    return n


def norm(t):
    return re.sub(r"\s+", " ", t.replace("₹", "₹")).lower()


def parse_numbers(text):
    """All numbers in a text as (value_in_base_units, kind) where kind is pct / money / plain."""
    out = []
    for m in NUM_RE.finditer(text):
        raw = m.group(2).replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        unit = (m.group(3) or "").lower().strip()
        if unit in ("%", "per cent", "percent"):
            out.append((v, "pct", m.start()))
            continue
        v *= UNIT_MULT.get(unit, 1)
        out.append((v, "money" if (m.group(1) or unit) else "plain", m.start()))
    return out


def facts_in(cap):
    """Checkable facts in one caption."""
    facts = []
    low = cap.lower()
    for m in NUM_RE.finditer(cap):
        raw = m.group(2).replace(",", "")
        if not raw or (len(raw) == 4 and raw.isdigit() and 1990 <= int(raw) <= 2100 and not m.group(1)):
            continue  # a year is checked through dates/names, not as an amount
        unit = (m.group(3) or "").lower().strip()
        if not unit and not m.group(1) and len(raw) <= 2:
            continue  # small bare numbers ("do units") are not amounts
        before = low[max(0, m.start() - 14): m.start()]
        val = float(raw)
        kind = "pct" if unit in ("%", "per cent", "percent") else ("money" if (m.group(1) or unit) else "plain")
        if kind != "pct":
            val *= UNIT_MULT.get(unit, 1)
        approx = any(w in before for w in APPROX_WORDS) or "se zyada" in low[m.end(): m.end() + 10]
        facts.append({"type": "number", "text": m.group(0).strip(), "value": val, "kind": kind, "approx": approx})
    for m in DATE_RE.finditer(cap):
        mon = m.group(2).lower()
        facts.append({"type": "date", "text": m.group(0), "day": int(m.group(1)), "month": MON3.get(mon[:3], mon)})
    for m in re.finditer(r"\b([A-Z][A-Za-z&.'-]+(?:\s+[A-Z][A-Za-z&.'-]+){0,3})\b", cap):
        words = [w for w in m.group(1).split() if w not in NOT_NAMES and w.lower() not in HINGLISH and w.lower() not in MONTHS and w.lower()[:3] not in MON3]
        if not words:
            continue
        name = " ".join(words)
        if name.upper() == name and name in ACRONYMS_SKIP:
            continue
        if len(name) < 3:
            continue
        facts.append({"type": "name", "text": name})
    # de-duplicate
    seen, out = set(), []
    for f in facts:
        k = (f["type"], f["text"].lower())
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def found(fact, text_norm, numbers):
    """Return a short evidence snippet if the fact appears in this article, else None."""
    if fact["type"] == "name":
        words = [w.lower() for w in fact["text"].split()]
        i = text_norm.find(fact["text"].lower())
        if i < 0 and all(re.search(r"\b" + re.escape(w) + r"\b", text_norm) for w in words):
            i = text_norm.find(words[-1])
        return text_norm[max(0, i - 60): i + 80] if i >= 0 else None
    if fact["type"] == "date":
        mon, d = fact["month"], fact["day"]
        pats = [rf"\b{d}(st|nd|rd|th)?\s+({mon}|{mon[:3]})\b", rf"\b({mon}|{mon[:3]})\.?\s+{d}\b"]
        for p in pats:
            m = re.search(p, text_norm)
            if m:
                return text_norm[max(0, m.start() - 60): m.end() + 60]
        return None
    tol = 0.06 if fact["approx"] else 0.012
    for v, kind, pos in numbers:
        if fact["kind"] == "pct" and kind != "pct":
            continue
        if fact["kind"] != "pct" and kind == "pct":
            continue
        if v and abs(v - fact["value"]) / max(abs(fact["value"]), 1e-9) <= tol:
            return text_norm[max(0, pos - 60): pos + 70]
    return None


def check(segments, articles):
    by_seg = {}
    for a in articles:
        t = norm(a["text"])
        by_seg.setdefault(a["segment_id"], []).append((publisher(a["publisher"]), t, parse_numbers(t)))
    claims = []
    for g in segments:
        if g["id"] in ("hook", "outro"):
            continue
        arts = by_seg.get(g["id"], [])
        facts = facts_in(g["cap"])
        if not facts:
            claims.append({"segment_id": g["id"], "claim": g["cap"][:120], "status": "manual", "sources": [],
                           "evidence": "No numbers, dates or names to check automatically — read this line against the sources.",
                           "fix": ""})
            continue
        for f in facts:
            pubs, ev = [], ""
            for pub, t, nums in arts:
                snip = found(f, t, nums)
                if snip and pub not in pubs:
                    pubs.append(pub)
                    ev = ev or snip
            st = "supported" if len(pubs) >= 2 else "partly" if pubs else "unsupported"
            fix = "" if st == "supported" else (
                f"Only {pubs[0]} states “{f['text']}” — confirm in a second source or soften/remove it."
                if pubs else f"No source article states “{f['text']}” — check it or remove it.")
            claims.append({"segment_id": g["id"], "claim": f["text"] + (" (approx.)" if f.get("approx") else ""),
                           "status": st, "sources": pubs, "evidence": ("…" + ev.strip() + "…") if ev else "", "fix": fix})
    return claims

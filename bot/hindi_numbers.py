"""Turn numbers in voice text into spoken Hindi so the voice reads them naturally.

    to_hindi_words(129)                 -> "एक सौ उनतीस"
    speak_numbers("₹8,981 crore IPO 19 November, 25% up, $9.6 billion")
      -> "आठ हज़ार नौ सौ इक्यासी करोड़ रुपये IPO उन्नीस November, पच्चीस percent up, नौ दशमलव छह billion dollar"

Indian grouping: hazaar (10^3), lakh (10^5), crore (10^7). Hindi 1-99 are irregular, so they are listed.
"""
import re

ONES = ("शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस "
        "इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस "
        "सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास पचास "
        "इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ "
        "अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी अस्सी इक्यासी "
        "बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे "
        "सत्तानवे अट्ठानवे निन्यानवे").split()
assert len(ONES) == 100


def to_hindi_words(n):
    n = int(n)
    if n < 0:
        return "माइनस " + to_hindi_words(-n)
    if n < 100:
        return ONES[n]
    parts = []
    for size, name in ((10 ** 7, "करोड़"), (10 ** 5, "लाख"), (1000, "हज़ार"), (100, "सौ")):
        if n >= size:
            q, n = divmod(n, size)
            parts.append(f"{to_hindi_words(q)} {name}")
    if n:
        parts.append(ONES[n])
    return " ".join(parts)


DIGITS = "शून्य एक दो तीन चार पाँच छह सात आठ नौ".split()


def decimal_words(s):
    s = s.replace(",", "")
    if "." in s:
        a, b = s.split(".", 1)
        if b.strip("0") == "":
            return to_hindi_words(int(a))
        if b == "5" and int(a) in (1, 2):
            return {1: "डेढ़", 2: "ढाई"}[int(a)]
        return f"{to_hindi_words(int(a or 0))} दशमलव " + " ".join(DIGITS[int(d)] for d in b)
    return to_hindi_words(int(s))


UNIT = r"(lakh crore|crore|cr|lakh|thousand|million|mn|billion|bn|trillion|tn)?"
NUM = r"(\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)"
CUR_RE = re.compile(r"(₹|Rs\.?\s?|INR\s?|\$|US\$|€|£)\s?" + NUM + r"\s?" + UNIT, re.I)
RANGE_RE = re.compile(r"(₹|Rs\.?\s?|\$)\s?" + NUM + r"\s?(?:-|–|to|se)\s?(?:₹|Rs\.?\s?|\$)?\s?" + NUM + r"\s?" + UNIT, re.I)
PCT_RE = re.compile(NUM + r"\s?(%|per cent|percent)", re.I)
PLAIN_RE = re.compile(NUM + r"(\s?(?:lakh crore|crore|lakh|million|billion|trillion))?(?![\w%])", re.I)
CUR_WORD = {"₹": "रुपये", "rs": "रुपये", "inr": "रुपये", "$": "डॉलर", "us$": "डॉलर", "€": "euro", "£": "pound"}
UNIT_WORD = {"lakh crore": "लाख करोड़", "crore": "करोड़", "cr": "करोड़", "lakh": "लाख", "thousand": "हज़ार",
             "million": "million", "mn": "million", "billion": "अरब", "bn": "अरब", "trillion": "trillion", "tn": "trillion"}


NUMBER_LANG = "en"   # "en" = numbers said in English (default), "hi" = Hindi number words


def speak_numbers(text, lang=None):
    """Replace digits in voice text with spoken words (English by default, Hindi with lang="hi")."""
    if (lang or NUMBER_LANG) == "en":
        return speak_numbers_en(text)
    def cur(m):
        sym = m.group(1).strip().rstrip(".").lower()
        unit = (m.group(3) or "").lower()
        words = decimal_words(m.group(2))
        tail = CUR_WORD.get(sym, "")
        return f"{words} {UNIT_WORD[unit]} {tail}".replace("  ", " ").strip() if unit else f"{words} {tail}".strip()

    def pct(m):
        return f"{decimal_words(m.group(1))} percent"

    def plain(m):
        if len(m.group(1).replace(",", "").split(".")[0]) == 4 and 1900 <= int(float(m.group(1).replace(",", ""))) <= 2100 and not m.group(2):
            y = int(m.group(1))                          # a year: "do hazaar chhabbees"
            return to_hindi_words(y)
        unit = (m.group(2) or "").strip().lower()
        return f"{decimal_words(m.group(1))}" + (f" {UNIT_WORD[unit]}" if unit else "")

    def rng(m):
        sym = m.group(1).strip().rstrip(".").lower()
        unit = (m.group(4) or "").lower()
        mid = f" {UNIT_WORD[unit]}" if unit else ""
        return f"{decimal_words(m.group(2))} से {decimal_words(m.group(3))}{mid} {CUR_WORD.get(sym, '')}".strip()

    pad = lambda f: (lambda m: f" {f(m)} ")  # keep a space on both sides so words never glue together
    text = RANGE_RE.sub(pad(rng), text)
    text = CUR_RE.sub(pad(cur), text)
    text = PCT_RE.sub(pad(pct), text)
    text = PLAIN_RE.sub(pad(plain), text)
    text = re.sub(r"\s+([।.,!?;:)])", r"\1", text).replace("( ", "(").replace(" -", "-")
    return re.sub(r"\s{2,}", " ", text).strip()


# ---- English mode (default since 2026-11-23: the user wants numbers said in English, "as is") ----
EN_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
           "sixteen seventeen eighteen nineteen").split()
EN_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def to_english_words(n):
    """Indian grouping in English, the way anchors say it: 1,10,000 -> one lakh ten thousand."""
    n = int(n)
    if n < 0:
        return "minus " + to_english_words(-n)
    if n < 20:
        return EN_ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return EN_TENS[t] + (f"-{EN_ONES[o]}" if o else "")
    parts = []
    for size, name in ((10 ** 7, "crore"), (10 ** 5, "lakh"), (1000, "thousand"), (100, "hundred")):
        if n >= size:
            q, n = divmod(n, size)
            parts.append(f"{to_english_words(q)} {name}")
    if n:
        parts.append(to_english_words(n))
    return " ".join(parts)


def decimal_words_en(s):
    s = s.replace(",", "")
    if "." in s:
        a, b = s.split(".", 1)
        if b.strip("0") == "":
            return to_english_words(int(a))
        return f"{to_english_words(int(a or 0))} point " + " ".join(EN_ONES[int(d)] for d in b)
    return to_english_words(int(s))


def year_en(y):
    if 2000 <= y <= 2009:
        return to_english_words(y)                       # two thousand five
    hi, lo = divmod(y, 100)
    return f"{to_english_words(hi)} " + (to_english_words(lo) if lo >= 10 else f"oh {EN_ONES[lo]}" if lo else "hundred")


CUR_WORD_EN = {"₹": "rupees", "rs": "rupees", "inr": "rupees", "$": "dollars", "us$": "dollars", "€": "euros", "£": "pounds"}
UNIT_WORD_EN = {"lakh crore": "lakh crore", "crore": "crore", "cr": "crore", "lakh": "lakh", "thousand": "thousand",
                "million": "million", "mn": "million", "billion": "billion", "bn": "billion", "trillion": "trillion", "tn": "trillion"}


def speak_numbers_en(text):
    """Replace digits with English words (₹28,000 crore -> twenty-eight thousand crore rupees)."""
    def cur(m):
        sym = m.group(1).strip().rstrip(".").lower()
        unit = (m.group(3) or "").lower()
        tail = CUR_WORD_EN.get(sym, "")
        if not unit and sym in ("₹", "rs", "inr") and m.group(2).replace(",", "") == "1":
            tail = "rupee"
        return " ".join(x for x in (decimal_words_en(m.group(2)), UNIT_WORD_EN.get(unit, ""), tail) if x)

    def pct(m):
        return f"{decimal_words_en(m.group(1))} percent"

    def plain(m):
        raw = m.group(1).replace(",", "")
        if len(raw.split(".")[0]) == 4 and "." not in raw and 1900 <= int(raw) <= 2100 and not m.group(2):
            return year_en(int(raw))
        unit = (m.group(2) or "").strip().lower()
        return decimal_words_en(m.group(1)) + (f" {UNIT_WORD_EN[unit]}" if unit else "")

    def rng(m):
        sym = m.group(1).strip().rstrip(".").lower()
        unit = (m.group(4) or "").lower()
        mid = f" {UNIT_WORD_EN[unit]}" if unit else ""
        return f"{decimal_words_en(m.group(2))} to {decimal_words_en(m.group(3))}{mid} {CUR_WORD_EN.get(sym, '')}".strip()

    pad = lambda f: (lambda m: f" {f(m)} ")
    text = RANGE_RE.sub(pad(rng), text)
    text = CUR_RE.sub(pad(cur), text)
    text = PCT_RE.sub(pad(pct), text)
    text = PLAIN_RE.sub(pad(plain), text)
    text = re.sub(r"\s+([।.,!?;:)])", r"\1", text).replace("( ", "(").replace(" -", "-")
    text = re.sub(r"\bMW\b", "megawatt", re.sub(r"\bGW\b", "gigawatt", text))
    return re.sub(r"\s{2,}", " ", text).strip()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for n in (0, 9, 19, 99, 100, 129, 136, 218, 1000, 2962, 8981, 90000, 125000, 18000000):
        print(n, to_hindi_words(n))
    print(speak_numbers("₹8,981 crore IPO 19 November, price band ₹129-136, 25% up, $9.6 billion, 2027 tak, 1.5 lakh crore", "hi"))
    print(speak_numbers("₹8,981 crore IPO 19 November, price band ₹129-136, 25% up, $9.6 billion, 2027 tak, 1.5 lakh crore"))

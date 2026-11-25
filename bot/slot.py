"""Slot timing helpers (all times IST).

    python bot/slot.py detect [slot]        -> prints am | pm | night (from the input, or from the current time)
    python bot/slot.py wait-cutoff <slot>   -> sleeps until the slot's news cut-off
    python bot/slot.py wait-post <slot> <date>  -> sleeps until post time; exit 3 if already past the late limit
    python bot/slot.py window <slot> <date> -> exit 0 if approval is still in time, 3 if too late
    python bot/slot.py minutes-to-post <slot> <date> -> minutes until the post time (negative = past)
"""
import datetime as dt, json, sys, time
from pathlib import Path

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
CONFIG = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
SLOTS = CONFIG["slots"]


def at(date, hhmm):
    h, m = map(int, hhmm.split(":"))
    return dt.datetime.combine(dt.date.fromisoformat(date), dt.time(h, m), IST)


def now():
    return dt.datetime.now(IST)


def detect(given=""):
    if given in SLOTS:
        return given
    n = now()
    best = min(SLOTS, key=lambda s: abs((at(n.date().isoformat(), SLOTS[s]["post"]) - n).total_seconds()))
    return best


def sleep_until(t):
    while (left := (t - now()).total_seconds()) > 0:
        print(f"waiting {left / 60:.1f} min until {t:%H:%M} IST", flush=True)
        time.sleep(min(left, 300))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "detect":
        s = detect(sys.argv[2] if len(sys.argv) > 2 else "")
        print(f"slot={s}\ndate={now().date().isoformat()}\npost={SLOTS[s]['post']}")
    elif cmd == "wait-cutoff":
        sleep_until(at(now().date().isoformat(), SLOTS[sys.argv[2]]["news_cutoff"]))
    elif cmd == "minutes-to-post":
        print(int((at(sys.argv[3], SLOTS[sys.argv[2]]["post"]) - now()).total_seconds() // 60))
    elif cmd in ("wait-post", "window"):
        slot, date = sys.argv[2], sys.argv[3]
        post = at(date, SLOTS[slot]["post"])
        late = post + dt.timedelta(minutes=CONFIG["max_late_minutes"])
        if now() > late:
            print(f"too late: the {slot} slot closed at {late:%H:%M} IST")
            sys.exit(3)
        if cmd == "wait-post":
            sleep_until(post)

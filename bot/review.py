"""Text for the review issue and the phone notification.

    python bot/review.py <slot> <date>  -> run/review.md (GitHub issue body) and run/notify.md (ntfy message)
"""
import json, sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "run"
CONFIG = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
LABEL = {"am": "8 AM", "pm": "4 PM", "night": "9 PM"}


def main(slot, date):
    d = json.loads((RUN / "draft.json").read_text(encoding="utf-8"))
    kit = json.loads((RUN / "kit.json").read_text(encoding="utf-8")) if (RUN / "kit.json").exists() else {}
    checks = (RUN / "checks.md").read_text(encoding="utf-8") if (RUN / "checks.md").exists() else ""
    ok = "✅ PASSED" in checks
    md = [f"<!-- stickbiz slot={slot} date={date} -->",
          f"## {LABEL[slot]} Short — {date}", "",
          "**Reply to this issue:** `OK` = approve and post · `SKIP` = don't post this slot · `STOP` = cancel after the preview · "
          "anything else = a change request in plain words (e.g. *make the hook punchier*, *drop the Wipro story*).", "",
          f"⏰ Posts at {CONFIG['slots'][slot]['post']} IST after your OK (up to {CONFIG['max_late_minutes']} min late is allowed).", "",
          "### 🎬 Script (voice)", "", f"**Hook:** {d['hook']['cap']}", ""]
    for s in d["stories"]:
        pubs = sorted({r["publisher"] for r in s["sources"]})
        md += [f"**{s['tag']} — {s['headline']}** · _{len(pubs)} sources: {', '.join(pubs)}_", "", s["cap"], "",
               "On screen: " + " → ".join(f"“{b['banner'][0]} / {b['banner'][1] if len(b['banner']) > 1 else ''}”" for b in s["beats"]), ""]
    md += [f"**Outro:** {d['outro']['cap']}", "", "### 📺 Titles", ""] + [f"{i}. {t}" for i, t in enumerate(d["titles"], 1)]
    md += ["", f"**Pinned comment:** {d['pinned_comment']}", "", f"**Tags:** {d['tags']}", "", checks]
    if kit.get("description"):
        md += ["", "<details><summary>Full description</summary>", "", "```", kit["description"], "```", "", "</details>"]
    (RUN / "review.md").write_text("\n".join(md), encoding="utf-8")

    n = [f"{'✅' if ok else '❌ CHECKS FAILED'} {LABEL[slot]} Short ready to review", "",
         f"HOOK: {d['hook']['cap']}", ""]
    for s in d["stories"]:
        n += [f"▶ {s['headline']} ({len({r['publisher'] for r in s['sources']})} sources)", s["cap"], ""]
    n += [f"TITLE: {d['titles'][0]}", "", "Reply OK / SKIP / your changes on the review page."]
    (RUN / "notify.md").write_text("\n".join(n), encoding="utf-8")
    print("review.md + notify.md written;", "checks passed" if ok else "checks FAILED")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

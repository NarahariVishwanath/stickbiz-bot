"""Phone notifications through ntfy (https://ntfy.sh).

    python bot/notify.py "<title>" <message-file-or-text> [--click URL] [--action "Label|URL"]... [--tags x,y] [--priority 4]
Topic from the NTFY_TOPIC secret (optional NTFY_SERVER, default https://ntfy.sh).
"""
import os, sys, urllib.request
from pathlib import Path


def send(title, message, click=None, actions=(), tags="", priority=3):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("NTFY_TOPIC not set; notification skipped:", title)
        return
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    if len(message.encode("utf-8")) > 3900:       # ntfy turns longer messages into attachments
        message = message.encode("utf-8")[:3850].decode("utf-8", "ignore") + "\n… (full script on the review page)"
    headers = {"Title": title.encode("utf-8"), "Priority": str(priority), "Markdown": "yes"}
    if click:
        headers["Click"] = click
    if tags:
        headers["Tags"] = tags
    if actions:
        headers["Actions"] = "; ".join(f"view, {label}, {url}" for label, url in actions).encode("utf-8")
    req = urllib.request.Request(f"{server}/{topic}", data=message.encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        print("ntfy:", r.status, title)


if __name__ == "__main__":
    args = sys.argv[1:]
    title, body = args[0], args[1]
    body = Path(body).read_text(encoding="utf-8") if Path(body).is_file() else body
    click, actions, tags, prio = None, [], "", 3
    i = 2
    while i < len(args):
        if args[i] == "--click":
            click = args[i + 1]
        elif args[i] == "--action":
            label, url = args[i + 1].split("|", 1)
            actions.append((label, url))
        elif args[i] == "--tags":
            tags = args[i + 1]
        elif args[i] == "--priority":
            prio = int(args[i + 1])
        i += 2
    send(title, body, click, actions, tags, prio)

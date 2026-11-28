"""Upload the finished Short to YouTube (Data API v3, resumable upload) and post the pinned-comment text.

    python bot/upload_youtube.py run/final.mp4     -> prints the video URL, writes run/youtube.json
Secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Note: until Google audits the API project, YouTube keeps API uploads PRIVATE - switch them to public in Studio.
"""
import json, os, sys, urllib.parse, urllib.request
from pathlib import Path

RUN = Path(__file__).parent.parent / "run"


def token():
    data = urllib.parse.urlencode({"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                                   "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    return json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30).read())["access_token"]


def main(video):
    if os.environ.get("YT_TEST") == "1":     # connection test: a private clip with a plain title, no comment
        kit = {"tags": "stickbiz bot test", "titles": ["StickBiz bot upload test (private) - delete me"],
               "description": "Automatic connection test from the StickBiz bot. Safe to delete.", "pinned_comment": ""}
    else:
        kit = json.loads((RUN / "kit.json").read_text(encoding="utf-8"))
    tags, total = [], 0
    for t in [x.strip() for x in kit["tags"].split(",") if x.strip()]:
        if total + len(t) + 3 > 480:
            break
        tags.append(t)
        total += len(t) + 3
    title = kit["titles"][0]
    if "#shorts" not in title.lower() and len(title) <= 90:
        title += " #Shorts"
    meta = {"snippet": {"title": title[:100], "description": kit["description"][:4990], "tags": tags,
                        "categoryId": "27", "defaultLanguage": "en", "defaultAudioLanguage": "hi"},
            "status": {"privacyStatus": "private" if os.environ.get("YT_TEST") == "1" else "public", "selfDeclaredMadeForKids": False}}
    at = token()
    size = os.path.getsize(video)
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(meta).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {at}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    loc = urllib.request.urlopen(req, timeout=60).headers["Location"]
    with open(video, "rb") as f:
        up = urllib.request.Request(loc, data=f.read(), method="PUT",
                                    headers={"Authorization": f"Bearer {at}", "Content-Type": "video/mp4"})
    res = json.loads(urllib.request.urlopen(up, timeout=600).read())
    vid = res["id"]
    url = f"https://youtube.com/shorts/{vid}"
    print("YouTube:", url, "| privacy:", res.get("status", {}).get("privacyStatus"))
    if not kit.get("pinned_comment"):
        (RUN / "youtube.json").write_text(json.dumps({"id": vid, "url": url, "privacy": res.get("status", {}).get("privacyStatus")}), encoding="utf-8")
        return
    try:   # the pinned-comment text as the first comment (pin it in the app - the API cannot pin)
        body = {"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": kit["pinned_comment"]}}}}
        urllib.request.urlopen(urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/commentThreads?part=snippet", data=json.dumps(body).encode("utf-8"),
            method="POST", headers={"Authorization": f"Bearer {at}", "Content-Type": "application/json"}), timeout=30)
    except Exception as e:
        print("comment not posted:", e)
    (RUN / "youtube.json").write_text(json.dumps({"id": vid, "url": url, "privacy": res.get("status", {}).get("privacyStatus")}), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])

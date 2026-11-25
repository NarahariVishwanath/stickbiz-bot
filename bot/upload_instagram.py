"""Publish the Short as an Instagram Reel (Instagram Graph API, content publishing).

    python bot/upload_instagram.py <public video URL>   -> prints the Reel link, writes run/instagram.json
Secrets: IG_USER_ID (Instagram professional account id), IG_ACCESS_TOKEN (long-lived token with
instagram_content_publish). The video must be at a public URL (the bot uses its GitHub release asset).
"""
import json, os, sys, time, urllib.parse, urllib.request
from pathlib import Path

RUN = Path(__file__).parent.parent / "run"
API = "https://graph.facebook.com/" + os.environ.get("IG_API_VERSION", "v21.0")


def call(path, params, method="POST"):
    params = dict(params, access_token=os.environ["IG_ACCESS_TOKEN"])
    data = urllib.parse.urlencode(params)
    if method == "GET":
        req = urllib.request.Request(f"{API}/{path}?{data}")
    else:
        req = urllib.request.Request(f"{API}/{path}", data=data.encode("utf-8"), method="POST")
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Instagram API error {e.code}: {e.read()[:400].decode(errors='replace')}")


def main(video_url):
    kit = json.loads((RUN / "kit.json").read_text(encoding="utf-8"))
    uid = os.environ["IG_USER_ID"]
    c = call(f"{uid}/media", {"media_type": "REELS", "video_url": video_url, "caption": kit["instagram_caption"][:2150],
                              "share_to_feed": "true"})
    cid = c["id"]
    for _ in range(60):                      # Instagram downloads and processes the video first
        st = call(cid, {"fields": "status_code,status"}, "GET")
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise SystemExit(f"Instagram could not process the video: {st}")
        time.sleep(10)
    else:
        raise SystemExit("Instagram processing timed out")
    pub = call(f"{uid}/media_publish", {"creation_id": cid})
    link = call(pub["id"], {"fields": "permalink"}, "GET").get("permalink", "")
    print("Instagram:", link)
    (RUN / "instagram.json").write_text(json.dumps({"id": pub["id"], "url": link}), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])

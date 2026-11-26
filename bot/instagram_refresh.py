"""Keep the Instagram token alive: renews the 60-day long-lived token (Instagram-login tokens, "IG...").

    python bot/instagram_refresh.py
If Instagram hands back a NEW token string and a GH_PAT secret exists (fine-grained token with
"Secrets: read and write" on this repo), the IG_ACCESS_TOKEN secret is updated automatically.
Otherwise it says what to do. Prints days left; exit 2 = the user must act.
"""
import base64, json, os, sys, urllib.parse, urllib.request

tok = os.environ["IG_ACCESS_TOKEN"].strip()
if not tok.startswith("IG"):
    print("Token is not an Instagram-login token; nothing to refresh (Facebook system-user tokens do not expire).")
    sys.exit(0)
url = "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": tok})
try:
    r = json.loads(urllib.request.urlopen(url, timeout=30).read())
except urllib.error.HTTPError as e:
    print("Refresh failed:", e.code, e.read()[:300].decode(errors="replace"))
    sys.exit(2)
new, days = r.get("access_token", ""), int(r.get("expires_in", 0)) // 86400
print(f"Refreshed: valid for {days} more days.")
if not new or new == tok:
    sys.exit(0)
pat, repo = os.environ.get("GH_PAT", "").strip(), os.environ.get("GITHUB_REPOSITORY", "")
if not pat:
    print("Instagram issued a NEW token string. Add a GH_PAT secret so the bot can store it, or generate a new token "
          "in the Meta app (Instagram -> API setup -> Generate token) and update IG_ACCESS_TOKEN.")
    sys.exit(2)
from nacl import encoding, public          # pip install pynacl
H = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
k = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=H)).read())
box = public.SealedBox(public.PublicKey(k["key"].encode(), encoding.Base64Encoder()))
enc = base64.b64encode(box.encrypt(new.encode())).decode()
req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/IG_ACCESS_TOKEN", method="PUT", headers=H,
                             data=json.dumps({"encrypted_value": enc, "key_id": k["key_id"]}).encode())
urllib.request.urlopen(req)
print("Stored the new token in the IG_ACCESS_TOKEN secret.")

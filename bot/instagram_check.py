"""Check the Instagram token WITHOUT posting: reads the account name and today's publishing allowance.

    python bot/instagram_check.py     (needs IG_ACCESS_TOKEN, optional IG_USER_ID)
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import upload_instagram as U

uid = os.environ.get("IG_USER_ID", "").strip() or "me"
print("API host:", U.API)
me = U.call(uid, {"fields": "username,account_type" if "instagram.com" in U.API else "username,name"}, "GET")
print("Account:", me.get("username"), "| type:", me.get("account_type", "-"), "| id:", me.get("id") or me.get("user_id"))
try:
    lim = U.call(f"{uid}/content_publishing_limit", {"fields": "quota_usage,config"}, "GET")
    print("Publishing limit:", json.dumps(lim.get("data", lim))[:200])
except SystemExit as e:
    print("Could not read the publishing limit:", e)

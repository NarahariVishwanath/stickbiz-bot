"""ONE-TIME, on your own PC: give the bot permission to upload to your YouTube channel.

    python bot/youtube_auth.py <client_id> <client_secret>

Opens Google's consent page in your browser (sign in with the channel's Google account and allow).
Then prints a REFRESH TOKEN. Save it as the GitHub secret YT_REFRESH_TOKEN (never paste it in chat).
Uses only the Python standard library.
"""
import http.server, json, sys, threading, urllib.parse, urllib.request, webbrowser

SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"


def main(cid, secret):
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got["code"] = (q.get("code") or [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done - you can close this tab and go back to the terminal.")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = f"http://127.0.0.1:{srv.server_port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {"client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
         "access_type": "offline", "prompt": "consent"})
    threading.Thread(target=srv.handle_request, daemon=True).start()
    print("Opening your browser for Google sign-in…\nIf it does not open, visit:\n" + url)
    webbrowser.open(url)
    while "code" not in got:
        pass
    data = urllib.parse.urlencode({"code": got["code"], "client_id": cid, "client_secret": secret,
                                   "redirect_uri": redirect, "grant_type": "authorization_code"}).encode()
    tok = json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data).read())
    print("\nYT_REFRESH_TOKEN (save as a GitHub secret, keep it private):\n")
    print(tok["refresh_token"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

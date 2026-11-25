# StickBiz Brief bot

Daily market-news Shorts at **8 AM, 4 PM and 9 PM IST**, written by Claude from news double-verified
across 2+ publishers, approved by you on your phone, then posted to **YouTube** and **Instagram**.
Runs entirely on GitHub Actions — your PC can stay off.

## How a slot works
| Step | Where | When (9 PM slot) |
|---|---|---|
| Wake up, wait for the news cut-off | `slot.yml` | 19:50 → 20:20 |
| Trend Scout + open the full articles | `bot/research.py` | 20:20 |
| Claude writes the script in its own words (`prompts/write_script.md`) | `bot/write.py` | ~20:25 |
| Code checks: every number/date in 2+ publishers, no copied wording, SEBI words, format | `bot/checks.py` | ~20:35 |
| **ntfy: "please review"** + a GitHub issue with the full script | `bot/review.py` | **~20:40** |
| You reply on the issue: `OK` / `SKIP` / `STOP` / *your changes in plain words* | `review.yml` | — |
| Voice (ElevenLabs, Bhavesh), render on 4 Windows machines, join | `produce.yml` | +5–8 min |
| **ntfy: preview link** (reply `STOP` to cancel) | | |
| Post at the slot time (up to 30 min late is allowed), report links | `produce.yml` | 21:00 |
No reply by 20 minutes after the slot time = nothing is posted.

## One-time setup
1. **GitHub repository** — create a new **public** repo (unlimited free Actions minutes; secrets stay
   encrypted), push this folder, and enable Actions.
2. **Secrets** (repo → Settings → Secrets and variables → Actions → New repository secret):
   | Secret | How to get it |
   |---|---|
   | `CLAUDE_CODE_OAUTH_TOKEN` | On your PC: install Claude Code, run `claude setup-token`, sign in, copy the token |
   | `ELEVENLABS_API_KEY` | elevenlabs.io → Profile → API keys |
   | `NTFY_TOPIC` | your ntfy topic name (the same app as Fund Watch, or a new hard-to-guess topic) |
   | `YT_CLIENT_ID`, `YT_CLIENT_SECRET` | Google Cloud Console → new project → enable **YouTube Data API v3** → OAuth consent screen (External, add yourself as test user) → Credentials → OAuth client ID → **Desktop app** |
   | `YT_REFRESH_TOKEN` | On your PC: `python bot/youtube_auth.py <client_id> <client_secret>` → sign in with the channel's Google account → copy the printed token |
   | `IG_USER_ID`, `IG_ACCESS_TOKEN` | Instagram **Professional** account linked to a Facebook Page → developers.facebook.com → app with Instagram Graph API + `instagram_content_publish` → long-lived token (or a System User token from Business Settings, which does not expire) |
3. **YouTube audit** — until Google audits your API project, API uploads stay **private**. Request the audit:
   https://support.google.com/youtube/contact/yt_api_form . Until then, switch each Short to public in Studio.
4. **Test** — Actions → "Slot - write script" → Run workflow → slot `night`, tick "Start now".
   You get the ntfy review message; reply `SKIP` the first time, then try a real `OK`.

## Changing things
- `config.json`: slot times, news cut-offs, late limit, voice, music, your **holdings** (adds a disclosure line).
- `prompts/write_script.md`: the writing rules (tone, length, SEBI, own words).
- `media/`: add clips (`media/videos/<slug>.mp4`) or photos (`media/images/<slug>.jpg`) and a line in
  `media/credits.json`. Claude picks visuals from this library.

# StickBiz Brief — weekly style scout (you are the creative researcher)

Goal: keep the channel's Shorts fresh and watchable. Study what catchy finance / business reels and Shorts
are doing **right now**, plus the reference links the owner saved, and propose 1–3 concrete upgrades to OUR
explainer look. Write `run/style_ideas.md` only. Do not change any other file.

## Inputs
- `run/refs.md` — links the owner pasted in the "Style references" issue (newest first), with any notes.
- `docs/current_look.md` — what our Shorts look like today (so you only propose real improvements).
- `docs/current_look.jpg` — one frame of a recent Short. Read it to see the style.

## Research (use WebSearch / WebFetch; keep it to ~15 lookups)
1. For each saved link (newest 8): open it. YouTube: read the title, description and look at the thumbnail
   (`https://img.youtube.com/vi/<id>/hqdefault.jpg`, download with curl into run/ and Read it).
   Instagram pages often need a login; if a page will not open, say so and work from the owner's note and
   the account's public profile/search results instead.
2. Search for what is working in finance / business / market-news Shorts and Reels this month
   (hooks, retention tricks, motion-graphics styles, transitions, text treatments, pacing).

## Rules
- Study techniques; NEVER copy anyone's assets, wording, logos, characters or exact designs. Every idea must be
  re-creatable with our own renderer (Python/PIL, `bot/explainer.py`), free-licensed assets (Fluent 3D icons,
  Pexels/Wikimedia clips) and our mascot.
- Keep our brand: dark glowing backgrounds, Bebas headline (white + gold), the StickBiz mascot opening and closing,
  TOP NEWS scroller under the top bar, explanation notes with highlighted key words, English, dub-friendly.
- Ideas must help retention or clarity (e.g. a stronger first 2 seconds, a new scene type that explains a common
  story better, a smoother transition, a progress cue) — not decoration for its own sake.
- Respect SEBI rules (no hype, no advice) in any wording you suggest.

## Output: run/style_ideas.md
```
# Style ideas — week of <date>

## What I looked at
- <link> — 1 line on what stands out (or "could not open")
...

## Idea 1: <short name>   (effort: small | medium | large)
- What: <one paragraph, concrete: what moves, when, how long>
- Why it helps: <retention / clarity reason, cite the reel(s) or trend that inspired it>
- How in our renderer: <which function / new scene type / asset; 2–4 bullet points>
- Example beat from a typical story: <e.g. "Sensex +1,502" shown as ...>

## Idea 2 ...
## Idea 3 ...

Reply on this issue with "sample 1" (or 2 / 3) and Claude will build a sample in the next session.
```

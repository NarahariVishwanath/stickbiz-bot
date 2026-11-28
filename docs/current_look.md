# Current look of StickBiz Brief Shorts (explainer v4, 26 Nov 2026)

- 1080×1920, 60–80 s, Hinglish voice since 28 Nov (ElevenLabs "Bhavesh", language hi, numbers spoken in Hindi, excited tag, tempo 1.15); on-screen text in English, warm 112 BPM music bed.
- Top bar: "StickBiz Brief" pill, date + slot, pulsing red SUBSCRIBE pill. Right under it: red "TOP NEWS" label and a
  scrolling ticker with one line per story.
- Hook: the StickBiz mascot (cartoon presenter in a navy suit) walks in and stands at a fixed spot (left) while he
  reads the headlines; 1–3 Fluent 3D icons pop in above him; big two-line Bebas headline at the bottom
  (white line + gold line) with a small spaced kicker above it.
- News part: the mascot walks out of frame; the whole screen is the explanation:
  - background = dark glow by mood (green up / red down / blue neutral), drifting slowly, with floating particles;
  - one scene per sentence: flow (icon A → icon B with an animated dashed arc and a value chip), compare (two white
    number cards with ▲/▼ colours and "VS"), bignum (icon + huge coloured number), icons (1–3 popping icons with
    labels and arrows), clip (real Pexels/Wikimedia video in a rounded card with a label);
  - an explanation card under the scene: one sentence; 2–3 key phrases get a gold marker swipe one after another;
  - the big Bebas headline at the bottom.
- Outro: the mascot walks back to the centre; "Thought of the day" quote card + big pulsing SUBSCRIBE.
- No burned-in captions (YouTube and Meta translate/dub the Hinglish audio). Transitions: scenes pop in with a small overshoot; tone colours crossfade.
- Renderer: `bot/explainer.py` (PIL), scenes in `SCENES`; assets in `media/icons`, `media/videos`, `media/images`.

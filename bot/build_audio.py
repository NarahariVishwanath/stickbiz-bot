"""Make the voiceover (edge-tts, Hindi neural voice), synthesize the news sounds
and music bed, and write out/mix.wav, out/envelope.npy and out/timeline.json.

Needs: pip install edge-tts imageio-ffmpeg
"""
import os
import asyncio, json, subprocess, sys, wave
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
OUT = Path(os.environ["STICKBIZ_OUT"]) if os.environ.get("STICKBIZ_OUT") else HERE / "out"  # separate work folder
OUT.mkdir(exist_ok=True)
SR, FPS = 44100, 30
MAX_LEN = 148.0  # stay under 2:30

SCRIPT = json.loads(Path(os.environ.get("STICKBIZ_SCRIPT", HERE / "script.json")).read_text(encoding="utf-8"))
SEGS = SCRIPT["segments"]


# ----------------------------------------------------------------------------
# voice
# ----------------------------------------------------------------------------
async def tts(text, rate, mp3):
    import edge_tts
    try:
        comm = edge_tts.Communicate(text, SCRIPT["voice"], rate=rate, boundary="WordBoundary")
    except TypeError:  # older edge-tts
        comm = edge_tts.Communicate(text, SCRIPT["voice"], rate=rate)
    words = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7))
    return words


def decode(path, tempo=1.0, chain=None):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    af = ["-af", f"atempo={tempo:.3f}"] if abs(tempo - 1) > 1e-3 else []
    if chain:
        af = ["-af", chain]
    raw = subprocess.run([ff, "-v", "quiet", "-i", str(path), *af, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def make_voice(rate):
    clips = []
    for s in SEGS:
        mp3 = OUT / f"vo_{s['id']}.mp3"
        words = asyncio.run(tts(s["tts"], rate, mp3))
        a = decode(mp3)
        # trim silence at both ends
        idx = np.where(np.abs(a) > 0.01)[0]
        lead = idx[0] / SR if len(idx) else 0
        a = a[idx[0]: idx[-1] + 1] if len(idx) else a
        words = [(max(0, w0 - lead), max(0, w1 - lead)) for w0, w1 in words]
        clips.append((a, words))
    return clips


def split_full_voice(path, tempo=1.0):
    """One human-voice file for the whole script (vidIQ / ElevenLabs): split it into the
    script's segments at the longest pauses, keeping each piece near its share of the text."""
    a = decode(path, tempo)
    frame = int(0.02 * SR)
    rms = np.array([np.sqrt(np.mean(a[i:i + frame] ** 2)) for i in range(0, len(a) - frame, frame)])
    quiet = rms < max(0.004, np.percentile(rms, 20) * 1.5)
    gaps, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if (j - i) * 0.02 >= 0.25:
                gaps.append(((i + j) / 2 * 0.02, (j - i) * 0.02))
            i = j
        else:
            i += 1
    total = len(a) / SR
    lens = np.array([len(x["tts"]) for x in SEGS], float)
    targets = np.cumsum(lens)[:-1] / lens.sum() * total
    cuts = []
    for tg in targets:  # long pause close to where this segment should end
        cands = [g for g in gaps if g[0] > (cuts[-1] if cuts else 0) + 1.0]
        best = max(cands, key=lambda g: g[1] - abs(g[0] - tg) * 0.15)
        cuts.append(best[0])
    bounds = [0.0] + cuts + [total]
    clips = []
    for k in range(len(SEGS)):
        c = a[int(bounds[k] * SR): int(bounds[k + 1] * SR)]
        idx = np.where(np.abs(c) > 0.01)[0]
        c = c[idx[0]: idx[-1] + 1] if len(idx) else c
        clips.append((c, []))
    print("cuts at", [round(c, 2) for c in cuts])
    return clips


def load_local_voice(tempo=1.08):
    """Sentences voiced by local_voice.py (Indic Parler-TTS): polish each one (EQ, compression,
    pace), join them with short breaths, and return per-sentence times for caption sync."""
    import re
    from voice_polish import CHAIN
    vdir = OUT / "vo_local"
    man = json.loads((vdir / "manifest.json").read_text(encoding="utf-8"))
    chain = CHAIN.rsplit(",", 1)[0].format(tempo=tempo)  # loudness is evened out below instead
    breath = np.zeros(int(0.16 * SR))
    clips = []
    for seg in man["segments"]:
        parts, spans, t = [], [], 0.0
        for f in seg["files"]:
            a = decode(vdir / f, chain=chain)
            idx = np.where(np.abs(a) > 0.01)[0]
            a = a[idx[0]: idx[-1] + 1] if len(idx) else a
            spans.append((t, t + len(a) / SR))
            parts += [a, breath]
            t += len(a) / SR + len(breath) / SR
        a = np.concatenate(parts[:-1])
        a = a / max(1e-6, np.sqrt(np.mean(a[np.abs(a) > 0.02] ** 2))) * 0.16  # even level per story
        a = np.clip(a, -0.98, 0.98)
        clips.append((a, {"sentences": spans}))
    return clips


# ----------------------------------------------------------------------------
# ElevenLabs (direct API) — same key as the long-form tool
# ----------------------------------------------------------------------------
KEY_FILE = HERE.parent / "longform" / ".elevenlabs_key"
# 2026-11-23: the user picked eleven_v3 (more fluent Hinglish) over multilingual_v2 in an A/B test.
# 2026-11-25: channel switched to English originals (YouTube auto-dubs to Hindi/Telugu/Tamil); user picked
# Bhavesh (Indian English) from 7 samples. Older Hindi scripts keep their own voice_id/language_code.
ELEVEN_DEFAULT = {"voice_id": "dloMvYEKtYloiwx06kR4", "voice_name": "Bhavesh - Indian English & Hindi",
                  "model": "eleven_v3", "language_code": "en", "tempo": 1.0,
                  "settings": {"stability": 0.5, "similarity_boost": 0.8}}
OLD_V2 = "eleven_multilingual_v2"   # scripts that still name it are moved to v3 unless they set "keep_model": true


def eleven_key():
    import os
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not k and KEY_FILE.exists():
        k = KEY_FILE.read_text(encoding="utf-8").strip()
    if not k:
        sys.exit(f"No ElevenLabs key: set ELEVENLABS_API_KEY or create {KEY_FILE}")
    return k


def eleven(path, body=None, method="GET"):
    import urllib.request, urllib.error
    req = urllib.request.Request("https://api.elevenlabs.io" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"xi-api-key": eleven_key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs error {e.code}: {e.read()[:400].decode(errors='replace')}")


def eleven_cfg():
    cfg = json.loads(json.dumps(ELEVEN_DEFAULT))
    user = dict(SCRIPT.get("elevenlabs", {}))
    if user.get("model") == OLD_V2 and not user.get("keep_model"):
        user.pop("model"); user.pop("settings", None)   # old v2 settings (style, speed) don't suit v3
    cfg["settings"].update(user.get("settings", {}))
    cfg.update({k: v for k, v in user.items() if k != "settings"})
    if not cfg["voice_id"]:
        sys.exit("Set elevenlabs.voice_id in script.json (run: build_audio.py --voices)")
    return cfg


def load_eleven_voice():
    """One request per story (with the neighbouring text for natural flow), cached by text +
    settings. Returns clips with per-sentence times taken from ElevenLabs' character timings."""
    import base64, hashlib, re
    cfg = eleven_cfg()
    vdir = HERE / "out" / "vo_eleven"  # shared voice cache (keyed by text + settings)
    vdir.mkdir(parents=True, exist_ok=True)
    clips = []
    for k, seg in enumerate(SEGS):
        text = seg["tts"]
        req_cfg = {k2: v for k2, v in cfg.items() if k2 != "tempo"}   # tempo is applied locally: no re-voicing
        key = hashlib.sha1(json.dumps([text, req_cfg], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        mp3, meta = vdir / f"{seg['id']}_{key}.mp3", vdir / f"{seg['id']}_{key}.json"
        if not (mp3.exists() and meta.exists()):
            body = {"text": text, "model_id": cfg["model"], "voice_settings": cfg["settings"]}
            if cfg.get("language_code"):
                body["language_code"] = cfg["language_code"]
            if cfg["model"] != "eleven_v3":          # v3 does not take neighbouring text
                if k > 0:
                    body["previous_text"] = SEGS[k - 1]["tts"]
                if k + 1 < len(SEGS):
                    body["next_text"] = SEGS[k + 1]["tts"]
            r = eleven(f"/v1/text-to-speech/{cfg['voice_id']}/with-timestamps?output_format=mp3_44100_128", body, "POST")
            mp3.write_bytes(base64.b64decode(r["audio_base64"]))
            meta.write_text(json.dumps(r.get("alignment") or r.get("normalized_alignment"), ensure_ascii=False),
                            encoding="utf-8")
            print(f"  voiced {seg['id']} ({len(text)} chars)")
        al = json.loads(meta.read_text(encoding="utf-8"))
        st, en = al["character_start_times_seconds"], al["character_end_times_seconds"]
        m = len(st)
        tmap = lambda i: (st[min(m - 1, int(i * m / max(1, len(text))))], en[min(m - 1, int(i * m / max(1, len(text))))])
        tempo = float(cfg.get("tempo", 1.0))   # pitch-preserving speed-up (ffmpeg atempo); v3 has no speed setting
        a = decode(mp3, tempo)
        idx = np.where(np.abs(a) > 0.01)[0]
        lead = idx[0] / SR if len(idx) else 0.0
        a = a[idx[0]: idx[-1] + 1] if len(idx) else a
        spans, pos = [], 0
        for sent in [x for x in re.split(r"(?<=[.!?।])\s+", text.strip()) if x]:
            i0 = text.find(sent, pos)
            i1 = i0 + len(sent) - 1
            pos = i1 + 1
            spans.append((float(max(0.0, tmap(i0)[0] / tempo - lead)), float(max(0.0, tmap(i1)[1] / tempo - lead))))
        clips.append((a, {"sentences": spans}))
    return clips


def list_eleven_voices():
    r = eleven("/v1/voices")
    for v in r.get("voices", []):
        print(f"{v['voice_id']}  {v.get('name', '')}  [{v.get('category', '')}]")


# ----------------------------------------------------------------------------
# synthesized sounds (no samples, no copyright)
# ----------------------------------------------------------------------------
rng = np.random.default_rng(1)


def env_adsr(n, a=0.005, r=0.3):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)
    return e


def tone(f, dur, r=0.3, harm=(1, 0.5, 0.25)):
    t = np.arange(int(dur * SR)) / SR
    y = sum(h * np.sin(2 * np.pi * f * (k + 1) * t) for k, h in enumerate(harm))
    return y * env_adsr(len(t), r=r)


def lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # small buffers only
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def riser(dur=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = t / dur
    sweep = np.sin(2 * np.pi * np.cumsum(180 + 1100 * k ** 2) / SR) * 0.35
    noise = rng.standard_normal(n)
    noise = noise - lowpass(noise, 0.05 + 0.4 * 0)  # brighter noise
    return (sweep + noise * 0.25 * k) * k ** 2


def impact():
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-t * 6) + 42) / SR) * np.exp(-t * 3.2)
    burst = rng.standard_normal(n) * np.exp(-t * 18) * 0.5
    stab = sum(tone(f, 1.4, r=0.45) for f in (220, 261.6, 329.6, 440)) * 0.18
    return boom * 0.9 + burst + stab


def whoosh(dur=0.45):
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = t / dur
    noise = rng.standard_normal(n)
    hi = noise - lowpass(noise, 0.15)
    shape = np.sin(np.pi * k) ** 2
    return hi * shape * 0.35


def chime():
    out = np.zeros(int(0.9 * SR))
    for i, f in enumerate((659.3, 987.8, 1318.5)):  # rising "news" notes
        s = tone(f, 0.6, r=0.18, harm=(1, 0.3, 0.1)) * 0.22
        o = int(i * 0.09 * SR)
        out[o:o + len(s)] += s[: len(out) - o]
    return out


def music_bed(dur, bpm=104):
    n = int(dur * SR)
    t = np.arange(n) / SR
    beat = 60 / bpm
    out = np.zeros(n)
    chords = [(220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (261.6, 329.6, 392.0), (196.0, 246.9, 293.7)]
    bar = beat * 4
    for b in range(int(dur / bar) + 1):
        ch = chords[b % 4]
        s0 = int(b * bar * SR)
        seg = np.arange(int(bar * SR)) / SR
        pad = sum(np.sin(2 * np.pi * f * seg) + 0.3 * np.sin(2 * np.pi * f * 2 * seg) for f in ch)
        pad *= np.minimum(1, seg / 0.3) * np.minimum(1, (bar - seg) / 0.3) * 0.05
        bass = np.sin(2 * np.pi * ch[0] / 2 * seg) * 0.12 * (0.6 + 0.4 * np.cos(2 * np.pi * seg / beat))
        e = min(n, s0 + len(seg))
        out[s0:e] += (pad + bass)[: e - s0]
    # pulse: kick on beats, ticks on 8ths, like a news ticker
    kick = np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-np.arange(int(0.25 * SR)) / SR * 30)) / SR) \
        * np.exp(-np.arange(int(0.25 * SR)) / SR * 14) * 0.35
    tick = rng.standard_normal(int(0.03 * SR)) * np.exp(-np.arange(int(0.03 * SR)) / SR * 150) * 0.06
    k = 0
    while k * beat / 2 < dur:
        p = int(k * beat / 2 * SR)
        src = kick if k % 2 == 0 else tick
        e = min(n, p + len(src))
        out[p:e] += src[: e - p]
        k += 1
    return out


def music_energy(dur, bpm=124):
    """Upbeat news-reel bed (2026-11-25, user: the old pad felt sleepy): four-on-the-floor kick, claps on 2 and 4,
    off-beat hats, driving 8th-note bass and a 16th-note pluck arpeggio over Am-F-C-G."""
    n = int(dur * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    s16 = beat / 4

    def put(clip, at, g=1.0):
        i = int(at * SR)
        if i < n:
            e = min(n, i + len(clip))
            out[i:e] += clip[: e - i] * g

    kn = int(0.22 * SR); kt = np.arange(kn) / SR
    kick = np.sin(2 * np.pi * np.cumsum(48 + 140 * np.exp(-kt * 35)) / SR) * np.exp(-kt * 16)
    cn = int(0.18 * SR); ct = np.arange(cn) / SR
    cnoise = rng.standard_normal(cn)
    clap = (cnoise - lowpass(cnoise, 0.25)) * (np.exp(-ct * 22) + 0.6 * np.exp(-np.abs(ct - 0.012) * 300)) * 0.5
    hn = int(0.05 * SR); ht = np.arange(hn) / SR
    hnoise = rng.standard_normal(hn)
    hat = (hnoise - lowpass(hnoise, 0.6)) * np.exp(-ht * 90) * 0.35
    prog = [(110.0, (220.0, 261.6, 329.6)), (87.31, (174.6, 220.0, 261.6)),
            (130.8, (261.6, 329.6, 392.0)), (98.0, (196.0, 246.9, 293.7))]
    bars = int(dur / (beat * 4)) + 1
    bass_cache, pluck_cache = {}, {}
    for b in range(bars):
        root, chord = prog[b % 4]
        t0 = b * beat * 4
        if root not in bass_cache:
            bt = np.arange(int(beat / 2 * SR)) / SR
            saw = sum(np.sin(2 * np.pi * root * k * bt) / k for k in range(1, 7))
            bass_cache[root] = saw * np.minimum(1, bt / 0.004) * np.exp(-bt * 7) * 0.22
        for q in range(4):
            put(kick, t0 + q * beat, 0.55)
            if q in (1, 3):
                put(clap, t0 + q * beat, 0.45)
            put(hat, t0 + q * beat + beat / 2, 0.5)
            put(hat, t0 + q * beat + beat / 4, 0.18)
            put(hat, t0 + q * beat + 3 * beat / 4, 0.18)
        for e8 in range(8):
            put(bass_cache[root], t0 + e8 * beat / 2)
        arp = [chord[0] * 2, chord[1] * 2, chord[2] * 2, chord[1] * 2]
        for k16 in range(16):
            f = arp[k16 % 4]
            if f not in pluck_cache:
                pluck_cache[f] = tone(f, 0.16, r=0.06, harm=(1, 0.45, 0.2)) * 0.07
            put(pluck_cache[f], t0 + k16 * s16, 1.0 if k16 % 4 == 0 else 0.7)
    return out


def music_from_file(path, dur):
    """A royalty-free track the user downloaded (e.g. YouTube Audio Library / Pixabay Music): looped and trimmed."""
    a = decode(Path(path) if Path(path).is_absolute() else HERE / path)
    if a.ndim > 1:
        a = a.mean(axis=1)
    n = int(dur * SR)
    reps = int(np.ceil(n / max(1, len(a))))
    return np.tile(a, reps)[:n]


def music_warm(dur, bpm=112):
    """Warm, lower bed (2026-11-26, user: the bright energy bed was 'disturbing'): soft sustained chords an
    octave down, a round sub bass, a gentle kick and barely-there hats. Same Am-F-C-G, steady but calm."""
    n = int(dur * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    bar = beat * 4

    def put(clip, at, g=1.0):
        i = int(at * SR)
        if 0 <= i < n:
            e = min(n, i + len(clip))
            out[i:e] += clip[: e - i] * g

    kn = int(0.30 * SR); kt = np.arange(kn) / SR
    kick = np.sin(2 * np.pi * np.cumsum(42 + 70 * np.exp(-kt * 22)) / SR) * np.exp(-kt * 9)
    hn = int(0.04 * SR); ht = np.arange(hn) / SR
    hnoise = rng.standard_normal(hn)
    hat = lowpass(hnoise - lowpass(hnoise, 0.5), 0.35) * np.exp(-ht * 120)
    prog = [(55.0, (110.0, 130.8, 164.8)), (43.65, (87.3, 110.0, 130.8)),
            (65.41, (130.8, 164.8, 196.0)), (49.0, (98.0, 123.5, 146.8))]
    bt = np.arange(int(bar * SR)) / SR
    env = np.minimum(1, bt / 0.6) * np.minimum(1, (bar - bt) / 0.5)          # slow swell in, soft release
    pads, basses = {}, {}
    for root, chord in prog:
        pads[root] = sum(sum(np.sin(2 * np.pi * f * k * (1 + d) * bt) / k ** 2 for k in (1, 2, 3))
                         for f in chord for d in (-0.003, 0.003)) * env * 0.045
        q = np.arange(int(beat * SR)) / SR
        basses[root] = (np.sin(2 * np.pi * root * q) + 0.25 * np.sin(4 * np.pi * root * q)) \
            * np.minimum(1, q / 0.01) * np.exp(-q * 3.5) * 0.30
    for b in range(int(dur / bar) + 1):
        root, _ = prog[b % 4]
        t0 = b * bar
        put(pads[root], t0)
        for q in range(4):
            put(basses[root], t0 + q * beat)
            put(kick, t0 + q * beat, 0.42 if q in (0, 2) else 0.28)
            put(hat, t0 + q * beat + beat / 2, 0.12)
    return out


def pick_music(dur):
    m = SCRIPT.get("music", {})
    if m.get("file"):
        bed = music_from_file(m["file"], dur)
    elif m.get("style", "calm") == "energy":
        bed = music_energy(dur, m.get("bpm", 124))
    elif m.get("style") == "warm":
        bed = music_warm(dur, m.get("bpm", 112))
    else:
        return music_bed(dur)
    ref = music_bed(min(dur, 8.0))                      # match the old bed's loudness, then apply the level
    rms = lambda x: float(np.sqrt(np.mean(x ** 2)) + 1e-9)
    return bed * (rms(ref) / rms(bed)) * float(m.get("level", 1.3))


def place(buf, clip, at):
    i = int(at * SR)
    if i < 0:  # sound starts before the video: keep only the part after 0 s
        clip, i = clip[-i:], 0
    if i >= len(buf) or len(clip) == 0:
        return
    e = min(len(buf), i + len(clip))
    buf[i:e] += clip[: e - i]


# ----------------------------------------------------------------------------
def main():
    full = OUT / "vo_full.mp3"
    gap, first = float(SCRIPT.get("gap", 0.45)), float(SCRIPT.get("lead_in", 1.4))  # gap: pause between stories
    if SCRIPT.get("voice_provider") == "elevenlabs":
        clips = load_eleven_voice()
        total = first + sum(len(c) / SR for c, _ in clips) + gap * (len(clips) - 1) + 1.3
        print(f"ElevenLabs voice -> {total:.1f}s")
        if total > MAX_LEN:
            print("WARNING: longer than 2:30 - shorten the script or raise elevenlabs.settings.speed")
        rate_pct = None
    elif SCRIPT.get("voice_provider") == "local":
        tempo = SCRIPT.get("local_voice", {}).get("tempo", 1.08)
        while True:
            clips = load_local_voice(tempo)
            total = first + sum(len(c) / SR for c, _ in clips) + gap * (len(clips) - 1) + 1.3
            print(f"local voice tempo {tempo:.2f} -> {total:.1f}s")
            if total <= MAX_LEN or tempo >= 1.3:
                break
            tempo = min(1.3, tempo * (total - 3) / (MAX_LEN - 3))
        rate_pct = None
    elif SCRIPT.get("voice_provider") == "vidiq" and full.exists():
        tempo = 1.0
        while True:
            clips = split_full_voice(full, tempo)
            total = first + sum(len(c) / SR for c, _ in clips) + gap * (len(clips) - 1) + 1.3
            print(f"tempo {tempo:.2f} -> {total:.1f}s")
            if total <= MAX_LEN or tempo >= 1.25:
                break
            tempo = min(1.25, tempo * (total - 3) / (MAX_LEN - 3))
        rate_pct = None
    else:
        rate_pct = int(SCRIPT.get("rate", "+10%").strip("%+"))
    while rate_pct is not None:
        clips = make_voice(f"+{rate_pct}%")
        total = first + sum(len(a) / SR for a, _ in clips) + gap * (len(clips) - 1) + 1.3
        print(f"rate +{rate_pct}% -> {total:.1f}s")
        if total <= MAX_LEN or rate_pct >= 30:
            break
        rate_pct += 5

    dur = total
    n = int(dur * SR)
    voice = np.zeros(n)
    fx = np.zeros(n)
    segs, t = [], first
    for s, (a, words) in zip(SEGS, clips):
        d = len(a) / SR
        place(voice, a, t)
        seg = {"id": s["id"], "start": round(t, 3), "end": round(t + d, 3)}
        # caption chunks: spread the on-screen words over the real spoken word times
        cw = s["cap"].split()
        chunks, cur = [], []
        for w in cw:
            cur.append(w)
            if len(cur) >= 4 or w[-1] in ".,?!:":
                chunks.append(" ".join(cur)); cur = []
        if cur:
            chunks.append(" ".join(cur))
        total_c = sum(len(c) for c in chunks)
        sent = words.get("sentences") if isinstance(words, dict) else None
        csents = [x for x in __import__("re").split(r"(?<=[.!?])\s+", s["cap"].strip()) if x]
        if sent and len(sent) == len(csents):
            # exact per-sentence sync: chunk each caption sentence inside its spoken span
            out = []
            for (s0, s1), cs in zip(sent, csents):
                ws, cur, ch = cs.split(), [], []
                for w in ws:
                    cur.append(w)
                    if len(cur) >= 4 or w[-1] in ",:":
                        ch.append(" ".join(cur)); cur = []
                if cur:
                    ch.append(" ".join(cur))
                tot, acc = sum(len(c) for c in ch), 0
                for c in ch:
                    a0 = s0 + (s1 - s0) * acc / tot
                    acc += len(c)
                    out.append({"text": c, "start": round(t + a0, 3), "end": round(t + s0 + (s1 - s0) * acc / tot, 3)})
            seg["chunks"] = out
            segs.append(seg)
            place(fx, whoosh(), t - 0.45)
            if s["id"] == "hook":
                place(fx, riser(1.0), t - 1.35)
                place(fx, impact(), t - 0.35)
            else:
                place(fx, chime() * (1.3 if s["id"] == "outro" else 1.0), t - 0.3)
            t += d + gap
            continue
        if words:
            wt = np.array([w0 for w0, _ in words] + [d])
            fr = np.linspace(0, 1, len(wt))
            tmap = lambda f: float(np.interp(f, fr, wt))
        else:
            tmap = lambda f: f * d
        acc, out = 0, []
        for c in chunks:
            st = tmap(acc / total_c)
            acc += len(c)
            out.append({"text": c, "start": round(t + st, 3), "end": round(t + tmap(acc / total_c), 3)})
        seg["chunks"] = out
        segs.append(seg)
        # sounds on each card change
        place(fx, whoosh(), t - 0.45)
        if s["id"] == "hook":
            place(fx, riser(1.0), t - 1.35)
            place(fx, impact(), t - 0.35)
        else:
            place(fx, chime() * (1.3 if s["id"] == "outro" else 1.0), t - 0.3)
        t += d + gap
    place(fx, impact() * 0.6, segs[-1]["end"] + 0.1)  # closing hit

    bed = pick_music(dur)   # script "music": {"style": "energy"|"calm", "bpm", "level"} or {"file": ...}
    # duck the music under the voice
    v_env = np.convolve(np.abs(voice), np.ones(int(0.12 * SR)) / int(0.12 * SR), mode="same")
    duck = 1 - 0.6 * np.clip(v_env * 12, 0, 1)
    fade = np.minimum(1, np.arange(n) / (0.5 * SR)) * np.minimum(1, (n - np.arange(n)) / (1.0 * SR))
    mix = voice * 1.0 + fx * 0.8 + bed * duck * fade * 0.9
    mix = mix / max(1e-6, np.max(np.abs(mix))) * 0.92
    pcm = (np.repeat(mix[:, None], 2, axis=1) * 32767).astype(np.int16)
    raw = OUT / "mix_raw.wav"
    with wave.open(str(raw), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    # bring the whole mix to YouTube's loudness (-14 LUFS) with a true-peak limit
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-i", str(raw),
                    "-af", "alimiter=limit=0.89:attack=3:release=50,loudnorm=I=-14:TP=-1.0:LRA=9",
                    "-ar", str(SR), "-ac", "2", str(OUT / "mix.wav")], check=True)

    # mouth envelope per video frame
    hop = SR // FPS
    fr = [np.sqrt(np.mean(voice[i:i + hop] ** 2)) for i in range(0, n, hop)]
    fr = np.array(fr)
    fr = fr / max(1e-6, np.percentile(fr[fr > 0], 95) if np.any(fr > 0) else 1)
    np.save(OUT / "envelope.npy", np.clip(fr, 0, 1))
    (OUT / "timeline.json").write_text(json.dumps({"duration": round(dur, 3), "segments": segs}, indent=1),
                                       encoding="utf-8")
    print(f"mix.wav {dur:.1f}s, {len(segs)} segments")


if __name__ == "__main__":
    if "--voices" in sys.argv:
        list_eleven_voices()
    else:
        main()

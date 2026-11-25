"""Broadcast-style polish for a voice clip: cleaner lows, more presence/clarity,
compression for a loud, even, punchy delivery, a slightly faster pace, and loudness
matched to YouTube's level.

python voice_polish.py in.wav out.wav [tempo]
"""
import subprocess, sys
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()

CHAIN = (
    "highpass=f=85,"                                  # remove rumble
    "equalizer=f=250:t=q:w=1.2:g=-2,"                 # less boxiness
    "equalizer=f=3200:t=q:w=1.0:g=4,"                 # presence: clearer consonants
    "equalizer=f=9000:t=q:w=1.0:g=2,"                 # a bit of air
    "acompressor=threshold=-20dB:ratio=4:attack=5:release=60:makeup=4,"  # punch + evenness
    "silenceremove=stop_periods=-1:stop_duration=0.35:stop_threshold=-42dB,"  # trim long gaps
    "atempo={tempo},"
    "loudnorm=I=-14:TP=-1.5:LRA=7"                    # YouTube-level loudness
)


def polish(src, dst, tempo=1.08):
    subprocess.run([FF, "-v", "error", "-y", "-i", str(src), "-af", CHAIN.format(tempo=tempo),
                    "-ar", "44100", str(dst)], check=True)


def loudness(path):
    r = subprocess.run([FF, "-v", "info", "-i", str(path), "-af", "loudnorm=print_format=summary", "-f", "null", "-"],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Input Integrated" in line:
            return line.split(":")[1].strip()
    return "?"


if __name__ == "__main__":
    polish(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 1.08)

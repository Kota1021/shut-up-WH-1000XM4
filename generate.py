#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Cathedral pipe-organ notification sounds for Sony WH-1000XM4 voice-guidance slots.

Synthesizes every sound from scratch (additive organ pipes + synthetic cathedral reverb).
No Sony audio is used or needed. Output: 48 kHz mono 64 kbps MP3, the same format as the
headset's own prompts.

Usage:
    uv run generate.py                 # writes sounds/*.mp3 and sounds/preview.m4a
    uv run generate.py --slots out/    # also writes out/prompt_NN.mp3, one per headset slot

Requires ffmpeg (with libmp3lame) on PATH.
"""
import argparse, shutil, subprocess
from pathlib import Path
import numpy as np

SR = 48000
PEAK_DB = -7.0
MAX_LEN = 2.0           # seconds, including reverb tail
FADE = 0.7              # gentle fade over the last part of the tail
REVERB_RT60, REVERB_WET, PREDELAY = 2.4, 0.55, 0.022

# Organ stops as (footage ratio to 8', level). 16' gives the weight, 4'/2 2/3'/2' the brilliance.
PRINCIPAL = [(0.5, 0.55), (1.0, 1.0), (2.0, 0.5), (3.0, 0.22), (4.0, 0.18), (6.0, 0.06), (8.0, 0.05)]
FLUTE = [(1.0, 0.5), (2.0, 1.0), (4.0, 0.35)]
DIAPASON = [(0.5, 0.35), (1.0, 1.0), (2.0, 0.3)]


def hz(name):
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    semis = names[name[0]] + (1 if "#" in name else 0) + 12 * (int(name[-1]) - 4)
    return 440.0 * 2 ** (semis / 12)


def pipe(freq, dur, stops=PRINCIPAL, attack=0.045, release=0.18, chiff=0.06):
    """One organ note: additive pipe ranks + celeste detune, wind 'chiff', slow speech."""
    n = int(SR * (dur + release))
    t = np.arange(n) / SR
    x = np.zeros(n)
    rng = np.random.default_rng(int(freq))
    for ratio, level in stops:
        f = freq * ratio
        if f > SR / 2.2 or f < 45:
            continue
        ph = rng.uniform(0, 2 * np.pi)
        x += level * np.sin(2 * np.pi * f * t + ph)
        x += 0.35 * level * np.sin(2 * np.pi * f * 1.0035 * t + ph * 1.7)  # celeste rank: slow beating, width
    env = np.clip(t / attack, 0, 1) ** 1.5
    env *= np.where(t < dur, 1.0, np.exp(-(t - dur) / (release / 4)))
    x *= env * (1 + 0.025 * np.sin(2 * np.pi * 5.2 * t))  # gentle tremulant
    noise = rng.standard_normal(n) * np.exp(-t / 0.018) * chiff  # pipe speaking transient
    return x + lowpass(noise, np.full(n, freq * 6))


def lowpass(x, cutoff):
    """Two-pole time-varying lowpass; cutoff is per-sample Hz."""
    a = 1 - np.exp(-2 * np.pi * np.minimum(cutoff, SR * 0.45) / SR)
    for _ in range(2):
        y = np.empty_like(x)
        acc = 0.0
        for i in range(len(x)):
            acc += a[i] * (x[i] - acc)
            y[i] = acc
        x = y
    return x


def place(events, length):
    out = np.zeros(int(SR * length) + SR)
    for start, sig in events:
        s = int(SR * start)
        out[s:s + len(sig)] += sig
    return out


def cathedral(x):
    rng = np.random.default_rng(7)
    n = int(SR * REVERB_RT60)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-6.9 * t / REVERB_RT60)
    ir = lowpass(ir, 6000 * np.exp(-t * 1.2) + 800)  # stone absorbs highs over time
    for d, g in ((0.031, 0.5), (0.047, 0.42), (0.063, 0.36), (0.089, 0.3), (0.113, 0.24), (0.151, 0.2)):
        ir[int(SR * d)] += g * 20  # distant walls and vaulting
    ir[:int(SR * PREDELAY)] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x) + n]
    wet *= np.max(np.abs(x)) / (np.max(np.abs(wet)) or 1)
    return np.pad(x, (0, n)) * (1 - REVERB_WET * 0.6) + wet * REVERB_WET


def finish(x):
    x = cathedral(x)[:int(SR * MAX_LEN)]
    f = int(SR * FADE)
    x[-f:] *= np.cos(np.linspace(0, np.pi / 2, f)) ** 2
    return x


def arpeggio(notes, step=0.07, hold=1.1, stops=PRINCIPAL):
    """Notes enter one by one and keep sounding together as a chord."""
    events = [(i * step, pipe(hz(nm), hold - i * step, stops)) for i, nm in enumerate(notes)]
    return finish(place(events, MAX_LEN))


def gesture(first, second, step=0.2, first_hold=0.75, second_hold=0.7, stops=PRINCIPAL):
    """One chord, then a second voicing enters above (rise) or below (fall) it."""
    events = [(0, pipe(hz(nm), first_hold, stops)) for nm in first]
    events += [(step, pipe(hz(nm), second_hold, stops)) for nm in second]
    return finish(place(events, MAX_LEN))


def swell(notes, cut_from, cut_to, dur=0.9, stops=PRINCIPAL):
    """Chord seen through a swell box whose shutters close (dark) or open (bright)."""
    x = place([(0, pipe(hz(nm), dur, stops, attack=0.06)) for nm in notes], MAX_LEN)
    t = np.arange(len(x)) / SR
    k = np.clip(t / dur, 0, 1) ** 0.7
    return finish(lowpass(x, cut_from * (cut_to / cut_from) ** k))


def silence(dur=0.12):
    return np.zeros(int(SR * dur))


# C major add9, spread over four octaves: rises and blooms / sinks back to the low C
power_on = arpeggio(["C2", "G2", "C3", "G3", "C4", "E4", "G4", "D5"])
power_off = arpeggio(["D5", "G4", "E4", "C4", "G3", "C3", "G2", "C2"])
# G major: low voicing, then the upper voicing joins above it / the upper voicing fades into the low one
connected = gesture(["G2", "D3", "G3"], ["B3", "D4", "G4", "B4"])
disconnected = gesture(["B3", "D4", "G4", "B4"], ["G2", "D3", "G3"], first_hold=0.25)
pairing = finish(place([(i * 0.2, pipe(hz(nm), 0.12, release=0.1))
                        for i in range(3) for nm in ("D3", "A3", "D4", "F#4")], MAX_LEN))
nc_on = swell(["C2", "G2", "C3", "E3", "G3", "C4"], 7000, 220)              # low, closes in: the world shuts out
ambient_on = swell(["G4", "B4", "D5", "G5", "D6"], 500, 9000, stops=FLUTE)  # high, opens up: the room comes in
asc_off = finish(place([(0, pipe(hz(nm), 0.4, DIAPASON)) for nm in ("D3", "A3", "D4")], MAX_LEN))  # plain open fifth

SOUNDS = {
    "power_on": power_on,
    "power_off": power_off,
    "pairing": pairing,
    "connected": connected,
    "disconnected": disconnected,
    "noise_canceling_on": nc_on,
    "ambient_sound_on": ambient_on,
    "ambient_sound_control_off": asc_off,
    "silence": silence(),
}

# Headset prompt slot -> sound. Slot numbers are the order of entries in the WH-1000XM4
# voice-guidance image; slots not listed keep their original voice.
SLOTS = {
    0: "power_on",                   # "Power on"
    1: "power_off",                  # "Power off"
    2: "pairing",                    # "Bluetooth pairing"
    3: "connected",                  # "Bluetooth connected"
    4: "disconnected",               # "Bluetooth disconnected"
    6: "noise_canceling_on",         # "Noise canceling"
    7: "ambient_sound_control_off",  # "Ambient Sound Control off"
    8: "ambient_sound_on",           # "Ambient sound"
    47: "connected",                 # "Bluetooth device 1 connected"
    48: "disconnected",              # "Bluetooth device 1 disconnected"
    49: "connected",                 # "Bluetooth device 2 connected"
    50: "disconnected",              # "Bluetooth device 2 disconnected"
    51: "connected",                 # "Bluetooth device 1 replaced"
    52: "connected",                 # "Bluetooth device 2 replaced"
    53: "connected",                 # "Bluetooth second device connected"
    # "Battery about XX%" right after power on -> silent
    16: "silence", 17: "silence", 18: "silence", 28: "silence", 29: "silence",
    30: "silence", 31: "silence", 32: "silence", 33: "silence",
}
PREVIEW = ["power_on", "connected", "disconnected", "pairing", "noise_canceling_on",
           "ambient_sound_on", "ambient_sound_control_off", "power_off"]


def pcm16(x):
    peak = np.max(np.abs(x)) or 1.0
    return (x / peak * 10 ** (PEAK_DB / 20) * 32767).astype("<i2").tobytes()


def ffmpeg(x, path, *codec):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    *codec, str(path)], input=pcm16(x), check=True)


def write_mp3(x, path):
    ffmpeg(x, path, "-c:a", "libmp3lame", "-b:a", "64k", "-ar", str(SR), "-ac", "1",
           "-write_xing", "0", "-id3v2_version", "0")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "sounds")
    ap.add_argument("--slots", type=Path, help="also write prompt_NN.mp3 per headset slot here")
    a = ap.parse_args()

    a.out.mkdir(parents=True, exist_ok=True)
    for name, x in SOUNDS.items():
        if name != "silence":
            write_mp3(x, a.out / f"{name}.mp3")
    gap = np.zeros(int(SR * 0.45))
    seq = np.concatenate([np.concatenate([SOUNDS[n] / np.max(np.abs(SOUNDS[n])), gap]) for n in PREVIEW])
    ffmpeg(seq, a.out / "preview.m4a", "-c:a", "aac", "-b:a", "128k")
    print(f"wrote {len(SOUNDS) - 1} sounds + preview.m4a to {a.out}")

    if a.slots:
        a.slots.mkdir(parents=True, exist_ok=True)
        for slot, name in sorted(SLOTS.items()):
            src = a.out / f"{name}.mp3"
            if name == "silence":
                write_mp3(SOUNDS["silence"], a.slots / f"prompt_{slot:02d}.mp3")
            else:
                shutil.copyfile(src, a.slots / f"prompt_{slot:02d}.mp3")
        print(f"wrote {len(SLOTS)} slot files to {a.slots}")


if __name__ == "__main__":
    main()

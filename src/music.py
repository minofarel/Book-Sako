"""
Original desert-blues / touareg-inspired instrumental for the Sako teaser.
No existing music. Everything synthesised in numpy. ~102 BPM, A minor
pentatonic, dramatic arc timed to the storyboard.

Usage:  python3 src/music.py out/sako_music.wav [duration_seconds]
"""
import sys
import numpy as np

SR = 44100
BPM = 102.0
BEAT = 60.0 / BPM
RNG = np.random.default_rng(20240501)

# A minor pentatonic
A2, C3, D3, E3, G3, A3, C4, D4, E4 = 110.0, 130.81, 146.83, 164.81, 196.0, 220.0, 261.63, 293.66, 329.63
SCALE = [A2, C3, D3, E3, G3, A3, C4, D4, E4]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def env(n, a=0.005, d=None, sustain=0.0, r=None, curve=2.0):
    """Simple AD/ADSR-ish envelope of length n samples."""
    e = np.ones(n, dtype=np.float32)
    na = max(1, int(a * SR))
    e[:na] = np.linspace(0, 1, na)
    if d is not None:
        nd = int(d * SR)
        tail = n - na
        idx = np.arange(tail)
        e[na:] = (sustain + (1 - sustain) * np.exp(-idx / max(1, nd)))
    return e


def fft_band(x, lo, hi, gain_out=1.0):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    m = ((f >= lo) & (f <= hi)).astype(np.float32)
    # soften edges
    m = np.convolve(m, np.ones(5) / 5, mode="same")
    return np.fft.irfft(X * m, n=n).astype(np.float32) * gain_out


def add(buf, sig, t, pan=0.5, gain=1.0):
    i0 = int(t * SR)
    n = len(sig)
    if i0 < 0:
        sig = sig[-i0:]
        n = len(sig)
        i0 = 0
    i1 = min(len(buf), i0 + n)
    if i1 <= i0:
        return
    s = sig[:i1 - i0] * gain
    buf[i0:i1, 0] += s * np.sqrt(1 - pan)
    buf[i0:i1, 1] += s * np.sqrt(pan)


# --------------------------------------------------------------------------
# instruments
# --------------------------------------------------------------------------
def ks_pluck(freq, dur, damp=0.996, drive=1.6, amp=0.5):
    """Karplus-Strong plucked string, block-vectorised."""
    N = max(2, int(SR / freq))
    total = int(dur * SR)
    cur = RNG.uniform(-1, 1, N).astype(np.float32)
    out = np.empty(N * (total // N + 1), dtype=np.float32)
    pos = 0
    nb = total // N + 1
    for _ in range(nb):
        out[pos:pos + N] = cur
        prev = np.empty_like(cur)
        prev[1:] = cur[:-1]
        prev[0] = cur[-1]
        cur = damp * 0.5 * (cur + prev)
        pos += N
    out = out[:total]
    out = np.tanh(out * drive)
    out *= env(total, a=0.002, d=dur * 0.5, sustain=0.05)
    return out * amp


def bass(freq, dur, amp=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * 2 * freq * t)
    x = np.tanh(x * 1.4)
    x *= env(n, a=0.004, d=dur * 0.4, sustain=0.15)
    return x.astype(np.float32) * amp


def calebasse(amp=0.7):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    f = 95 * np.exp(-t / 0.05) + 52
    body = np.sin(2 * np.pi * np.cumsum(f) / SR)
    click = RNG.uniform(-1, 1, n) * np.exp(-t / 0.004)
    x = body * np.exp(-t / 0.09) + click * 0.5
    return x.astype(np.float32) * amp


def djembe(slap=False, amp=0.6):
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    noise = RNG.uniform(-1, 1, n)
    if slap:
        x = fft_band(noise, 900, 2200) * np.exp(-t / 0.03)
    else:
        x = fft_band(noise, 250, 520) * np.exp(-t / 0.06)
        x += np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05) * 0.5
    return x.astype(np.float32) * amp


def shaker(amp=0.25):
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    x = fft_band(RNG.uniform(-1, 1, n), 5000, 12000) * np.exp(-t / 0.02)
    return x.astype(np.float32) * amp


def clap(amp=0.5):
    n = int(0.13 * SR)
    out = np.zeros(n, dtype=np.float32)
    for k in range(3):
        d = int(k * 0.008 * SR)
        b = RNG.uniform(-1, 1, n - d)
        tt = np.arange(len(b)) / SR
        out[d:] += fft_band(b, 1100, 2600) * np.exp(-tt / 0.02)
    return out * amp


def pad_chord(freqs, dur, amp=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n, dtype=np.float32)
    for f in freqs:
        saw = 2 * (t * f - np.floor(0.5 + t * f))
        x += saw
    x /= len(freqs)
    # slowly opening lowpass (approx via fft on whole, fixed) + swell
    x = fft_band(x, 40, 2600)
    swell = np.clip(t / (dur * 0.5), 0, 1) * np.exp(-np.maximum(0, t - dur * 0.6) / (dur * 0.3))
    return (x * swell).astype(np.float32) * amp


def drone(freq, dur, amp=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 1.5 * t + 0.3)
    x += 0.2 * np.sin(2 * np.pi * freq * 0.5 * t)
    lfo = 1 + 0.06 * np.sin(2 * np.pi * 0.2 * t)
    fade = np.clip(t / 0.5, 0, 1) * np.clip((dur - t) / 0.8, 0, 1)
    return (x * lfo * fade).astype(np.float32) * amp


# --------------------------------------------------------------------------
# SFX
# --------------------------------------------------------------------------
def whoosh(dur=0.6, amp=0.5):
    n = int(dur * SR)
    noise = RNG.uniform(-1, 1, n)
    out = np.zeros(n, dtype=np.float32)
    win = 1024
    for s in range(0, n, win):
        seg = noise[s:s + win]
        tt = (s / n)
        c = 300 + (4200 - 300) * np.sin(np.pi * tt) if tt < 0.6 else 800 + 400 * (1 - tt)
        out[s:s + len(seg)] = fft_band(seg, max(120, c - 500), c + 700)
    t = np.arange(n) / SR
    out *= np.sin(np.pi * t / dur) ** 0.7
    return out * amp


def boom(amp=0.9):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    f = 58 * np.exp(-t / 0.12) + 30
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.18)
    kick = np.sin(2 * np.pi * 120 * np.exp(-t / 0.02) * t) * np.exp(-t / 0.04)
    x = np.tanh((sub + 0.6 * kick) * 1.2)
    return x.astype(np.float32) * amp


def ding(amp=0.4):
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n, dtype=np.float32)
    for p, a in ((1320, 1.0), (1760, 0.6), (2640, 0.35)):
        x += a * np.sin(2 * np.pi * p * t)
    x *= np.exp(-t / 0.35)
    return x.astype(np.float32) * amp / 1.95


def tick(amp=0.3):
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    f = RNG.uniform(2600, 3400)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.008)
    return x.astype(np.float32) * amp


def laser(dur=0.5, amp=0.15):
    n = int(dur * SR)
    t = np.arange(n) / SR
    base = np.diff(RNG.uniform(-1, 1, n + 1))
    mod = 0.5 + 0.5 * np.sin(2 * np.pi * 30 * t + 3 * np.sin(2 * np.pi * 7 * t))
    x = fft_band(base * mod, 1500, 6000)
    x *= np.sin(np.pi * t / dur) ** 0.5
    return x.astype(np.float32) * amp


def creak(dur=1.4, amp=0.28):
    """A 'grincement' — a slowly pitch-wobbling resonant scrape."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    base = np.diff(RNG.uniform(-1, 1, n + 1))
    f = 220 + 90 * np.sin(2 * np.pi * 1.3 * t) * (t / dur)
    out = np.zeros(n, dtype=np.float32)
    win = 2048
    for s in range(0, n, win):
        seg = base[s:s + win]
        c = float(f[min(s, n - 1)])
        out[s:s + len(seg)] = fft_band(seg, c - 120, c + 260)
    out *= np.sin(np.pi * t / dur) ** 0.6 * (0.6 + 0.4 * (t / dur))
    return out.astype(np.float32) * amp


def riser(dur=1.5, amp=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 55 * (2 ** (t / dur))          # 55 -> 110
    saw = 2 * (np.cumsum(f) / SR - np.floor(0.5 + np.cumsum(f) / SR))
    out = np.zeros(n, dtype=np.float32)
    win = 2048
    for s in range(0, n, win):
        seg = saw[s:s + win]
        tt = s / n
        out[s:s + len(seg)] = fft_band(seg, 40, 300 + 4000 * tt)
    out *= np.clip(t / (dur * 0.9), 0, 1) ** 1.5
    return out * amp


# --------------------------------------------------------------------------
# arrangement
# --------------------------------------------------------------------------
def build(dur):
    N = int(dur * SR)
    buf = np.zeros((N, 2), dtype=np.float32)

    # ---- 0-4s : mystery : drone + sparse guitar + laser + ticks ----------
    add(buf, drone(A2, 5.2), 0.0, 0.5, 0.9)
    for t, f in [(0.7, A3), (1.6, C4), (2.5, E3), (3.3, G3)]:
        add(buf, ks_pluck(f, 1.4, amp=0.42), t, 0.5 + RNG.uniform(-0.2, 0.2))
    add(buf, laser(2.7, amp=0.12), 0.3, 0.6)
    for t in np.arange(0.2, 3.0, 0.33):
        add(buf, tick(0.22), t + RNG.uniform(-0.03, 0.03), RNG.uniform(0.2, 0.8))
    add(buf, whoosh(0.7, 0.5), 2.7, 0.5)
    add(buf, boom(0.85), 3.0, 0.5)

    # ---- 4-9s : reveal : pad swell + rising guitar phrase + light pulse --
    add(buf, pad_chord([A2, C3, E3, A3], 5.4), 4.0, 0.5, 1.0)
    phrase = [(4.3, A3), (4.9, C4), (5.5, D4), (6.1, E4), (6.9, C4), (7.7, A3)]
    for t, f in phrase:
        add(buf, ks_pluck(f, 1.2, amp=0.4), t, 0.5)
    for t in np.arange(6.2, 9.0, BEAT):
        add(buf, calebasse(0.5), t, 0.45)
        add(buf, shaker(0.22), t + BEAT / 2, 0.6)
    add(buf, whoosh(0.6, 0.5), 7.2, 0.55)
    add(buf, boom(0.8), 7.53, 0.5)
    add(buf, ding(0.42), 8.2, 0.6)

    # ---- 9-19s : full groove --------------------------------------------
    roots = [A2, A2, G3, C3, D3, A2, G3, E3]     # progression per bar
    bar = 0
    for t in np.arange(9.0, 19.0, BEAT):
        beat_in_bar = int(round((t - 9.0) / BEAT)) % 4
        if beat_in_bar == 0:
            bar = int((t - 9.0) / (4 * BEAT)) % len(roots)
            add(buf, bass(roots[bar], BEAT * 1.6, 0.5), t, 0.5)
        add(buf, calebasse(0.62), t, 0.5)
        add(buf, djembe(slap=(beat_in_bar in (1, 3)), amp=0.4), t + BEAT / 2, 0.42)
        if beat_in_bar in (1, 3):
            add(buf, clap(0.4), t, 0.4)
        # swung shaker on offbeats
        for sub in (0.5, 1.0, 1.5):
            add(buf, shaker(0.2), t + sub * BEAT / 2 + (0.06 * BEAT if sub % 1 else 0), 0.6)
    # guitar riffs over the groove
    riff = [A3, C4, D4, C4, A3, G3, E3, G3, A3, D4, E4, D4, C4, A3]
    tt = 9.4
    for k, f in enumerate(riff * 2):
        if tt > 18.6:
            break
        add(buf, ks_pluck(f, 0.7, amp=0.34), tt, 0.4 + 0.2 * np.sin(k))
        tt += BEAT * (0.5 if k % 3 else 1.0)
    add(buf, ding(0.4), 12.47, 0.55)      # pill
    add(buf, ding(0.4), 17.8, 0.6)        # toast

    # ---- 19-22.2s : breaks on the flashes -------------------------------
    add(buf, riser(1.6, 0.35), 17.5, 0.5)
    flash_cuts = [19.0, 19.8, 20.53, 21.17, 21.7]
    for k, t in enumerate(flash_cuts):
        add(buf, boom(0.85 + 0.03 * k), t, 0.5)
        add(buf, djembe(slap=True, amp=0.5), t, 0.4)
        add(buf, ks_pluck(SCALE[(k * 2) % len(SCALE)], 0.5, amp=0.36), t, 0.5)
    add(buf, whoosh(0.5, 0.4), 21.7, 0.5)

    # ---- 22.2-23.4 : silence (only a low tail) --------------------------
    # (leave mostly empty; a soft sub swell under "Elle arrive")
    add(buf, drone(A2, 1.4, 0.12), 22.4, 0.5)
    add(buf, boom(0.8), 22.43, 0.5)       # punch on "Elle arrive."

    # ---- 23.4-29 : final groove + concluding chord ----------------------
    add(buf, riser(1.2, 0.3), 22.9, 0.5)
    add(buf, boom(0.9), 24.0, 0.5)        # logo hit
    for t in np.arange(24.0, 27.2, BEAT):
        b = int(round((t - 24.0) / BEAT)) % 4
        add(buf, calebasse(0.6), t, 0.5)
        add(buf, djembe(slap=(b in (1, 3)), amp=0.38), t + BEAT / 2, 0.42)
        add(buf, shaker(0.2), t + BEAT / 2, 0.6)
        if b == 0:
            add(buf, bass(A2, BEAT * 1.6, 0.45), t, 0.5)
    # concluding pentatonic strum, ringing out
    for k, f in enumerate([A2, E3, A3, C4, E4]):
        add(buf, ks_pluck(f, 4.0, damp=0.9975, amp=0.32), 24.0 + k * 0.05, 0.5)
    add(buf, pad_chord([A2, E3, A3, C4], 5.0, 0.2), 24.0, 0.5)
    for k, f in enumerate([A2, C4, E4, A3]):     # final resolve
        add(buf, ks_pluck(f, 4.5, damp=0.9978, amp=0.34), 27.4 + k * 0.04, 0.5)

    # ---- master ----------------------------------------------------------
    buf = np.tanh(buf * 1.05) * 0.93
    # global fade out
    fade_n = int(1.6 * SR)
    if N > fade_n:
        buf[N - fade_n:] *= np.linspace(1, 0, fade_n)[:, None]
    buf[:int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))[:, None]
    return buf


def build_pole(dur):
    """Soundtrack for the 1:1 pole-position spot (~22s), F1-inspired arc."""
    N = int(dur * SR)
    buf = np.zeros((N, 2), dtype=np.float32)

    # 0-3s : lockup + countdown 0:02 -> DÉPART
    add(buf, drone(A2, 3.4, 0.16), 0.0, 0.5)
    for t in (0.0, 1.0, 2.0):
        add(buf, ding(0.3), t, 0.5)
        add(buf, tick(0.35), t, 0.5)
    add(buf, riser(1.4, 0.4), 1.5, 0.5)
    add(buf, boom(0.95), 2.85, 0.5)          # DÉPART
    add(buf, whoosh(0.6, 0.55), 2.75, 0.5)

    # 3-6s : card on asphalt + sweep (engine-like groove)
    for t in np.arange(3.0, 6.0, BEAT):
        add(buf, calebasse(0.6), t, 0.5)
        add(buf, djembe(slap=False, amp=0.4), t + BEAT / 2, 0.42)
        add(buf, shaker(0.2), t + BEAT / 2, 0.6)
    add(buf, bass(A2, 1.4, 0.5), 3.0, 0.5)
    add(buf, whoosh(0.6, 0.4), 3.8, 0.55)    # silver sweep
    add(buf, ks_pluck(A3, 1.4, amp=0.36), 4.2, 0.5)
    add(buf, ks_pluck(E4, 1.2, amp=0.32), 5.1, 0.5)

    # 6-11s : trapdoor -> burst -> comet
    add(buf, creak(1.8, 0.3), 6.0, 0.5)
    add(buf, riser(2.2, 0.42), 6.6, 0.5)
    add(buf, boom(1.0), 8.8, 0.5)            # light burst
    add(buf, ding(0.5), 8.85, 0.5)
    add(buf, whoosh(0.8, 0.6), 9.2, 0.7)     # comet flies right (pan)
    add(buf, ks_pluck(A3, 2.0, amp=0.34), 8.9, 0.5)

    # 11-14s : tagline typed
    add(buf, pad_chord([A2, C3, E3, A3], 3.4, 0.2), 11.0, 0.5)
    tt = 11.0
    while tt < 13.4:
        add(buf, tick(0.28), tt, RNG.uniform(0.3, 0.7))
        tt += 0.11

    # 14-18s : diamond card + sweep + champagne
    for t in np.arange(14.0, 18.0, BEAT):
        add(buf, calebasse(0.6), t, 0.5)
        add(buf, djembe(slap=(int(round((t-14)/BEAT)) % 2 == 1), amp=0.4), t + BEAT / 2, 0.42)
        add(buf, shaker(0.2), t + BEAT / 2, 0.6)
    add(buf, bass(A2, 1.4, 0.5), 14.0, 0.5)
    add(buf, whoosh(0.6, 0.45), 14.3, 0.5)
    add(buf, ding(0.45), 15.0, 0.55)
    add(buf, ks_pluck(C4, 1.5, amp=0.34), 15.2, 0.5)

    # 18-22s : outro logo reveal + resolve
    add(buf, whoosh(0.7, 0.4), 18.0, 0.5)
    add(buf, ding(0.5), 18.2, 0.55)
    add(buf, boom(0.85), 18.1, 0.5)
    for k, f in enumerate([A2, E3, A3, C4, E4]):
        add(buf, ks_pluck(f, 4.0, damp=0.9977, amp=0.33), 18.3 + k * 0.05, 0.5)
    add(buf, pad_chord([A2, E3, A3, C4], 4.0, 0.2), 18.3, 0.5)

    buf = np.tanh(buf * 1.05) * 0.93
    fade_n = int(1.6 * SR)
    if N > fade_n:
        buf[N - fade_n:] *= np.linspace(1, 0, fade_n)[:, None]
    buf[:int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))[:, None]
    return buf


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "out/sako_music.wav"
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 29.1
    mode = sys.argv[3] if len(sys.argv) > 3 else "main"
    buf = build_pole(dur) if mode == "pole" else build(dur)
    peak = np.max(np.abs(buf))
    print(f"peak {peak:.3f}  len {len(buf)/SR:.2f}s")
    data = np.clip(buf, -1, 1)
    data = (data * 32767).astype(np.int16)
    import wave
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("wrote", out)


if __name__ == "__main__":
    main()

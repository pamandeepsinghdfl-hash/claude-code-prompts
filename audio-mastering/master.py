#!/usr/bin/env python3
"""
master.py - transparent, streaming-ready mastering chain.

Signal flow (in order):
  decode -> headroom trim -> EQ -> de-ess -> multiband compression
  -> harmonic saturation -> M/S widening (+ bass mono) -> glue compression
  -> LUFS normalization -> true-peak limiter -> dither -> encode

Design intent: enhancement + loudness with the artistic intent intact.
Everything is conservative and phase-aware. No pitch/tempo/structure changes.
This is deterministic DSP, not "mastering by ear" - tune the numbers to taste.

Usage:
  python3 master.py input.wav output.wav [--target-lufs -14] [--tp -1.0]
                    [--style modern|warm|loud|transparent] [--width 1.15]
                    [--no-encode]

Outputs:
  <output>.wav           24-bit master
  <output>.mp3           320 kbps (streaming/portable)  [unless --no-encode]
  <output>.m4a           256 kbps AAC                    [unless --no-encode]
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal
from scipy.ndimage import minimum_filter1d

try:
    import pyloudnorm as pyln
except Exception:  # pragma: no cover
    pyln = None


# ----------------------------------------------------------------------------
# I/O (ffmpeg decodes anything; soundfile handles the float WAV interchange)
# ----------------------------------------------------------------------------
def decode(path):
    """Decode any input to float64 stereo at native sample rate via ffmpeg."""
    ff = shutil.which("ffmpeg")
    if path.lower().endswith((".wav", ".flac", ".aiff", ".aif")) or not ff:
        x, fs = sf.read(path, always_2d=True, dtype="float64")
    else:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        subprocess.run(
            [ff, "-y", "-i", path, "-c:a", "pcm_f32le", tmp_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        x, fs = sf.read(tmp_path, always_2d=True, dtype="float64")
        Path(tmp_path).unlink(missing_ok=True)
    if x.shape[1] == 1:                       # mono -> dual mono
        x = np.repeat(x, 2, axis=1)
    return x, fs


def encode_deliverables(wav_path):
    ff = shutil.which("ffmpeg")
    if not ff:
        return []
    base = wav_path.rsplit(".", 1)[0]
    made = []
    for ext, args in (
        ("mp3", ["-c:a", "libmp3lame", "-b:a", "320k"]),
        ("m4a", ["-c:a", "aac", "-b:a", "256k"]),
    ):
        out = f"{base}.{ext}"
        try:
            subprocess.run([ff, "-y", "-i", wav_path, *args, out],
                           check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            made.append(out)
        except Exception:
            pass
    return made


# ----------------------------------------------------------------------------
# Filters (RBJ Audio-EQ-Cookbook biquads + Linkwitz-Riley crossovers)
# ----------------------------------------------------------------------------
def rbj(kind, fs, f0, Q=0.707, gain_db=0.0):
    """Return a single second-order section (sos row) for an RBJ biquad."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / fs
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * Q)
    if kind == "lowshelf":
        b0 = A * ((A + 1) - (A - 1) * cw + 2 * np.sqrt(A) * alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cw)
        b2 = A * ((A + 1) - (A - 1) * cw - 2 * np.sqrt(A) * alpha)
        a0 = (A + 1) + (A - 1) * cw + 2 * np.sqrt(A) * alpha
        a1 = -2 * ((A - 1) + (A + 1) * cw)
        a2 = (A + 1) + (A - 1) * cw - 2 * np.sqrt(A) * alpha
    elif kind == "highshelf":
        b0 = A * ((A + 1) + (A - 1) * cw + 2 * np.sqrt(A) * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cw)
        b2 = A * ((A + 1) + (A - 1) * cw - 2 * np.sqrt(A) * alpha)
        a0 = (A + 1) - (A - 1) * cw + 2 * np.sqrt(A) * alpha
        a1 = 2 * ((A - 1) - (A + 1) * cw)
        a2 = (A + 1) - (A - 1) * cw - 2 * np.sqrt(A) * alpha
    elif kind == "peak":
        b0 = 1 + alpha * A
        b1 = -2 * cw
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cw
        a2 = 1 - alpha / A
    elif kind == "highpass":
        b0 = (1 + cw) / 2
        b1 = -(1 + cw)
        b2 = (1 + cw) / 2
        a0 = 1 + alpha
        a1 = -2 * cw
        a2 = 1 - alpha
    else:
        raise ValueError(kind)
    return np.array([b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0])


def apply_sos(x, sos_rows):
    sos = np.atleast_2d(sos_rows)
    return signal.sosfilt(sos, x, axis=0)


def lr4(x, fs, fc, mode):
    """Linkwitz-Riley 4th-order (Butterworth-2 applied twice) low/high pass."""
    sos = signal.butter(2, fc / (fs / 2), btype=mode, output="sos")
    return signal.sosfilt(sos, signal.sosfilt(sos, x, axis=0), axis=0)


def split_3way(x, fs, lo_xover, hi_xover):
    low = lr4(x, fs, lo_xover, "low")
    rest = lr4(x, fs, lo_xover, "high")
    mid = lr4(rest, fs, hi_xover, "low")
    high = lr4(rest, fs, hi_xover, "high")
    return low, mid, high


# ----------------------------------------------------------------------------
# Dynamics
# ----------------------------------------------------------------------------
def _onepole(x, tau_ms, fs):
    """Vectorized one-pole smoother (used for level detection)."""
    a = np.exp(-1.0 / (max(tau_ms, 1e-3) * 1e-3 * fs))
    return signal.lfilter([1 - a], [1, -a], x, axis=0)


def compress(x, fs, thr_db, ratio, attack_ms, release_ms, knee_db=6.0, makeup_db=0.0):
    """
    Stereo-linked feed-forward compressor. Detection uses an attack/release
    smoothed peak envelope (vectorized one-poles) so transients are preserved.
    Soft knee for transparent onset.
    """
    det = np.max(np.abs(x), axis=1, keepdims=True)            # link channels
    fast = _onepole(det, attack_ms, fs)
    env = _onepole(np.maximum(det, fast), release_ms, fs)
    env_db = 20 * np.log10(np.maximum(env, 1e-9))

    over = env_db - thr_db
    gr = np.zeros_like(over)
    knee = knee_db
    in_knee = (over > -knee / 2) & (over < knee / 2)
    above = over >= knee / 2
    gr[in_knee] = (1 / ratio - 1) * (over[in_knee] + knee / 2) ** 2 / (2 * knee)
    gr[above] = (over[above]) * (1 / ratio - 1)
    gain = 10 ** ((gr + makeup_db) / 20.0)
    return x * gain


def saturate(x, drive=1.6, mix=0.18):
    """Subtle analog-style warmth: parallel tanh waveshaper, gain-compensated."""
    wet = np.tanh(x * drive) / np.tanh(drive)
    return (1 - mix) * x + mix * wet


def ms_widen(x, width=1.15, bass_mono_hz=120.0, fs=44100):
    """Mid/side widening with low end kept mono for a tight, phase-safe bottom."""
    mid = (x[:, 0] + x[:, 1]) * 0.5
    side = (x[:, 0] - x[:, 1]) * 0.5
    if bass_mono_hz > 0:                                       # remove lows from side
        sos = signal.butter(2, bass_mono_hz / (fs / 2), btype="high", output="sos")
        side = signal.sosfilt(sos, side)
    side *= width
    return np.stack([mid + side, mid - side], axis=1)


# ----------------------------------------------------------------------------
# Loudness + limiting
# ----------------------------------------------------------------------------
def measure(x, fs):
    out = {}
    if pyln is not None:
        try:
            out["lufs"] = float(pyln.Meter(fs).integrated_loudness(x))
        except Exception:
            out["lufs"] = float("nan")
    peak = np.max(np.abs(x)) + 1e-12
    out["peak_db"] = 20 * np.log10(peak)
    up = signal.resample_poly(x, 4, 1, axis=0)                 # 4x for inter-sample
    out["tp_db"] = 20 * np.log10(np.max(np.abs(up)) + 1e-12)
    if x.shape[1] == 2 and np.std(x[:, 0]) > 0 and np.std(x[:, 1]) > 0:
        out["corr"] = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1])
    else:
        out["corr"] = 1.0
    rms = np.sqrt(np.mean(x ** 2) + 1e-12)
    out["crest_db"] = 20 * np.log10(peak / rms)
    return out


def normalize_lufs(x, fs, target):
    if pyln is None:
        return x
    cur = pyln.Meter(fs).integrated_loudness(x)
    if not np.isfinite(cur):
        return x
    return x * 10 ** ((target - cur) / 20.0)


def true_peak_limiter(x, fs, ceiling_db=-1.0, lookahead_ms=2.0, release_ms=120.0, os=4):
    """
    Look-ahead brick-wall limiter operating on a 4x-oversampled true-peak
    detector. Lookahead gives instant attack (no transient overshoot); release
    is smoothed; a hard min + final clamp guarantees the ceiling is respected.
    """
    ceiling = 10 ** (ceiling_db / 20.0)
    up = signal.resample_poly(x, os, 1, axis=0)
    peak = np.max(np.abs(up), axis=1) + 1e-12
    desired = np.minimum(1.0, ceiling / peak)

    look = max(1, int(lookahead_ms * 1e-3 * fs * os))
    g = minimum_filter1d(desired, size=look, mode="nearest")   # dip before peak
    a = np.exp(-1.0 / (release_ms * 1e-3 * fs * os))            # smooth recovery
    g = signal.lfilter([1 - a], [1, -a], g)
    g = np.minimum(g, desired)                                  # never exceed need

    up *= g[:, None]
    y = signal.resample_poly(up, 1, os, axis=0)[: x.shape[0]]
    return np.clip(y, -ceiling, ceiling)                       # safety clamp


def dither(x, bits=24):
    """TPDF dither at the target bit depth (transparent, no noise shaping)."""
    q = 2.0 ** -(bits - 1)
    n = (np.random.random(x.shape) - np.random.random(x.shape)) * q
    return x + n


# ----------------------------------------------------------------------------
# Style presets (EQ + loudness targets)
# ----------------------------------------------------------------------------
STYLES = {
    # warm lows, controlled low-mid mud, vocal presence, gentle air
    "modern":      dict(low_shelf=2.0, mud=-1.5, presence=2.0, air=2.5, sat=0.18, lufs=-14),
    "warm":        dict(low_shelf=3.0, mud=-2.0, presence=1.0, air=1.0, sat=0.26, lufs=-14),
    "loud":        dict(low_shelf=1.5, mud=-1.0, presence=2.5, air=2.5, sat=0.22, lufs=-9),
    "transparent": dict(low_shelf=0.8, mud=-0.5, presence=0.8, air=1.2, sat=0.08, lufs=-16),
}


def eq_chain(x, fs, st):
    x = apply_sos(x, rbj("highpass", fs, 28, 0.707))             # subsonic clean-up
    x = apply_sos(x, rbj("lowshelf", fs, 110, 0.707, st["low_shelf"]))
    x = apply_sos(x, rbj("peak", fs, 320, 1.0, st["mud"]))       # tame boxiness
    x = apply_sos(x, rbj("peak", fs, 4200, 0.9, st["presence"]))  # vocal/instr clarity
    x = apply_sos(x, rbj("highshelf", fs, 12000, 0.707, st["air"]))
    return x


def deess(x, fs, f_lo=5500, f_hi=9500):
    """Split out the sibilance band, compress only that, recombine."""
    sos_bp = signal.butter(2, [f_lo / (fs / 2), f_hi / (fs / 2)],
                           btype="band", output="sos")
    band = signal.sosfilt(sos_bp, x, axis=0)
    reduced = compress(band, fs, thr_db=-30, ratio=4.0,
                       attack_ms=1.0, release_ms=60.0, knee_db=4.0)
    return x - band + reduced


def master(x, fs, style="modern", target_lufs=None, tp_db=-1.0, width=1.15):
    st = STYLES[style]
    target_lufs = st["lufs"] if target_lufs is None else target_lufs

    x = x * 10 ** (-3 / 20.0)                                    # working headroom
    x = eq_chain(x, fs, st)
    x = deess(x, fs)

    low, mid, high = split_3way(x, fs, 200, 3000)               # multiband glue
    low = compress(low, fs, -24, 2.0, 30, 180, makeup_db=1.0)
    mid = compress(mid, fs, -22, 1.8, 20, 150)
    high = compress(high, fs, -26, 1.6, 8, 110)
    x = low + mid + high

    x = saturate(x, drive=1.6, mix=st["sat"])
    x = ms_widen(x, width=width, bass_mono_hz=120, fs=fs)
    x = compress(x, fs, -18, 1.5, 30, 200)                     # gentle bus glue

    x = normalize_lufs(x, fs, target_lufs)
    x = true_peak_limiter(x, fs, ceiling_db=tp_db)
    return x, target_lufs


def fmt(m):
    return (f"LUFS={m.get('lufs', float('nan')):6.2f}  "
            f"TP={m['tp_db']:6.2f}dBTP  peak={m['peak_db']:6.2f}dB  "
            f"corr={m['corr']:+.2f}  crest={m['crest_db']:4.1f}dB")


def main():
    ap = argparse.ArgumentParser(description="Transparent streaming-ready mastering chain")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--style", choices=list(STYLES), default="modern")
    ap.add_argument("--target-lufs", type=float, default=None)
    ap.add_argument("--tp", type=float, default=-1.0)
    ap.add_argument("--width", type=float, default=1.15)
    ap.add_argument("--no-encode", action="store_true")
    args = ap.parse_args()

    x, fs = decode(args.input)
    before = measure(x, fs)
    y, tgt = master(x, fs, args.style, args.target_lufs, args.tp, args.width)
    after = measure(y, fs)

    out = args.output if args.output.lower().endswith(".wav") else args.output + ".wav"
    sf.write(out, dither(y, 24), fs, subtype="PCM_24")
    extra = [] if args.no_encode else encode_deliverables(out)

    print(f"\nstyle={args.style}  target={tgt} LUFS  ceiling={args.tp} dBTP  sr={fs}")
    print(f"  before : {fmt(before)}")
    print(f"  after  : {fmt(after)}")
    print(f"  wrote  : {out}")
    for f in extra:
        print(f"           {f}")


if __name__ == "__main__":
    sys.exit(main())

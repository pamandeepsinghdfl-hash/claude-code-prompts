#!/usr/bin/env python3
"""Generate a synthetic stereo 'mix' and run the mastering chain on it.

This exists so the pipeline can be validated end-to-end without a real track:
the test signal deliberately spans low/mid/high content and has stereo width,
so the before/after measurements exercise every stage.
"""
import numpy as np
import soundfile as sf

import master as M

fs = 44100
dur = 8.0
t = np.linspace(0, dur, int(fs * dur), endpoint=False)
rng = np.random.default_rng(0)


def kick(bpm=90):
    period = 60.0 / bpm
    sig = np.zeros_like(t)
    for beat in np.arange(0, dur, period):
        i = (t >= beat) & (t < beat + 0.18)
        env = np.exp(-(t[i] - beat) * 35)
        f = 110 * np.exp(-(t[i] - beat) * 30) + 45
        sig[i] += np.sin(2 * np.pi * f * (t[i] - beat)) * env
    return sig


def bassline():
    notes = [55, 55, 73.4, 65.4]
    seg = len(t) // len(notes)
    sig = np.zeros_like(t)
    for k, f in enumerate(notes):
        s = slice(k * seg, (k + 1) * seg)
        sig[s] = 0.6 * signal_saw(f, t[s])
    return sig


def signal_saw(f, tt):
    x = np.zeros_like(tt)
    for h in range(1, 12):
        x += ((-1) ** (h + 1)) * np.sin(2 * np.pi * f * h * tt) / h
    return x * 0.5


def pad():
    chord = [261.6, 329.6, 392.0]
    x = sum(np.sin(2 * np.pi * f * t) for f in chord) / len(chord)
    return 0.25 * x * (0.6 + 0.4 * np.sin(2 * np.pi * 0.2 * t))


def hats(bpm=90):
    period = 60.0 / (bpm * 2)
    sig = np.zeros_like(t)
    noise = rng.standard_normal(len(t))
    for beat in np.arange(0, dur, period):
        i = (t >= beat) & (t < beat + 0.04)
        sig[i] += noise[i] * np.exp(-(t[i] - beat) * 120)
    return 0.25 * sig


def lead():  # stand-in 'vocal': mid-range tone with vibrato + a little sibilant air
    f = 440 * (1 + 0.01 * np.sin(2 * np.pi * 5 * t))
    v = 0.4 * np.sin(2 * np.pi * f * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 1.5 * t))
    air = 0.05 * rng.standard_normal(len(t))
    return v + air


mono = kick() + bassline() + pad() + hats() + lead()
mono /= np.max(np.abs(mono)) * 1.2

# create stereo width: pan pad/hats slightly, keep kick/bass centered
left = mono + 0.15 * pad()
right = mono - 0.15 * pad() + 0.1 * np.roll(hats(), 50)
mix = np.stack([left, right], axis=1)
mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.5          # leave headroom, ~quiet master

sf.write("test_input.wav", mix, fs, subtype="PCM_24")

before = M.measure(mix, fs)
mastered, tgt = M.master(mix, fs, style="modern")
after = M.measure(mastered, fs)
sf.write("test_master.wav", M.dither(mastered, 24), fs, subtype="PCM_24")

print("SELF-TEST (synthetic mix, modern style)")
print(f"  target  : {tgt} LUFS")
print(f"  before  : {M.fmt(before)}")
print(f"  after   : {M.fmt(after)}")
print("  files   : test_input.wav, test_master.wav")

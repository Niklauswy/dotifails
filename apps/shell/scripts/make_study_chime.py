#!/usr/bin/env python3
"""Generates the study mode chimes (our own sounds, no third-party assets): soft sine tones with a short
attack and an exponential decay. Run from the repo root: python3 apps/shell/scripts/make_study_chime.py"""
import array
import math
from pathlib import Path
import wave

RATE = 44100
OUT = Path(__file__).resolve().parents[1] / 'assets/sounds'


def tone(freq, start, length, peak, total):
    """Adds a decaying sine (with a quieter octave above for warmth) into `total`."""
    attack = int(0.02 * RATE)
    for i in range(int(length * RATE)):
        t = i / RATE
        env = min(1.0, i / attack) * math.exp(-4.2 * t / length)
        value = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(4 * math.pi * freq * t)
        total[int(start * RATE) + i] += peak * env * value / 1.25


def write(name, seconds, notes):
    total = [0.0] * int(seconds * RATE)
    for freq, start, length in notes:
        tone(freq, start, length, 0.55, total)
    samples = array.array('h', (int(max(-1.0, min(1.0, v)) * 32767) for v in total))
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())


if __name__ == '__main__':
    # End of a focus block: two rising tones. End of a break: one lower, shorter tone.
    write('study-chime.wav', 0.9, [(660, 0.0, 0.6), (880, 0.22, 0.68)])
    write('study-chime-soft.wav', 0.6, [(523.25, 0.0, 0.6)])

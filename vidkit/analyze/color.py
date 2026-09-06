"""Farblook messen: Helligkeit, Kontrast, Saettigung, Farbtemperatur.

Ergebnis sind Werte, die direkt als eq/colorbalance-Grade taugen — bezogen auf
ein neutrales Referenzbild.
"""
from __future__ import annotations

import numpy as np

from .frames import FrameSource

# Referenz: wie ein unbearbeitetes, neutrales Bild im Mittel aussieht.
REF_SATURATION = 0.32
REF_CONTRAST = 0.21


def measure_color(src: FrameSource, *, fps: float = 1.0, width: int = 256) -> dict:
    lum_all: list[np.ndarray] = []
    sat_all: list[float] = []
    con_all: list[float] = []
    rgb_mean = np.zeros(3)
    hist = np.zeros(32)
    n = 0

    for _t, frame in src.iter_frames(fps, scale=width):
        f = frame.astype(np.float32) / 255.0
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        mx, mn = f.max(axis=2), f.min(axis=2)
        sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
        lum_all.append(lum.ravel()[::7])
        sat_all.append(float(sat.mean()))
        con_all.append(float(lum.std()))
        rgb_mean += np.array([r.mean(), g.mean(), b.mean()])
        hist += np.histogram(lum, bins=32, range=(0, 1))[0]
        n += 1

    if n == 0:
        return {"available": False}

    lum_cat = np.concatenate(lum_all)
    rgb_mean /= n
    sat = float(np.mean(sat_all))
    con = float(np.mean(con_all))
    # Farbtemperatur grob: Rot-Blau-Differenz, positiv = waermer
    temp = float(rgb_mean[0] - rgb_mean[2])
    hist = hist / hist.sum() if hist.sum() else hist

    return {
        "available": True,
        "measured": {
            "luma_mean": round(float(lum_cat.mean()), 4),
            "luma_median": round(float(np.median(lum_cat)), 4),
            "luma_p05": round(float(np.percentile(lum_cat, 5)), 4),
            "luma_p95": round(float(np.percentile(lum_cat, 95)), 4),
            "contrast_std": round(con, 4),
            "saturation_mean": round(sat, 4),
            "rgb_mean": [round(float(x), 4) for x in rgb_mean],
            "warmth": round(temp, 4),
            "luma_histogram": [round(float(x), 5) for x in hist],
            "frames_sampled": n,
        },
        "grade": {
            "brightness": round(float(np.clip((lum_cat.mean() - 0.45) * 0.5, -0.15, 0.15)), 3),
            "contrast": round(float(np.clip(con / REF_CONTRAST, 0.85, 1.35)), 3),
            "saturation": round(float(np.clip(sat / REF_SATURATION, 0.7, 1.6)), 3),
            "gamma": 1.0,
            "temperature_shift": round(float(np.clip(temp * 1.5, -0.3, 0.3)), 3),
        },
    }

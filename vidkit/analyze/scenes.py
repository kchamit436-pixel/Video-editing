"""Schnittrhythmus messen: wo sitzen die Szenenwechsel, wie lang sind die Einstellungen."""
from __future__ import annotations

import statistics
from pathlib import Path

from ..util import debug, warn


def detect_scenes(path: Path, threshold: float = 27.0) -> list[tuple[float, float]]:
    try:
        from scenedetect import ContentDetector, detect
    except ModuleNotFoundError:
        warn("PySceneDetect fehlt (pip install scenedetect) — Schnittrhythmus wird nicht gemessen.")
        return []
    try:
        scenes = detect(str(path), ContentDetector(threshold=threshold))
    except Exception as exc:  # noqa: BLE001
        warn(f"Szenenerkennung fehlgeschlagen: {exc}")
        return []
    return [(s.get_seconds(), e.get_seconds()) for s, e in scenes]


def measure_cuts(path: Path, duration: float, threshold: float = 27.0) -> dict:
    scenes = detect_scenes(path, threshold)
    if not scenes:
        return {"cut_times": [], "shot_lengths": [], "count": 0}
    lengths = [round(e - s, 3) for s, e in scenes if e > s]
    cut_times = [round(s, 3) for s, _ in scenes[1:]]
    lengths_sorted = sorted(lengths)

    def pct(p: float) -> float:
        if not lengths_sorted:
            return 0.0
        k = min(len(lengths_sorted) - 1, max(0, int(round(p * (len(lengths_sorted) - 1)))))
        return lengths_sorted[k]

    # Histogramm in festen Klassen, damit sich Stile vergleichen lassen
    edges = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 1e9]
    hist = [0] * (len(edges) - 1)
    for x in lengths:
        for i in range(len(edges) - 1):
            if edges[i] <= x < edges[i + 1]:
                hist[i] += 1
                break
    debug(f"Szenen: {len(scenes)}, Laengen {lengths_sorted[:5]}…")
    return {
        "cut_times": cut_times,
        "shot_lengths": lengths,
        "count": len(scenes),
        "avg": round(statistics.fmean(lengths), 3) if lengths else 0.0,
        "median": round(statistics.median(lengths), 3) if lengths else 0.0,
        "min": round(min(lengths), 3) if lengths else 0.0,
        "p10": round(pct(0.10), 3),
        "p90": round(pct(0.90), 3),
        "cuts_per_10s": round(len(cut_times) / (duration / 10), 2) if duration else 0.0,
        "histogram": {"edges": edges[:-1] + [None], "counts": hist},
    }

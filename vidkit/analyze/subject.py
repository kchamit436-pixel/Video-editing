"""Talking-Head-Anteil gegen B-Roll-Anteil schaetzen.

Zwei Wege, in dieser Reihenfolge:
  1. Gesichtserkennung (OpenCV-Haar-Kaskade) — direkt und belastbar.
     In OpenCV 5 ist CascadeClassifier nicht mehr im Hauptmodul, dann greift:
  2. Shot-Clustering — die groesste Gruppe optisch aehnlicher Einstellungen gilt
     als Talking Head, der Rest als B-Roll. Ergebnis ist eine Schaetzung und
     wird als solche gekennzeichnet.
"""
from __future__ import annotations

import numpy as np

from ..util import debug
from .frames import FrameSource


def _cascade():
    try:
        import cv2
    except ModuleNotFoundError:
        return None
    if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data"):
        return None
    try:
        c = cv2.CascadeClassifier(cv2.data.haarcascades +
                                  "haarcascade_frontalface_default.xml")
        return None if c.empty() else c
    except Exception:  # noqa: BLE001
        return None


def _by_faces(src: FrameSource, cascade, fps: float) -> dict:
    total = with_face = 0
    for _t, frame in src.iter_frames(fps, scale=480, gray=True):
        total += 1
        if len(cascade.detectMultiScale(frame, scaleFactor=1.15, minNeighbors=5,
                                        minSize=(40, 40))):
            with_face += 1
    if total == 0:
        return {"available": False}
    ratio = with_face / total
    return {"available": True, "method": "gesichtserkennung", "frames": total,
            "with_face": with_face, "talking_head_ratio": round(ratio, 3),
            "broll_ratio": round(1 - ratio, 3)}


def _hist(frame: np.ndarray) -> np.ndarray:
    f = frame.astype(np.float32) / 255.0
    h = []
    for c in range(3):
        h.append(np.histogram(f[..., c], bins=12, range=(0, 1))[0])
    v = np.concatenate(h).astype(np.float64)
    return v / (v.sum() + 1e-9)


def _by_clustering(src: FrameSource, scenes: list[tuple[float, float]], fps: float) -> dict:
    """Ohne Gesichtserkennung: aehnlich aussehende Einstellungen gehoeren zusammen."""
    sigs: list[tuple[float, np.ndarray]] = []
    if scenes:
        wanted = [((s + e) / 2, e - s) for s, e in scenes]
        by_time: dict[int, np.ndarray] = {}
        for t, frame in src.iter_frames(4.0, scale=192):
            by_time[int(round(t * 4))] = _hist(frame)
        for mid, dur in wanted:
            if not by_time:
                break
            key = int(round(mid * 4))
            if key not in by_time:
                key = min(by_time, key=lambda k: abs(k - int(round(mid * 4))))
            sigs.append((dur, by_time[key]))
    else:
        for t, frame in src.iter_frames(1.0, scale=192):
            sigs.append((1.0, _hist(frame)))

    if len(sigs) < 2:
        return {"available": True, "method": "geschaetzt", "shots": len(sigs),
                "talking_head_ratio": 1.0, "broll_ratio": 0.0}

    n = len(sigs)
    sim = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            a, b = sigs[i][1], sigs[j][1]
            sim[i, j] = float(np.minimum(a, b).sum())      # Histogramm-Schnittmenge
    group = sim.mean(axis=1).argmax()
    members = [i for i in range(n) if sim[group, i] >= 0.72]
    total = sum(d for d, _ in sigs)
    head = sum(sigs[i][0] for i in members)
    ratio = head / total if total else 1.0
    debug(f"Shot-Clustering: {len(members)}/{n} Einstellungen in der Hauptgruppe")
    return {"available": True, "method": "shot-clustering (geschaetzt)", "shots": n,
            "main_group": len(members), "talking_head_ratio": round(ratio, 3),
            "broll_ratio": round(1 - ratio, 3)}


def measure_subject(src: FrameSource, *, scenes: list[tuple[float, float]] | None = None,
                    fps: float = 1.0) -> dict:
    cascade = _cascade()
    if cascade is not None:
        res = _by_faces(src, cascade, fps)
        if res.get("available"):
            return res
    return _by_clustering(src, scenes or [], fps)

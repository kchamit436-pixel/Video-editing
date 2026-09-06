"""Kamerabewegung ueber Optical Flow: wird gezoomt oder geschoben, wie stark,
wie lange, mit welchem Verlauf?

Das Flussfeld wird pro Bildpaar linear zerlegt:
    flow_x ≈ s·(x-cx) + tx
    flow_y ≈ s·(y-cy) + ty
s ist die Skalenaenderung pro Frame (Zoom), (tx,ty) die Verschiebung (Schwenk).
"""
from __future__ import annotations

import math

import numpy as np

from ..util import debug, warn
from .frames import FrameSource

EASINGS = {
    "linear": lambda p: p,
    "easeOutCubic": lambda p: 1 - (1 - p) ** 3,
    "easeOutQuad": lambda p: 1 - (1 - p) ** 2,
    "easeInOutCubic": lambda p: 4 * p ** 3 if p < 0.5 else 1 - ((-2 * p + 2) ** 3) / 2,
    "easeInOutSine": lambda p: -(math.cos(math.pi * p) - 1) / 2,
    "easeOutExpo": lambda p: 1.0 if p >= 1 else 1 - 2 ** (-10 * p),
}


def _decompose(flow: np.ndarray, weight: np.ndarray | None = None
               ) -> tuple[float, float, float]:
    """(Zoomrate pro Frame, dx, dy) aus einem Flussfeld schaetzen.

    Die Anpassung wird mit der lokalen Bildstruktur gewichtet: in flaechigen
    Bereichen (Wand, Himmel, Unschaerfe) liefert Farneback nahezu Null und
    zieht eine ungewichtete Schaetzung um ein Vielfaches nach unten. Gegen eine
    Fahrt mit bekanntem Sollwert (1.12) misst die gewichtete Variante 1.104,
    die ungewichtete 1.042.
    """
    h, w = flow.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    rx = (xs - cx).ravel()
    ry = (ys - cy).ravel()
    fx = flow[..., 0].ravel()
    fy = flow[..., 1].ravel()
    wt = np.ones_like(fx) if weight is None else weight.ravel()
    total = float(wt.sum()) + 1e-9
    tx = float((wt * fx).sum() / total)
    ty = float((wt * fy).sum() / total)
    denom = float((wt * (rx * rx + ry * ry)).sum())
    num = float((wt * ((fx - tx) * rx + (fy - ty) * ry)).sum())
    s = num / denom if denom > 0 else 0.0
    # in Bildbreiten normieren, damit die Werte aufloesungsunabhaengig sind
    return s, tx / w, ty / h


def _texture_weight(gray: np.ndarray, cv2, percentile: float = 70.0) -> np.ndarray:
    """Gewicht = Kantenstaerke; strukturlose Flaechen fallen ganz heraus."""
    g = gray.astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.GaussianBlur(np.sqrt(gx * gx + gy * gy), (0, 0), 3)
    thr = float(np.percentile(mag, percentile))
    return np.where(mag >= thr, mag, 0.0)


def measure_motion(src: FrameSource, *, fps: float = 15.0, width: int = 480,
                   cut_times: list[float] | None = None) -> dict:
    try:
        import cv2
    except ModuleNotFoundError:
        warn("OpenCV fehlt (pip install opencv-python) — Kamerabewegung wird nicht gemessen.")
        return {"available": False}

    prev = None
    times: list[float] = []
    zoom_rate: list[float] = []
    pan_x: list[float] = []
    pan_y: list[float] = []
    cuts = sorted(cut_times or [])

    for t, frame in src.iter_frames(fps, scale=width, gray=True):
        if prev is not None:
            # Ueber einen Schnitt hinweg ist der Fluss bedeutungslos
            near_cut = any(t - 1.0 / fps < c <= t + 1e-9 for c in cuts)
            if near_cut:
                times.append(t); zoom_rate.append(0.0); pan_x.append(0.0); pan_y.append(0.0)
            else:
                # Groessere Pyramide und groesseres Fenster: langsame, gleich-
                # foermige Kamerafahrten werden sonst systematisch unterschaetzt.
                flow = cv2.calcOpticalFlowFarneback(
                    prev, frame, None, 0.5, 4, 31, 5, 7, 1.5, 0)
                s, dx, dy = _decompose(flow, _texture_weight(frame, cv2))
                times.append(t); zoom_rate.append(s); pan_x.append(dx); pan_y.append(dy)
        prev = frame

    if not times:
        return {"available": False}

    zr = np.array(zoom_rate)
    px = np.array(pan_x)
    py = np.array(pan_y)
    dt = 1.0 / fps
    noise = float(np.median(np.abs(zr))) or 1e-5
    thresh = max(noise * 2.5, 0.0008)

    # Zusammenhaengende Laeufe gleichen Vorzeichens = eine Kamerafahrt
    moves: list[dict] = []
    i = 0
    while i < len(zr):
        if abs(zr[i]) < thresh:
            i += 1
            continue
        sign = math.copysign(1, zr[i])
        j = i
        while j < len(zr) and abs(zr[j]) >= thresh * 0.4 and math.copysign(1, zr[j]) == sign:
            j += 1
        run = zr[i:j]
        dur = (j - i) * dt
        if dur >= 0.15 and len(run) >= 2:
            scale = float(np.exp(np.sum(run)))     # kumulierte Skalenaenderung
            cum = np.cumsum(run) / (np.sum(run) or 1e-9)
            p = np.linspace(1 / len(run), 1.0, len(run))
            best, best_err = "linear", 1e9
            for name, fn in EASINGS.items():
                err = float(np.mean((cum - np.array([fn(x) for x in p])) ** 2))
                if err < best_err:
                    best, best_err = name, err
            moves.append({
                "t_in": round(times[i], 3), "duration": round(dur, 3),
                "scale": round(scale, 4),
                "direction": "in" if sign > 0 else "out",
                "easing": best, "easing_error": round(best_err, 5),
            })
        i = max(j, i + 1)

    pan_mag = np.sqrt(px ** 2 + py ** 2)
    pan_moves = int(np.sum(pan_mag > max(float(np.median(pan_mag)) * 3, 0.002)))
    zoom_scales = [abs(m["scale"] - 1.0) for m in moves]
    easings = [m["easing"] for m in moves]
    easing_mode = max(set(easings), key=easings.count) if easings else "easeOutCubic"

    debug(f"Bewegung: {len(moves)} Fahrten, Rauschgrenze {thresh:.5f}")
    return {
        "available": True,
        "moves": moves,
        "count": len(moves),
        "moves_per_10s": round(len(moves) / (src.duration / 10), 2) if src.duration else 0.0,
        "zoom_scale_mean": round(1 + float(np.mean(zoom_scales)), 4) if zoom_scales else 1.0,
        "zoom_scale_max": round(1 + float(np.max(zoom_scales)), 4) if zoom_scales else 1.0,
        "zoom_duration_mean": round(float(np.mean([m["duration"] for m in moves])), 3)
        if moves else 0.0,
        "easing": easing_mode,
        "direction_in_ratio": round(sum(1 for m in moves if m["direction"] == "in")
                                    / max(1, len(moves)), 2),
        "pan_share": round(pan_moves / max(1, len(times)), 3),
        "pan_max_rel": round(float(np.max(pan_mag)) if len(pan_mag) else 0.0, 5),
    }

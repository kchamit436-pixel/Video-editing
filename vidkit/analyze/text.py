"""Text im Bild ausmessen: Position, Groesse, Farben, Kontur, Schreibweise, Standzeit.

Getrennt nach zwei Ebenen: grosse Einblendungen und Captions. Die Trennung
faellt anhand der gemessenen Schriftgroessen, nicht anhand einer festen Regel.
"""
from __future__ import annotations

import re
from collections import Counter

import numpy as np

from ..util import debug, warn
from .frames import FrameSource

_WORD = re.compile(r"\w{2,}", re.UNICODE)


def _ocr_backend():
    try:
        import easyocr  # noqa: F401
        return "easyocr"
    except ModuleNotFoundError:
        pass
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return "tesseract"
    except Exception:  # noqa: BLE001
        return None


def _channels(frame: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Bildkanaele, auf denen OCR laeuft.

    Nur Helligkeit reicht nicht: gelber Text auf heller Flaeche hat in Luma
    kaum Kontrast und wird gar nicht erkannt, im b-Kanal von LAB (gelb/blau)
    dagegen sauber. Deshalb beide, Ergebnisse werden zusammengefuehrt.
    """
    try:
        import cv2
        g = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY), (0, 0), 1.2)
        lab = cv2.cvtColor(frame, cv2.COLOR_RGB2LAB)
        b = cv2.GaussianBlur(lab[..., 2], (0, 0), 1.2)
        return [("luma", g), ("lab_b", b)]
    except Exception:  # noqa: BLE001
        from PIL import Image, ImageFilter
        g = np.array(Image.fromarray(frame).convert("L")
                     .filter(ImageFilter.GaussianBlur(1.2)))
        return [("luma", g)]


def _tess_words(img: np.ndarray, lang: str, min_conf: float) -> list[dict]:
    import pytesseract
    from PIL import Image
    d = pytesseract.image_to_data(Image.fromarray(img), lang=lang, config="--psm 11",
                                  output_type=pytesseract.Output.DICT)
    out = []
    for i, txt in enumerate(d["text"]):
        txt = (txt or "").strip()
        conf = float(d["conf"][i]) if d["conf"][i] not in ("", "-1", -1) else -1.0
        if not txt or conf < min_conf:
            continue
        out.append({"text": txt, "conf": conf, "x": d["left"][i], "y": d["top"][i],
                    "w": d["width"][i], "h": d["height"][i]})
    return out


def _same_box(a: dict, b: dict) -> bool:
    """Zwei Funde derselben Stelle — Kaesten ueberlappen oder gleicher Text nah beieinander.

    Der zweite Fall ist noetig, weil die Kaesten aus verschiedenen Kanaelen
    unterschiedlich gross ausfallen und sonst als zwei Zeilen durchgehen.
    """
    if _iou(a, b) > 0.30:
        return True
    if _norm_text(a["text"]) and _norm_text(a["text"]) == _norm_text(b["text"]):
        acy, bcy = a["y"] + a["h"] / 2, b["y"] + b["h"] / 2
        acx, bcx = a["x"] + a["w"] / 2, b["x"] + b["w"] / 2
        tol = max(a["h"], b["h"])
        return abs(acy - bcy) <= tol and abs(acx - bcx) <= tol
    return False


def _iou(a: dict, b: dict) -> float:
    ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1, bx2, by2 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
    ix = max(0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0, min(ay2, by2) - max(ay1, by1))
    inter = ix * iy
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union > 0 else 0.0


def _group_lines(words: list[dict]) -> list[dict]:
    """Woerter geometrisch zu Zeilen buendeln.

    Die block/par/line-Nummern von Tesseract taugen bei --psm 11 nicht: sie
    fassen weit auseinander liegende Zeilen zusammen und verfaelschen damit die
    gemessene Schriftgroesse.
    """
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["y"] + w["h"] / 2, w["x"])):
        cy = w["y"] + w["h"] / 2
        placed = False
        for ln in lines:
            ref = ln[-1]
            rcy = ref["y"] + ref["h"] / 2
            same_row = abs(cy - rcy) <= 0.55 * max(w["h"], ref["h"])
            close = (w["x"] - (ref["x"] + ref["w"])) <= 2.0 * max(w["h"], ref["h"])
            if same_row and close and abs(w["h"] - ref["h"]) <= 0.6 * max(w["h"], ref["h"]):
                ln.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])
    out = []
    for ln in lines:
        x0 = min(w["x"] for w in ln)
        y0 = min(w["y"] for w in ln)
        x1 = max(w["x"] + w["w"] for w in ln)
        y1 = max(w["y"] + w["h"] for w in ln)
        out.append({"text": " ".join(w["text"] for w in sorted(ln, key=lambda w: w["x"])),
                    "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
                    "conf": float(np.mean([w["conf"] for w in ln]))})
    return out


def _ocr_frame(backend, frame: np.ndarray, reader=None, lang: str = "deu",
               min_conf: float = 45.0) -> list[dict]:
    """Zeilenweise Textkaesten eines Frames."""
    if backend == "tesseract":
        words: list[dict] = []
        for ci, (_name, img) in enumerate(_channels(frame)):
            for w in _tess_words(img, lang, min_conf):
                overlap = next((prev for prev in words if _same_box(w, prev)), None)
                if ci == 0:
                    if overlap is None:
                        words.append(w)
                    elif w["conf"] > overlap["conf"]:
                        overlap.update(w)
                    continue
                # Zusatzkanaele duerfen nur fuellen, was der Luma-Kanal gar nicht
                # gesehen hat. Ihre Kaesten sind unzuverlaessig und wuerden sonst
                # gute Messungen aus dem Hauptkanal verschlechtern.
                if overlap is None and not any(_iou(w, prev) > 0.05 for prev in words):
                    words.append(w)
        return _group_lines(words)

    if backend == "easyocr":
        res = reader.readtext(frame)
        out = []
        for box, txt, conf in res:
            if conf < 0.45 or not txt.strip():
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            out.append({"text": txt.strip(), "x": int(min(xs)), "y": int(min(ys)),
                        "w": int(max(xs) - min(xs)), "h": int(max(ys) - min(ys)),
                        "conf": conf * 100})
        return out
    return []


def _glyph_colors(frame: np.ndarray, box: dict) -> dict:
    """Textfarbe, Konturfarbe und ob ueberhaupt eine Kontur/Schatten da ist."""
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    H, W = frame.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return {}
    patch = frame[y0:y1, x0:x1].astype(np.float32)
    lum = 0.2126 * patch[..., 0] + 0.7152 * patch[..., 1] + 0.0722 * patch[..., 2]
    # >= / <=, nicht > / < : bei hartem Schwarz-Weiss-Text liegt das 80.
    # Perzentil exakt auf dem Maximum, ein striktes > liefert dann leere Cluster.
    hi = lum >= np.percentile(lum, 80)
    lo = lum <= np.percentile(lum, 20)
    if hi.sum() < 4 or lo.sum() < 4:
        return {}
    text_rgb = patch[hi].mean(axis=0)
    dark_rgb = patch[lo].mean(axis=0)
    # Ring um den Kasten: sitzt dort deutlich dunkleres Material, gibt es eine Kontur
    pad = max(2, int(0.12 * (y1 - y0)))
    rx0, ry0 = max(0, x0 - pad), max(0, y0 - pad)
    rx1, ry1 = min(W, x1 + pad), min(H, y1 + pad)
    ring = frame[ry0:ry1, rx0:rx1].astype(np.float32)
    ring_lum = 0.2126 * ring[..., 0] + 0.7152 * ring[..., 1] + 0.0722 * ring[..., 2]
    contrast = float(lum[hi].mean() - float(np.median(ring_lum)))
    return {
        "text_rgb": [int(v) for v in text_rgb],
        "dark_rgb": [int(v) for v in dark_rgb],
        "outline_contrast": round(contrast, 1),
        "has_outline": bool(float(lum[lo].mean()) < 70 and contrast > 60),
    }


def _hex(rgb: list[int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*[max(0, min(255, int(v))) for v in rgb])


def _norm_text(t: str) -> str:
    return re.sub(r"[^\w]", "", t.lower())


# Ein OCR-Kasten umschliesst die Glyphen, nicht das em-Quadrat der Schrift.
# Fuer eine serifenlose Versalschrift liegt das Verhaeltnis bei etwa 0.72 —
# damit rechnen wir die gemessene Kastenhoehe in eine CSS-Schriftgroesse um.
GLYPH_TO_EM = 0.72


def _split_height(events: list[dict]) -> float | None:
    """Trennlinie zwischen grossen Einblendungen und Captions (1D-k-Means, k=2)."""
    hs = sorted(np.log(max(e["h_rel"], 1e-4)) for e in events)
    if len(hs) < 4:
        return None
    c0, c1 = hs[0], hs[-1]
    if c1 - c0 < 0.30:                      # weniger als ~35 % Groessenunterschied
        return None
    for _ in range(25):
        left = [h for h in hs if abs(h - c0) <= abs(h - c1)]
        right = [h for h in hs if abs(h - c0) > abs(h - c1)]
        if not left or not right:
            return None
        n0, n1 = sum(left) / len(left), sum(right) / len(right)
        if abs(n0 - c0) < 1e-6 and abs(n1 - c1) < 1e-6:
            break
        c0, c1 = n0, n1
    if c1 - c0 < 0.30:
        return None
    return float(np.exp((c0 + c1) / 2))


def measure_text(src: FrameSource, *, fps: float = 2.0, lang: str = "deu",
                 max_frames: int = 400) -> dict:
    backend = _ocr_backend()
    if backend is None:
        warn("Weder easyocr noch tesseract gefunden — Text-Overlays werden nicht gemessen.\n"
             "   brew install tesseract tesseract-lang   oder   pip install easyocr")
        return {"available": False}
    reader = None
    if backend == "easyocr":
        import easyocr
        reader = easyocr.Reader(["de", "en"], gpu=False, verbose=False)

    H, W = src.height, src.width
    interval = 1.0 / fps
    events: list[dict] = []       # abgeschlossene Einblendungen
    live: list[dict] = []         # gerade sichtbare Einblendungen
    frames_seen = 0
    debug(f"OCR-Backend: {backend}")

    def matches(track: dict, box: dict) -> bool:
        """Gleiche Einblendung wie im Bild davor?

        Verfolgt wird ueber Lage und Groesse, nicht ueber den Text: die
        OCR-Ausgabe schwankt von Bild zu Bild ('MEHR ZEIT' / 'MEHR ZEI'), und
        ein Textvergleich wuerde eine Einblendung in mehrere zerlegen — Dichte
        und Standzeit waeren dann Unsinn.
        """
        b = track["box"]
        h = max(box["h"], b["h"])
        dy = abs((box["y"] + box["h"] / 2) - (b["y"] + b["h"] / 2))
        dx = abs((box["x"] + box["w"] / 2) - (b["x"] + b["w"] / 2))
        size_ok = 0.6 <= (box["h"] / max(b["h"], 1)) <= 1.7
        return dy <= 0.8 * h and dx <= 1.2 * max(box["w"], b["w"]) and size_ok

    for t, frame in src.iter_frames(fps):
        frames_seen += 1
        if frames_seen > max_frames:
            break
        boxes = _ocr_frame(backend, frame, reader, lang)
        used: set[int] = set()
        for b in boxes:
            colors = _glyph_colors(frame, b)
            sample = {
                "y_rel": round((b["y"] + b["h"] / 2) / H, 4),
                "x_rel": round((b["x"] + b["w"] / 2) / W, 4),
                "h_rel": round(b["h"] / H, 4),
                "w_rel": round(b["w"] / W, 4),
                **colors,
            }
            hit = None
            for i, tr in enumerate(live):
                if i not in used and matches(tr, b):
                    hit = (i, tr)
                    break
            if hit is not None:
                i, tr = hit
                used.add(i)
                tr["t_out"] = t
                tr["box"] = b
                tr["samples"].append(sample)
                tr["texts"].append(b["text"])
                tr["missed"] = 0
            else:
                live.append({"text": b["text"], "texts": [b["text"]], "box": b,
                             "t_in": t, "t_out": t, "samples": [sample], "missed": 0})
                used.add(len(live) - 1)
        # Eine Aussetzer-Runde tolerieren, damit ein Flackern nichts zerschneidet
        still: list[dict] = []
        for i, tr in enumerate(live):
            if i in used:
                still.append(tr)
                continue
            tr["missed"] += 1
            (still if tr["missed"] <= 1 else events).append(tr)
        live = still
    events.extend(live)

    # Haeufigste Lesart als Text der Einblendung
    for e in events:
        e["text"] = Counter(e["texts"]).most_common(1)[0][0]

    # OCR-Muell aussortieren: Fragmente ohne echtes Wort tragen keine Information.
    events = [e for e in events if len(re.sub(r"\W", "", e["text"], flags=re.UNICODE)) >= 3]
    if not events:
        return {"available": True, "backend": backend, "events": 0,
                "note": "kein Text erkannt"}

    # Standzeit: eine Einblendung, die nur in einem Sample auftaucht, stand
    # mindestens ein Abtastintervall.
    for e in events:
        e["duration"] = round(max(1.0 / fps, e["t_out"] - e["t_in"] + 1.0 / fps), 3)
        e["h_rel"] = float(np.median([s["h_rel"] for s in e["samples"]]))
        e["y_rel"] = float(np.median([s["y_rel"] for s in e["samples"]]))
        e["x_rel"] = float(np.median([s["x_rel"] for s in e["samples"]]))
        e["w_rel"] = float(np.median([s["w_rel"] for s in e["samples"]]))
        e["words"] = len(_WORD.findall(e["text"]))
        e["upper"] = bool(e["text"] == e["text"].upper() and any(c.isalpha() for c in e["text"]))
        outl = [s.get("has_outline") for s in e["samples"] if "has_outline" in s]
        e["has_outline"] = bool(outl and sum(1 for o in outl if o) / len(outl) > 0.5)
        txt = [s["text_rgb"] for s in e["samples"] if "text_rgb" in s]
        drk = [s["dark_rgb"] for s in e["samples"] if "dark_rgb" in s]
        e["text_color"] = _hex(list(np.median(np.array(txt), axis=0))) if txt else None
        e["outline_color"] = _hex(list(np.median(np.array(drk), axis=0))) if drk else None

    # Zwei Ebenen trennen: gross (Overlays) vs. klein (Captions).
    split = _split_height(events)
    if split is not None:
        big = [e for e in events if e["h_rel"] >= split]
        small = [e for e in events if e["h_rel"] < split]
    else:
        # Nur eine Groessenklasse: nach Lage entscheiden — unteres Drittel = Captions
        big = [e for e in events if e["y_rel"] < 0.55]
        small = [e for e in events if e["y_rel"] >= 0.55]

    def summarize(group: list[dict], duration: float) -> dict | None:
        if not group:
            return None
        med = lambda k: round(float(np.median([e[k] for e in group])), 4)  # noqa: E731
        colors = [e["text_color"] for e in group if e["text_color"]]
        outlines = [e["outline_color"] for e in group if e["outline_color"]]
        return {
            "count": len(group),
            "per_10s": round(len(group) / (duration / 10), 2) if duration else 0.0,
            "glyph_height_rel": med("h_rel"),
            "font_size_rel": round(med("h_rel") / GLYPH_TO_EM, 4),
            "y_rel": med("y_rel"),
            "x_rel": med("x_rel"),
            "max_width_rel": round(float(np.percentile([e["w_rel"] for e in group], 90)), 4),
            "hold_seconds": med("duration"),
            "words_mean": round(float(np.mean([e["words"] for e in group])), 2),
            "uppercase_ratio": round(sum(1 for e in group if e["upper"]) / len(group), 2),
            "outline_ratio": round(sum(1 for e in group if e["has_outline"]) / len(group), 2),
            "color": Counter(colors).most_common(1)[0][0] if colors else None,
            "outline_color": Counter(outlines).most_common(1)[0][0] if outlines else None,
            "examples": [e["text"] for e in group[:5]],
            "times": [round(e["t_in"], 2) for e in group],
        }

    return {
        "available": True,
        "backend": backend,
        "events": len(events),
        "frames_sampled": frames_seen,
        "split_h_rel": round(split, 4) if split else None,
        "overlays": summarize(big, src.duration),
        "captions": summarize(small, src.duration),
    }

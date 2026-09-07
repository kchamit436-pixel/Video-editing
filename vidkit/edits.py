"""Schnittoperationen auf der edit.json — Passagen loeschen, teilen, trimmen.

Der Trick liegt darin, dass alle Elemente (Captions, Overlays, Zooms, Sounds)
in der *fertigen* Zeitachse liegen, die Segmente aber die Quelle beschreiben.
Aendert sich ein Segment, verschiebt sich alles dahinter.

Deshalb wird jedes Element vor der Aenderung in Quellzeit umgerechnet und
danach zurueck. Was in der weggeworfenen Passage lag, faellt dabei heraus.
"""
from __future__ import annotations

from typing import Any

from .editdoc import sort_all

POINT_KINDS = ("sfx",)                     # Elemente mit nur einem Zeitpunkt
SPAN_KINDS = ("captions", "overlays", "zooms", "broll", "motion_graphics")


# --------------------------------------------------------------------------- #
# Zeitumrechnung
# --------------------------------------------------------------------------- #
def out_to_source(segments: list[dict], t: float) -> float | None:
    for seg in segments:
        if seg["t_in"] - 1e-6 <= t <= seg["t_out"] + 1e-6:
            return seg["source_in"] + (t - seg["t_in"])
    return None


def source_to_out(segments: list[dict], src: float) -> float | None:
    for seg in segments:
        if seg["source_in"] - 1e-6 <= src <= seg["source_out"] + 1e-6:
            return seg["t_in"] + (src - seg["source_in"])
    return None


def renumber(segments: list[dict]) -> list[dict]:
    """Ausgabezeiten aus den Segmentlaengen neu aufbauen."""
    t = 0.0
    for i, seg in enumerate(segments):
        dur = max(0.0, seg["source_out"] - seg["source_in"])
        seg["id"] = f"seg{i:03d}"
        seg["t_in"] = round(t, 3)
        seg["t_out"] = round(t + dur, 3)
        t += dur
    return segments


def duration_of(segments: list[dict]) -> float:
    return segments[-1]["t_out"] if segments else 0.0


# --------------------------------------------------------------------------- #
# Elemente mitziehen
# --------------------------------------------------------------------------- #
def remap_elements(doc: dict, old: list[dict], new: list[dict]) -> dict[str, int]:
    """Alle Elemente von der alten auf die neue Zeitachse umrechnen.

    Was in einer entfernten Passage lag, wird geloescht. Elemente, die nur mit
    einem Rand hineinragen, werden auf den verbleibenden Teil gekuerzt.
    """
    stats = {"removed": 0, "trimmed": 0, "moved": 0}
    total_new = duration_of(new)

    for kind in POINT_KINDS:
        keep = []
        for el in doc.get(kind, []):
            src = out_to_source(old, float(el["t"]))
            t_new = source_to_out(new, src) if src is not None else None
            if t_new is None:
                stats["removed"] += 1
                continue
            if abs(t_new - el["t"]) > 1e-6:
                stats["moved"] += 1
            el["t"] = round(min(t_new, total_new), 3)
            keep.append(el)
        doc[kind] = keep

    for kind in SPAN_KINDS:
        keep = []
        for el in doc.get(kind, []):
            src_in = out_to_source(old, float(el["t_in"]))
            src_out = out_to_source(old, float(el["t_out"]))
            if src_in is None or src_out is None:
                stats["removed"] += 1
                continue
            a = source_to_out(new, src_in)
            b = source_to_out(new, src_out)
            if a is None and b is None:
                stats["removed"] += 1
                continue
            if a is None or b is None:
                # Nur ein Rand ueberlebt: auf den verbleibenden Teil kuerzen
                stats["trimmed"] += 1
                a = a if a is not None else _nearest(new, src_in)
                b = b if b is not None else _nearest(new, src_out)
            if b - a < 0.06:
                stats["removed"] += 1
                continue
            if abs(a - el["t_in"]) > 1e-6:
                stats["moved"] += 1
            old_len = el["t_out"] - el["t_in"]
            el["t_in"] = round(max(0.0, a), 3)
            el["t_out"] = round(min(b, total_new), 3)
            # Wortzeiten der Captions sind relativ zum Blockanfang und muessen
            # mitskaliert werden, sonst laeuft die Hervorhebung aus dem Takt.
            if kind == "captions" and el.get("words") and old_len > 0:
                f = (el["t_out"] - el["t_in"]) / old_len
                if abs(f - 1.0) > 1e-6:
                    el["words"] = [{"w": w["w"], "t_in": round(w["t_in"] * f, 3),
                                    "t_out": round(w["t_out"] * f, 3)} for w in el["words"]]
            keep.append(el)
        doc[kind] = keep
    return stats


def _nearest(segments: list[dict], src: float) -> float:
    """Naechstgelegene Ausgabezeit zu einer Quellzeit, die weggeschnitten wurde."""
    if not segments:
        return 0.0
    if src <= segments[0]["source_in"]:
        return segments[0]["t_in"]
    for seg in segments:
        if src <= seg["source_out"]:
            if src >= seg["source_in"]:
                return seg["t_in"] + (src - seg["source_in"])
            return seg["t_in"]
    return segments[-1]["t_out"]


# --------------------------------------------------------------------------- #
# Die Operationen
# --------------------------------------------------------------------------- #
def _apply(doc: dict, new_segments: list[dict]) -> dict:
    old = [dict(s) for s in doc["segments"]]
    renumber(new_segments)
    stats = remap_elements(doc, old, new_segments)
    doc["segments"] = new_segments
    doc["duration"] = round(duration_of(new_segments), 3)
    sort_all(doc)          # nach jedem Schnitt bleibt alles zeitlich geordnet
    return stats


def delete_segment(doc: dict, seg_id: str) -> dict:
    """Eine Passage wegwerfen. Alles dahinter rutscht nach vorn."""
    segs = doc.get("segments", [])
    if len(segs) <= 1:
        raise ValueError("Das letzte Segment laesst sich nicht loeschen.")
    if not any(s["id"] == seg_id for s in segs):
        raise ValueError(f"Segment {seg_id} gibt es nicht.")
    return _apply(doc, [dict(s) for s in segs if s["id"] != seg_id])


def split_segment(doc: dict, seg_id: str, t: float) -> dict:
    """Ein Segment an der Ausgabezeit t in zwei teilen."""
    segs = doc.get("segments", [])
    seg = next((s for s in segs if s["id"] == seg_id), None)
    if seg is None:
        raise ValueError(f"Segment {seg_id} gibt es nicht.")
    if not (seg["t_in"] + 0.06 < t < seg["t_out"] - 0.06):
        raise ValueError("Der Trennpunkt liegt zu nah am Rand des Segments.")
    src = seg["source_in"] + (t - seg["t_in"])
    out: list[dict] = []
    for s in segs:
        if s["id"] != seg_id:
            out.append(dict(s))
            continue
        out.append({**s, "source_out": round(src, 3)})
        out.append({**s, "source_in": round(src, 3), "reason": s.get("reason", "sprache")})
    return _apply(doc, out)


def trim_segment(doc: dict, seg_id: str, *, source_in: float | None = None,
                 source_out: float | None = None) -> dict:
    """Anfang oder Ende einer Passage verschieben (in Quellzeit)."""
    segs = doc.get("segments", [])
    seg = next((s for s in segs if s["id"] == seg_id), None)
    if seg is None:
        raise ValueError(f"Segment {seg_id} gibt es nicht.")
    a = seg["source_in"] if source_in is None else float(source_in)
    b = seg["source_out"] if source_out is None else float(source_out)
    if b - a < 0.08:
        raise ValueError("Die Passage waere danach zu kurz.")
    out = [dict(s) for s in segs]
    for s in out:
        if s["id"] == seg_id:
            s["source_in"], s["source_out"] = round(a, 3), round(b, 3)
    return _apply(doc, out)


def delete_range(doc: dict, t_in: float, t_out: float) -> dict:
    """Einen Bereich der fertigen Zeitachse herausschneiden, quer ueber Segmente."""
    segs = doc.get("segments", [])
    out: list[dict] = []
    for s in segs:
        if t_out <= s["t_in"] or t_in >= s["t_out"]:
            out.append(dict(s))
            continue
        left_len = max(0.0, t_in - s["t_in"])
        right_len = max(0.0, s["t_out"] - t_out)
        if left_len > 0.05:
            out.append({**s, "source_out": round(s["source_in"] + left_len, 3)})
        if right_len > 0.05:
            out.append({**s, "source_in": round(s["source_out"] - right_len, 3)})
    if not out:
        raise ValueError("Damit waere das ganze Video weg.")
    return _apply(doc, out)

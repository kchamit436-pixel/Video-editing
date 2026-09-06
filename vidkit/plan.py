"""Schritt 3: Schnittplan bauen.

Eingang: transcript.json + style.json.  Ausgang: edit.json.
Alle Zahlen (Dichten, Dauern, Schwellen) kommen aus style.json — hier steht nur
die Logik, die sie anwendet.
"""
from __future__ import annotations

import datetime as _dt
import random
import statistics
from pathlib import Path
from typing import Any

from . import german
from .config import Style
from .editdoc import SCHEMA_VERSION, save_edit, sort_all
from .paths import Project
from .util import clamp, die, ok, read_json, step, warn


# --------------------------------------------------------------------------- #
# Zeitachse: Quelle -> Ausgabe
# --------------------------------------------------------------------------- #
class Timeline:
    """Bildet Quellzeit auf Ausgabezeit ab, nachdem Pausen/Fueller entfernt sind."""

    def __init__(self, segments: list[dict]):
        self.segments = segments

    @property
    def duration(self) -> float:
        return self.segments[-1]["t_out"] if self.segments else 0.0

    def to_out(self, src_t: float) -> float | None:
        for seg in self.segments:
            if seg["source_in"] - 1e-6 <= src_t <= seg["source_out"] + 1e-6:
                return seg["t_in"] + (src_t - seg["source_in"])
        return None

    def to_out_clamped(self, src_t: float) -> float:
        """Wie to_out, aber Zeiten in geschnittenen Luecken rutschen auf die Kante."""
        if not self.segments:
            return 0.0
        if src_t <= self.segments[0]["source_in"]:
            return 0.0
        for seg in self.segments:
            if src_t <= seg["source_out"]:
                if src_t >= seg["source_in"]:
                    return seg["t_in"] + (src_t - seg["source_in"])
                return seg["t_in"]
        return self.segments[-1]["t_out"]

    @property
    def cut_points(self) -> list[float]:
        """Ausgabezeiten, an denen ein Schnitt sitzt (ohne Anfang)."""
        return [s["t_in"] for s in self.segments[1:]]


def build_segments(words: list[dict], style: Style, source_duration: float) -> tuple[list[dict], dict]:
    """Pausen und Fuellwoerter herausschneiden."""
    cfg = style.section("cuts")
    sil = cfg.get("silence_cut", {})
    enabled = bool(sil.get("enabled", True))
    min_pause = float(sil.get("min_pause_seconds", 0.45))
    keep_head = float(sil.get("keep_head_seconds", 0.08))
    keep_tail = float(sil.get("keep_tail_seconds", 0.12))
    cut_fillers = bool(cfg.get("cut_filler_words", True))
    fillers = cfg.get("filler_words", german.FILLERS_DEFAULT)
    min_shot = float(cfg.get("min_shot_seconds", 0.0))

    stats = {"pause_cuts": 0, "filler_cuts": 0, "removed_seconds": 0.0}
    if not words:
        return ([{"id": "seg000", "source_in": 0.0, "source_out": source_duration,
                  "t_in": 0.0, "t_out": source_duration, "reason": "voll"}], stats)

    # Bereiche, die entfernt werden
    drops: list[tuple[float, float, str]] = []
    if cut_fillers:
        for w in words:
            if german.is_filler(w["w"], fillers):
                drops.append((w["start"] - 0.04, w["end"] + 0.04, "fueller"))
                stats["filler_cuts"] += 1

    if enabled:
        prev_end = None
        for w in words:
            if prev_end is not None and w["start"] - prev_end >= min_pause:
                a = prev_end + keep_tail
                b = w["start"] - keep_head
                if b - a > 0.05:
                    drops.append((a, b, "pause"))
                    stats["pause_cuts"] += 1
            prev_end = max(prev_end or 0.0, w["end"])
        # Vorlauf vor dem ersten und Nachlauf nach dem letzten Wort
        first, last = words[0]["start"], words[-1]["end"]
        if first - keep_head > 0.15:
            drops.append((0.0, first - keep_head, "vorlauf"))
        if source_duration - (last + keep_tail) > 0.15:
            drops.append((last + keep_tail, source_duration, "nachlauf"))

    drops.sort()
    merged: list[tuple[float, float, str]] = []
    for a, b, why in drops:
        if merged and a <= merged[-1][1] + 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b), merged[-1][2])
        else:
            merged.append((a, b, why))

    # Splitter aufraeumen: bleibt zwischen zwei Schnitten nur ein Rest ohne Wort
    # uebrig (Padding-Reste rund um Fuellwoerter), kommt der Rest mit weg.
    min_keep = float(sil.get("min_keep_seconds", 0.25))
    if min_keep > 0 and len(merged) > 1:
        spans = [(w["start"], w["end"]) for w in words]
        cleaned = [merged[0]]
        for a, b, why in merged[1:]:
            gap_a, gap_b = cleaned[-1][1], a
            has_word = any(ws < gap_b and we > gap_a for ws, we in spans)
            if (gap_b - gap_a) < min_keep and not has_word:
                cleaned[-1] = (cleaned[-1][0], b, cleaned[-1][2])
            else:
                cleaned.append((a, b, why))
        merged = cleaned

    segments: list[dict] = []
    cursor = 0.0
    out_t = 0.0
    for a, b, why in merged:
        a = max(0.0, min(a, source_duration))
        b = max(0.0, min(b, source_duration))
        if a > cursor + 1e-3:
            dur = a - cursor
            segments.append({"id": f"seg{len(segments):03d}", "source_in": round(cursor, 3),
                             "source_out": round(a, 3), "t_in": round(out_t, 3),
                             "t_out": round(out_t + dur, 3), "reason": "sprache"})
            out_t += dur
        stats["removed_seconds"] += max(0.0, b - a)
        cursor = max(cursor, b)
    if cursor < source_duration - 1e-3:
        dur = source_duration - cursor
        segments.append({"id": f"seg{len(segments):03d}", "source_in": round(cursor, 3),
                         "source_out": round(source_duration, 3), "t_in": round(out_t, 3),
                         "t_out": round(out_t + dur, 3), "reason": "sprache"})

    # Zu kurze Schnipsel mit dem Vorgaenger verschmelzen
    if min_shot > 0 and len(segments) > 1:
        fixed: list[dict] = []
        for seg in segments:
            if fixed and (seg["source_out"] - seg["source_in"]) < min_shot \
                    and abs(fixed[-1]["source_out"] - seg["source_in"]) < 1e-6:
                fixed[-1]["source_out"] = seg["source_out"]
            else:
                fixed.append(seg)
        # Ausgabezeiten neu aufbauen
        out_t = 0.0
        for i, seg in enumerate(fixed):
            dur = seg["source_out"] - seg["source_in"]
            seg["id"] = f"seg{i:03d}"
            seg["t_in"] = round(out_t, 3)
            seg["t_out"] = round(out_t + dur, 3)
            out_t += dur
        segments = fixed

    stats["removed_seconds"] = round(stats["removed_seconds"], 2)
    return segments, stats


# --------------------------------------------------------------------------- #
# Elemente
# --------------------------------------------------------------------------- #
def sentence_end_ids(transcript: dict) -> set[int]:
    """Wort-Indizes, nach denen ein Satz endet.

    Zwei Quellen: Satzzeichen (Whisper setzt sie meist) und die Segmentgrenzen
    aus dem Transkript (greift auch bei Transkripten ohne Interpunktion).
    """
    words = transcript.get("words", [])
    ends = {w["i"] for w in words if german.ends_sentence(w["w"])}
    last_of_segment: dict[Any, int] = {}
    for w in words:
        if "segment" in w:
            last_of_segment[w["segment"]] = w["i"]
    ends |= set(last_of_segment.values())
    if words:
        ends.add(words[-1]["i"])
    return ends
def _mapped_words(words: list[dict], tl: Timeline, fillers: list[str]) -> list[dict]:
    """Woerter auf die Ausgabezeit umrechnen; herausgeschnittene fliegen raus."""
    out = []
    for w in words:
        if german.is_filler(w["w"], fillers):
            continue
        t_in = tl.to_out(w["start"])
        t_out = tl.to_out(w["end"])
        if t_in is None or t_out is None or t_out <= t_in:
            continue
        out.append({**w, "t_in": round(t_in, 3), "t_out": round(t_out, 3)})
    return out


def build_captions(mwords: list[dict], style: Style, ends: set[int]) -> list[dict]:
    cfg = style.section("captions")
    if not cfg.get("enabled", True):
        return []
    per_group = max(1, int(cfg.get("words_per_group", 3)))
    max_len = float(cfg.get("max_group_seconds", 1.6))
    min_len = float(cfg.get("min_group_seconds", 0.3))

    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in mwords:
        if cur:
            too_long = (w["t_out"] - cur[0]["t_in"]) > max_len
            gap = w["t_in"] - cur[-1]["t_out"] > 0.35
            if len(cur) >= per_group or too_long or gap:
                groups.append(cur)
                cur = []
        cur.append(w)
        if w["i"] in ends:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)

    captions = []
    for i, g in enumerate(groups):
        t_in = g[0]["t_in"]
        t_out = max(g[-1]["t_out"], t_in + min_len)
        captions.append({
            "id": f"cap{i:03d}",
            "t_in": round(t_in, 3),
            "t_out": round(t_out, 3),
            "text": " ".join(german.clean(w["w"]) for w in g),
            "words": [{"w": german.clean(w["w"]), "t_in": round(w["t_in"] - t_in, 3),
                       "t_out": round(w["t_out"] - t_in, 3)} for w in g],
            "style": "captions",
            "enabled": True,
        })
    return captions


def _word_features(words: list[dict]) -> tuple[float, list[float]]:
    durs, chars = [], []
    for w in words:
        n = len(german.clean(w["w"]))
        if n:
            durs.append((w["end"] - w["start"]) / n)
            chars.append(n)
    median_char_time = statistics.median(durs) if durs else 0.06
    pauses = []
    prev_end = None
    for w in words:
        pauses.append(0.0 if prev_end is None else max(0.0, w["start"] - prev_end))
        prev_end = w["end"]
    return median_char_time, pauses


def build_overlays(words: list[dict], mwords: list[dict], tl: Timeline, style: Style,
                   ends: set[int]) -> list[dict]:
    cfg = style.section("overlays")
    if not cfg.get("enabled", True):
        return []
    duration = tl.duration
    target = max(0, round(float(cfg.get("per_10s", 1.2)) * duration / 10.0))
    if target == 0:
        return []
    hold = float(cfg.get("hold_seconds", 0.7))
    min_gap = float(cfg.get("min_gap_seconds", 1.2))
    span = max(1, int(cfg.get("words_per_overlay", 2)))

    median_char_time, pauses = _word_features(words)
    pos_in_sentence = 0
    scored: list[tuple[float, int]] = []
    by_index = {w["i"]: w for w in mwords}
    for idx, w in enumerate(words):
        s = german.keyword_score(
            w["w"], position_in_sentence=pos_in_sentence,
            duration=w["end"] - w["start"], median_char_time=median_char_time,
            pause_before=pauses[idx],
        )
        pos_in_sentence = 0 if w["i"] in ends else pos_in_sentence + 1
        if s > 0 and w["i"] in by_index:
            scored.append((s, idx))
    scored.sort(reverse=True)

    chosen: list[dict] = []
    used_spans: list[tuple[float, float]] = []
    for score, idx in scored:
        if len(chosen) >= target:
            break
        # Phrase aus bis zu `span` aufeinanderfolgenden, sinntragenden Woertern
        phrase_idx = [idx]
        j = idx + 1
        while len(phrase_idx) < span and j < len(words):
            nxt = words[j]
            if german.is_filler(nxt["w"]) or nxt["i"] not in by_index:
                break
            if german.is_stopword(nxt["w"]) and len(phrase_idx) >= 1:
                break
            phrase_idx.append(j)
            if nxt["i"] in ends:
                break
            j += 1
        mapped = [by_index[words[k]["i"]] for k in phrase_idx if words[k]["i"] in by_index]
        if not mapped:
            continue
        t_in = mapped[0]["t_in"]
        t_out = max(mapped[-1]["t_out"], t_in + hold)
        if any(not (t_out + min_gap <= a or t_in - min_gap >= b) for a, b in used_spans):
            continue
        used_spans.append((t_in, t_out))
        chosen.append({
            "t_in": round(t_in, 3), "t_out": round(min(t_out, duration), 3),
            "text": " ".join(german.clean(words[k]["w"]) for k in phrase_idx),
            "score": round(score, 2),
        })

    chosen.sort(key=lambda c: c["t_in"])
    return [{"id": f"ovl{i:03d}", **c, "style": "overlays", "enabled": True}
            for i, c in enumerate(chosen)]


def build_zooms(words: list[dict], mwords: list[dict], tl: Timeline, style: Style,
                ends: set[int], rng: random.Random) -> list[dict]:
    cfg = style.section("motion").get("zoom", {})
    if not cfg.get("enabled", True):
        return []
    duration = tl.duration
    max_n = max(0, int(round(float(cfg.get("max_per_10s", 2.0)) * duration / 10.0)))
    if max_n == 0:
        return []
    dur = float(cfg.get("duration", 0.45))
    lo = float(cfg.get("min_scale", 1.03))
    hi = float(cfg.get("max_scale", 1.08))
    easing = cfg.get("easing", "easeOutCubic")
    direction = cfg.get("direction", "in")

    median_char_time, pauses = _word_features(words)
    by_index = {w["i"]: w for w in mwords}
    cands: list[tuple[float, float]] = []   # (prioritaet, t_in)
    sentence_start = True
    for idx, w in enumerate(words):
        if w["i"] in by_index:
            t = by_index[w["i"]]["t_in"]
            if sentence_start and cfg.get("on_sentence_start", True):
                cands.append((2.0, t))
            elif cfg.get("on_emphasis", True):
                n = max(1, len(german.clean(w["w"])))
                stretch = ((w["end"] - w["start"]) / n) / median_char_time if median_char_time else 1
                if stretch > 1.25 or pauses[idx] > 0.3:
                    cands.append((1.0 + min(1.0, stretch - 1.0), t))
        sentence_start = w["i"] in ends

    cands.sort(reverse=True)
    picked: list[float] = []
    for _prio, t in cands:
        if len(picked) >= max_n:
            break
        if all(abs(t - p) > dur * 1.6 for p in picked):
            picked.append(t)
    picked.sort()

    zooms = []
    for i, t in enumerate(picked):
        scale = round(rng.uniform(lo, hi), 4)
        frm, to = (1.0, scale) if direction == "in" else (scale, 1.0)
        zooms.append({"id": f"zom{i:03d}", "t_in": round(t, 3),
                      "t_out": round(min(t + dur, duration), 3),
                      "from": frm, "to": to, "easing": easing, "enabled": True})
    return zooms


def build_broll(words: list[dict], mwords: list[dict], tl: Timeline, style: Style,
                overlays: list[dict]) -> list[dict]:
    cfg = style.section("broll")
    if not cfg.get("enabled", True):
        return []
    duration = tl.duration
    n = max(0, int(round(float(cfg.get("per_10s", 0.8)) * duration / 10.0)))
    if n == 0:
        return []
    lo = float(cfg.get("min_seconds", 1.2))
    hi = float(cfg.get("max_seconds", 2.5))
    ratio = float(cfg.get("ratio", 0.22))
    budget = ratio * duration
    per_slot = clamp(budget / max(1, n), lo, hi)
    queries_per_slot = int(cfg.get("queries_per_slot", 3))

    # Slots gleichmaessig verteilen, aber nicht auf einer grossen Einblendung
    slots: list[dict] = []
    step_t = duration / (n + 1)
    for k in range(1, n + 1):
        t_in = k * step_t - per_slot / 2
        t_in = clamp(t_in, 0.0, max(0.0, duration - per_slot))
        t_out = min(duration, t_in + per_slot)
        if any(not (t_out <= o["t_in"] or t_in >= o["t_out"]) for o in overlays):
            shifted = None
            for o in overlays:
                if not (t_out <= o["t_in"] or t_in >= o["t_out"]):
                    cand = o["t_out"] + 0.1
                    if cand + per_slot <= duration:
                        shifted = cand
                    break
            if shifted is None:
                continue
            t_in, t_out = shifted, min(duration, shifted + per_slot)
        window = [w["w"] for w in mwords if w["t_out"] > t_in - 1.5 and w["t_in"] < t_out + 1.5]
        queries = german.broll_queries(window, limit=queries_per_slot)
        slots.append({
            "id": f"brl{len(slots):03d}",
            "t_in": round(t_in, 3), "t_out": round(t_out, 3),
            "queries": queries or ["lifestyle"],
            "selection": None, "candidates": [], "file": None, "enabled": True,
        })
    return slots


def build_motion_graphics(mwords: list[dict], tl: Timeline, style: Style,
                          overlays: list[dict], ends: set[int]) -> list[dict]:
    cfg = style.section("motion_graphics")
    if not cfg.get("enabled", True):
        return []
    duration = tl.duration
    n = max(0, int(round(float(cfg.get("per_10s", 0.3)) * duration / 10.0)))
    if n == 0:
        return []
    dur = float(cfg.get("duration", 0.8))
    # An Satzenden platzieren, dort sitzt eine Aussage fertig im Ohr.
    marks = [w["t_out"] for w in mwords if w["i"] in ends]
    marks = [e for e in marks if e + dur < duration]
    picked: list[float] = []
    if marks:
        stride = max(1, len(marks) // n)
        for k in range(0, len(marks), stride):
            if len(picked) >= n:
                break
            t = marks[k] + 0.05
            if all(abs(t - p) > dur * 2 for p in picked):
                picked.append(t)
    out = []
    for i, t in enumerate(picked):
        near = [o["text"] for o in overlays if abs(o["t_in"] - t) < 3.0]
        out.append({
            "id": f"mgr{i:03d}", "t_in": round(t, 3), "t_out": round(min(t + dur, duration), 3),
            "template": cfg.get("template", "white_screen"),
            "text": (near[0] if near else ""), "enabled": True,
        })
    return out


def build_sfx(tl: Timeline, style: Style, overlays: list[dict], zooms: list[dict],
              rng: random.Random) -> list[dict]:
    cfg = style.section("audio").get("sfx", {})
    if not cfg.get("enabled", True):
        return []
    gain = float(cfg.get("gain_db_rel_voice", -12.0))
    min_gap = float(cfg.get("min_gap_seconds", 0.25))

    marks: list[tuple[float, str, list[str]]] = []

    def add(rule: str, times: list[float]) -> None:
        r = cfg.get(rule, {})
        if not r.get("enabled", False):
            return
        prob = float(r.get("probability", 1.0))
        cats = list(r.get("categories", [])) or ["pop"]
        off = float(r.get("offset_seconds", 0.0))
        for t in times:
            if rng.random() <= prob:
                marks.append((max(0.0, t + off), rule.replace("on_", ""), cats))

    add("on_cut", tl.cut_points)
    add("on_overlay", [o["t_in"] for o in overlays])
    add("on_zoom", [z["t_in"] for z in zooms])

    marks.sort()
    out: list[dict] = []
    last_t = -99.0
    for t, reason, cats in marks:
        if t - last_t < min_gap:
            continue
        last_t = t
        out.append({
            "id": f"sfx{len(out):03d}", "t": round(t, 3), "reason": reason,
            "category": cats[rng.randrange(len(cats))] if len(cats) > 1 else cats[0],
            "categories": cats, "gain_db": gain, "file": None, "enabled": True,
        })
    return out


# --------------------------------------------------------------------------- #
def plan(project: Project, style: Style, *, seed: int | None = None,
         force: bool = False) -> Path:
    if not project.transcript.exists():
        die(f"{project.transcript} fehlt — erst 'vidkit transcribe' laufen lassen.")
    if project.edit.exists() and not force:
        die(f"{project.edit} existiert schon. Mit --force ueberschreiben "
            f"(deine Aenderungen gehen dabei verloren).")
    project.ensure_dirs()

    tr = read_json(project.transcript)
    words: list[dict] = tr.get("words", [])
    source_duration = float(tr.get("duration") or 0.0)
    if source_duration <= 0 and project.ingest_video.exists():
        from .ffmpeg import duration_of
        source_duration = duration_of(project.ingest_video)
    if not words:
        warn("Transkript ohne Woerter — es entstehen weder Captions noch Overlays.")

    rng = random.Random(seed if seed is not None else 20240501)
    step(f"Plane Schnitt: {len(words)} Woerter, {source_duration:.2f}s Quelle")

    segments, cut_stats = build_segments(words, style, source_duration)
    tl = Timeline(segments)
    fillers = style.get("cuts.filler_words", german.FILLERS_DEFAULT)
    mwords = _mapped_words(words, tl, fillers)

    ends = sentence_end_ids(tr)
    captions = build_captions(mwords, style, ends)
    overlays = build_overlays(words, mwords, tl, style, ends)
    zooms = build_zooms(words, mwords, tl, style, ends, rng)
    broll = build_broll(words, mwords, tl, style, overlays)
    mgfx = build_motion_graphics(mwords, tl, style, overlays, ends)
    sfx = build_sfx(tl, style, overlays, zooms, rng)

    doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "project": project.name,
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "style_file": str(style.path) if style.path else None,
        "seed": seed if seed is not None else 20240501,
        "source": str(project.ingest_video),
        "source_duration": round(source_duration, 3),
        "duration": round(tl.duration, 3),
        "format": {"width": style.width, "height": style.height, "fps": style.fps},
        "segments": segments,
        "captions": captions,
        "overlays": overlays,
        "zooms": zooms,
        "broll": broll,
        "motion_graphics": mgfx,
        "sfx": sfx,
        "stats": {
            **cut_stats,
            "cuts": max(0, len(segments) - 1),
            "cuts_per_10s": round(max(0, len(segments) - 1) / (tl.duration / 10), 2) if tl.duration else 0,
            "overlays_per_10s": round(len(overlays) / (tl.duration / 10), 2) if tl.duration else 0,
            "broll_ratio": round(sum(b["t_out"] - b["t_in"] for b in broll) / tl.duration, 3)
            if tl.duration else 0,
        },
    }
    save_edit(project, sort_all(doc))

    s = doc["stats"]
    ok(f"{project.edit.name}: {source_duration:.2f}s → {tl.duration:.2f}s "
       f"({s['removed_seconds']}s raus: {s['pause_cuts']} Pausen, {s['filler_cuts']} Fueller)")
    print(f"  Schnitte {s['cuts']} ({s['cuts_per_10s']}/10s) · Captions {len(captions)} · "
          f"Overlays {len(overlays)} ({s['overlays_per_10s']}/10s) · Zooms {len(zooms)} · "
          f"B-Roll {len(broll)} ({s['broll_ratio']:.0%}) · Motion {len(mgfx)} · SFX {len(sfx)}")
    if overlays:
        print("  Keywords: " + ", ".join(f"„{o['text']}\"" for o in overlays[:8]))
    return project.edit

"""Schritt 5: Sound-Effekte auf die Marker legen.

Quelle ist ausschliesslich die eigene Bibliothek unter assets/sfx/, sortiert
nach Kategorien. Kein Download, kein Kopieren aus Referenzvideos.

Die Auswahl ist seed-basiert und wird in die edit.json geschrieben — derselbe
Seed ergibt dieselbe Mischung, und einzelne Zuordnungen lassen sich von Hand
oder in der Weboberflaeche aendern.
"""
from __future__ import annotations

import json
import random
import re
import subprocess
from collections import deque
from pathlib import Path

from .config import Style
from .editdoc import load_edit, save_edit
from .paths import Project, repo_root, sfx_library
from .util import die, ok, read_json, step, warn, write_json

AUDIO_EXT = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}
CATEGORIES = ("whoosh", "impact", "pop", "riser", "sub", "click", "transition")
_MAXVOL = re.compile(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB")


def scan_library(base: Path | None = None) -> dict[str, list[Path]]:
    lib = base or sfx_library()
    out: dict[str, list[Path]] = {}
    if not lib.exists():
        return out
    for cat_dir in sorted(p for p in lib.iterdir() if p.is_dir()):
        files = sorted(f for f in cat_dir.rglob("*")
                       if f.is_file() and f.suffix.lower() in AUDIO_EXT)
        if files:
            out[cat_dir.name] = files
    return out


def _peak_db(path: Path, cache: dict) -> float:
    """Spitzenpegel einer Datei, gecacht — sonst misst jeder Lauf alles neu."""
    key = f"{path}:{path.stat().st_mtime_ns}"
    if key in cache:
        return cache[key]
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af", "volumedetect",
         "-f", "null", "-"], capture_output=True, text=True)
    m = _MAXVOL.search(proc.stderr or "")
    val = float(m.group(1)) if m else 0.0
    cache[key] = val
    return val


def assign_sfx(project: Project, style: Style, *, seed: int | None = None,
               reassign: bool = False) -> Path:
    doc = load_edit(project)
    markers = doc.get("sfx", [])
    if not markers:
        warn("Keine SFX-Marker in der edit.json — 'plan' setzt sie nach den Regeln "
             "in style.json (audio.sfx).")
        return project.edit

    lib = scan_library()
    if not lib:
        die(f"Keine Sounds gefunden in {sfx_library()}/.\n"
            f"  Lege deine Bibliothek nach Kategorien an: "
            f"{', '.join(c + '/' for c in CATEGORIES)}\n"
            f"  Zum Ausprobieren:  python tools/make_placeholder_sfx.py")

    cfg = style.section("audio").get("sfx", {})
    rel_gain = float(cfg.get("gain_db_rel_voice", -12.0))
    voice_peak = float(style.get("audio.voice_true_peak_db", -1.0))
    target_peak = voice_peak + rel_gain
    avoid_last = int(cfg.get("avoid_repeat_last", 3))

    rng = random.Random(seed if seed is not None else doc.get("seed", 0))
    recent: deque[str] = deque(maxlen=max(0, avoid_last))
    cache_file = sfx_library() / ".peaks.json"
    cache = read_json(cache_file) if cache_file.exists() else {}

    step(f"SFX: {len(markers)} Marker, Bibliothek {sum(len(v) for v in lib.values())} Dateien "
         f"in {len(lib)} Kategorien")

    assigned = 0
    missing_cats: set[str] = set()
    per_cat: dict[str, int] = {}
    for m in markers:
        if m.get("file") and not reassign:
            continue
        cats = [c for c in (m.get("categories") or [m.get("category")]) if c and c in lib]
        if not cats:
            missing_cats.update(c for c in (m.get("categories") or [m.get("category")]) if c)
            continue
        cat = m.get("category") if m.get("category") in cats else cats[rng.randrange(len(cats))]
        # Auswahl variieren: was zuletzt lief, kommt hinten an
        pool = [f for f in lib[cat] if str(f) not in recent] or list(lib[cat])
        choice = pool[rng.randrange(len(pool))]
        recent.append(str(choice))

        peak = _peak_db(choice, cache)
        m["category"] = cat
        m["file"] = str(choice.relative_to(repo_root()))
        m["gain_db"] = round(target_peak - peak, 2)
        m["source_peak_db"] = peak
        assigned += 1
        per_cat[cat] = per_cat.get(cat, 0) + 1

    write_json(cache_file, cache)
    save_edit(project, doc)

    if missing_cats:
        warn(f"Keine Dateien fuer Kategorie(n): {', '.join(sorted(missing_cats))} — "
             f"diese Marker bleiben stumm.")
    ok(f"{assigned} Marker belegt "
       f"({', '.join(f'{k}×{v}' for k, v in sorted(per_cat.items())) or '–'}), "
       f"Zielpegel {target_peak:.1f} dBFS ({rel_gain:+.0f} dB zur Stimme)")
    return project.edit

#!/usr/bin/env python3
"""Prueft 'vidkit learn' gegen die bekannten Sollwerte des Referenz-Fixtures.

  python tests/make_reference.py     # Referenz + Sollwerte erzeugen
  python tests/check_learn.py        # messen und vergleichen

Die Toleranzen sind bewusst weit: gemessen wird aus dem fertigen Bild, ohne
Kenntnis der Erzeugung. Es geht darum, grobe Fehler zu finden — nicht darum,
auf drei Stellen zu treffen.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"


def main() -> int:
    ref = FIX / "sample_reference_ad.mp4"
    truth_file = FIX / "sample_reference_truth.json"
    if not ref.exists() or not truth_file.exists():
        sys.exit("Fixture fehlt — erst 'python tests/make_reference.py' laufen lassen.")
    truth = json.loads(truth_file.read_text())

    out = Path(tempfile.mkdtemp(prefix="vidkit-check-")) / "style.json"
    proc = subprocess.run([sys.executable, "-m", "vidkit", "learn", str(ref), "-o", str(out)],
                          capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        sys.exit(f"learn fehlgeschlagen:\n{proc.stderr[-2000:]}")
    st = json.loads(out.read_text())
    meas = json.loads((out.with_name(out.stem + ".measurements.json")).read_text())

    def g(dotted: str, src: dict):
        node = src
        for part in dotted.split("."):
            node = node.get(part, {}) if isinstance(node, dict) else {}
        return node if not isinstance(node, dict) or node else None

    # (Bezeichnung, gemessen, soll, Toleranz relativ, Toleranz absolut)
    checks = [
        ("Einstellungen",      meas["cuts"]["count"],               truth["shots"],                 0.0,  0),
        ("Schnitte/10s",       st["cuts"]["cuts_per_10s"],          truth["cuts_per_10s"],          0.15, 0.3),
        ("mittlere Laenge",    st["cuts"]["avg_shot_seconds"],      truth["avg_shot_seconds"],      0.15, 0.2),
        ("kuerzeste Laenge",   meas["cuts"]["min"],                 truth["min_shot_seconds"],      0.20, 0.2),
        ("Zoomfahrten",        meas["motion"]["count"],             truth["zoom_moves"],            0.0,  1),
        ("Zoomdauer",          st["motion"]["zoom"]["duration"],    truth["zoom_duration"],         0.35, 0.15),
        ("Zoom max",           st["motion"]["zoom"]["max_scale"],   truth["zoom_max_scale"],        0.06, 0.05),
        ("Overlay-Groesse",    st["overlays"]["font_size_rel"],     truth["overlay_font_size_rel"], 0.30, 0.02),
        ("Overlay-Position y", st["overlays"]["position"]["y_rel"], truth["overlay_y_rel"],         0.20, 0.06),
        ("Caption-Groesse",    st["captions"]["font_size_rel"],     truth["caption_font_size_rel"], 0.30, 0.01),
        ("Caption-Position y", st["captions"]["position"]["y_rel"], truth["caption_y_rel"],         0.15, 0.05),
    ]
    ok = True
    print(f"\n{'Messwert':<22}{'gemessen':>12}{'soll':>12}   Ergebnis")
    print("─" * 62)
    for label, got, want, rel, absolute in checks:
        got_f, want_f = float(got), float(want)
        tol = max(abs(want_f) * rel, absolute)
        good = abs(got_f - want_f) <= tol
        ok &= good
        print(f"{label:<22}{got_f:>12.3f}{want_f:>12.3f}   "
              f"{'ok' if good else 'ABWEICHUNG'} (±{tol:.3f})")

    # Ja/Nein-Aussagen
    bools = [
        ("Versalschrift erkannt", st["overlays"]["uppercase"], truth["uppercase"]),
        ("Kontur erkannt",        st["captions"]["stroke"]["enabled"], True),
        ("Musik erkannt",         st["audio"]["music"]["present"], truth["music_present"]),
        ("SFX an Schnitten",      st["audio"]["sfx"]["on_cut"]["enabled"], truth["sfx_on_every_cut"]),
        ("SFX an Einblendungen",  st["audio"]["sfx"]["on_overlay"]["enabled"],
         truth["sfx_on_every_overlay"]),
        ("Zoomrichtung hinein",   st["motion"]["zoom"]["direction"] == "in", True),
    ]
    print("─" * 62)
    for label, got, want in bools:
        good = bool(got) == bool(want)
        ok &= good
        print(f"{label:<22}{str(bool(got)):>12}{str(bool(want)):>12}   "
              f"{'ok' if good else 'ABWEICHUNG'}")
    print("─" * 62)
    print(("Alle Messungen im Rahmen." if ok else
           "Mindestens eine Messung liegt ausserhalb der Toleranz.") + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prueft die Schnittoperationen: rutscht wirklich alles korrekt nach?

Gebaut auf einem Plan mit bekannten Zahlen, damit jede Erwartung nachrechenbar
im Skript steht.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vidkit.edits import (delete_range, delete_segment, duration_of,  # noqa: E402
                          split_segment, trim_segment)


def doc_fixture() -> dict:
    """Drei Passagen à 4 s (Quelle 0-4, 6-10, 12-16) → Ausgabe 0-4, 4-8, 8-12."""
    return {
        "schema_version": 1,
        "segments": [
            {"id": "seg000", "source_in": 0.0, "source_out": 4.0, "t_in": 0.0, "t_out": 4.0},
            {"id": "seg001", "source_in": 6.0, "source_out": 10.0, "t_in": 4.0, "t_out": 8.0},
            {"id": "seg002", "source_in": 12.0, "source_out": 16.0, "t_in": 8.0, "t_out": 12.0},
        ],
        "captions": [
            {"id": "cap000", "t_in": 0.5, "t_out": 2.5, "text": "erste",
             "words": [{"w": "erste", "t_in": 0.0, "t_out": 2.0}]},
            {"id": "cap001", "t_in": 5.0, "t_out": 7.0, "text": "zweite",
             "words": [{"w": "zweite", "t_in": 0.0, "t_out": 2.0}]},
            {"id": "cap002", "t_in": 9.0, "t_out": 11.0, "text": "dritte",
             "words": [{"w": "dritte", "t_in": 0.0, "t_out": 2.0}]},
            # ragt spaeter genau in den Schnitt hinein
            {"id": "cap003", "t_in": 2.6, "t_out": 3.6, "text": "randlage",
             "words": [{"w": "randlage", "t_in": 0.0, "t_out": 1.0}]},
        ],
        "overlays": [{"id": "ovl000", "t_in": 6.0, "t_out": 7.0, "text": "MITTE"}],
        "zooms": [], "broll": [], "motion_graphics": [],
        "sfx": [{"id": "sfx000", "t": 1.0}, {"id": "sfx001", "t": 5.5},
                {"id": "sfx002", "t": 9.5}],
    }


def check(label: str, got, want) -> bool:
    good = got == want
    print(f"  {'ok ' if good else 'FEHLER'} {label:<44} {got!r}"
          + ("" if good else f"   erwartet {want!r}"))
    return good


def main() -> int:
    ok = True
    print("\nMittlere Passage loeschen (seg001, 4 s)")
    d = doc_fixture()
    stats = delete_segment(d, "seg001")
    ok &= check("Gesamtlaenge 12 s → 8 s", duration_of(d["segments"]), 8.0)
    ok &= check("Captions: mittlere ist weg", [c["id"] for c in d["captions"]],
                ["cap000", "cap003", "cap002"])
    ok &= check("dritte Caption rutscht 4 s nach vorn",
                (d["captions"][2]["t_in"], d["captions"][2]["t_out"]), (5.0, 7.0))
    ok &= check("erste Caption bleibt liegen",
                (d["captions"][0]["t_in"], d["captions"][0]["t_out"]), (0.5, 2.5))
    ok &= check("Overlay in der Passage ist weg", d["overlays"], [])
    ok &= check("Sounds: mittlerer weg, letzter rutscht",
                [(s["id"], s["t"]) for s in d["sfx"]], [("sfx000", 1.0), ("sfx002", 5.5)])
    ok &= check("Zaehlung stimmt", (stats["removed"], stats["moved"]), (3, 2))

    print("\nSegment teilen (seg000 bei t=2)")
    d = doc_fixture()
    split_segment(d, "seg000", 2.0)
    ok &= check("aus 3 Segmenten werden 4", len(d["segments"]), 4)
    ok &= check("Gesamtlaenge unveraendert", duration_of(d["segments"]), 12.0)
    ok &= check("Quellzeiten der Haelften",
                (d["segments"][0]["source_out"], d["segments"][1]["source_in"]), (2.0, 2.0))
    ok &= check("Caption unveraendert",
                (d["captions"][0]["t_in"], d["captions"][0]["t_out"]), (0.5, 2.5))

    print("\nPassage kuerzen (seg000 endet 1 s frueher)")
    d = doc_fixture()
    trim_segment(d, "seg000", source_out=3.0)
    ok &= check("Gesamtlaenge 12 s → 11 s", duration_of(d["segments"]), 11.0)
    ok &= check("Caption ganz im Rest bleibt unangetastet",
                (d["captions"][0]["t_in"], d["captions"][0]["t_out"]), (0.5, 2.5))
    rand = next(c for c in d["captions"] if c["id"] == "cap003")
    ok &= check("Caption die in den Schnitt ragt wird gekuerzt",
                (rand["t_in"], rand["t_out"]), (2.6, 3.0))
    ok &= check("ihre Wortzeiten werden mitskaliert",
                round(rand["words"][0]["t_out"], 2), 0.4)
    zweite = next(c for c in d["captions"] if c["id"] == "cap001")
    ok &= check("spaetere Caption rutscht 1 s vor",
                (zweite["t_in"], zweite["t_out"]), (4.0, 6.0))

    print("\nBereich quer ueber Segmente wegschneiden (t 3-5)")
    d = doc_fixture()
    delete_range(d, 3.0, 5.0)
    ok &= check("Gesamtlaenge 12 s → 10 s", duration_of(d["segments"]), 10.0)
    ok &= check("Caption vor dem Schnitt unveraendert",
                (d["captions"][0]["t_in"], d["captions"][0]["t_out"]), (0.5, 2.5))
    zweite = next(c for c in d["captions"] if c["id"] == "cap001")
    ok &= check("Caption nach dem Schnitt rutscht 2 s vor",
                (zweite["t_in"], zweite["t_out"]), (3.0, 5.0))

    print("\nGrenzfaelle")
    d = {"schema_version": 1, "segments": [dict(doc_fixture()["segments"][0])],
         "captions": [], "overlays": [], "zooms": [], "broll": [],
         "motion_graphics": [], "sfx": []}
    try:
        delete_segment(d, "seg000")
        ok &= check("letztes Segment loeschen wird abgelehnt", "kein Fehler", "ValueError")
    except ValueError:
        ok &= check("letztes Segment loeschen wird abgelehnt", "ValueError", "ValueError")

    print("\n" + ("Alle Schnittoperationen korrekt." if ok else "FEHLER gefunden.") + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

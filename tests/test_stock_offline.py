#!/usr/bin/env python3
"""Prueft den stock-Ablauf ohne Netz: Suche und Download werden eingespeist.

Damit ist alles ausser dem eigentlichen HTTP-Aufruf abgedeckt — Antwort
auswerten, Kandidaten ablegen, in die edit.json schreiben, Auswahl aufloesen.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vidkit.editdoc import load_edit, save_edit  # noqa: E402
from vidkit.paths import Project  # noqa: E402
from vidkit.stock import fetch_stock, resolve_selection  # noqa: E402


def fake_search(query, key, per_page, orientation):
    return {"videos": [
        {"id": 1000 + i, "duration": 8, "url": f"https://example/{query}/{i}",
         "user": {"name": "Testperson"},
         "video_files": [
             {"link": f"https://example/{query}/{i}/sd.mp4", "width": 640, "height": 360},
             {"link": f"https://example/{query}/{i}/hd.mp4", "width": 1080, "height": 1920},
         ]}
        for i in range(per_page)]}


def fake_download(url, dest: Path) -> Path:
    """Statt Netz: lokal einen kurzen Clip erzeugen."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"testsrc2=s=1080x1920:r=30:d=3", "-c:v", "libx264",
                    "-crf", "30", "-pix_fmt", "yuv420p", str(dest)], check=True)
    return dest


def main() -> int:
    project = Project.open("demo")
    doc = load_edit(project)
    if not doc.get("broll"):
        sys.exit("Kein B-Roll-Slot in projects/demo/edit.json — erst 'vidkit plan' laufen lassen.")

    fetch_stock(project, per_slot=3, search=fake_search, download=fake_download)
    doc = load_edit(project)
    slot = doc["broll"][0]
    assert len(slot["candidates"]) == 3, slot["candidates"]
    assert all(Path(project.root / c["file"]).exists() for c in slot["candidates"])
    # Es wird bewusst nichts automatisch ausgewaehlt
    assert slot["selection"] is None and not slot["file"], "stock darf nicht selbst auswaehlen"
    print(f"  {len(slot['candidates'])} Kandidaten geladen, keine Auswahl getroffen  ✓")
    # Groesste Portraet-Datei bevorzugt
    assert slot["candidates"][0]["height"] == 1920, slot["candidates"][0]
    print("  Portraet-Variante bevorzugt (1080x1920)  ✓")

    slot["selection"] = slot["candidates"][1]["id"]
    save_edit(project, doc)
    doc = load_edit(project)
    assert resolve_selection(doc) == 1
    assert doc["broll"][0]["file"] == slot["candidates"][1]["file"]
    print(f"  Auswahl {slot['selection']} → {doc['broll'][0]['file']}  ✓")
    save_edit(project, doc)
    print("stock: alle Pruefungen bestanden (Netzzugriff eingespeist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Schritt 6 (optional): B-Roll-Kandidaten von Pexels laden.

Pro Slot werden mehrere Kandidaten heruntergeladen und in die edit.json
eingetragen. Ausgewaehlt wird nicht automatisch — das macht der Mensch, indem
er 'selection' auf eine Kandidaten-ID setzt (von Hand oder in 'vidkit serve').

Der einzige Netzdienst im ganzen Werkzeug. Ohne API-Key passiert nichts.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from .editdoc import load_edit, save_edit
from .paths import Project
from .util import die, ok, step, warn

API_SEARCH = "https://api.pexels.com/videos/search"
KEY_ENV = "PEXELS_API_KEY"
KEY_FILE = Path.home() / ".config" / "vidkit" / "pexels_key"


def api_key(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit.strip()
    env = os.environ.get(KEY_ENV)
    if env:
        return env.strip()
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip() or None
    return None


def _http_search(query: str, key: str, per_page: int, orientation: str) -> dict[str, Any]:
    import requests
    resp = requests.get(
        API_SEARCH, headers={"Authorization": key},
        params={"query": query, "per_page": per_page, "orientation": orientation,
                "size": "medium"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _http_download(url: str, dest: Path) -> Path:
    import requests
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
        tmp.replace(dest)
    return dest


def _best_file(video: dict, min_height: int = 1080) -> dict | None:
    """Portraet bevorzugen, sonst die groesste Datei unterhalb 4K."""
    files = [f for f in video.get("video_files", []) if f.get("link")]
    if not files:
        return None
    def score(f: dict) -> tuple:
        h = int(f.get("height") or 0)
        w = int(f.get("width") or 0)
        portrait = 1 if h >= w else 0
        big_enough = 1 if h >= min_height else 0
        return (portrait, big_enough, -abs(h - 1920))
    return sorted(files, key=score, reverse=True)[0]


def fetch_stock(project: Project, *, per_slot: int = 5, slot: str | None = None,
                key: str | None = None, orientation: str = "portrait",
                search: Callable[..., dict] | None = None,
                download: Callable[[str, Path], Path] | None = None) -> Path:
    """search/download sind einspeisbar — so laesst sich der Ablauf ohne Netz testen."""
    doc = load_edit(project)
    slots = [b for b in doc.get("broll", []) if b.get("enabled", True)]
    if slot:
        slots = [b for b in slots if b["id"] == slot]
    if not slots:
        warn("Keine B-Roll-Slots in der edit.json.")
        return project.edit

    search = search or _http_search
    download = download or _http_download
    k = api_key(key)
    if search is _http_search and not k:
        die(f"Kein Pexels-API-Key.\n"
            f"  export {KEY_ENV}=…   oder in {KEY_FILE} ablegen.\n"
            f"  Key gibt es kostenlos auf https://www.pexels.com/api/")

    project.stock_dir.mkdir(parents=True, exist_ok=True)
    step(f"Stock: {len(slots)} Slot(s), bis zu {per_slot} Kandidaten je Slot")

    total = 0
    for b in slots:
        queries = b.get("queries") or []
        if not queries:
            warn(f"{b['id']}: keine Suchbegriffe — uebersprungen.")
            continue
        dest_dir = project.stock_dir / b["id"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[dict] = []
        seen: set[int] = set()
        for query in queries:
            if len(candidates) >= per_slot:
                break
            try:
                data = search(query, k, per_slot, orientation)
            except Exception as exc:  # noqa: BLE001
                warn(f"{b['id']}: Suche nach '{query}' fehlgeschlagen: {exc}")
                continue
            for video in data.get("videos", []):
                if len(candidates) >= per_slot or video["id"] in seen:
                    continue
                seen.add(video["id"])
                f = _best_file(video)
                if not f:
                    continue
                dest = dest_dir / f"{video['id']}.mp4"
                try:
                    if not dest.exists():
                        download(f["link"], dest)
                except Exception as exc:  # noqa: BLE001
                    warn(f"{b['id']}: Download {video['id']} fehlgeschlagen: {exc}")
                    continue
                candidates.append({
                    "id": str(video["id"]),
                    "query": query,
                    "file": str(dest.relative_to(project.root)),
                    "width": f.get("width"), "height": f.get("height"),
                    "duration": video.get("duration"),
                    "page": video.get("url"),
                    "author": video.get("user", {}).get("name"),
                })
                total += 1
        b["candidates"] = candidates
        # Bereits getroffene Auswahl in einen Dateipfad aufloesen
        if b.get("selection"):
            hit = next((c for c in candidates if c["id"] == str(b["selection"])), None)
            if hit:
                b["file"] = hit["file"]
        print(f"  {b['id']}  {', '.join(queries)}  → {len(candidates)} Kandidaten "
              f"in {dest_dir.relative_to(project.root)}/")

    save_edit(project, doc)
    ok(f"{total} Clips geladen. Auswahl triffst du selbst: 'selection' in der edit.json "
       f"auf eine Kandidaten-ID setzen (oder in 'vidkit serve').")
    return project.edit


def resolve_selection(doc: dict) -> int:
    """selection → file. Wird von render aufgerufen, damit die Auswahl sofort greift."""
    n = 0
    for b in doc.get("broll", []):
        if b.get("file") or not b.get("selection"):
            continue
        hit = next((c for c in b.get("candidates", [])
                    if str(c.get("id")) == str(b["selection"])), None)
        if hit:
            b["file"] = hit["file"]
            n += 1
    return n

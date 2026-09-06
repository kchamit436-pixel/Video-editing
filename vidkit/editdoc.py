"""edit.json lesen/schreiben. Das ist der Schnittplan im Klartext — die Datei,
die ein Mensch zwischen 'plan' und 'render' anfassen darf."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .paths import Project
from .util import die, read_json, write_json

SCHEMA_VERSION = 1
ELEMENT_KINDS = ("captions", "overlays", "zooms", "broll", "motion_graphics", "sfx")


def load_edit(project: Project) -> dict[str, Any]:
    if not project.edit.exists():
        die(f"{project.edit} fehlt — erst 'vidkit plan' laufen lassen.")
    doc = read_json(project.edit)
    if doc.get("schema_version") != SCHEMA_VERSION:
        die(f"edit.json hat Schema-Version {doc.get('schema_version')}, erwartet {SCHEMA_VERSION}.")
    for kind in ELEMENT_KINDS:
        doc.setdefault(kind, [])
    doc.setdefault("segments", [])
    return doc


def save_edit(project: Project, doc: dict[str, Any]) -> Path:
    doc["schema_version"] = SCHEMA_VERSION
    return write_json(project.edit, doc)


def elements(doc: dict, kind: str) -> list[dict]:
    return [e for e in doc.get(kind, []) if e.get("enabled", True)]


def by_id(doc: dict, element_id: str) -> tuple[str, dict] | tuple[None, None]:
    for kind in ELEMENT_KINDS:
        for e in doc.get(kind, []):
            if e.get("id") == element_id:
                return kind, e
    return None, None


def timeline_duration(doc: dict) -> float:
    ends: list[float] = [float(s.get("t_out", 0.0)) for s in doc.get("segments", [])]
    return max(ends) if ends else float(doc.get("duration", 0.0))


def sort_all(doc: dict) -> dict:
    doc["segments"] = sorted(doc.get("segments", []), key=lambda s: s.get("t_in", 0.0))
    for kind in ELEMENT_KINDS:
        key = "t" if kind == "sfx" else "t_in"
        doc[kind] = sorted(doc.get(kind, []), key=lambda e: e.get(key, 0.0))
    return doc


def next_id(doc: dict, kind: str, prefix: str) -> str:
    used = {e.get("id", "") for e in doc.get(kind, [])}
    n = len(used)
    while f"{prefix}{n:03d}" in used:
        n += 1
    return f"{prefix}{n:03d}"


def iter_all(doc: dict) -> Iterable[tuple[str, dict]]:
    for kind in ELEMENT_KINDS:
        for e in doc.get(kind, []):
            yield kind, e

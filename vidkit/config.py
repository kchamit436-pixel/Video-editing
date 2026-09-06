"""style.json laden, mergen, abfragen.

Regel des Projekts: kein Stilwert steht im Code. Alles kommt aus style.json.
Die Defaults hier sind nur ein Sicherheitsnetz, falls ein Feld in einer
aelteren style.json fehlt.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .paths import Project, repo_root
from .util import die, read_json, warn


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class Style:
    """Dict-Wrapper mit Pfadzugriff: style.get('captions.font_size_rel', 0.04)."""

    def __init__(self, data: dict, path: Path | None = None):
        self.data = data
        self.path = path

    # -- Zugriff --------------------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def section(self, name: str) -> dict:
        v = self.get(name, {})
        return v if isinstance(v, dict) else {}

    def __getitem__(self, dotted: str) -> Any:
        v = self.get(dotted, _MISSING)
        if v is _MISSING:
            raise KeyError(dotted)
        return v

    # -- haeufig gebraucht ----------------------------------------------------
    @property
    def width(self) -> int:
        return int(self.get("format.width", 1080))

    @property
    def height(self) -> int:
        return int(self.get("format.height", 1920))

    @property
    def fps(self) -> int:
        return int(self.get("format.fps", 30))

    def rel_x(self, v: float) -> float:
        return v * self.width

    def rel_y(self, v: float) -> float:
        return v * self.height

    def px(self, rel: float) -> float:
        """Relative Groesse -> Pixel, immer auf die Bildhoehe bezogen."""
        return rel * self.height


_MISSING = object()


def default_style_path(project: Project | None = None) -> Path:
    """Projekt-eigene style.json schlaegt die globale."""
    if project is not None and project.local_style.exists():
        return project.local_style
    return repo_root() / "style.json"


def load_style(path: Path | None = None, project: Project | None = None) -> Style:
    p = Path(path) if path else default_style_path(project)
    if not p.exists():
        die(f"style.json nicht gefunden: {p}")
    try:
        data = read_json(p)
    except Exception as exc:  # noqa: BLE001
        die(f"style.json ist kein gueltiges JSON ({p}): {exc}")
    fallback = repo_root() / "style.json"
    if fallback.exists() and fallback != p:
        try:
            data = _deep_merge(read_json(fallback), data)
        except Exception:  # noqa: BLE001
            warn("Konnte Basis-style.json nicht mergen, nutze Datei wie sie ist.")
    return Style(data, p)

"""Projektpfade. Jeder Schritt schreibt sein Ergebnis in eine Datei in projects/<name>/."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Project:
    name: str
    root: Path

    @classmethod
    def open(cls, name: str, base: Path | None = None) -> "Project":
        base = base or (repo_root() / "projects")
        root = base / name
        root.mkdir(parents=True, exist_ok=True)
        return cls(name=name, root=root)

    # --- Ergebnisdateien der einzelnen Schritte -------------------------------
    @property
    def ingest_video(self) -> Path:
        return self.root / "ingest.mp4"

    @property
    def ingest_meta(self) -> Path:
        return self.root / "ingest.json"

    @property
    def transcript(self) -> Path:
        return self.root / "transcript.json"

    @property
    def edit(self) -> Path:
        return self.root / "edit.json"

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def assets_manifest(self) -> Path:
        return self.assets_dir / "manifest.json"

    @property
    def stock_dir(self) -> Path:
        return self.root / "stock"

    @property
    def render_dir(self) -> Path:
        return self.root / "render"

    @property
    def base_video(self) -> Path:
        return self.render_dir / "base.mp4"

    @property
    def composite_video(self) -> Path:
        return self.render_dir / "composite.mp4"

    @property
    def mix_audio(self) -> Path:
        return self.render_dir / "mix.wav"

    @property
    def out_video(self) -> Path:
        return self.root / "out.mp4"

    @property
    def preview_video(self) -> Path:
        return self.root / "preview.mp4"

    @property
    def local_style(self) -> Path:
        return self.root / "style.json"

    def ensure_dirs(self) -> None:
        for d in (self.assets_dir, self.stock_dir, self.render_dir):
            d.mkdir(parents=True, exist_ok=True)


def sfx_library(base: Path | None = None) -> Path:
    return (base or repo_root()) / "assets" / "sfx"


def resolve_asset(project: Project, value: str) -> Path:
    """Pfad aus edit.json aufloesen: erst projektrelativ, dann repo-relativ.

    Assets und B-Roll liegen im Projektordner, die SFX-Bibliothek liegt im Repo —
    beide Schreibweisen sollen in der edit.json funktionieren.
    """
    p = Path(value)
    if p.is_absolute():
        return p
    local = project.root / p
    if local.exists():
        return local
    shared = repo_root() / p
    if shared.exists():
        return shared
    return local

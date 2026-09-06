"""Frames aus einem Video ziehen — einmal dekodieren, mehrfach benutzen."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np


@dataclass
class FrameSource:
    path: Path
    width: int
    height: int
    duration: float

    def iter_frames(self, fps: float, *, scale: int | None = None,
                    gray: bool = False) -> Iterator[tuple[float, np.ndarray]]:
        """Frames mit Zeitstempel liefern. scale = Zielbreite (Hoehe proportional)."""
        w, h = self.width, self.height
        if scale and scale < w:
            h = int(round(h * scale / w)) // 2 * 2
            w = scale
        pix = "gray" if gray else "rgb24"
        depth = 1 if gray else 3
        vf = f"fps={fps},scale={w}:{h}"
        proc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(self.path),
             "-vf", vf, "-pix_fmt", pix, "-f", "rawvideo", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        size = w * h * depth
        i = 0
        assert proc.stdout is not None
        while True:
            buf = proc.stdout.read(size)
            if not buf or len(buf) < size:
                break
            arr = np.frombuffer(buf, dtype=np.uint8)
            arr = arr.reshape((h, w) if gray else (h, w, 3))
            yield i / fps, arr
            i += 1
        proc.stdout.close()
        proc.wait()


def open_source(path: Path) -> FrameSource:
    from ..ffmpeg import probe_summary
    info = probe_summary(path)
    return FrameSource(path=Path(path), width=info["width"], height=info["height"],
                       duration=info["duration"])

"""ffmpeg/ffprobe-Huelle: Probing, Encoder-Wahl (VideoToolbox), Loudness, Audio-IO."""
from __future__ import annotations

import functools
import json
import platform
from pathlib import Path
from typing import Any, Sequence

from .util import die, debug, run, which


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not which(tool):
            die(f"{tool} nicht gefunden. Auf dem Mac:  brew install ffmpeg")


@functools.lru_cache(maxsize=1)
def _encoders() -> set[str]:
    proc = run(["ffmpeg", "-hide_banner", "-encoders"], check=False, desc="ffmpeg -encoders")
    names = set()
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0][:1] in "VAS":
            names.add(parts[1])
    return names


def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")


def has_encoder(name: str) -> bool:
    return name in _encoders()


def video_encoder_args(*, quality: str = "final", hw: bool = True,
                       bitrate: str | None = None) -> list[str]:
    """H.264-Encoder-Argumente. VideoToolbox wenn vorhanden, sonst libx264.

    quality: 'final' | 'intermediate' | 'preview'
    """
    if hw and has_encoder("h264_videotoolbox"):
        q = {"final": "65", "intermediate": "55", "preview": "45"}[quality]
        args = ["-c:v", "h264_videotoolbox", "-q:v", q, "-realtime", "0"]
        if bitrate:
            args = ["-c:v", "h264_videotoolbox", "-b:v", bitrate]
        return args + ["-pix_fmt", "yuv420p", "-tag:v", "avc1"]
    crf = {"final": "18", "intermediate": "16", "preview": "28"}[quality]
    preset = {"final": "medium", "intermediate": "veryfast", "preview": "veryfast"}[quality]
    return ["-c:v", "libx264", "-crf", crf, "-preset", preset, "-pix_fmt", "yuv420p"]


def alpha_encoder_args() -> list[str]:
    """Verlustfreier Codec mit Alphakanal fuer die HTML-Overlays."""
    if has_encoder("qtrle"):
        return ["-c:v", "qtrle", "-pix_fmt", "argb"]
    if has_encoder("prores_ks"):
        return ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    return ["-c:v", "png", "-pix_fmt", "rgba"]


def ffprobe(path: Path) -> dict[str, Any]:
    proc = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ], desc=f"ffprobe {Path(path).name}")
    return json.loads(proc.stdout or "{}")


def probe_summary(path: Path) -> dict[str, Any]:
    info = ffprobe(path)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = info.get("format", {})
    fps = 0.0
    if v and v.get("avg_frame_rate", "0/0") not in ("0/0", None):
        num, _, den = v["avg_frame_rate"].partition("/")
        try:
            fps = float(num) / float(den) if float(den) else 0.0
        except (ValueError, ZeroDivisionError):
            fps = 0.0
    return {
        "path": str(path),
        "duration": float(fmt.get("duration") or (v or {}).get("duration") or 0.0),
        "width": int((v or {}).get("width") or 0),
        "height": int((v or {}).get("height") or 0),
        "fps": round(fps, 3),
        "video_codec": (v or {}).get("codec_name"),
        "audio_codec": (a or {}).get("codec_name"),
        "sample_rate": int((a or {}).get("sample_rate") or 0) if a else 0,
        "channels": int((a or {}).get("channels") or 0) if a else 0,
        "has_audio": a is not None,
        "bitrate": int(fmt.get("bit_rate") or 0),
    }


def duration_of(path: Path) -> float:
    return probe_summary(path)["duration"]


def run_ffmpeg(args: Sequence[str], desc: str = "ffmpeg") -> None:
    run(["ffmpeg", "-hide_banner", "-nostdin", "-y", *args], desc=desc)


def measure_loudness(path: Path) -> dict[str, float]:
    """EBU-R128-Messung (loudnorm print_format=json), fuer den zweiten Pass."""
    proc = run([
        "ffmpeg", "-hide_banner", "-nostdin", "-i", str(path),
        "-af", "loudnorm=print_format=json", "-f", "null", "-",
    ], check=False, desc="loudnorm measure")
    err = proc.stderr or ""
    start = err.rfind("{")
    end = err.rfind("}")
    if start == -1 or end == -1:
        debug("loudnorm: keine JSON-Ausgabe gefunden")
        return {}
    try:
        raw = json.loads(err[start:end + 1])
    except json.JSONDecodeError:
        return {}
    out = {}
    for k, v in raw.items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            out[k] = v
    return out


def extract_audio(src: Path, dst: Path, *, sample_rate: int = 16000,
                  channels: int = 1) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-i", str(src), "-vn", "-ac", str(channels), "-ar", str(sample_rate),
        "-c:a", "pcm_s16le", str(dst),
    ], desc="Audio extrahieren")
    return dst


def read_audio_mono(src: Path, sample_rate: int = 16000):
    """Audio als float32-numpy-Array lesen (ohne Zwischendatei)."""
    import subprocess

    import numpy as np

    proc = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostdin", "-i", str(src), "-vn",
        "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-",
    ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if proc.returncode != 0 or not proc.stdout:
        return np.zeros(0, dtype="float32"), sample_rate
    return np.frombuffer(proc.stdout, dtype="<f4").copy(), sample_rate

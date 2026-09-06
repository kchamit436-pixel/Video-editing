"""Schritt 1: Rohvideo normalisieren.

Zuschnitt auf das Zielformat (Default 1080x1920), feste fps, Ton auf die in
style.json hinterlegte Lautheit (EBU R128, zweistufiges loudnorm).
"""
from __future__ import annotations

from pathlib import Path

from .config import Style
from .ffmpeg import (measure_loudness, probe_summary, run_ffmpeg, video_encoder_args)
from .paths import Project
from .util import die, ok, step, write_json


def _crop_scale_filter(style: Style, src: dict) -> str:
    """Formatfuellend zuschneiden, dann exakt auf die Zielgroesse."""
    w, h = style.width, style.height
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={w}:{h},setsar=1,fps={style.fps}"
    )


def ingest(project: Project, source: Path, style: Style, *, hw: bool = True,
           skip_loudnorm: bool = False) -> Path:
    source = Path(source)
    if not source.exists():
        die(f"Quelldatei nicht gefunden: {source}")
    project.ensure_dirs()
    src = probe_summary(source)
    if src["width"] == 0:
        die(f"Keine Videospur in {source}")
    step(f"Ingest: {source.name}  {src['width']}x{src['height']} @{src['fps']}fps, "
         f"{src['duration']:.1f}s")

    vf = _crop_scale_filter(style, src)
    target_lufs = float(style.get("audio.voice_lufs", -14.0))
    target_tp = float(style.get("audio.voice_true_peak_db", -1.0))

    measured: dict = {}
    af: str | None = None
    args: list[str] = []
    if not src["has_audio"]:
        # Stille Tonspur anlegen, damit alle spaeteren Schritte eine Audiospur haben.
        args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                 "-i", str(source), "-map", "1:v:0", "-map", "0:a:0", "-shortest"]
    else:
        args += ["-i", str(source), "-map", "0:v:0", "-map", "0:a:0"]
        if not skip_loudnorm:
            measured = measure_loudness(source)
            if measured.get("input_i") is not None:
                af = (
                    "loudnorm=I={i}:TP={tp}:LRA=11:"
                    "measured_I={mi}:measured_TP={mtp}:measured_LRA={mlra}:"
                    "measured_thresh={mth}:offset={off}:linear=true:print_format=summary"
                ).format(i=target_lufs, tp=target_tp,
                         mi=measured["input_i"], mtp=measured["input_tp"],
                         mlra=measured["input_lra"], mth=measured["input_thresh"],
                         off=measured.get("target_offset", 0.0))
            else:
                af = f"loudnorm=I={target_lufs}:TP={target_tp}:LRA=11"

    args += ["-vf", vf, *video_encoder_args(quality="intermediate", hw=hw)]
    if af:
        args += ["-af", af]
    args += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-movflags", "+faststart", str(project.ingest_video)]
    run_ffmpeg(args, desc="Ingest")

    out = probe_summary(project.ingest_video)
    after = {} if skip_loudnorm or not src["has_audio"] else measure_loudness(project.ingest_video)
    meta = {
        "source": str(source.resolve()),
        "source_probe": src,
        "output": str(project.ingest_video),
        "output_probe": out,
        "target": {"width": style.width, "height": style.height, "fps": style.fps,
                   "lufs": target_lufs, "true_peak_db": target_tp},
        "loudness_before": {k: measured.get(k) for k in ("input_i", "input_tp", "input_lra")},
        "loudness_after": {k: after.get(k) for k in ("input_i", "input_tp", "input_lra")},
    }
    write_json(project.ingest_meta, meta)
    lb = meta["loudness_before"].get("input_i")
    la = meta["loudness_after"].get("input_i")
    loud = ""
    if lb is not None:
        loud = f", Ton {lb:.1f} → {la:.1f} LUFS" if la is not None else f", Ton {lb:.1f} LUFS"
    ok(f"{project.ingest_video.relative_to(project.root.parent.parent)}  "
       f"{out['width']}x{out['height']} @{out['fps']}fps, {out['duration']:.2f}s{loud}")
    return project.ingest_video

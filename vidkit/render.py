"""Schritt 7: Alles zusammensetzen.

Vier Stufen, jede schreibt eine Datei — so laesst sich jede einzeln wiederholen:
  base       Schnitte + Zooms + Farblook          → render/base.mp4
  composite  B-Roll + Overlays/Captions/Motion    → render/composite.mp4
  audio      Stimme + Sound-Effekte + Musik       → render/mix.wav
  mux        Bild + Ton → out.mp4
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .config import Style
from .editdoc import elements, load_edit, timeline_duration
from .ffmpeg import probe_summary, run_ffmpeg, video_encoder_args
from .paths import Project, resolve_asset
from .util import die, ok, read_json, step, warn

STAGES = ["base", "composite", "audio", "mux"]


# --------------------------------------------------------------------------- #
# Zoom-Ausdruck
# --------------------------------------------------------------------------- #
_EASINGS = {
    # p in [0,1] -> eased p, als ffmpeg-Expression mit Platzhalter {p}
    "linear": "({p})",
    "easeOutCubic": "(1-pow(1-({p}),3))",
    "easeInOutCubic": "if(lt({p},0.5),4*pow({p},3),1-pow(-2*{p}+2,3)/2)",
    "easeOutQuad": "(1-pow(1-({p}),2))",
    "easeOutBack": "(1+2.70158*pow(({p})-1,3)+1.70158*pow(({p})-1,2))",
    "easeInOutSine": "(-(cos(PI*({p}))-1)/2)",
}


def _ease_expr(name: str, p: str) -> str:
    tmpl = _EASINGS.get(name, _EASINGS["easeOutCubic"])
    return tmpl.replace("{p}", p)


def zoom_expression(zooms: list[dict], seg_t_in: float, fps: int) -> str | None:
    """z-Ausdruck fuer zoompan, in segment-lokaler Zeit (on/fps)."""
    if not zooms:
        return None
    expr = "1"
    for z in zooms:
        t0 = max(0.0, float(z["t_in"]) - seg_t_in)
        t1 = max(t0 + 1.0 / fps, float(z["t_out"]) - seg_t_in)
        a, b = float(z.get("from", 1.0)), float(z.get("to", 1.05))
        t = f"(on/{fps})"
        p = f"clip(({t}-{t0:.4f})/{t1 - t0:.4f},0,1)"
        eased = _ease_expr(z.get("easing", "easeOutCubic"), p)
        # nach dem Zoom auf dem Endwert stehen bleiben, davor auf dem Startwert
        expr = (f"if(lt({t},{t0:.4f}),{expr},"
                f"{a:.4f}+({b:.4f}-{a:.4f})*{eased})")
    return expr


def grade_filter(style: Style) -> str | None:
    cfg = style.section("color")
    if not cfg.get("enabled", True):
        return None
    g = cfg.get("grade", {})
    parts = []
    eq = []
    for key, name, default in (("brightness", "brightness", 0.0), ("contrast", "contrast", 1.0),
                               ("saturation", "saturation", 1.0), ("gamma", "gamma", 1.0)):
        v = float(g.get(key, default))
        if abs(v - default) > 1e-4:
            eq.append(f"{name}={v}")
    if eq:
        parts.append("eq=" + ":".join(eq))
    temp = float(g.get("temperature_shift", 0.0))
    if abs(temp) > 1e-4:
        # positiv = waermer: rot hoch, blau runter
        parts.append(f"colorbalance=rm={temp:.3f}:bm={-temp:.3f}")
    return ",".join(parts) if parts else None


# --------------------------------------------------------------------------- #
# Stufe 1: Basis
# --------------------------------------------------------------------------- #
def render_base(project: Project, style: Style, doc: dict, *, hw: bool = True,
                preview: bool = False) -> Path:
    src = Path(doc.get("source") or project.ingest_video)
    if not src.exists():
        die(f"Quellvideo fehlt: {src}")
    segments = doc.get("segments") or []
    if not segments:
        die("edit.json enthaelt keine Segmente.")
    fps = int(doc.get("format", {}).get("fps", style.fps))
    w = int(doc.get("format", {}).get("width", style.width))
    h = int(doc.get("format", {}).get("height", style.height))
    zooms = elements(doc, "zooms")

    chains: list[str] = []
    labels: list[str] = []
    for i, seg in enumerate(segments):
        lbl = f"v{i}"
        # fps bewusst pro Zweig, nicht nach dem concat: ein 'fps' hinter dem
        # concat-Filter rechnet die Zeitbasis der zoompan-Zweige falsch um und
        # blaeht das Ergebnis auf ein Vielfaches der Laenge auf.
        f = [f"trim=start={seg['source_in']:.4f}:end={seg['source_out']:.4f}",
             "setpts=PTS-STARTPTS", f"fps={fps}"]
        seg_zooms = [z for z in zooms
                     if z["t_out"] > seg["t_in"] + 1e-4 and z["t_in"] < seg["t_out"] - 1e-4]
        expr = zoom_expression(seg_zooms, seg["t_in"], fps)
        if expr:
            f.append(f"zoompan=z='{expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                     f":d=1:s={w}x{h}:fps={fps}")
        chains.append(f"[0:v]{','.join(f)}[{lbl}]")
        labels.append(f"[{lbl}]")

    graph = ";".join(chains)
    graph += ";" + "".join(labels) + f"concat=n={len(labels)}:v=1:a=0[cat]"
    grade = grade_filter(style)
    last = "[cat]"
    if grade:
        graph += f";[cat]{grade}[grd]"
        last = "[grd]"
    graph += f";{last}format=yuv420p[vout]"

    quality = "preview" if preview else "intermediate"
    project.render_dir.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-i", str(src), "-filter_complex", graph, "-map", "[vout]", "-an",
        *video_encoder_args(quality=quality, hw=hw), str(project.base_video),
    ], desc="Basis rendern")
    return project.base_video


# --------------------------------------------------------------------------- #
# Stufe 2: Compositing
# --------------------------------------------------------------------------- #
def _broll_inputs(project: Project, doc: dict) -> list[dict]:
    from .stock import resolve_selection
    resolve_selection(doc)          # 'selection' zaehlt genauso wie ein Dateipfad
    out = []
    for b in elements(doc, "broll"):
        f = b.get("file")
        if not f:
            continue
        p = resolve_asset(project, f)
        if p.exists():
            out.append({**b, "path": p})
        else:
            warn(f"B-Roll-Datei fehlt, Slot {b['id']} wird uebersprungen: {p}")
    return out


def _asset_inputs(project: Project, doc: dict) -> list[dict]:
    if not project.assets_manifest.exists():
        return []
    manifest = read_json(project.assets_manifest)
    items = []
    for kind in ("motion_graphics", "overlays", "captions"):
        for e in elements(doc, kind):
            info = manifest.get("elements", {}).get(e["id"])
            if not info:
                continue
            p = resolve_asset(project, info["file"])
            if not p.exists():
                warn(f"Asset fehlt: {p}")
                continue
            # Position immer aus der edit.json — sie ist die Wahrheit. Aus dem
            # Manifest kommt nur die Laenge des gerenderten Clips (mit Auslauf).
            clip_len = float(info.get("t_out", e["t_out"])) - float(info.get("t_in", e["t_in"]))
            t_in = float(e["t_in"])
            items.append({"id": e["id"], "kind": kind, "path": p,
                          "t_in": t_in, "t_out": t_in + max(clip_len, 0.04),
                          "x": int(info.get("x", 0)), "y": int(info.get("y", 0))})
    items.sort(key=lambda x: (("motion_graphics", "overlays", "captions").index(x["kind"]),
                              x["t_in"]))
    return items


def render_composite(project: Project, style: Style, doc: dict, *, hw: bool = True,
                     preview: bool = False) -> Path:
    base = project.base_video
    if not base.exists():
        die("render/base.mp4 fehlt — erst die Stufe 'base' rendern.")
    w = int(doc.get("format", {}).get("width", style.width))
    h = int(doc.get("format", {}).get("height", style.height))
    fps = int(doc.get("format", {}).get("fps", style.fps))

    brolls = _broll_inputs(project, doc)
    assets = _asset_inputs(project, doc)
    from .assets import stale_elements
    stale = stale_elements(project, style, doc)
    if stale:
        warn(f"{len(stale)} Element(e) haben sich seit dem letzten 'assets'-Lauf geaendert "
             f"({', '.join(stale[:4])}{' …' if len(stale) > 4 else ''}).\n"
             f"   Erst 'vidkit assets -p {project.name}' laufen lassen, sonst fehlen sie "
             f"oder stehen falsch.")
    if not brolls and not assets:
        # Nichts zu ueberlagern — Basis durchreichen.
        import shutil
        shutil.copyfile(base, project.composite_video)
        return project.composite_video

    inputs: list[str] = ["-i", str(base)]
    parts: list[str] = []
    last = "[0:v]"
    idx = 1

    for b in brolls:
        inputs += ["-i", str(b["path"])]
        dur = float(b["t_out"]) - float(b["t_in"])
        parts.append(
            f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{h},setsar=1,fps={fps},trim=duration={dur:.3f},"
            f"setpts=PTS-STARTPTS+{float(b['t_in']):.3f}/TB[b{idx}]"
        )
        parts.append(f"{last}[b{idx}]overlay=0:0:eof_action=pass:"
                     f"enable='between(t,{float(b['t_in']):.3f},{float(b['t_out']):.3f})'[vb{idx}]")
        last = f"[vb{idx}]"
        idx += 1

    for a in assets:
        inputs += ["-i", str(a["path"])]
        parts.append(f"[{idx}:v]setpts=PTS-STARTPTS+{a['t_in']:.3f}/TB,"
                     f"format=rgba[a{idx}]")
        parts.append(f"{last}[a{idx}]overlay={a['x']}:{a['y']}:eof_action=pass:shortest=0:"
                     f"enable='between(t,{a['t_in']:.3f},{a['t_out'] + 0.05:.3f})'[va{idx}]")
        last = f"[va{idx}]"
        idx += 1

    parts.append(f"{last}format=yuv420p[vout]")
    quality = "preview" if preview else "intermediate"
    run_ffmpeg([*inputs, "-filter_complex", ";".join(parts), "-map", "[vout]", "-an",
                *video_encoder_args(quality=quality, hw=hw), str(project.composite_video)],
               desc="Compositing")
    return project.composite_video


# --------------------------------------------------------------------------- #
# Stufe 3: Ton
# --------------------------------------------------------------------------- #
def render_audio(project: Project, style: Style, doc: dict) -> Path:
    src = Path(doc.get("source") or project.ingest_video)
    segments = doc.get("segments") or []
    duration = timeline_duration(doc)
    sr = 48000

    parts: list[str] = []
    labels: list[str] = []
    for i, seg in enumerate(segments):
        parts.append(f"[0:a]atrim=start={seg['source_in']:.4f}:end={seg['source_out']:.4f},"
                     f"asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[a{i}]")
    parts.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1,aresample={sr}[voice]")

    inputs: list[str] = ["-i", str(src)]
    idx = 1
    mix_labels = ["[voice]"]

    sfx_list = [s for s in elements(doc, "sfx") if s.get("file")]
    for s in sfx_list:
        p = resolve_asset(project, s["file"])
        if not p.exists():
            warn(f"SFX-Datei fehlt: {p}")
            continue
        inputs += ["-i", str(p)]
        delay_ms = int(round(float(s["t"]) * 1000))
        gain = float(s.get("gain_db", -12.0))
        parts.append(f"[{idx}:a]aresample={sr},aformat=channel_layouts=stereo,"
                     f"volume={gain:.2f}dB,adelay={delay_ms}|{delay_ms}[s{idx}]")
        mix_labels.append(f"[s{idx}]")
        idx += 1

    # SFX auf einen eigenen Bus, damit sie sich gemeinsam unter die Stimme ducken lassen.
    sfx_labels = mix_labels[1:]
    if sfx_labels and bool(style.get("audio.sfx.duck_under_voice", False)):
        if len(sfx_labels) > 1:
            parts.append("".join(sfx_labels) +
                         f"amix=inputs={len(sfx_labels)}:normalize=0:dropout_transition=0[sfxbus]")
        else:
            parts.append(f"{sfx_labels[0]}anull[sfxbus]")
        parts.append("[voice]asplit=2[voice_main][voice_key1]")
        parts.append("[sfxbus][voice_key1]sidechaincompress="
                     "threshold=0.08:ratio=4:attack=8:release=220:makeup=1[sfxducked]")
        mix_labels = ["[voice_main]", "[sfxducked]"]

    music_cfg = style.section("audio").get("music", {})
    music_file = doc.get("music") or music_cfg.get("file")
    music_label = None
    if music_file:
        mp = resolve_asset(project, music_file)
        if mp.exists():
            inputs += ["-stream_loop", "-1", "-i", str(mp)]
            gain = float(music_cfg.get("gain_db_rel_voice", -18.0))
            parts.append(f"[{idx}:a]aresample={sr},aformat=channel_layouts=stereo,"
                         f"volume={gain:.2f}dB,atrim=duration={duration:.3f}[music]")
            music_label = "[music]"
            idx += 1
        else:
            warn(f"Musikdatei fehlt: {mp}")

    if music_label:
        duck = float(music_cfg.get("duck_db", 0.0))
        if abs(duck) > 0.01:
            voice_in = mix_labels[0]
            parts.append(f"{voice_in}asplit=2[voice_out][voice_key2]")
            parts.append(f"{music_label}[voice_key2]sidechaincompress="
                         f"threshold=0.05:ratio=6:attack=15:release=280:makeup=1[musicd]")
            mix_labels[0] = "[voice_out]"
            mix_labels.append("[musicd]")
        else:
            mix_labels.append(music_label)

    n = len(mix_labels)
    if n == 1:
        parts.append("[voice]anull[mix]")
    else:
        parts.append("".join(mix_labels) + f"amix=inputs={n}:normalize=0:dropout_transition=0[mix]")
    target = float(style.get("audio.voice_lufs", -14.0))
    tp = float(style.get("audio.voice_true_peak_db", -1.0))
    parts.append(f"[mix]alimiter=limit={10 ** (tp / 20):.4f},"
                 f"atrim=duration={duration:.3f},aresample={sr}[aout]")

    run_ffmpeg([*inputs, "-filter_complex", ";".join(parts), "-map", "[aout]",
                "-c:a", "pcm_s16le", "-ar", str(sr), "-ac", "2", str(project.mix_audio)],
               desc="Ton mischen")
    return project.mix_audio


# --------------------------------------------------------------------------- #
# Stufe 4: Mux
# --------------------------------------------------------------------------- #
def render_mux(project: Project, style: Style, doc: dict, out: Path, *, hw: bool = True,
               preview: bool = False) -> Path:
    video = project.composite_video if project.composite_video.exists() else project.base_video
    audio = project.mix_audio
    target_lufs = float(style.get("audio.voice_lufs", -14.0))
    tp = float(style.get("audio.voice_true_peak_db", -1.0))
    args = ["-i", str(video)]
    if audio.exists():
        args += ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
                 "-af", f"loudnorm=I={target_lufs}:TP={tp}:LRA=11",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    else:
        args += ["-map", "0:v:0", "-an"]
    vf = []
    if preview:
        w = int(style.width * 0.5) // 2 * 2
        h = int(style.height * 0.5) // 2 * 2
        vf.append(f"scale={w}:{h}:flags=bilinear")
    if vf:
        args += ["-vf", ",".join(vf)]
    args += [*video_encoder_args(quality="preview" if preview else "final", hw=hw),
             "-movflags", "+faststart", str(out)]
    run_ffmpeg(args, desc="Mux")
    return out


# --------------------------------------------------------------------------- #
def render(project: Project, style: Style, *, out: Path | None = None, preview: bool = False,
           hw: bool = True, from_stage: str = "base") -> Path:
    doc = load_edit(project)
    out = Path(out) if out else (project.preview_video if preview else project.out_video)
    start = STAGES.index(from_stage) if from_stage in STAGES else 0

    dur = timeline_duration(doc)
    step(f"Render{' (Vorschau)' if preview else ''}: {dur:.2f}s, "
         f"{len(doc.get('segments', []))} Segmente, ab Stufe '{STAGES[start]}'")

    if start <= 0:
        render_base(project, style, doc, hw=hw, preview=preview)
        ok(f"  base.mp4 ({probe_summary(project.base_video)['duration']:.2f}s)")
    if start <= 1:
        render_composite(project, style, doc, hw=hw, preview=preview)
        ok(f"  composite.mp4 ({probe_summary(project.composite_video)['duration']:.2f}s)")
    if start <= 2:
        render_audio(project, style, doc)
        ok(f"  mix.wav ({probe_summary(project.mix_audio)['duration']:.2f}s)")
    if start <= 3:
        render_mux(project, style, doc, out, hw=hw, preview=preview)

    info = probe_summary(out)
    ok(f"{out}  {info['width']}x{info['height']} @{info['fps']}fps, {info['duration']:.2f}s, "
       f"{info['bitrate'] / 1000:.0f} kbit/s")
    return out

#!/usr/bin/env python3
"""Erzeugt tests/fixtures/sample_reference_ad.mp4 — ein Referenz-Ad mit bekannten Werten.

Nichts daran ist heruntergeladen: alle Bilder, Texte und Toene werden hier
synthetisiert. Der Sinn ist, 'vidkit learn' gegen Sollwerte pruefen zu koennen,
die oben im Skript stehen.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H, FPS = 1080, 1920, 30

# Sollwerte: Einstellungen (Dauer, Grundfarbe, Zoom von→bis, grosses Overlay)
SHOTS = [
    (1.6, "0x1d3b53", (1.00, 1.12), "MEHR ZEIT"),
    (0.9, "0x8a2d3b", (1.00, 1.00), None),
    (2.4, "0x2f6f4e", (1.00, 1.10), "OHNE ABO"),
    (1.2, "0x6b4b8a", (1.00, 1.00), None),
    (3.0, "0x1d3b53", (1.00, 1.14), "JETZT TESTEN"),
    (1.5, "0xb07a2a", (1.00, 1.00), None),
]
CAPTIONS = ["spart dir zeit", "jeden morgen", "kein aufwand",
            "kein abo", "probier es aus", "ganz einfach"]
OVERLAY_HOLD = 0.8
CAPTION_SIZE = 0.040      # relativ zur Bildhoehe
OVERLAY_SIZE = 0.095


def require_espeak() -> None:
    """espeak-ng erzeugt die Sprachspur des Testmaterials."""
    if shutil.which("espeak-ng") is None:
        sys.exit("espeak-ng nicht gefunden — es synthetisiert die Sprache fuer das\n"
                 "Testmaterial.  Auf dem Mac:  brew install espeak-ng")


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"Fehler: {' '.join(str(c) for c in cmd)[:200]}\n{p.stderr[-1500:]}")


def main() -> int:
    require_espeak()
    if not Path(FONT).exists():
        sys.exit(f"Schrift fehlt: {FONT}")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="vidkit-ref-"))
    parts = []
    cut_times, overlay_times = [], []
    t = 0.0

    for i, (dur, colr, (z0, z1), overlay) in enumerate(SHOTS):
        if i:
            cut_times.append(round(t, 3))
        cap = CAPTIONS[i % len(CAPTIONS)]
        cap_size = int(CAPTION_SIZE * H)
        ov_size = int(OVERLAY_SIZE * H)
        # Grundbild: Farbflaeche + Struktur, damit Optical Flow etwas zu fassen hat
        vf = [
            f"drawbox=x=0:y={int(H*0.18)}:w={W}:h={int(H*0.5)}:color=white@0.30:t=fill",
            f"drawbox=x={int(W*0.12)}:y={int(H*0.30)}:w={int(W*0.5)}:h={int(H*0.26)}:"
            f"color=white@0.55:t=fill",
            # Raster als Textur: echtes Kameramaterial hat ueberall Struktur
            f"drawgrid=w={int(W*0.11)}:h={int(W*0.11)}:t=3:color=white@0.22",
            f"drawtext=fontfile={FONT}:text='{cap.upper()}':fontcolor=white:fontsize={cap_size}:"
            f"borderw={max(2,int(cap_size*0.14))}:bordercolor=black:"
            f"x=(w-text_w)/2:y={int(H*0.72)}",
        ]
        if overlay:
            overlay_times.append(round(t + 0.15, 3))
            vf.append(
                f"drawtext=fontfile={FONT}:text='{overlay}':fontcolor=0xF2E14C:"
                f"fontsize={ov_size}:borderw={max(3,int(ov_size*0.06))}:bordercolor=black:"
                f"x=(w-text_w)/2:y={int(H*0.30)}:"
                f"enable='between(t,0.15,{0.15 + OVERLAY_HOLD})'")
        if z1 > z0:
            zdur = 0.5
            zexpr = (f"if(lt(on/{FPS},{zdur}),"
                     f"{z0}+({z1}-{z0})*(1-pow(1-(on/{FPS})/{zdur},3)),{z1})")
            vf.append(f"zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                      f":d=1:s={W}x{H}:fps={FPS}")
        # Filmkorn: ohne Struktur hat Optical Flow nichts zu fassen —
        # echtes Kameramaterial rauscht immer.
        vf.append("noise=alls=6:allf=t+u")
        vf.append("eq=saturation=1.25:contrast=1.10")
        shot = tmp / f"shot{i}.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
             "-i", f"color=c={colr}:s={W}x{H}:r={FPS}:d={dur}",
             "-vf", ",".join(vf), "-c:v", "libx264", "-crf", "18",
             "-pix_fmt", "yuv420p", str(shot)])
        parts.append(shot)
        t += dur

    total = t
    listfile = tmp / "list.txt"
    listfile.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    silent = tmp / "video.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listfile),
         "-c", "copy", str(silent)])

    # Ton: Sprache + Klick an jedem Schnitt + Impact an jeder Einblendung + Musikbett
    speech = tmp / "speech.wav"
    run(["espeak-ng", "-v", "de", "-s", "150", "-w", str(speech),
         "Mehr Zeit am Morgen. Ohne Abo. Ganz einfach. Jetzt testen und selber sehen. "
         "Das spart dir jeden Tag zehn Minuten."])

    inputs = ["-i", str(speech)]
    chains = [f"[0:a]aresample=48000,apad=whole_dur={total:.2f},volume=6dB[voice]"]
    mixes = ["[voice]"]
    idx = 1
    for k, ct in enumerate(cut_times):
        inputs += ["-f", "lavfi", "-i", "anoisesrc=c=pink:r=48000:a=0.6:d=0.25"]
        chains.append(f"[{idx}:a]highpass=f=700,volume='0.9*(1-t/0.25)':eval=frame,"
                      f"aformat=channel_layouts=stereo,adelay={int(ct*1000)}|{int(ct*1000)}[c{k}]")
        mixes.append(f"[c{k}]")
        idx += 1
    for k, ot in enumerate(overlay_times):
        inputs += ["-f", "lavfi", "-i", "sine=frequency=90:r=48000:d=0.35"]
        chains.append(f"[{idx}:a]volume='0.9*exp(-8*t)':eval=frame,"
                      f"aformat=channel_layouts=stereo,adelay={int(ot*1000)}|{int(ot*1000)}[o{k}]")
        mixes.append(f"[o{k}]")
        idx += 1
    # Musikbett: leiser, durchgehender Akkord
    inputs += ["-f", "lavfi", "-i", f"sine=frequency=196:r=48000:d={total:.2f}",
               "-f", "lavfi", "-i", f"sine=frequency=294:r=48000:d={total:.2f}"]
    chains.append(f"[{idx}:a][{idx+1}:a]amix=inputs=2:normalize=0,"
                  f"volume=-26dB,aformat=channel_layouts=stereo[music]")
    mixes.append("[music]")
    idx += 2
    chains.append("".join(mixes) + f"amix=inputs={len(mixes)}:normalize=0:dropout_transition=0,"
                                   f"atrim=duration={total:.2f},aresample=48000[aout]")
    audio = tmp / "audio.wav"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(chains),
         "-map", "[aout]", "-ac", "2", "-ar", "48000", str(audio)])

    ref = OUT / "sample_reference_ad.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(audio),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-shortest", str(ref)])

    truth = {
        "duration": round(total, 3),
        "shots": len(SHOTS),
        "cut_times": cut_times,
        "cuts_per_10s": round(len(cut_times) / (total / 10), 2),
        "shot_lengths": [s[0] for s in SHOTS],
        "avg_shot_seconds": round(sum(s[0] for s in SHOTS) / len(SHOTS), 3),
        "min_shot_seconds": min(s[0] for s in SHOTS),
        "zoom_moves": sum(1 for s in SHOTS if s[2][1] > s[2][0]),
        "zoom_max_scale": max(s[2][1] for s in SHOTS),
        "zoom_duration": 0.5,
        "zoom_easing": "easeOutCubic",
        "overlay_times": overlay_times,
        "overlays": len(overlay_times),
        "overlay_hold_seconds": OVERLAY_HOLD,
        "overlay_font_size_rel": OVERLAY_SIZE,
        "overlay_y_rel": 0.30 + OVERLAY_SIZE / 2,
        "caption_font_size_rel": CAPTION_SIZE,
        "caption_y_rel": 0.72 + CAPTION_SIZE / 2,
        "uppercase": True,
        "music_present": True,
        "sfx_on_every_cut": True,
        "sfx_on_every_overlay": True,
    }
    (OUT / "sample_reference_truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{ref}  ({total:.2f}s, {len(SHOTS)} Einstellungen)")
    print(f"{OUT / 'sample_reference_truth.json'}  (Sollwerte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Erzeugt das Testmaterial: tests/fixtures/sample_talking_head.mp4 + sample_transcript.json.

Jedes Wort wird einzeln mit espeak-ng synthetisiert und mit definierten Pausen
aneinandergehaengt. Dadurch sind die Wort-Timecodes im Fixture exakt und die
Schritte plan/assets/sfx/render lassen sich ohne Whisper-Download testen.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "tests" / "fixtures"

# (Wort, Pause danach in Sekunden). Lange Pausen und ein Fuellwort sind Absicht:
# sie sind das Futter fuer die Schnitt-Regeln in plan.
SCRIPT: list[tuple[str, float]] = [
    ("Hallo", 0.10), ("ich", 0.06), ("bin", 0.06), ("Amit", 0.55),
    ("ähm", 0.62),
    ("ich", 0.06), ("zeige", 0.06), ("dir", 0.06), ("heute", 0.10),
    ("unser", 0.06), ("neues", 0.06), ("Produkt", 0.70),
    ("Es", 0.06), ("spart", 0.06), ("dir", 0.06), ("jeden", 0.06),
    ("Morgen", 0.10), ("zehn", 0.06), ("Minuten", 0.75),
    ("Kein", 0.06), ("Aufwand", 0.40), ("kein", 0.06), ("Abo", 0.80),
    ("Probier", 0.06), ("es", 0.06), ("aus", 0.30),
]
LEAD_IN = 0.70
TAIL = 1.00
SR = 48000


def require_espeak() -> None:
    """espeak-ng erzeugt die Sprachspur des Testmaterials."""
    if shutil.which("espeak-ng") is None:
        sys.exit("espeak-ng nicht gefunden — es synthetisiert die Sprache fuer das\n"
                 "Testmaterial.  Auf dem Mac:  brew install espeak-ng")


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"Fehler: {' '.join(cmd[:4])}…\n{proc.stderr[-800:]}")


def wav_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout.strip()
    return float(out)


def main() -> int:
    require_espeak()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="vidkit-fixture-"))
    parts: list[Path] = []
    words: list[dict] = []
    t = LEAD_IN

    silence = tmp / "sil.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"anullsrc=r={SR}:cl=mono", "-t", str(LEAD_IN), str(silence)])
    parts.append(silence)

    for i, (word, gap) in enumerate(SCRIPT):
        raw = tmp / f"w{i:03d}_raw.wav"
        wav = tmp / f"w{i:03d}.wav"
        run(["espeak-ng", "-v", "de", "-s", "150", "-p", "42", "-w", str(raw), word])
        run(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
             "-af", "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,"
                    "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,areverse",
             "-ar", str(SR), "-ac", "1", str(wav)])
        dur = wav_duration(wav)
        words.append({"i": i, "w": word, "start": round(t, 3), "end": round(t + dur, 3),
                      "prob": 0.99, "segment": 0})
        t += dur
        parts.append(wav)
        if gap > 0:
            g = tmp / f"g{i:03d}.wav"
            run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                 "-i", f"anullsrc=r={SR}:cl=mono", "-t", str(gap), str(g)])
            parts.append(g)
            t += gap

    tail = tmp / "tail.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"anullsrc=r={SR}:cl=mono", "-t", str(TAIL), str(tail)])
    parts.append(tail)
    total = t + TAIL

    listfile = tmp / "list.txt"
    listfile.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    speech = tmp / "speech.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listfile),
         "-af", "highpass=f=90,lowpass=f=7200,acompressor=threshold=0.12:ratio=3,volume=4dB",
         "-ar", str(SR), "-ac", "2", str(speech)])

    video = OUT_DIR / "sample_talking_head.mp4"
    run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"color=c=0x16232f:s=1920x1080:r=30:d={total:.3f}",
        "-f", "lavfi", "-i", f"color=c=0xe8c39e:s=520x640:r=30:d={total:.3f}",
        "-i", str(speech),
        "-filter_complex",
        "[1:v]format=yuv420p[head];"
        "[0:v][head]overlay=x='(W-w)/2+40*sin(t*1.1)':y='H-h+90+18*sin(t*2.3)':shortest=1,"
        "drawbox=x=0:y=ih-140:w=iw:h=140:color=0x0d161f@1:t=fill,"
        "noise=alls=6:allf=t+u,eq=saturation=1.05[v]",
        "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(video),
    ])

    sentences = [(0, 3), (4, 11), (12, 18), (19, 22), (23, 25)]
    segments = []
    for si, (a, b) in enumerate(sentences):
        segments.append({
            "id": si, "start": words[a]["start"], "end": words[b]["end"],
            "text": " ".join(w["w"] for w in words[a:b + 1]),
        })
    for si, (a, b) in enumerate(sentences):
        for w in words[a:b + 1]:
            w["segment"] = si

    transcript = {
        "language": "de",
        "duration": round(total, 3),
        "backend": "fixture/espeak-ng (exakte Timecodes per Konstruktion)",
        "source": str(video),
        "seconds_taken": 0.0,
        "text": " ".join(s["text"] for s in segments),
        "segments": segments,
        "words": words,
    }
    (OUT_DIR / "sample_transcript.json").write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{video}  ({total:.2f}s)")
    print(f"{OUT_DIR / 'sample_transcript.json'}  ({len(words)} Woerter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

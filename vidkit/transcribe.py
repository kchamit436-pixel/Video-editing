"""Schritt 2: Transkript mit Wort-Timecodes.

Backends in dieser Reihenfolge:
  mlx      mlx-whisper   — Apple Silicon, schnellster Weg (Metal)
  faster   faster-whisper (CTranslate2) — schnell auf CPU, laeuft ueberall
  openai   openai-whisper — Fallback

Wort-Timecodes sind Pflicht; alle Backends werden entsprechend aufgerufen.
"""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path

from .ffmpeg import duration_of, extract_audio
from .paths import Project
from .util import die, ok, read_json, step, warn, write_json

DEFAULT_MODELS = {
    "mlx": "mlx-community/whisper-large-v3-turbo",
    "faster": "small",
    "openai": "small",
}


def _available(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def pick_backend(preferred: str = "auto") -> str:
    if preferred != "auto":
        return preferred
    for name, mod in (("mlx", "mlx_whisper"), ("faster", "faster_whisper"), ("openai", "whisper")):
        if _available(mod):
            return name
    die("Kein Whisper-Backend gefunden.\n"
        "  Apple Silicon:  pip install mlx-whisper\n"
        "  sonst:          pip install faster-whisper")


def _norm_word(w: str) -> str:
    return w.strip()


def _transcribe_mlx(audio: Path, model: str, language: str) -> dict:
    import mlx_whisper

    res = mlx_whisper.transcribe(
        str(audio), path_or_hf_repo=model, language=language,
        word_timestamps=True, condition_on_previous_text=False,
    )
    segments, words = [], []
    for si, seg in enumerate(res.get("segments", [])):
        segments.append({"id": si, "start": float(seg["start"]), "end": float(seg["end"]),
                         "text": seg["text"].strip()})
        for w in seg.get("words", []) or []:
            token = _norm_word(w.get("word", ""))
            if token:
                words.append({"w": token, "start": float(w["start"]), "end": float(w["end"]),
                              "prob": float(w.get("probability", 1.0)), "segment": si})
    return {"text": res.get("text", "").strip(), "segments": segments, "words": words}


def _transcribe_faster(audio: Path, model: str, language: str) -> dict:
    from faster_whisper import WhisperModel

    compute = "int8"
    mdl = WhisperModel(model, device="cpu", compute_type=compute)
    seg_iter, _info = mdl.transcribe(
        str(audio), language=language, word_timestamps=True,
        vad_filter=False, condition_on_previous_text=False, beam_size=5,
    )
    segments, words, texts = [], [], []
    for si, seg in enumerate(seg_iter):
        segments.append({"id": si, "start": float(seg.start), "end": float(seg.end),
                         "text": seg.text.strip()})
        texts.append(seg.text.strip())
        for w in (seg.words or []):
            token = _norm_word(w.word)
            if token:
                words.append({"w": token, "start": float(w.start), "end": float(w.end),
                              "prob": float(getattr(w, "probability", 1.0)), "segment": si})
    return {"text": " ".join(texts).strip(), "segments": segments, "words": words}


def _transcribe_openai(audio: Path, model: str, language: str) -> dict:
    import whisper

    mdl = whisper.load_model(model)
    res = mdl.transcribe(str(audio), language=language, word_timestamps=True, verbose=False)
    segments, words = [], []
    for si, seg in enumerate(res.get("segments", [])):
        segments.append({"id": si, "start": float(seg["start"]), "end": float(seg["end"]),
                         "text": seg["text"].strip()})
        for w in seg.get("words", []) or []:
            token = _norm_word(w.get("word", ""))
            if token:
                words.append({"w": token, "start": float(w["start"]), "end": float(w["end"]),
                              "prob": float(w.get("probability", 1.0)), "segment": si})
    return {"text": res.get("text", "").strip(), "segments": segments, "words": words}


def import_transcript(project: Project, path: Path) -> Path:
    """Fertiges Transkript uebernehmen (z.B. aus einem anderen Werkzeug oder Fixture)."""
    data = read_json(Path(path))
    words = data.get("words") or []
    if not words:
        die(f"{path} enthaelt keine 'words' mit Timecodes.")
    for i, w in enumerate(words):
        missing = [k for k in ("w", "start", "end") if k not in w]
        if missing:
            die(f"Wort {i} fehlt {missing} — Wort-Timecodes sind Pflicht.")
        w["i"] = i
    data.setdefault("language", "de")
    data.setdefault("segments", [])
    data["backend"] = data.get("backend", "import") + " (importiert)"
    write_json(project.transcript, data)
    ok(f"{project.transcript.name}: {len(words)} Woerter importiert aus {path}")
    return project.transcript


def transcribe(project: Project, *, backend: str = "auto", model: str | None = None,
               language: str = "de", source: Path | None = None,
               import_path: Path | None = None) -> Path:
    project.ensure_dirs()
    if import_path:
        return import_transcript(project, import_path)
    src = Path(source) if source else project.ingest_video
    if not src.exists():
        die(f"{src} fehlt — erst 'vidkit ingest <rohvideo>' laufen lassen.")

    backend = pick_backend(backend)
    model = model or DEFAULT_MODELS[backend]
    step(f"Transkription: Backend {backend}, Modell {model}, Sprache {language}")

    audio = project.render_dir / "voice_16k.wav"
    extract_audio(src, audio)

    t0 = time.time()
    fn = {"mlx": _transcribe_mlx, "faster": _transcribe_faster, "openai": _transcribe_openai}[backend]
    try:
        res = fn(audio, model, language)
    except ModuleNotFoundError as exc:
        die(f"Backend '{backend}' ist nicht installiert: {exc}")
    took = time.time() - t0

    for i, w in enumerate(res["words"]):
        w["i"] = i
    dur = duration_of(src)
    data = {
        "language": language,
        "duration": dur,
        "backend": f"{backend}/{model}",
        "source": str(src),
        "seconds_taken": round(took, 2),
        "text": res["text"],
        "segments": res["segments"],
        "words": res["words"],
    }
    write_json(project.transcript, data)

    n_words = len(res["words"])
    if n_words == 0:
        warn("Keine Woerter erkannt — ist auf der Tonspur ueberhaupt Sprache?")
    wpm = n_words / (dur / 60) if dur else 0
    ok(f"{project.transcript.name}: {n_words} Woerter, {len(res['segments'])} Segmente, "
       f"{wpm:.0f} Woerter/min, {took:.1f}s Rechenzeit")
    if res["text"]:
        preview = res["text"][:160] + ("…" if len(res["text"]) > 160 else "")
        print(f'  „{preview}"')
    return project.transcript

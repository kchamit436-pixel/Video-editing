"""Kleine Helfer: Logging, JSON-IO, Subprozesse."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

VERBOSE = False


def set_verbose(v: bool) -> None:
    global VERBOSE
    VERBOSE = v


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def step(msg: str) -> None:
    log(f"\033[1;36m▸\033[0m {msg}")


def ok(msg: str) -> None:
    log(f"\033[1;32m✓\033[0m {msg}")


def warn(msg: str) -> None:
    log(f"\033[1;33m!\033[0m {msg}")


def die(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[valid-type]
    log(f"\033[1;31m✗\033[0m {msg}")
    raise SystemExit(code)


def debug(msg: str) -> None:
    if VERBOSE:
        log(f"  \033[2m{msg}\033[0m")


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)
    return path


def which(name: str) -> str | None:
    return shutil.which(name)


def run(cmd: Sequence[str], *, check: bool = True, capture: bool = True,
        desc: str | None = None) -> subprocess.CompletedProcess:
    """Subprozess ausfuehren. Bei Fehler wird das Ende von stderr gezeigt."""
    debug((desc or "run") + ": " + " ".join(str(c) for c in cmd))
    t0 = time.time()
    proc = subprocess.run(
        [str(c) for c in cmd],
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
    )
    debug(f"  -> exit {proc.returncode} in {time.time() - t0:.1f}s")
    if check and proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-25:]
        die((desc or "Befehl") + " fehlgeschlagen:\n" + "\n".join(tail))
    return proc


def human_time(seconds: float) -> str:
    m, s = divmod(max(0.0, seconds), 60)
    return f"{int(m):d}:{s:05.2f}"


def chunks(seq: Sequence[Any], n: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def slug(text: str, maxlen: int = 40) -> str:
    keep = []
    for ch in text.lower():
        if ch.isalnum():
            keep.append(ch)
        elif ch in " -_":
            keep.append("-")
    out = "".join(keep).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:maxlen] or "x"

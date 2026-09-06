"""Deutsche Sprachheuristik fuer die Schnittplanung.

Bewusst ohne NLP-Modell: ein Werbespot hat 40-80 Woerter, da schlagen einfache,
nachvollziehbare Regeln ein Modell, das man nicht debuggen kann.
"""
from __future__ import annotations

import re
import unicodedata

STOPWORDS = {
    "aber", "alle", "allem", "allen", "aller", "alles", "als", "also", "am", "an", "andere",
    "anderem", "anderen", "anderer", "anderes", "auch", "auf", "aus", "bei", "beim", "bin",
    "bis", "bist", "da", "damit", "dann", "das", "dass", "dein", "deine", "dem", "den", "denn",
    "der", "des", "dessen", "dich", "die", "dies", "diese", "diesem", "diesen", "dieser",
    "dieses", "dir", "doch", "dort", "du", "durch", "ein", "eine", "einem", "einen", "einer",
    "eines", "er", "es", "etwas", "euch", "euer", "eure", "für", "gegen", "gewesen", "hab",
    "habe", "haben", "hat", "hatte", "hatten", "hier", "hin", "ich", "ihm", "ihn", "ihnen",
    "ihr", "ihre", "im", "in", "ins", "ist", "ja", "jede", "jedem", "jeden", "jeder", "jedes",
    "jetzt", "kann", "kannst", "können", "könnt", "mal", "man", "mein", "meine", "mich", "mir",
    "mit", "muss", "musst", "müssen", "nach", "nicht", "nichts", "noch", "nun", "nur", "ob",
    "oder", "ohne", "schon", "sehr", "sein", "seine", "seid", "sich", "sie", "sind", "so",
    "soll", "sollte", "sondern", "sonst", "über", "um", "und", "uns", "unser", "unsere",
    "unserem", "unseren", "unserer", "unseres", "unter", "vom", "von", "vor", "war", "waren",
    "was", "weil", "weiter", "welche", "wenn", "wer", "werde", "werden", "wie", "wieder",
    "wir", "wird", "wirst", "wo", "wollen", "wollte", "würde", "zu", "zum", "zur", "zwar",
    "zwischen", "the", "a", "of",
}

# Woerter, die in einem Ad fast immer den Punkt tragen.
POWER_WORDS = {
    "gratis", "kostenlos", "neu", "sofort", "jetzt", "nie", "immer", "endlich", "spart",
    "sparst", "sparen", "besser", "beste", "schneller", "einfach", "ohne", "kein", "keine",
    "garantie", "geheimnis", "fehler", "stopp", "achtung", "warum", "wirklich", "minuten",
    "sekunden", "tage", "wochen", "prozent", "euro", "abo", "aufwand", "probier", "teste",
}

FILLERS_DEFAULT = ["ähm", "äh", "ähh", "öhm", "hmm", "mhm", "ehm", "em"]

_PUNCT_END = ".!?"
_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def clean(word: str) -> str:
    """Satzzeichen weg, Rest bleibt wie gesprochen."""
    return word.strip().strip(",.!?;:„“\"'»«…-–—").strip()


def fold(word: str) -> str:
    """Kleinschreibung ohne Akzente, fuer Vergleiche."""
    w = clean(word).lower()
    return "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c))


def is_filler(word: str, fillers: list[str] | None = None) -> bool:
    f = {fold(x) for x in (fillers if fillers is not None else FILLERS_DEFAULT)}
    return fold(word) in f


def ends_sentence(word: str) -> bool:
    return word.strip().endswith(tuple(_PUNCT_END))


def is_stopword(word: str) -> bool:
    return fold(word) in STOPWORDS


def is_noun_like(word: str) -> bool:
    """Im Deutschen sind Substantive gross geschrieben — das reicht als Signal."""
    w = clean(word)
    return bool(w) and w[0].isupper()


def has_digit(word: str) -> bool:
    return any(c.isdigit() for c in word)


NUMBER_WORDS = {
    "null", "eins", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun",
    "zehn", "elf", "zwölf", "zwanzig", "dreissig", "dreißig", "fünfzig", "hundert", "tausend",
    "doppelt", "halb", "erste", "erster",
}


def keyword_score(word: str, *, position_in_sentence: int, duration: float,
                  median_char_time: float, pause_before: float) -> float:
    """0..~4. Wie gut taugt das Wort als grosse Einblendung?"""
    w = clean(word)
    if not w or is_stopword(w) or is_filler(w):
        return 0.0
    letters = len(_TOKEN_RE.sub(lambda m: m.group(), w))
    if letters < 3 and not has_digit(w):
        return 0.0

    score = 0.35
    f = fold(w)
    if f in POWER_WORDS:
        score += 1.3
    if f in NUMBER_WORDS or has_digit(w):
        score += 0.9
    if is_noun_like(w):
        score += 0.7
    if letters >= 7:
        score += 0.35
    elif letters >= 5:
        score += 0.2
    if position_in_sentence == 0:
        score += 0.2
    if pause_before >= 0.25:
        score += 0.45          # bewusst gesetzte Pause davor = Betonung
    # gedehnt gesprochen = betont
    if letters and median_char_time > 0:
        stretch = (duration / letters) / median_char_time
        if stretch > 1.35:
            score += 0.6
        elif stretch > 1.15:
            score += 0.3
    return score


def broll_queries(words: list[str], limit: int = 3) -> list[str]:
    """Aus einem Wortfenster Suchbegriffe fuer Stock-Material ableiten."""
    seen: list[str] = []
    for w in words:
        c = clean(w)
        if not c or is_stopword(c) or is_filler(c) or len(c) < 4:
            continue
        if fold(c) in {fold(x) for x in seen}:
            continue
        seen.append(c.lower())
        if len(seen) >= limit:
            break
    return seen

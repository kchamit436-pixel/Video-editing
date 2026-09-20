# Auftrag: „Adkit" — lokale KI-Schnitt-App für Short-Form-Ads

> Dieses Dokument ist der Auftrag an dich. Lies es ganz, bevor du eine Zeile
> schreibst. Es beschreibt, was gebaut werden soll, was schon existiert, wo die
> ehrlichen Grenzen liegen und woran das Ergebnis gemessen wird.

---

## 1. Wer das benutzt und wofür

Ein Solo-Founder dreht regelmäßig deutschsprachige Werbevideos für seine
DTC-Marke. Er filmt sich selbst mit dem iPhone (4K, Hochformat), redet in einem
Rutsch, und braucht daraus 9:16-Ads für TikTok, Reels und Shorts.

Er ist **kein Entwickler.** Er will eine App öffnen, ein Projekt anlegen, sein
Rohvideo hineinziehen und geführt werden. Terminal-Befehle sind eine Zumutung,
JSON von Hand bearbeiten erst recht.

Er hat einen **MacBook Air mit Apple Silicon**.

## 2. Was am Ende dastehen soll

Eine Mac-App, die er herunterlädt, öffnet, einmal durch eine Einrichtung klickt
— und dann benutzt. Darin:

1. **Projekte.** Er legt beliebig viele an („Januar-Kampagne", „Produkt X").
   Jedes Projekt hält sein Rohmaterial, seinen Schnittplan, seinen Stil und das
   fertige Video.
2. **Format-Auswahl.** Die App schlägt bewährte Ad-Formate vor, die zum Projekt
   passen, und erklärt jedes. Er wählt eins aus.
3. **Drehbrief.** Zum gewählten Format sagt die App ihm, **was er aufnehmen
   muss**: welcher Beat, wie lang, was ungefähr gesagt werden soll, welche
   Einstellung.
4. **Rohmaterial rein.** Er zieht sein Video ins Projekt.
5. **KI schneidet.** Transkript, Schnittvorschläge, Captions, Keyword-Overlays,
   Motion Graphics, B-Roll-Vorschläge, Sound-Effekte — als **Vorschläge**, die
   er annehmen, ändern oder verwerfen kann.
6. **Timeline.** Er sieht alles als Blöcke, schiebt, löscht, schreibt um.
7. **Export.** Fertiges MP4, 1080×1920, H.264, yuv420p, 30 fps, −14 LUFS.

## 3. Die eine Bedingung, die alles andere schlägt

**Kostenlos.** Keine Abos, keine laufenden Kosten, keine Kreditkarte, keine
Cloud-Render-Dienste. Der Nutzer hat das mehrfach und ausdrücklich gesagt.

Das hat eine Folge, die du nicht umgehen darfst: **die KI muss lokal laufen.**
Siehe Abschnitt 6.

---

## 4. Was schon existiert — bau darauf auf, fang nicht neu an

Im Repository liegt `vidkit`, eine funktionierende, getestete Pipeline
(~5.100 Zeilen Python). Das ist das Fundament. Die App ist eine Oberfläche
darauf plus die KI-Schicht — **kein Neubau.**

| Vorhanden | Zustand |
|---|---|
| `ingest` — Normalisieren auf 1080×1920, 30 fps, −14 LUFS (EBU R128) | getestet, misst −21,4 → −14,3 LUFS |
| `transcribe` — Wort-Timecodes via mlx-whisper (Apple Silicon) | läuft auf dem Zielrechner |
| `plan` — Schnittplan `edit.json` aus Transkript + Stil | heuristisch, s. Abschnitt 6 |
| `assets` — Overlays als HTML/CSS in Chromium, Alpha-MOV | 27 Frames/s, inkrementell gecacht |
| `sfx` — Sounds aus lokaler Bibliothek, pegelgerechnet | getestet |
| `stock` — Pexels-Kandidaten je B-Roll-Slot | Ablauf getestet (Netz eingespeist) |
| `render` — vier Stufen, einzeln wiederholbar | H.264/yuv420p, VideoToolbox |
| `serve` — lokale Timeline im Browser | Blöcke schieben, Passagen wegwerfen |
| `learn` — Referenz-Ad ausmessen → `style.json` | 17/17 Messwerte gegen Sollwerte |
| `edits.py` — Ripple-Schnitt | 4 Operationen, gegen Zahlen geprüft |

Lies vor allem: **`CLAUDE.md`** (Projektregeln, Datenverträge, drei teuer
gefundene Fehler, die nicht zurückgebaut werden dürfen) und **`README.md`**.

### Die Datenverträge, an die du dich hältst

* **`edit.json`** ist der Schnittplan. `segments` sind die *behaltenen* Stücke
  (`source_in/out` zeigen ins `ingest.mp4`, `t_in/out` in die fertige
  Zeitachse). Alle anderen Elemente liegen in der **fertigen** Zeitachse.
  Wortzeiten in Captions sind relativ zum Blockanfang.
* **`style.json`** hält den kompletten Stil. Kein Stilwert steht im Code.
  Größen mit `_rel` sind relativ zur Bildhöhe. `per_10s` ist Dichte, nicht
  Anzahl.
* **Die KI schreibt nie direkt ins Rendering.** Sie erzeugt Vorschläge, die in
  `edit.json` landen. Der Mensch darf dazwischen. `render` liest nur die
  `edit.json`.

---

## 5. Drei Spannungen im Auftrag — und wie du sie auflöst

Ein Auftrag, der so tut, als gäbe es sie nicht, führt zu einer App, die drei
Versprechen bricht. Hier sind sie, und hier ist der jeweils ehrliche Weg.

### 5.1 „Kostenlos" gegen „KI editiert"

Echtes Sprachverständnis kostet — außer es läuft lokal.

**Lösung: Ollama mit einem lokalen Modell.** Auf Apple Silicon läuft ein
7–8B-Modell brauchbar schnell. Die Aufgaben hier sind winzig (ein Transkript
hat 100–300 Wörter), also reicht das.

```
brew install ollama
ollama pull qwen2.5:7b        # oder llama3.1:8b
```

Das ist der **Standardweg** der App: kostenlos, offline, kein Schlüssel.

**Optionaler Aufpreis-Weg** (ausgeschaltet, muss aktiv eingeschaltet werden):
Anbieter-API für bessere Qualität. Zur Einordnung, gerechnet für ein Transkript
von ~200 Wörtern (~2.000 Eingabe-, ~1.000 Ausgabe-Tokens pro Aufruf):

| Modell | Preis / 1 Mio. Tokens (ein/aus) | ~Kosten pro Video |
|---|---|---|
| lokal via Ollama | — | **0 €** |
| `claude-haiku-4-5` | $1 / $5 | ~0,7 Cent |
| `claude-sonnet-5` | $2 / $10 | ~1,4 Cent |
| `claude-opus-5` | $5 / $25 | ~3,5 Cent |

Baue die KI-Schicht **hinter einer Schnittstelle**, damit der Nutzer in den
Einstellungen zwischen „Lokal (kostenlos)" und einem API-Anbieter umschalten
kann, ohne dass sich sonst etwas ändert. Standard ist lokal.

**Sei ehrlich in der Oberfläche:** Ein 7B-Modell trifft schwächere
redaktionelle Entscheidungen als ein großes. Zeig das als Hinweis an, nicht im
Kleingedruckten.

### 5.2 „Formate aus dem Web holen" gegen das, was tatsächlich geht

Der Nutzer wünscht sich, dass die App laufend neue Formate von Meta und
ähnlichen Seiten zieht. Prüfe das, bevor du es zusagst — nach jetzigem Stand:

* **Metas Ad Library API** ist laut Metas eigener Dokumentation auf Anzeigen zu
  **sozialen Themen, Wahlen und Politik** beschränkt. Gewöhnliche
  Produktwerbung ist dort nur in der Weboberfläche durchsuchbar, nicht über die
  API. **Prüfe den aktuellen Stand selbst**, bevor du darauf baust.
* **TikTok Creative Center** zeigt Top-Ads öffentlich im Browser, bietet aber
  keine offene API dafür.
* **Scraping** dieser Oberflächen verstößt gegen deren Nutzungsbedingungen und
  bricht bei jeder Layout-Änderung. **Nicht bauen.**

**Deshalb drei Stufen, in dieser Reihenfolge:**

1. **Mitgelieferte Format-Bibliothek** (Abschnitt 7). Kuratierte, bewährte
   Strukturen als JSON. Trägt sofort, ohne Netz. Aktualisierbar, indem die App
   eine versionierte JSON-Datei von einem vom Betreiber selbst gepflegten Ort
   nachlädt — nicht durch Scraping fremder Seiten.
2. **Eigene Sammelmappe.** Der Nutzer speichert selbst Ads, die ihm gefallen
   (Bildschirmaufnahme oder Download über die dafür vorgesehenen Wege), zieht
   sie in die App, und `learn` misst sie aus → wird zu einem Stil und einem
   Format-Entwurf. **Das existiert schon und funktioniert.**
3. **Offizielle APIs**, falls und soweit sie den Fall abdecken — erst prüfen,
   dann bauen, und die App muss ohne sie vollständig funktionieren.

### 5.3 „Nur runterladen" gegen 2 GB Modelle und ffmpeg

Eine `.app`, die alles mitbringt, wäre riesig und lizenzrechtlich heikel
(ffmpeg-Bundling). Eine, die nichts mitbringt, ist wieder Terminal-Arbeit.

**Lösung: kleine App, geführte Ersteinrichtung.** Beim ersten Start prüft die
App jede Voraussetzung und installiert sie auf Knopfdruck, mit Fortschritt und
verständlicher Fehlermeldung:

| Prüfung | Bei Fehlen |
|---|---|
| Homebrew | Anleitung + Knopf, der den offiziellen Installer startet |
| `ffmpeg` | `brew install ffmpeg` im Hintergrund, mit Log |
| Whisper-Modell (~1,6 GB) | Download mit Fortschrittsbalken |
| Ollama + Modell (~4,5 GB) | `brew install ollama`, `ollama pull …` |
| Chromium für Overlays | `playwright install chromium` |

Das sind die „1–2 Sachen", die der Nutzer akzeptiert hat — aber sie müssen
**in der App** passieren, mit Knöpfen, nicht im Terminal.

---

## 6. Wo die KI eingreift — und wo ausdrücklich nicht

Die bestehende Pipeline entscheidet heuristisch: Substantive erkennen,
Power-Wörter zählen, betonte Stellen messen. Das ergibt Dinge wie das Overlay
„Vielleicht benutzt" — grammatisch ein Treffer, redaktionell wertlos.

Genau diese Lücke füllt die KI. **Sechs Aufgaben, jede mit festem
Eingabe-/Ausgabevertrag.** Jede liefert JSON, das in die `edit.json` gemappt
wird. Keine Aufgabe rendert etwas.

### 6.1 Format vorschlagen

**Ein:** Transkript (Text), Projektbeschreibung, Liste verfügbarer Formate
(Name + Beschreibung).
**Aus:**
```json
{"vorschlaege": [
  {"format": "hook_problem_solution", "eignung": 0.82,
   "begruendung": "Du beschreibst ab Sekunde 4 ein Problem und ab 14 die Lösung.",
   "passt_nicht": ["Kein Handlungsaufruf am Ende"]}
]}
```

### 6.2 Drehbrief erzeugen

**Ein:** gewähltes Format, Projektbeschreibung (Produkt, Zielgruppe, Angebot).
**Aus:** pro Beat: Name, Sollzeit, was gesagt werden soll (Vorschlag, kein
Skript zum Ablesen), Einstellung, häufiger Fehler.

### 6.3 Schnittvorschläge

**Ein:** Transkript mit Wort-Timecodes, gewähltes Format.
**Aus:** Liste von Zeitbereichen mit Begründung:
```json
{"weg": [{"t_in": 12.4, "t_out": 17.1, "grund": "Wiederholung von Sekunde 6"}],
 "hook_kandidat": {"t_in": 21.0, "t_out": 24.2,
                   "grund": "stärkster Satz, gehört nach vorn"}}
```
Umsetzung über die vorhandenen Funktionen in `edits.py`. **Nie automatisch
anwenden** — als Vorschlag in der Timeline zeigen, mit „Übernehmen" und
„Verwerfen".

### 6.4 Overlay-Texte

**Ein:** Transkript-Abschnitte, Stil-Dichte aus `style.json`.
**Aus:** pro Einblendung: Zeitpunkt, Text (**nicht** der Wortlaut, sondern der
Punkt — max. 3 Wörter), Begründung.

### 6.5 B-Roll-Motive

**Ein:** Transkript-Abschnitt je Slot.
**Aus:** 3 englische Suchbegriffe je Slot (Pexels sucht auf Englisch deutlich
besser) plus eine Begründung auf Deutsch.

### 6.6 Motion Graphics

**Ein:** Beats des Formats, verfügbare Vorlagen.
**Aus:** welche Vorlage wann, mit welchem Text.

### Ausdrücklich nicht Aufgabe der KI

* **Nicht rendern.** Bild und Ton macht ffmpeg, Text macht Chromium.
* **Nicht ungefragt anwenden.** Jeder Vorschlag ist ablehnbar.
* **Nicht schweigend scheitern.** Kein Modell da, Zeitüberschreitung, kaputtes
  JSON → die App sagt es und fällt auf die vorhandene Heuristik zurück. Die
  Pipeline muss **ohne KI vollständig funktionieren.**

---

## 7. Format-Bibliothek: Datenformat

Ein Format ist eine Datei unter `formats/<name>.json`. Die App liefert eine
kuratierte Auswahl mit; der Nutzer kann eigene anlegen (auch aus `learn`).

```jsonc
{
  "id": "hook_problem_solution",
  "name": "Hook → Problem → Lösung → CTA",
  "beschreibung": "Der Klassiker für kalte Zielgruppen. Fängt mit einer Aussage, die weh tut.",
  "eignet_sich_fuer": ["Produktvorstellung", "kalte Zielgruppe", "Problemlöser"],
  "gesamtlaenge": { "min": 15, "max": 35, "ideal": 22 },

  "beats": [
    {
      "id": "hook",
      "name": "Hook",
      "laenge": { "min": 1.5, "max": 3.0 },
      "drehhinweis": "Ein Satz, der die Zielgruppe trifft. Keine Begrüßung, kein Name.",
      "haeufiger_fehler": "Zu lang. Nach 3 Sekunden ist gescrollt.",
      "stil": {
        "cuts.cuts_per_10s": 5.0,
        "overlays.per_10s": 2.0,
        "motion.zoom.max_scale": 1.12
      },
      "pflicht_overlay": true
    },
    {
      "id": "problem",
      "name": "Problem",
      "laenge": { "min": 4.0, "max": 8.0 },
      "drehhinweis": "Beschreibe den Zustand vorher. Konkret, nicht abstrakt.",
      "stil": { "cuts.cuts_per_10s": 3.0, "broll.ratio": 0.35 }
    },
    {
      "id": "loesung",
      "name": "Lösung",
      "laenge": { "min": 5.0, "max": 12.0 },
      "drehhinweis": "Zeig das Produkt in Benutzung, nicht auf dem Tisch.",
      "stil": { "broll.ratio": 0.45 }
    },
    {
      "id": "cta",
      "name": "Handlungsaufruf",
      "laenge": { "min": 2.0, "max": 4.0 },
      "drehhinweis": "Eine Handlung. Nicht drei.",
      "pflicht_overlay": true,
      "stil": { "overlays.per_10s": 3.0, "motion_graphics.per_10s": 2.0 }
    }
  ],

  "pruefungen": [
    { "id": "hook_laenge", "beat": "hook", "regel": "laenge <= 3.0",
      "meldung": "Dein Hook ist {wert}s lang. Über 3 s wird weggescrollt." },
    { "id": "cta_vorhanden", "beat": "cta", "regel": "vorhanden",
      "meldung": "Es fehlt ein Handlungsaufruf in den letzten Sekunden." },
    { "id": "gesamtlaenge", "regel": "15 <= laenge <= 35",
      "meldung": "Mit {wert}s bist du außerhalb von 15–35 s." }
  ]
}
```

**Regel: Beat-`stil` überschreibt `style.json` nur für die Dauer des Beats.**
Dadurch wird der Hook hart geschnitten und die Lösung ruhig — mit einer
einzigen Formatdatei, ohne Code.

### Mitzuliefernde Formate (Startsatz)

`hook_problem_solution`, `three_reasons` (mit Zähler-Overlay), `before_after`,
`myth_bust`, `testimonial`, `unboxing_demo`, `founder_story`, `objection_kill`.

Jedes mit ehrlichem `eignet_sich_fuer` — die App soll nicht alles vorschlagen.

---

## 8. Die App: was der Nutzer sieht

Fünf Ansichten, mehr nicht.

1. **Projekte** — Kacheln mit Vorschaubild, Name, Länge, Status. „Neues Projekt".
2. **Projekt anlegen** — Name, worum es geht (Freitext, geht an die KI),
   Zielplattform. Danach: Format wählen oder „Ich habe schon Material".
3. **Formate** — Karten mit Name, Beschreibung, Beats als Balken, „eignet sich
   für". Bei vorhandenem Transkript oben die KI-Empfehlung mit Begründung.
4. **Drehbrief** — die Beats des gewählten Formats als Checkliste, mit Sollzeit
   und Hinweis. Druckbar. Daneben: Video hineinziehen.
5. **Werkbank** — die Hauptansicht. Links Player, darunter Timeline mit allen
   Spuren (Passagen, Captions, Overlays, Zooms, Motion, B-Roll, Sound), rechts
   der Inspektor. Oben eine Leiste mit offenen KI-Vorschlägen, jeder mit
   „Übernehmen" / „Verwerfen". Unten die Format-Prüfungen als Ampel.

Die bestehende `serve`-Oberfläche ist der Ausgangspunkt für Ansicht 5. Sie kann
bereits Timeline, Blöcke schieben, Passagen wegwerfen, Rendern anstoßen.

---

## 9. Technik

| Teil | Wahl | Warum |
|---|---|---|
| Kern | Python 3.11+, das vorhandene `vidkit` | funktioniert, getestet |
| Oberfläche | HTML/CSS/JS ohne Framework, lokal ausgeliefert | vorhanden, bleibt wartbar |
| Fenster | **pywebview** → `.app` via **briefcase** | Python-nah, klein; kein Electron-Ballast |
| KI | **Ollama** über HTTP auf `localhost:11434` | kostenlos, lokal, kein Schlüssel |
| Video | ffmpeg, VideoToolbox auf Apple Silicon | vorhanden |
| Transkript | mlx-whisper, Rückfall faster-whisper | vorhanden, läuft |
| Overlays | Chromium über Playwright | vorhanden |
| B-Roll | Pexels-API (kostenloser Schlüssel) | vorhanden |

**Zwingend:** Die App muss weiter **ohne** Ollama, ohne Pexels und ohne Netz
laufen — dann eben mit Heuristik statt KI und ohne B-Roll. Kein Teil darf zur
Voraussetzung eines anderen werden.

### Strukturierte Antworten erzwingen

Lokale Modelle erfinden gern Felder. Nutze Ollamas `format`-Parameter mit
JSON-Schema, validiere jede Antwort gegen das Schema, und wiederhole bei
Fehlschlag genau einmal mit der Fehlermeldung im Prompt. Danach: Heuristik.

---

## 10. Abnahmekriterien

Nicht „läuft durch" — messbar. An diesen Punkten wird die Arbeit beurteilt.

**Einrichtung**
1. Auf einem Mac ohne Homebrew, ohne Python-Kenntnisse: App laden, öffnen,
   Ersteinrichtung durchklicken, erstes Projekt anlegen — **ohne einen einzigen
   Terminal-Befehl.**
2. Fehlt eine Voraussetzung, nennt die App sie im Klartext und bietet den
   Knopf, der sie behebt.

**Formate**
3. `formats/` enthält mindestens acht Formate nach dem Schema aus Abschnitt 7.
4. Bei vorhandenem Transkript nennt die App die drei bestpassenden Formate mit
   je einer Begründung, die sich auf den tatsächlichen Inhalt bezieht.
5. Die Format-Prüfungen melden korrekt: zu langer Hook, fehlender CTA,
   Gesamtlänge außerhalb des Fensters. Gegen Testmaterial mit bekannten Werten
   nachweisen.

**Schnitt**
6. Rohvideo rein → fertiges MP4 raus, ohne dass der Nutzer die Timeline
   anfassen muss.
7. Jeder KI-Vorschlag ist einzeln annehmbar und verwerfbar. Nichts wird ohne
   Zutun angewendet.
8. Nach jedem Schnitt stimmen alle Elementzeiten. Nachweis wie in
   `tests/test_edits.py`: Passage von 3,59 s weg → Video 3,59 s kürzer,
   nachfolgende Caption exakt 3,59 s früher.

**Ergebnis**
9. Export: 1080×1920, H.264 High, yuv420p, 30 fps, −14 LUFS ±0,5, Safe Zones
   eingehalten. Per `ffprobe` und `ebur128` nachweisen, nicht behaupten.
10. Zweiter Durchlauf desselben Projekts mit einer geänderten Zahl in
    `style.json` ergibt ein sichtbar anderes Video, **ohne Codeänderung**.

**Kosten**
11. Vollständiger Durchlauf ohne einen einzigen kostenpflichtigen Dienst.
    Nachweisbar: kein API-Schlüssel außer dem kostenlosen Pexels-Schlüssel.

---

## 11. Reihenfolge

Nicht alles auf einmal. Nach jeder Stufe muss die App benutzbar sein.

1. **Ollama-Anbindung** + Schnittstelle für Anbieterwechsel + Schema-Validierung
   und Rückfall auf Heuristik. *Ohne das ist alles andere Kosmetik.*
2. **Format-Bibliothek**: Schema, acht Formate, Prüfungen, `--format` in `plan`.
3. **KI-Aufgaben 6.1 und 6.4** (Format vorschlagen, Overlay-Texte) — die zwei
   mit dem größten sichtbaren Unterschied.
4. **Projektverwaltung** in der Oberfläche, Video per Ziehen hineinlegen.
5. **Vorschlagsleiste** in der Werkbank: annehmen/verwerfen.
6. **KI-Aufgaben 6.3, 6.5, 6.6** (Schnitt, B-Roll, Motion Graphics).
7. **B-Roll-Browser**: im Programm suchen, Vorschau sehen, per Klick einsetzen.
8. **Drehbrief-Ansicht.**
9. **Verpacken** als `.app` mit Ersteinrichtung.

---

## 12. Ausdrücklich nicht

* Keine Cloud-Renderdienste, keine Abo-Werkzeuge.
* Keine CapCut-Integration. (Es gibt keine öffentliche API; das Entwurfsformat
  ist undokumentiert und bricht bei Updates.)
* Kein Scraping von Werbebibliotheken.
* Keine Assets aus fremden Videos — `learn` misst Zahlen, sonst nichts. Keine
  Sounds, keine Grafiken, keine Bildausschnitte.
* Kein Zwangs-Login, keine Telemetrie, kein Konto.
* Kein Text über ffmpeg `drawtext` — Overlays laufen über HTML/CSS.

---

## 13. Arbeitsweise

Aus `CLAUDE.md`, gilt unverändert:

* **Messen, nicht behaupten.** Bei Bild und Ton heißt „läuft durch" wenig.
  Frames ziehen und ansehen, Pegel messen, gegen Sollwerte rechnen.
* **Auf kurzem Testmaterial prüfen, bevor es weitergeht.** `tests/make_fixture.py`
  und `tests/make_reference.py` erzeugen es lokal.
* **Jede neue Messung bekommt eine Prüfung** mit einem nachrechenbaren Sollwert.
* **Fehlermeldungen auf Deutsch, mit dem nächsten Schritt darin.**
* **Code und Kommentare auf Deutsch**, keine Umlaute in Bezeichnern. Kommentare
  erklären das Warum.
* Die drei dokumentierten Fallen in `CLAUDE.md` nicht zurückbauen.

---

## 14. Wenn etwas nicht geht

Sag es. Dieser Auftrag enthält Wünsche, die technisch nicht sauber erfüllbar
sind — Formate automatisch von Meta ziehen ist der klarste Fall. Ein Werkzeug,
das so tut, als könnte es das, ist schlechter als eines, das die Grenze
benennt und den nächstbesten Weg anbietet.

Der Nutzer hat mehrfach gezeigt, dass er ehrliche Auskunft einer glatten
vorzieht. Halte es so.

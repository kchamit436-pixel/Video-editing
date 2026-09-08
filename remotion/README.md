# remotion — Motion Graphics fuer die Shorts

Animierte Einblendungen in 1080x1920, gebaut mit [Remotion](https://remotion.dev)
(React im Browser, gerendert mit Chromium — laeuft komplett lokal, kein Abo,
kein Cloud-Render).

Der Ordner ist eigenstaendig: `vidkit` weiss nichts davon, und Remotion weiss
nichts von `vidkit`. Die Bruecke ist eine Datei — entweder rendert Remotion
ueber ein fertiges Video, oder es rendert die Grafiken mit transparentem
Hintergrund, die dann in der Pipeline darueber gelegt werden.

## Loslegen

```
npm install
npm run dev        # oeffnet das Studio auf localhost:3000
```

Im Studio steht links jede Komposition einzeln. Parameter (Texte, Zeiten,
Farben) lassen sich rechts aendern, ohne den Code anzufassen.

## Rendern

```
npx remotion render Demo out/demo.mp4
```

Als Overlay mit Transparenz, zum Darueberlegen in der Pipeline:

```
npx remotion render Titel out/titel.mov --codec=prores --prores-profile=4444
```

Dafuer muss die Komposition ohne Hintergrund laufen — die Einzelansichten in
`Root.tsx` haben den Grund nur zur besseren Vorschau.

## Die Abfolge

`Abfolge` zeigt Wecker, Matheaufgabe und QR-Code hintereinander — immer nur
eins, jedes springt herein. Die Abstaende werden von Motiv zu Motiv kuerzer
(`TAKTE` in `Abfolge.tsx`), dadurch steigt der Druck. Am Ende bleibt der
Wecker stehen, klingelt heftiger und wird heruntergerissen.

Es gibt sie zweimal:

* **`Abfolge`** — ohne Hintergrund. Dahinter ist wirklich nichts, auch im
  weggerissenen Bereich. Das ist die Fassung zum Darueberlegen.
* **`AbfolgeAufRaster`** — mit dem dunklen Raster dahinter, als fertiges Bild.

Mit durchsichtigem Hintergrund exportieren — der Riss braucht einen
Alphakanal, sonst wird aus "weg" ein schwarzer Fleck:

```
npx remotion render Abfolge overlay.webm \
  --codec=vp8 --pixel-format=yuva420p --image-format=png
```

Fuer den Schnitt in Premiere oder Resolve stattdessen ProRes 4444:

```
npx remotion render Abfolge overlay.mov \
  --codec=prores --prores-profile=4444 --image-format=png
```

Der QR-Code wird aus `qrZiel` wirklich erzeugt und ist scanbar — im Studio
rechts umstellen oder beim Rendern mit `--props='{"qrZiel":"https://..."}'`.
Der Wecker ist gezeichnet; wer ein eigenes Freisteller-PNG hat, legt es nach
`public/` und gibt `bild="wecker.png"` an, dann wird das genommen.

## Aufbau

```
src/
  stil.ts            Farben, Schriftgroessen, Federn — alle Stilwerte
  Abfolge.tsx        Wecker/Mathe/QR nacheinander, mit Abriss am Ende
  Demo.tsx           alle Elemente nacheinander
  Root.tsx           registriert jede Komposition fuers Studio
  elemente/
    feder.ts         Federn und Staffelung, gekapselt
    zufall.ts        wiederholbarer Zufall fuer Risskanten
    Abriss.tsx       reisst Inhalt weg, dahinter bleibt Transparenz
    Papier.tsx       weisses Blatt mit gerissenen Kanten
    Wecker.tsx       gezeichneter Wecker im Zeitungsdruck-Look
    Matheaufgabe.tsx Integral als Bruch
    QrCode.tsx       echter, scanbarer Code mit runden Modulen
    RasterGrund.tsx  dunkles Raster mit Schimmer
    Hintergrund.tsx  wandernder Verlauf plus Vignette
    Titel.tsx        Kicker und Schlagzeile, Wort fuer Wort
    ListenPunkte.tsx abgehakte Aufzaehlung
    Zaehler.tsx      hochlaufende Zahl mit auslaufender Kurve
    UntereDrittel.tsx  aufgedeckter Namenskasten
    Stempel.tsx      Abzeichen, springt herein
    Caption.tsx      Untertitel mit Wort-Hervorhebung
```

## Regeln, die hier gelten

* Stilwerte gehoeren in `src/stil.ts`, nicht in ein Element. Groessen mit
  `_rel` sind relativ zur Bildhoehe — wie in der `style.json`.
* Wortzeiten in `Caption` sind Bilder **relativ zum Blockanfang**, dieselbe
  Abmachung wie in der `edit.json`.
* Bewegung laeuft ueber `useCurrentFrame()`, nie ueber CSS-`transition` oder
  `Date.now()`. Sonst flackert der Render, weil jedes Bild einzeln entsteht.
* Videodateien kommen nach `public/` und bleiben lokal — nicht ins Repo.
* Risskanten werden mit gesetztem Samen gewuerfelt (`zufall.ts`). Mit
  `Math.random` waere die Kante in jedem Bild anders und wuerde flimmern.
* Was reisst, muss vorher wie Papier ausgesehen haben. Deshalb sitzt jedes
  Motiv auf einem `Papier`-Blatt, nicht nur das letzte.

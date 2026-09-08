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

## Aufbau

```
src/
  stil.ts            Farben, Schriftgroessen, Federn — alle Stilwerte
  Demo.tsx           alle Elemente nacheinander
  Root.tsx           registriert jede Komposition fuers Studio
  elemente/
    feder.ts         Federn und Staffelung, gekapselt
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

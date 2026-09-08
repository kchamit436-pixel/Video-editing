import { AbsoluteFill, Series } from "remotion";
import { Caption, type Wortzeit } from "./elemente/Caption";
import { Hintergrund } from "./elemente/Hintergrund";
import { ListenPunkte } from "./elemente/ListenPunkte";
import { Stempel } from "./elemente/Stempel";
import { Titel } from "./elemente/Titel";
import { UntereDrittel } from "./elemente/UntereDrittel";
import { Zaehler } from "./elemente/Zaehler";

export const DEMO_WOERTER: Wortzeit[] = [
  { wort: "Und", von: 0, bis: 8 },
  { wort: "genau", von: 8, bis: 20 },
  { wort: "deshalb", von: 20, bis: 34 },
  { wort: "haben", von: 34, bis: 44 },
  { wort: "wir", von: 44, bis: 52 },
  { wort: "es", von: 52, bis: 58 },
  { wort: "anders", von: 58, bis: 74 },
  { wort: "gemacht.", von: 74, bis: 95 },
];

// Zeigt alle Elemente hintereinander. Der Hintergrund laeuft durch, damit
// zwischen den Abschnitten nichts blitzt.
export const Demo: React.FC = () => {
  return (
    <AbsoluteFill>
      <Hintergrund />
      <Series>
        <Series.Sequence durationInFrames={105}>
          <Titel
            kicker="Neu im Shop"
            zeilen={["Drei Wochen", "Arbeit in", "elf Minuten."]}
            betont="elf"
            start={0}
            versatz={3}
          />
        </Series.Sequence>

        <Series.Sequence durationInFrames={105}>
          <ListenPunkte
            punkte={[
              "Kein Abo, kein Cloud-Upload",
              "Laeuft auf deinem eigenen Rechner",
              "Fertig geschnitten in 9:16",
            ]}
            start={0}
            versatz={7}
          />
        </Series.Sequence>

        <Series.Sequence durationInFrames={90}>
          <Zaehler
            von={0}
            bis={11}
            praefix=""
            einheit=" Min."
            unterzeile="statt drei Wochen"
            start={0}
            dauer={45}
            nachkommastellen={0}
          />
        </Series.Sequence>

        <Series.Sequence durationInFrames={90}>
          <Stempel text="Ohne Abo" start={6} neigung={-4} />
          <UntereDrittel name="Hamit K." zeile="Gruender" start={0} />
        </Series.Sequence>

        <Series.Sequence durationInFrames={120}>
          <Caption woerter={DEMO_WOERTER} start={0} />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};

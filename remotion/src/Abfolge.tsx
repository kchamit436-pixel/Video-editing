import { AbsoluteFill, Series, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Abriss } from "./elemente/Abriss";
import { Matheaufgabe } from "./elemente/Matheaufgabe";
import { Papier } from "./elemente/Papier";
import { QrCode } from "./elemente/QrCode";
import { Wecker } from "./elemente/Wecker";
import { useFeder } from "./elemente/feder";

// Die Taktung ist der eigentliche Effekt: die Abstaende werden kuerzer, der
// Druck steigt. Gleich lange Einblendungen wirken wie eine Diashow.
export const TAKTE = [20, 18, 16, 15, 13, 12, 11, 10];
export const FINALE_DAUER = 95;
export const ABFOLGE_DAUER = TAKTE.reduce((a, b) => a + b, 0) + FINALE_DAUER;

const MATHE = [
  { zaehler: "x² + 2", nenner: "x² + 1", ende: "dx" },
  { zaehler: "sin x", nenner: "1 + cos x", ende: "dx" },
  { zaehler: "3x − 1", nenner: "x² + 4", ende: "dx" },
];

type MotivArt = "wecker" | "mathe" | "qr";
const REIHE: MotivArt[] = ["wecker", "mathe", "qr", "wecker", "mathe", "qr", "wecker", "mathe"];

// Jedes Motiv springt herein und wird nicht eingeblendet. Der Unterschied
// liegt in der Feder: sie schiesst ueber 1 hinaus und wippt zurueck.
const Auftritt: React.FC<{
  neigung: number;
  dauer: number;
  kinder: React.ReactNode;
}> = ({ neigung, dauer, kinder }) => {
  const frame = useCurrentFrame();
  const feder = useFeder(0, "ueberschwingen");

  // Kurz vor dem Schnitt ein winziges Zusammenziehen — das verdeckt die
  // harte Kante zum naechsten Motiv, ohne den Takt weich zu machen.
  const abgang = interpolate(frame, [dauer - 3, dauer], [1, 0.94], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          transform: `scale(${Math.max(0, feder) * abgang}) rotate(${neigung * Math.min(1, feder)}deg)`,
          opacity: Math.max(0, Math.min(1, feder * 3)),
        }}
      >
        {kinder}
      </div>
    </AbsoluteFill>
  );
};

const Motiv: React.FC<{ art: MotivArt; nummer: number; qrZiel: string }> = ({
  art,
  nummer,
  qrZiel,
}) => {
  if (art === "mathe") {
    const aufgabe = MATHE[nummer % MATHE.length];
    return (
      <Papier breite={860} hoehe={540} samen={nummer * 7 + 1} rauheit={1.6} kinder={
        <Matheaufgabe {...aufgabe} groesse={120} />
      } />
    );
  }

  if (art === "qr") {
    return (
      <Papier breite={720} hoehe={720} samen={nummer * 7 + 2} rauheit={1.6} kinder={
        <QrCode inhalt={qrZiel} groesse={560} farbe="#0A0A0A" papier="transparent" eckenradius={0.24} />
      } />
    );
  }

  return (
    <Papier breite={760} hoehe={760} samen={nummer * 7 + 3} rauheit={2.0} kinder={
      <Wecker groesse={600} stunde={1} minute={50} klingeln={3.2} />
    } />
  );
};

export const Abfolge: React.FC<{ qrZiel: string }> = ({ qrZiel }) => {
  return (
    <AbsoluteFill>
      <Series>
        {REIHE.map((art, i) => (
          <Series.Sequence key={i} durationInFrames={TAKTE[i]}>
            <Auftritt
              neigung={i % 2 === 0 ? -3.5 : 3.5}
              dauer={TAKTE[i]}
              kinder={<Motiv art={art} nummer={i} qrZiel={qrZiel} />}
            />
          </Series.Sequence>
        ))}

        <Series.Sequence durationInFrames={FINALE_DAUER}>
          <Finale />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};

// Der Wecker kommt wie die anderen, bleibt aber stehen, klingelt lauter —
// und wird dann heruntergerissen.
const Finale: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const feder = useFeder(0, "ueberschwingen");

  const rissStart = Math.round(fps * 1.5);
  const rissDauer = Math.round(fps * 1.05);
  const fortschritt = interpolate(frame, [rissStart, rissStart + rissDauer], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Kurz vor dem Riss wird das Klingeln heftiger. Das ist die Ansage, dass
  // gleich etwas passiert — ohne sie kommt der Riss aus dem Nichts.
  const klingeln = interpolate(frame, [0, rissStart - 12, rissStart], [3.2, 3.2, 9], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ transform: `scale(${Math.max(0, feder)})` }}>
        <Abriss fortschritt={fortschritt} samen={91} rauheit={5.5} kinder={
          <Papier breite={860} hoehe={860} samen={5} rauheit={2.2} kinder={
            <Wecker groesse={680} stunde={1} minute={50} klingeln={klingeln} />
          } />
        } />
      </div>
    </AbsoluteFill>
  );
};

import "./index.css";
import { AbsoluteFill, Composition } from "remotion";
import { Demo, DEMO_WOERTER } from "./Demo";
import { Caption } from "./elemente/Caption";
import { Hintergrund } from "./elemente/Hintergrund";
import { ListenPunkte } from "./elemente/ListenPunkte";
import { Stempel } from "./elemente/Stempel";
import { Titel } from "./elemente/Titel";
import { UntereDrittel } from "./elemente/UntereDrittel";
import { Zaehler } from "./elemente/Zaehler";
import { FORMAT } from "./stil";

// Jedes Element ist einzeln registriert, damit man im Studio daran arbeiten
// kann, ohne die ganze Demo abzuspielen. "Demo" zeigt alles nacheinander.
const format = {
  fps: FORMAT.fps,
  width: FORMAT.breite,
  height: FORMAT.hoehe,
} as const;

// Fuer die Einzelansichten: gleicher Grund wie in der Demo, sonst steht der
// Text auf Weiss und man sieht nichts.
const mitGrund =
  <P extends object>(Element: React.FC<P>): React.FC<P> =>
  (props) => (
    <AbsoluteFill>
      <Hintergrund />
      <Element {...props} />
    </AbsoluteFill>
  );

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Demo"
        component={Demo}
        durationInFrames={510}
        {...format}
      />

      <Composition
        id="Titel"
        component={mitGrund(Titel)}
        durationInFrames={105}
        {...format}
        defaultProps={{
          kicker: "Neu im Shop",
          zeilen: ["Drei Wochen", "Arbeit in", "elf Minuten."],
          betont: "elf",
          start: 0,
          versatz: 3,
        }}
      />

      <Composition
        id="ListenPunkte"
        component={mitGrund(ListenPunkte)}
        durationInFrames={105}
        {...format}
        defaultProps={{
          punkte: [
            "Kein Abo, kein Cloud-Upload",
            "Laeuft auf deinem eigenen Rechner",
            "Fertig geschnitten in 9:16",
          ],
          start: 0,
          versatz: 7,
        }}
      />

      <Composition
        id="Zaehler"
        component={mitGrund(Zaehler)}
        durationInFrames={90}
        {...format}
        defaultProps={{
          von: 0,
          bis: 11,
          praefix: "",
          einheit: " Min.",
          unterzeile: "statt drei Wochen",
          start: 0,
          dauer: 45,
          nachkommastellen: 0,
        }}
      />

      <Composition
        id="UntereDrittel"
        component={mitGrund(UntereDrittel)}
        durationInFrames={90}
        {...format}
        defaultProps={{
          name: "Hamit K.",
          zeile: "Gruender",
          start: 0,
        }}
      />

      <Composition
        id="Stempel"
        component={mitGrund(Stempel)}
        durationInFrames={60}
        {...format}
        defaultProps={{
          text: "Ohne Abo",
          start: 0,
          neigung: -4,
        }}
      />

      <Composition
        id="Caption"
        component={mitGrund(Caption)}
        durationInFrames={120}
        {...format}
        defaultProps={{
          woerter: DEMO_WOERTER,
          start: 0,
        }}
      />
    </>
  );
};

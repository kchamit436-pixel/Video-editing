import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { FARBEN, GROESSE, SCHRIFT, rel } from "../stil";
import { useFeder, useFederStaffel } from "./feder";

export type TitelProps = {
  kicker: string;
  zeilen: string[];
  betont: string;
  start: number;
  versatz: number;
};

// Ein Wort steigt von unten herein und wird dabei sichtbar. Der Versatz
// zwischen den Woertern ist das ganze Geheimnis: gleichzeitig wirkt es
// billig, nacheinander wirkt es gesprochen.
const Wort: React.FC<{
  wort: string;
  index: number;
  versatz: number;
  start: number;
  betont: boolean;
  hoehe: number;
}> = ({ wort, index, versatz, start, betont, hoehe }) => {
  const feder = useFederStaffel(index, versatz, start, "knackig");
  const hub = rel(hoehe, 0.045);

  // Der Balken unter dem betonten Wort laeuft erst los, wenn das Wort steht.
  const balken = useFederStaffel(index, versatz, start + 6, "weich");

  return (
    <span
      style={{
        display: "inline-block",
        position: "relative",
        marginRight: "0.28em",
        opacity: interpolate(feder, [0, 1], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
        transform: `translateY(${(1 - feder) * hub}px)`,
        color: betont ? FARBEN.akzent : FARBEN.schrift,
      }}
    >
      {wort}
      {betont ? (
        <span
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: "-0.12em",
            height: "0.09em",
            backgroundColor: FARBEN.akzent,
            borderRadius: 999,
            transform: `scaleX(${Math.max(0, Math.min(1, balken))})`,
            transformOrigin: "left center",
          }}
        />
      ) : null}
    </span>
  );
};

export const Titel: React.FC<TitelProps> = ({
  kicker,
  zeilen,
  betont,
  start,
  versatz,
}) => {
  const frame = useCurrentFrame();
  const { height, durationInFrames } = useVideoConfig();
  const kickerFeder = useFeder(start, "weich");

  // Am Ende geht der ganze Block wieder weg — sonst muss die Komposition
  // hart schneiden, und das sieht man.
  const abgang = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        padding: rel(height, GROESSE.rand_rel),
        justifyContent: "center",
        fontFamily: SCHRIFT.familie,
        opacity: abgang,
      }}
    >
      <div
        style={{
          fontSize: rel(height, GROESSE.kicker_rel),
          fontWeight: SCHRIFT.halbfett,
          letterSpacing: "0.22em",
          textTransform: "uppercase",
          color: FARBEN.akzent,
          marginBottom: rel(height, 0.022),
          opacity: Math.max(0, Math.min(1, kickerFeder)),
          transform: `translateX(${(1 - kickerFeder) * -rel(height, 0.02)}px)`,
        }}
      >
        {kicker}
      </div>

      <div
        style={{
          fontSize: rel(height, GROESSE.titel_rel),
          fontWeight: SCHRIFT.fett,
          lineHeight: 1.08,
          letterSpacing: "-0.02em",
        }}
      >
        {zeilen.map((zeile, zeileIndex) => {
          // Der Wortzaehler laeuft ueber Zeilengrenzen hinweg weiter, damit
          // die Staffel nicht bei jeder Zeile von vorn anfaengt.
          const vorher = zeilen
            .slice(0, zeileIndex)
            .reduce((summe, z) => summe + z.split(" ").length, 0);

          return (
            <div key={zeileIndex}>
              {zeile.split(" ").map((wort, wortIndex) => (
                <Wort
                  key={`${zeileIndex}-${wortIndex}`}
                  wort={wort}
                  index={vorher + wortIndex}
                  versatz={versatz}
                  start={start}
                  betont={
                    betont.length > 0 &&
                    wort.replace(/[.,!?:;]/g, "").toLowerCase() ===
                      betont.toLowerCase()
                  }
                  hoehe={height}
                />
              ))}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

import { AbsoluteFill, useVideoConfig } from "remotion";
import { FARBEN, GROESSE, SCHRIFT, rel } from "../stil";
import { useFederStaffel } from "./feder";

export type ListenPunkteProps = {
  punkte: string[];
  start: number;
  versatz: number;
};

const Punkt: React.FC<{
  text: string;
  index: number;
  versatz: number;
  start: number;
  hoehe: number;
}> = ({ text, index, versatz, start, hoehe }) => {
  const feder = useFederStaffel(index, versatz, start, "knackig");
  // Der Haken kommt eine Spur nach der Zeile — erst da sein, dann abhaken.
  const haken = useFederStaffel(index, versatz, start + 4, "ueberschwingen");
  const sichtbar = Math.max(0, Math.min(1, feder));

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: rel(hoehe, 0.02),
        marginBottom: rel(hoehe, 0.028),
        opacity: sichtbar,
        transform: `translateX(${(1 - feder) * -rel(hoehe, 0.06)}px)`,
      }}
    >
      <div
        style={{
          flex: "none",
          width: rel(hoehe, 0.042),
          height: rel(hoehe, 0.042),
          borderRadius: 999,
          backgroundColor: FARBEN.akzent,
          color: FARBEN.aufAkzent,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: rel(hoehe, 0.024),
          fontWeight: SCHRIFT.fett,
          transform: `scale(${Math.max(0, haken)})`,
        }}
      >
        &#10003;
      </div>
      <div
        style={{
          fontSize: rel(hoehe, GROESSE.punkt_rel),
          fontWeight: SCHRIFT.halbfett,
          color: FARBEN.schrift,
          lineHeight: 1.2,
        }}
      >
        {text}
      </div>
    </div>
  );
};

export const ListenPunkte: React.FC<ListenPunkteProps> = ({
  punkte,
  start,
  versatz,
}) => {
  const { height } = useVideoConfig();

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        padding: rel(height, GROESSE.rand_rel),
        fontFamily: SCHRIFT.familie,
      }}
    >
      <div>
        {punkte.map((punkt, index) => (
          <Punkt
            key={index}
            text={punkt}
            index={index}
            versatz={versatz}
            start={start}
            hoehe={height}
          />
        ))}
      </div>
    </AbsoluteFill>
  );
};

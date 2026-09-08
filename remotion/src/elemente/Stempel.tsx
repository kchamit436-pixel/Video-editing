import { AbsoluteFill, useVideoConfig } from "remotion";
import { FARBEN, SCHRIFT, rel } from "../stil";
import { useFeder } from "./feder";

export type StempelProps = {
  text: string;
  start: number;
  neigung: number;
};

// Springt herein und wippt nach — die harte Feder darf ueber 1 schiessen,
// deshalb wird der Wert hier bewusst nicht geklemmt.
export const Stempel: React.FC<StempelProps> = ({ text, start, neigung }) => {
  const { height } = useVideoConfig();
  const feder = useFeder(start, "ueberschwingen");

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        fontFamily: SCHRIFT.familie,
      }}
    >
      <div
        style={{
          padding: `${rel(height, 0.016)}px ${rel(height, 0.034)}px`,
          borderRadius: 999,
          backgroundColor: FARBEN.akzent,
          color: FARBEN.aufAkzent,
          fontSize: rel(height, 0.032),
          fontWeight: SCHRIFT.fett,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          transform: `scale(${Math.max(0, feder)}) rotate(${neigung * feder}deg)`,
          boxShadow: `0 ${rel(height, 0.01)}px ${rel(height, 0.03)}px #00000055`,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

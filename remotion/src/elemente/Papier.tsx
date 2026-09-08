import { useMemo } from "react";
import { risskante } from "./zufall";

// Weisses Blatt mit gerissenen Kanten. Alle Motive sitzen darauf, damit der
// Abriss am Ende nicht aus dem Nichts kommt — was reisst, muss vorher wie
// Papier ausgesehen haben.
export const Papier: React.FC<{
  breite: number;
  hoehe: number;
  samen: number;
  rauheit: number;
  kinder: React.ReactNode;
}> = ({ breite, hoehe, samen, rauheit, kinder }) => {
  const form = useMemo(() => {
    const oben = risskante(samen, 14, rauheit, 0);
    const rechts = risskante(samen + 1, 18, rauheit, 100);
    const unten = risskante(samen + 2, 14, rauheit, 100);
    const links = risskante(samen + 3, 18, rauheit, 0);

    const punkte = [
      ...oben.map((k) => `${k.p}% ${Math.max(0, k.q)}%`),
      ...rechts.map((k) => `${Math.min(100, k.q)}% ${k.p}%`),
      ...unten.reverse().map((k) => `${k.p}% ${Math.min(100, k.q)}%`),
      ...links.reverse().map((k) => `${Math.max(0, k.q)}% ${k.p}%`),
    ];
    return `polygon(${punkte.join(", ")})`;
  }, [samen, rauheit]);

  return (
    <div
      style={{
        width: breite,
        height: hoehe,
        clipPath: form,
        backgroundColor: "#FBFBF7",
        // Papierkorn: sehr feine Punkte, sonst wirkt die Flaeche wie Plastik.
        backgroundImage:
          "radial-gradient(rgba(0,0,0,0.05) 0.7px, transparent 0.8px)",
        backgroundSize: "4px 4px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        filter: "drop-shadow(0 24px 34px rgba(0,0,0,0.55))",
      }}
    >
      {kinder}
    </div>
  );
};

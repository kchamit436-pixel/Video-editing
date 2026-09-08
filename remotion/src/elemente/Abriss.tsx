import { useMemo } from "react";
import { zufallsfolge } from "./zufall";

// Reisst den Inhalt weg. Was weggerissen ist, ist wirklich weg — dort steht
// kein Hintergrund, sondern nichts. Beim Export mit Alphakanal
// (ProRes 4444 oder WebM) bleibt genau dort das Bild durchsichtig.
//
// Zwei Kopien desselben Inhalts: die eine wird an der Risslinie nach unten
// abgeschnitten und faellt weg, die andere faengt an der Risslinie an und
// bleibt liegen. Weil beide dieselbe Zackenfolge benutzen, passen die Kanten
// zusammen wie zwei Haelften eines Blattes.
const ZACKEN = 34;

export const Abriss: React.FC<{
  fortschritt: number;
  samen: number;
  rauheit: number;
  kinder: React.ReactNode;
}> = ({ fortschritt, samen, rauheit, kinder }) => {
  // Einmal gewuerfelt, dann fest: die Zacken duerfen sich beim Wandern der
  // Linie nicht veraendern, sonst flimmert die Kante.
  const zacken = useMemo(() => {
    const wuerfel = zufallsfolge(samen);
    return Array.from({ length: ZACKEN + 1 }, (_, i) => {
      const grob = (wuerfel() - 0.5) * rauheit;
      const fein = (wuerfel() - 0.5) * rauheit * 0.4;
      // Zur Mitte hin darf der Riss weiter ausschlagen als an den Raendern,
      // wo das Papier noch gehalten wird.
      const mitte = Math.sin((i / ZACKEN) * Math.PI);
      return (grob + fein) * (0.35 + 0.65 * mitte);
    });
  }, [samen, rauheit]);

  // Die Linie laeuft von oberhalb des Blattes bis unterhalb, damit Anfang
  // und Ende sauber ausserhalb liegen.
  const linie = -10 + fortschritt * 120;
  const punkte = zacken.map((abweichung, i) => ({
    x: (i / ZACKEN) * 100,
    y: linie + abweichung,
  }));

  const alsPolygon = (folge: { x: number; y: number }[]) =>
    `polygon(${folge.map((p) => `${p.x}% ${p.y}%`).join(", ")})`;

  const oben = alsPolygon([
    { x: 0, y: -30 },
    { x: 100, y: -30 },
    ...[...punkte].reverse(),
  ]);
  const unten = alsPolygon([
    ...punkte,
    { x: 100, y: 130 },
    { x: 0, y: 130 },
  ]);

  // Der abgerissene Teil muss sofort weg sein, nicht gemaechlich fallen:
  // bewegt er sich langsam, liegt er genau auf dem Rest und man sieht vom
  // Riss nichts. Der Exponent unter 1 heisst "reisst an und faellt dann".
  const fall = Math.max(0, fortschritt) ** 0.7 * 300;
  const seitlich = fortschritt * 12;
  const drehung = fortschritt * 17;

  // Die erste Kopie liegt im Fluss und gibt dem Kasten seine Groesse — nur
  // deshalb beziehen sich die Prozente auf das Blatt und nicht auf das
  // ganze Bild. Die zweite liegt deckungsgleich darueber.
  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <div style={{ clipPath: unten }}>{kinder}</div>

      <div
        style={{
          position: "absolute",
          inset: 0,
          clipPath: oben,
          transform: `translate(${seitlich}%, ${fall}%) rotate(${drehung}deg)`,
          transformOrigin: "50% 0%",
          opacity: fortschritt > 0.75 ? Math.max(0, (1 - fortschritt) / 0.25) : 1,
        }}
      >
        {kinder}
      </div>
    </div>
  );
};

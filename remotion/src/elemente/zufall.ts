// Wiederholbarer Zufall. Ein Riss muss bei jedem Bild derselbe sein, sonst
// zappelt die Kante — mit Math.random waere sie in jedem Frame anders.
export const zufallsfolge = (samen: number) => {
  let zustand = (samen * 2654435761) >>> 0;
  return () => {
    zustand = (zustand * 1664525 + 1013904223) >>> 0;
    return zustand / 4294967296;
  };
};

// Gerissene Kante als Polygonpunkte in Prozent. 'rauheit' ist der Ausschlag
// quer zur Kante, 'zacken' die Zahl der Stuetzpunkte.
export const risskante = (
  samen: number,
  zacken: number,
  rauheit: number,
  grundlinie: number,
): { p: number; q: number }[] => {
  const wuerfel = zufallsfolge(samen);
  const punkte: { p: number; q: number }[] = [];
  for (let i = 0; i <= zacken; i += 1) {
    const p = (i / zacken) * 100;
    // Zwei Ausschlaege uebereinander: grobe Wellen plus feine Fasern.
    const grob = (wuerfel() - 0.5) * rauheit;
    const fein = (wuerfel() - 0.5) * rauheit * 0.35;
    punkte.push({ p, q: grundlinie + grob + fein });
  }
  return punkte;
};

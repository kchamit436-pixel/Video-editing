// Integral als Bruch, in einer Serifenschrift gesetzt. Kein Bild, damit die
// Aufgabe austauschbar bleibt.
export const Matheaufgabe: React.FC<{
  zaehler: string;
  nenner: string;
  ende: string;
  groesse: number;
}> = ({ zaehler, nenner, ende, groesse }) => {
  const serif = '"Times New Roman", "Nimbus Roman", Georgia, serif';

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: groesse * 0.12,
        color: "#0A0A0A",
        fontFamily: serif,
        fontSize: groesse,
        lineHeight: 1,
      }}
    >
      <span style={{ fontSize: groesse * 2.1, fontWeight: 400 }}>&#8747;</span>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <span style={{ fontStyle: "italic", padding: `0 ${groesse * 0.1}px` }}>
          {zaehler}
        </span>
        <div
          style={{
            width: "100%",
            height: Math.max(2, groesse * 0.045),
            backgroundColor: "#0A0A0A",
            margin: `${groesse * 0.1}px 0`,
          }}
        />
        <span style={{ fontStyle: "italic", padding: `0 ${groesse * 0.1}px` }}>
          {nenner}
        </span>
      </div>
      <span style={{ fontStyle: "italic" }}>{ende}</span>
    </div>
  );
};

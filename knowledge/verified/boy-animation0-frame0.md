# Prop 220 Boy: Animation 0, Frame 0

Status: **VERIFIED** für Bitstrom, Root-Q10 und exakt diesen einen
Animationsframe. Die unten ausdrücklich als `SUPERSEDED` markierten alten
Matrix-/Bounding-Box-Werte gehören nicht zum aktuellen Produktionsstand.

- Prop 220 besitzt 52 Animationseinträge; Index 0 verweist auf Animations-ID
  1026.
- Der 544-Byte-Blob liegt bei ROM `0x16E37C0..0x16E39E0` und hat SHA-256
  `0693bf4740d35faa69637a37dede4a81fc84e2d9aabc812da03fdb6164de1d78`.
- Die Kanalmap für Animation 0 ist `0..20`.
- Frame 0 beginnt bei Bloboffset `0x8e`, hat 25 Byte und wird MSB-first
  gelesen.
- Die Root-Translation ist raw Q10 `(0,-9216,0)`, im Modellraum
  `(0,-9,0)`. `func_80074B50` berechnet sie als
  `(signed_base << 11) + (sample << 10)` und dividiert danach durch 1024.
  Die frühere Rechnung ohne `sample << 10` wurde bei der zeitlichen
  Validierung korrigiert.
- Der Frame liefert 60 gespeicherte Winkelskalare für Kanäle 0 bis 19. Ihre
  Reihenfolge relativ zum Matrixhelfer ist A/C/B; `_local_matrix(A,B,C)`
  erhält `[stored[0], stored[2], stored[1]]`. Scratchslot
  20 wird von diesem Decoder nicht geschrieben und ist für Boy ein Leaf ohne
  aktive Geometrie; im sauberen statischen Initialzustand ist er null.
- 4096 Winkelindizes entsprechen einem Vollkreis. JFG verwendet seine
  Quarter-Sine-Tabelle bei ROM `0xA8994`.
- Alle für Kanäle 0 bis 19 dekodierten Scale-Rohwerte sind null und bewirken
  Faktor 1.
- Mit den bereits bestätigten lokalen Prop-Translationen, der korrigierten
  Komponentenabbildung und der parent-before-child-Hierarchie entstehen 21
  reproduzierbare Model-Space-Matrizen.
- **SUPERSEDED:** Die frühere transformierte Bounding Box
  `(-89,-4,-63)..(56,216,88)` wurde mit direkter gespeicherter
  Komponentenreihenfolge berechnet. Sie ist kein aktueller Referenzwert.

Diese Aussagen bestätigen keine weiteren Frames, Animationen oder Modelle.
Die vollständige Evidenz steht in
`research/boy/animation0-temporal-validation.md` und im generierten
Mehrframe-JSON-Report.

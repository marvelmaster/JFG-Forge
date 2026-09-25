# Prop 220 Boy: struktureller Animationskatalog

Status: **VERIFIED** für die 52 über die Prop-220-Tabellen erreichbaren
Animationsblobs der gepinnten US-ROM.

> Die Katalog-/Bitstromaussagen bleiben aktuell. Numerische Poseartefakte aus
> der ursprünglichen Animation-43-Validierung, die noch die direkte
> gespeicherte Eulerreihenfolge verwendeten, sind `SUPERSEDED`; die aktuelle
> A/C/B-Abbildung steht in `boy-transform-runtime.md`.

- Alle 52 numerischen IDs und ROM-Bereiche sind maschinenlesbar katalogisiert.
- Alle besitzen 21 Kanalslots und die Identitätsmap `0..20`.
- Alle besitzen 60 Winkeldeskriptoren für Kanäle 0 bis 19.
- Alle gespeicherten Samples lassen sich MSB-first innerhalb des angegebenen
  Strides lesen; vorhandenes Padding ist null.
- Samplezahlen variieren zwischen 3 und 76, Strides zwischen 0 und 52 Byte.
- 27 Animationen sind loopend, 25 nicht loopend.
- Keine der 52 Animationen enthält einen optionalen Scale-Stream.
- Es wurden keine Animationsnamen nachgewiesen oder erfunden.

Animation 43 / ID 1069 wurde zusätzlich vollständig über Matrizen, Vertices
und fünf OBJ-Snapshots validiert. Sie bestätigt den Laufzeitpfad für eine
nicht loopende 76-Sample-Variante mit dynamischem Root auf allen drei Achsen.

Der Katalog bestätigt die strukturelle Hülle für alle 52 Einträge. Er erklärt
nicht automatisch die semantische Bedeutung jeder Animation und ersetzt
keine vollständige Posevalidierung jedes einzelnen Eintrags.

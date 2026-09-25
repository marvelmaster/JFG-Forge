# Boy: Strukturkatalog und zweite Animationsvalidierung

> **SUPERSEDED NUMERICAL POSES:** Der 52-Clip-Strukturkatalog, die
> Animations-43-Bitstromwerte und die Root-Q10-Werte bleiben gültig. Ältere
> Matrix-, Vertex- und Bounding-Box-Zahlen in diesem Bericht wurden vor der
> runtimebestätigten A/C/B-Komponentenkorrektur erzeugt und sind keine
> aktuellen Forge-Referenzwerte.

Datum: 2026-09-23. Katalogisiert wurden ausschließlich die 52 bereits über
Prop 220 erreichbaren Animationseinträge. Ein vollständiger Matrix-, Vertex-
und OBJ-Lauf wurde nur für Animationindex 43 / ID 1069 ausgeführt.

## Katalogergebnis

Der maschinenlesbare Katalog `boy-animation-catalog.json` enthält pro Eintrag
Index, numerische ID, Asset- und ROM-Bereich, Blobgröße und SHA-256,
Kanalmap, Headerbytes, Sampleanzahl, Stride, Deskriptoren, Bitbreiten,
Rootfelder, Scale-Angaben, Loopstatus und exakte Strukturvariante. Eine
Namensquelle wurde nicht nachgewiesen; sämtliche Namen bleiben `null`.

Gemeinsame Eigenschaften aller 52 Einträge:

- 21 Transformkanalslots und die Kanalmap `0..20`;
- Framebereich bei Bloboffset `0x8e`, zweiter/Loopoffset ebenfalls `0x8e`;
- 60 variable Winkeldeskriptoren für Kanäle 0 bis 19;
- sechs unbenutzte Bytes zwischen Deskriptorende und Samplebereich;
- MSB-first lesbare Samplebits mit Nullpadding;
- kein einziger Scale-Stream.

Die Samplezahl variiert von 3 bis 76, der Stride von 0 bis 52 Byte. Index 51
besitzt drei Samples mit Stride 0 und ausschließlich konstanten
Nullbitfeldern. 27 Einträge sind über das Header-High-Nibble als loopend
markiert, 25 als nicht loopend. Unter einer exakten Signatur aus Samplezahl,
Stride, Bitbreitensequenz, Rootfeldern, Loopstatus und Kanalmap entstehen 49
Varianten. Nur die Paare `11/49`, `12/50` und `26/28` teilen sich jeweils
eine vollständige Signatur.

Samplezahlverteilung:

```text
3:1, 4:1, 5:1, 6:1, 8:2, 9:1, 10:1, 11:1, 14:2, 15:3,
16:21, 17:1, 20:2, 21:2, 22:1, 26:3, 31:1, 40:3, 50:2,
55:1, 76:1
```

## Auswahl der zweiten Animation

Keine Animation erfüllt Priorität 1 oder 2: Es gibt weder Scale-Streams noch
abweichende Kanalmaps. Gewählt wurde daher **Index 43 / ID 1069**:

- größter Samplebestand mit 76 Samples;
- 49 Byte beziehungsweise 392 belegte Bits pro Sample;
- dynamische Root-Q10-Felder auf X, Y und Z mit Breiten `[5,1,7]`;
- Winkelbreiten `0,2,3,4,5,6,7,8,9,10`;
- nicht loopend und damit anderer Endpfad als Animation 0;
- ROM `0x16EA490..0x16EB3B0`, Blobgröße 3872 Byte.

Der Laufzeitbereich ist `[0,75]`. Der Objektplayer begrenzt die normierte
Phase am Ende; `modGenAnimMatrices` verwendet bei nicht loopenden Blobs
`sample_count - 1` als Multiplikator. Sample 75 ist ein echter Endpunkt und
wird nicht mit Sample 0 interpoliert.

## Vollständige Testzeiten

| Zeit | Root XYZ | Bounding Box, s16 |
| ---: | --- | --- |
| `0` | `(-1,-1,0)` | `(-77,5,-30)..(50,214,36)` |
| `1` | `(-1,-1,0)` | `(-77,5,-31)..(54,212,39)` |
| `37` | `(-1,-1,0)` | `(-77,5,-45)..(60,243,30)` |
| `37.5` | `(-1,-1,0)` | `(-77,5,-45)..(60,243,30)` |
| `75` | `(-26,-2,78)` | `(-97,-13,54)..(24,214,116)` |

Für jede Zeit wurden alle 21 lokalen und Worldmatrizen, 638 aktive Vertices,
502 Faces und 478 bereits RGBA16-bestätigte Texturfaces erzeugt. Alle Werte
sind endlich und bleiben im `s16`-Bereich. Topologie, UVs, Materialgrenzen
und Parenthierarchie sind identisch.

## Interpolation bei 37.5

Die Fraktion ist exakt `512/1024`. Der größte Matrixursprungsweg von Sample
37 zum Halbzeitpunkt beträgt `0.6599046` Modelleinheiten. Zwei Winkelwerte
überschreiten die `u16/s16`-Grenze:

| Scalar | Aktuell | Nächster | packed Delta | Halbwert |
| ---: | ---: | ---: | ---: | ---: |
| 30 | `0` | `-416` | `-13` | `-224` |
| 32 | `32` | `-256` | `-9` | `-128` |

Der signed-11-Bit-Pfad produziert die kurzen Deltas ohne langen
Winkelsprung. Ein Scale-Test ist nicht möglich, da alle 52 Boy-Animationen
keinen Scale-Stream besitzen.

## Vergleich mit Animation 0

**Für beide vollständig VERIFIED:** Tabellenkette, 21 Slots, Identitätsmap,
MSB-first-Bits, 60 Deskriptoren, Root-Q10, 10-Bit-Interpolation, signed
Winkeldeltas, Rotations- und Matrixpfad sowie Vertextransformation.

**Animationsabhängig:** Samplezahl, Stride, konkrete Bitbreiten, Rootachsen
und -basen, Loopstatus und Endeverhalten.

**Für alle 52 strukturell VERIFIED:** Headerpositionen, 21 Slots, Map
`0..20`, 60 Deskriptoren, Sampleadressierbarkeit und fehlende Scale-Streams.
Die vollständige numerische Posevalidierung aller 52 ist damit nicht
behauptet.

**UNKNOWN:** feste FPS, semantische Animationsnamen sowie Scaleverhalten aus
tatsächlichen Boy-Daten.

Der kleinste nächste Schritt ist ein Rig-Validierungsartefakt mit den 21
bereits bestätigten Knoten und lokalen Matrizen für Animation 0 und 43. Dabei
darf weiterhin keine unbekannte Bindpose oder Gewichtung ergänzt werden.

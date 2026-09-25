# Boy/Prop 220 gegen GLideN64 SceneRipper `boy-test-001`

## Umfang und Eingaben

Diese Untersuchung vergleicht den unveränderten Einzelbild-Capture
`data/source/scene-ripper/boy-test-001` mit dem bestehenden US-Prop-220-Decoder.
Der Capture und alle bestehenden Migrationsdateien wurden nur gelesen. Der auf
Wunsch entfallene zweite 18.005-Dateien-Integritätslauf wurde nicht ausgeführt.

| Eingabe | Identität |
| --- | --- |
| `n64_scene.glr` | 232.100 Bytes; SHA-256 `cef48c72251696f318bb1c031a0e14bd16e554e5163fc531f79d1b8d1168535f` |
| Prop 220 `Boy` | SHA-256 `2cd9e008852355d8191cf11e383de833b7ab1ea2814b3dd71583c8aa104f0baf` |
| ROM | US Z64; SHA-1 `493ced9008dbe932d6e91179b68e8630cf23a023` |

## 1. GLR-Struktur

**VERIFIED** für diesen Capture und die lokal installierte
GLideN64-SceneRipper-Revision `df2e671`:

- Der 36-Byte-Header enthält `GL64R\0`, Version 4, `JET FORCE GEMINI`, die
  Anzahl 784 und den noch semantisch unbekannten Wert 10 bei `+0x20`.
- Es folgen exakt 784 Records à `0x128` Bytes. Dateiende und Recordanzahl
  stimmen ohne Rest überein.
- Jeder Record beschreibt ein geripptes Dreieck mit drei Vertexslots à
  `0x2C` Bytes. Die lokalen DLL-Symbole nennen den Typ `Debugger::RipTriangle`;
  `_performSceneRip` initialisiert und kopiert jeweils genau `0x128` Bytes.
- Ein Vertexslot enthält 11 Little-Endian-`f32`: XYZ, vier farbähnliche Werte,
  zwei normalisierte Texturkoordinaten und zwei Texelkoordinaten. Die beiden
  Koordinatenpaare sind durch die Boy-S10.5-Werte und die PNG-Abmessungen
  unabhängig bestätigt. Die genaue Farbfeld-Semantik bleibt **LIKELY RGBA**.
- Der primäre Texture-CRC64 liegt Little Endian bei Record `+0xF0`, ein
  sekundärer bei `+0x10C`. Die Dateinamen der Capture-PNGs entsprechen diesen
  CRC-Werten in normaler Hexdarstellung.
- Der Parser findet 51 aufeinanderfolgende identische State-Runs. Das sind
  **LIKELY Render-State-Batches**, keine behaupteten Draw-Call-Grenzen.

Der Capture enthält 57 RGBA-PNGs. 41 werden als primäre Textur referenziert;
eine weitere CRC (`7C6641AD00AA166D`) wird in 40 Records als sekundäre Textur
referenziert. Der GLR enthält keine separat auslesbaren Modell-, View- oder
Projektionsmatrizen.

## 2. Positive Boy-Identifikation

Boy ist im Rip **VERIFIED**. Die Identifikation beruht gleichzeitig auf vier
unabhängigen Merkmalen:

1. Alle 14 bestätigten Boy-RGBA16-Texturen besitzen genau eine in Abmessungen
   und RGBA5551-Pixelcodes identische SceneRipper-PNG.
2. Für jede dieser Texturen existiert ein Recordsatz mit exakt der vom
   Prop-Decoder erwarteten Face-Zahl.
3. Die GLR-Texelkoordinaten reproduzieren, soweit der Tile-Pfad sie nicht
   verändert, die Boy-Triangle-Werte exakt als `raw_S_or_T / 32`.
4. 629 Boy-Quellvertices lassen sich matrixweise mit maximal
   `4,236366e-6` Positionseinheiten auf die GLR-Positionen abbilden.

Der zusammenhängende relevante Bereich ist GLR-Record 184 bis 741. Er enthält
558 Triangle-Records beziehungsweise 1.674 Corner-Vertexrecords. Darin liegen
der 494-Face-Hauptsatz sowie zwei zusätzliche Instanzen eines 32-Face-Handsets.

## 3. Texturkorrelation

| Boy TextureRecord / ID | Verifiziertes Asset | SceneRipper-PNG |
| --- | --- | --- |
| 1 / `0x8436` | `254760_8x16.png` | `8DDCA1694901CFF1.png` |
| 2 / `0x8422` | `24C260_8x16.png` | `658494641C21109F.png` |
| 4 / `0x8209` | `1767A0_64x32.png` | `437536501747A5D9.png` |
| 5 / `0x820D` | `178670_16x16.png` | `404AD9CC6E6A2F01.png` |
| 6 / `0x80F8` | `11BC00_24x20.png` | `4C01254E2288BED2.png` |
| 8 / `0x9048` | `753600_44x44.png` | `373E3EFA35104BFD.png` |
| 9 / `0x80F7` | `11BA10_16x16.png` | `2454EB3ABFAD4118.png` |
| 10 / `0x852F` | `2BD2B0_32x64.png` | `A0110AF19F9637C2.png` |
| 11 / `0x820A` | `1772A0_48x40.png` | `1D91C37C3C64D9DA.png` |
| 12 / `0x809F` | `101130_16x16.png` | `5E7CF9F4DAABE8CE.png` |
| 14 / `0x80F9` | `11BEA0_32x16.png` | `E1CC11F8FCA6EAB2.png` |
| 15 / `0x852E` | `2BCAD0_32x48.png` | `C281BBEB54B2256A.png` |
| 16 / `0x8089` | `0F8CC0_32x64.png` | `290690CAAC6D3896.png` |
| 17 / `0x820B` | `177A60_64x32.png` | `3EB19D4ED404D778.png` |

Es ist keine Spiegelung, Rotation oder Zeilenumsortierung nötig. Die
RGBA8888-Bytes und PNG-Dateihashes sind nicht identisch, weil SceneRipper die
5-Bit-RGB-Kanäle anders nach 8 Bit erweitert. Nach Rückquantisierung sind alle
RGBA5551-Codes und sämtliche Alpha-Bits exakt gleich. Das ist eine
Pixelkorrelation, keine visuelle Zuordnung.

Die bislang nicht unterstützten Gruppen werden im Capture wie folgt greifbar:

- Gruppe 80 / Triangles 504–511: GLR 694–701, CRC
  `D3A262405BC43D50`, Positionsfehler maximal `2,42e-6`.
- Gruppe 81 / Triangles 512–519: GLR 702–709, CRC
  `E9BC43C85D23DF6E`, Positionsfehler maximal `2,42e-6`; alle acht S/T-Records
  stimmen zusätzlich exakt.
- Für Gruppe 79 / Triangles 496–503 existiert in diesem Frame kein eigener
  Draw mit ihrer TextureRecord-3-Textur. Der Grund bleibt **UNKNOWN**.

Die beiden Capture-PNGs der Gruppen 80/81 werden hier nur zugeordnet. Ihre
N64-Formate werden nicht neu interpretiert.

## 4. Quantitativer Geometrievergleich

Für den Hauptsatz wurden 478 Faces der 14 bestätigten RGBA16-Materialien und
16 Faces der Gruppen 80/81 verwendet:

| Größe | Ergebnis |
| --- | ---: |
| GLR-Triangle-Records im Hauptvergleich | 494 |
| untersuchte GLR-Corner-Vertices | 1.482 |
| eindeutige GLR-Positionen | 252 |
| repräsentierte aktive Boy-Faces | 494 / 502 = 98,41 % |
| repräsentierte aktive Boy-Quellvertices | 629 / 638 = 98,59 % |
| mittlerer Positionsfehler nach matrixweiser Affinabbildung | `1,461454e-6` |
| maximaler Positionsfehler | `4,236366e-6` |

Die neun nicht repräsentierten Quellvertices 633–641 und die acht Faces
496–503 gehören ausschließlich zu Gruppe 79. Es wurden keine großen
Toleranzen verwendet: Die maximale Abweichung liegt unter `5e-6`.

### Koordinatenraum

- **VERIFIED:** GLR-XYZ ist nicht das rohe Prop-XYZ. Für jede tatsächlich
  verwendete Boy-Matrix-ID bildet eine eigene affine Transformation die
  Quellvertices auf die Capture-Positionen ab. Eine Perspektivdivision hat an
  den gespeicherten XYZ noch nicht stattgefunden.
- **LIKELY:** post-model/post-modelview in einer gemeinsamen Capture-Basis.
- **UNKNOWN:** ob diese gemeinsame Basis exakt World, View oder
  Pre-Divide-Clip heißt. Ohne gespeicherte Matrix oder `w` lässt der GLR dies
  nicht weiter trennen.

## 5. Zusätzliche Laufzeitgeometrie: `severedLimb`

Die Boy-Quelltriangles 89–120 sind die bekannte 32-Face-/42-Vertex-Hand auf
Matrix 9. Diese komplette Teilmenge erscheint dreimal:

| GLR-Records | Lage/Bedeutung | mittlerer / maximaler Fitfehler |
| --- | --- | --- |
| 302–333 | gewöhnliche matrix-9-affine Prop-Instanz | `1,56e-6` / `3,67e-6` |
| 270–301 | zusätzliche, gegenüberliegende Laufzeitinstanz | `0,174` / `0,459` |
| 710–741 | zweite zusätzliche, nahezu gleiche Laufzeitinstanz | `0,240` / `0,420` |

Alle drei besitzen exakt dieselben 32 Triangle-/S/T-Records und die verifizierte
Textur `4C01254E2288BED2.png`. Die beiden zusätzlichen Instanzen liegen bei
`x=-10,02..-3,42`; die gewöhnliche Matrix-9-Hand liegt bei
`x=14,87..22,18`. Ihre Sub-Unit-Abweichungen von einer reinen Affinabbildung
sind mit dem bereits bestätigten s16-Rundungspfad erzeugter Limb-Geometrie
vereinbar.

- **VERIFIED:** GLR 302–333 ist die gewöhnliche, von `makeModelGfx`
  ausgegebene Prop-220-Geometrie der Gruppen 18–20 auf Matrix 9.
- **VERIFIED:** Die beiden zusätzlichen Kopien stammen ebenfalls aus diesen
  Prop-220-Gruppen. `severedLimbInit` (`0x800275E8`) übergibt bei
  `0x80027748` und `0x80027770` dasselbe Quellmodell und denselben durch die
  Konfigurationsbytes `+0x10/+0x11` begrenzten Gruppenbereich an
  `modMakeLimbModel` (`0x8003E638`). Dort liest `0x8003E70C` Gruppenbyte `+1`,
  prüft es bei `0x8003E718..0x8003E724` gegen diese Grenzen und transformiert
  die ausgewählten Vertices bei `0x8003E990` über `func_80048B60`. Die exakt
  übereinstimmende Triangle-/S/T-Folge 89–120 identifiziert den ausgewählten
  Bereich als Boy-Gruppen 18–20 beziehungsweise Matrix 9.
- **VERIFIED:** Die zwei Aufrufe in `severedLimbInit` erzeugen keine zwei
  gleichzeitigen Hände. Sie schreiben zwei Displaylistenvarianten nach
  Objektzustand `+0x0c` und `+0x10`; der vierte Parameter `2` beziehungsweise
  `6` fließt bei `0x8003E78C..0x8003E7A8` nur in den Renderzustand ein.
  `objPrintSeveredLimb` (`0x80009FB4`) wählt bei `0x8000A074..0x8000A0E4`
  anhand des Objekt-Alpha-Bytes `+0x39` genau eine der beiden Listen
  (opak: `+0x0c`, sonst `+0x10`) und gibt genau einen `G_DL` aus.
- **VERIFIED:** GLR 270–301 und GLR 710–741 sind deshalb zwei getrennte
  Aufrufe des `severedLimb`-Renderpfads mit durch `severedLimbInit` erzeugter
  Handgeometrie. Der Objektdispatch ruft `objPrintSeveredLimb` bei
  `0x8000AF84` mit dem aktuellen Objekt auf und kehrt danach unmittelbar aus
  diesem Dispatch zurück. Beide Aufrufe verwenden die Matrix-9-Quellhand;
  anschließend wird jeweils der Transform des übergebenen Runtimeobjekts
  angewendet. Die leicht verschiedenen Bounding Boxes bestätigen zwei
  unterschiedliche Rendertransforms. **LIKELY** sind dies zwei gleichzeitig
  lebende Severed-Limb-Objekte; der Capture enthält jedoch keine Objekt-ID,
  mit der ihre Identität direkt bewiesen werden könnte.
- **WIDERLEGT:** Eine der Zusatzkopien als direkt an Matrix 6 gebundene,
  fehlende Boy-Hand zu behandeln. Matrix 6 erhält durch diesen Pfad keine
  Handgeometrie; die Matrix-9-Geometrie wird vor dem separaten
  Severed-Limb-Objekttransform bereits in einen neuen `s16`-Vertexpuffer
  geschrieben.
- **UNKNOWN:** Welches konkrete Gameplay-Ereignis in diesem Capture die zwei
  `severedLimb`-Renderaufrufe erzeugt hat und ob sie sicher zwei verschiedenen
  Objektidentitäten entsprechen. Ebenso ist nicht feststellbar, welche
  Objektidentität GLR 270–301 beziehungsweise GLR 710–741 entspricht; der GLR
  enthält keine Objekt-ID.

Dies widerspricht dem früheren Befund nicht: Im Prop selbst bleibt Matrix 6
ohne aktive Mesh-Geometrie. Neu ist die unabhängige Render-Evidenz, dass JFG
zur Laufzeit vollständige Handgeometrie zusätzlich instanziiert.

## 6. Pose und Arm-Override

Die aus dem Capture rekonstruierten vollen Node-Affinen wurden gegen die
vorhandene Animation-0/Frame-0-Rekonstruktion faktorisiert. Bei einer passenden
Pose müsste `inverse(Frame0World_i) * CaptureAffine_i` für alle Nodes derselbe
Szenentransform sein. Die Abweichungen vom komponentenweisen Median liegen
stattdessen zwischen `26,98` und `77,07` in Frobenius-Norm.

**VERIFIED:** Der Capture entspricht nicht direkt der vorhandenen
Animation-0/Frame-0-Pose. **UNKNOWN** bleiben Animationsindex, Phase,
`racer+0x580`, `racer+0x540` Bit `0x40` und die Selector-Liste. Die zusätzlichen
Handinstanzen sind konkrete Runtime-Evidenz, reichen aber nicht aus, um ihre
Ancestor-Matrizen oder die Arm-Override-Parameter zu rekonstruieren.

## 7. Einstufung

### VERIFIED

- GLR-v4-Struktur mit 784 Triangle-Records à `0x128` Bytes.
- Boy-Identität durch Texturen, S/T, Face-Abfolge und matrixweisen Geometriefit.
- 494/502 Faces und 629/638 aktive Quellvertices im Hauptvergleich.
- Alle 14 RGBA16-Texturen pixelidentisch auf RGBA5551-Codeebene.
- Drei Renderinstanzen der Boy-Hand-Quelltriangles 89–120: eine reguläre
  Prop-220-Instanz und zwei separate `severedLimb`-Instanzen.
- Der Capture ist nicht Animation 0, Frame 0 unter nur einem zusätzlichen
  Szenentransform.

### LIKELY

- GLR-XYZ liegt im Post-Model/Modelview-Bereich.

### UNKNOWN

- Exakte Benennung des gemeinsamen GLR-Koordinatenraums.
- Auslösendes Gameplay-Ereignis und Objektlistenidentität der beiden
  `severedLimb`-Instanzen.
- Ursache des fehlenden separaten Gruppe-79-Draws.
- Aktive Animation, Phase und Runtime-Override-Werte.
- Semantik der nicht benötigten opaque GLR-Statefelder.

## 8. Reproduzierbarkeit

Der Parser und Vergleich liegen in `src/jfg_re/scene_ripper_glr.py`; der dünne
CLI-Einstieg liegt in `tools/analyze_boy_scene_ripper.py`. Das vollständige
maschinenlesbare Ergebnis einschließlich GLR-, State-Run-, PNG-, Textur-,
Face-, Matrix- und Handinventar steht unter
`data/generated/boy-scene-ripper-validation/scene-ripper-validation.json`.

Zwei direkt relevante Tests prüfen fehlerhafte Header/Bounds, den gepinnten
Capture, alle Ergebniszahlen und byteidentische Wiederholungsausgabe.

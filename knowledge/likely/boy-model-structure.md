# Boy (Prop 220): interne Modellstruktur

> **Historical evidence ledger:** Die frühe Untersuchung begann mit mehreren
> `LIKELY`-Einstufungen, die inzwischen unabhängig bestätigt wurden. Der
> kanonische aktuelle Status steht in
> [`../verified/boy-juno-milestone-1.md`](../verified/boy-juno-milestone-1.md).
> Abweichende frühe Statussätze unten sind `SUPERSEDED`.

Stand: 2026-09-22. Diese Untersuchung betrifft ausschließlich den dekomprimierten
US-Prop `Boy`. Die VERIFIED-Aussagen unten beziehen sich auf Bytes, Größen,
Grenzen und Rechenbeziehungen. Eine vollständige Semantik des Formats ist nicht
VERIFIED.

## Identität und Quellen

- `extracted/index.json` nennt ID 220 `Boy`, ROM-Offset `0x1410260`,
  komprimierte Größe 10.080 und dekomprimierte Größe 20.848 Bytes (`0x5170`).
- `extracted/characters/0220_Boy.bin` und
  `jfg-re/data/generated/props-us-verified/bins/0220_Boy.bin` sind kanonische
  Ausgaben der VERIFIED Prop-Bank-Pipeline.
- SHA-256 des untersuchten Props:
  `2cd9e008852355d8191cf11e383de833b7ab1ea2814b3dd71583c8aa104f0baf`.
- Bytes `0x00..0x03` sind `42 6f 79 00` (`Boy\0`). Damit sind Name und
  Prop-Index konsistent. Boy/Prop 220 ist inzwischen das bestätigte
  Juno-Basismodell der Referenzimplementierung; PowerBoy/Prop 221 besitzt
  zusätzliche Rücken-Upgrades und ist nicht die primäre Referenz. Die frühere
  `LIKELY`-/`HYPOTHESIS`-Einstufung dieses Absatzes ist `SUPERSEDED`.

## Binärkarte

Alle Offsets sind relativ zur dekomprimierten Boy-Datei. Die Einteilung folgt
direkt den Headerwerten und exakt passenden Record-Größen; die Bezeichnungen
der Records sind teilweise vorläufig.

| Bereich | Länge | Beobachtung | Status |
| --- | ---: | --- | --- |
| `0x0000..0x0087` | 136 | Header/Metadaten mit `Boy\0` und internen Offsetwerten | VERIFIED Bytes; Feldbedeutungen teils UNKNOWN |
| `0x0088..0x0117` | 144 | 18 × 8-Byte-Texturrecords; ID bei `+6`, geladener Pointer ersetzt Bytes `+0..+3` | VERIFIED durch `modLoadModel` |
| `0x0118..0x0647` | 1.328 | 82 Gruppen à 16 Bytes plus Grenzrecord | VERIFIED durch `makeModelGfx` |
| `0x0648..0x26c7` | 8.320 | 520 Dreiecke à 16 Bytes | VERIFIED Record/Indexformat und signed S10.5-S/T-Semantik |
| `0x26c8..0x408f` | 6.600 | 660 Vertices à 10 Bytes: drei BE-s16 plus vier Attribute | VERIFIED durch Loader und Transformationspfad |
| `0x4090..0x4097` | 8 | zwei 4-Byte-Records, erster u16 je Record indexiert einen Vertex | VERIFIED Zugriff; Zweck UNKNOWN |
| `0x4098..0x41e7` | 336 | 21 Bone-/Transformrecords à 16 Bytes | VERIFIED Laufzeitstruktur |
| `0x41e8..0x425f` | 120 | 10 × 12 Bytes möglich; Inhalt unbekannt | UNKNOWN |
| `0x4260..0x4925` | 1.734 | 289 × 6 Bytes möglich; Inhalt unbekannt | UNKNOWN |
| `0x4926..0x5029` | 1.796 | 449 × 4 Bytes möglich; Inhalt unbekannt | UNKNOWN |
| `0x502a..0x516f` | 326 | Letzter Datenbereich; Inhalt unbekannt | UNKNOWN |

Wichtige Big-Endian-u32-Werte im Header:

| Feld-Offset | Wert | gesicherte Beziehung |
| --- | ---: | --- |
| `0x18` | `0x88` | Anfang 18×8-Byte-Bereich |
| `0x1c` | `0x26c8` | Anfang 660×10-Byte-Bereich |
| `0x20` | `0x648` | Anfang 520×16-Byte-Bereich |
| `0x24` | `0x118` | Anfang 83×16-Byte-Bereich |
| `0x30` | `0x4090` | zwei 4-Byte-Records; Anzahl steht als Byte bei `0x2d` (`2`) |
| `0x34`, `0x38` | `0x41e8` | Ende dieses Bereichs plus 8 Bytes |
| `0x48` | `0x5170` | exakte Dateigröße |
| `0x4f` | `0x15` | Anzahl der Transform-/Bone-Records: 21 |
| `0x54` | `0x4098` | Pointer auf 21 Records à 16 Bytes |
| `0x68`, `0x80` | `0x4260` | Anfang unbekannter Bereich |
| `0x6c` | `0x4926` | Anfang unbekannter Bereich |
| `0x70` | `0x502a` | Anfang unbekannter Bereich |

Diese Wörter sind **dateirelative Offsets**. `modLoadModel` bei `0x8003B9E8`
addiert an `0x8003BC90..0x8003BD28` die geladene Basisadresse und schreibt die
resultierenden Pointer in den Header zurück. Die Grenzen
`0x4926` und `0x502a` zeigen, dass nicht alle Bereiche auf 4 oder 16 Bytes
ausgerichtet sind. Für die unbekannten Bereiche beweist Teilbarkeit durch 4,
6 oder 12 allein kein Recordformat.

## Geometrie: voneinander abhängige Indizien

Die 83 Records ab `0x118` enthalten an Byte `+6` und `+8` je einen
Big-Endian-u16-Startwert. Die beiden Folgen beginnen bei `(0,0)`, steigen bei
allen 82 Übergängen und enden im 83. Record bei `(660,520)`.
Damit kann jeder der 82 Records den Bereich bis zum Folgerecord abgrenzen.
Alle 520 Records ab `0x648` lassen sich so zuordnen: Ihre Bytes `+1..+3` sind
als **gruppenlokale** Indizes in jedem Fall kleiner als die jeweilige Zahl
von 10-Byte-Records. Alle 660 Kandidaten werden von mindestens einem
Dreieckseintrag referenziert; kein Index läuft über eine Gruppengrenze.

Die 10-Byte-Records ab `0x26c8` enthalten bei Interpretation der ersten sechs
Bytes als drei Big-Endian-s16 Werte enge Bereiche: X `-34..47`, Y `-79..44`,
Z `-35..25`. `func_8003C1B4` multipliziert die Anzahl bei Header `+0x12`
ausdrücklich mit 10, kopiert alle zehn Bytes jedes Records und richtet erst
den gesamten Block auf acht Bytes aus. `modMakeLimbModel` liest XYZ an
`+0/+2/+4`, transformiert sie durch `func_80048B60` und schreibt wieder
10-Byte-Vertices. Mit dem 10-Byte-Layout und den lokalen
Indizes haben 505 der 520 Kandidatendreiecke eine nicht nullgroße 3D-Fläche;
15 sind entartet. **10-Byte-Vertexrecord und s16-XYZ: VERIFIED.**

Die sechs weiteren Bytes jedes 16-Byte-Dreieckseintrags ergeben drei
Big-Endian-s16-Paare. Geteilte Ecken in benachbarten Dreiecken haben meist
identische Paare. 647 der 660 referenzierten Kandidaten haben genau ein
Paar, 13 mehrere. Beispiel: Dreiecke 0 und 1 teilen lokale Indizes 0 und 2;
deren Paare sind in beiden Records `(-20,118)` beziehungsweise `(-25,86)`.
`modMakeLimbModel` kopiert genau diese sechs s16-Felder an denselben Positionen
in neu erzeugte Dreiecke; `makeModelGfx` übergibt die Records mit dem
F3DDKR-Befehl `G_TRIN` und einer Länge von `triangle_count × 16` an den RSP.
Ihre ABI-Rolle als drei Koordinatenpaare ist VERIFIED. Spätere JFG-Pfad- und
Einzelgruppenvalidierung bestätigt sie als signed S10.5-S/T-Koordinaten mit
`texel_s=raw_s/32` und `texel_t=raw_t/32`. Forge-/OBJ-V-Konvention sowie der
belegte Boy-Tilezustand stehen in `../verified/boy-group16-uv-tile.md` und der
kanonischen Milestone-Datei. Die frühere `LIKELY`-/`UNKNOWN`-Einstufung dieses
Punkts ist `SUPERSEDED`. Das erste Byte ist 494-mal `0x00`, 26-mal `0x40`.

Die letzten vier Bytes werden von `modMakeLimbModel` einzeln und unverändert
vom Eingabevertex in den transformierten 10-Byte-Ausgabevertex kopiert und
durch `gSPVertexDKR` an den RSP übergeben. Das ist VERIFIED. Das verwandte
DKR-Projekt benennt dieselben vier Felder `r/g/b/a`; sein Batchformat erlaubt
aber auch eine Beleuchtungs-/Normaleninterpretation. Daher bleibt die genaue
Boy-Semantik **UNKNOWN**: vier F3DDKR-Vertexattribute, nicht pauschal als Farbe
oder Normale festgelegt. Beispiel: `f9 f9 f9 00` kommt 532-mal vor,
`36 58 70 92` 27-mal.

Das einzelfallgebundene Prüfskript `tools/inspect_boy_static.py` erzeugte
`data/generated/boy-study/boy-static-hypothesis.obj` mit 660 Positionen und
505 nicht entarteten Faces. Das OBJ belegt die Index-Kohärenz und erlaubt
visuelle Prüfung. Es enthält bewusst keine UVs, Materialien, Bones oder
Animationen. Seine visuelle Plausibilität beweist die Formatsemantik nicht.

## Rendering, Texturen und Skelett

- In Boy existiert kein wörtliches `ING`, `KNEE` oder `AND`. Die bisherigen
  Markerbehauptungen aus `docs/prop_binary_format.md` erklären Boy nicht.
  `makeModelGfx` baut jedoch nachweislich F3DDKR-Display-Lists: pro aktiver
  Gruppe bindet es einen Textur-/Renderzustand, erzeugt `gSPVertexDKR` und
  verweist mit `gSPPolygon` direkt auf die 16-Byte-Dreiecke. Die Prop-Datei
  enthält damit kompakte Eingabedaten, nicht eine vollständige vorgefertigte
  Standard-Display-List.
- Header `+0x10=18` steuert in `modLoadModel` eine Schleife über die
  8-Byte-Records bei `+0x18`. Aus jedem Record wird die signed-u16-ID bei
  `+6` an `texLoadTexture` (`0x80055694`) übergeben; der Rückgabepointer wird
  bei `+0` gespeichert. In `makeModelGfx` wählt Gruppenbyte `+0` den
  8-Byte-Record; `0xff` bedeutet keine Textur. Der Pointer und das aus
  Gruppenbyte `+0xb` abgeleitete Frame-Argument gehen an `texDPTextureX`
  (`0x80055C00`), zusammen mit den Renderflags bei Gruppe `+0xc`.
  **Textur- und Materialreferenzkette: VERIFIED.** Alle 18 IDs sind inzwischen
  bis zum ROM-Asset aufgelöst; 14 sind pixelvalidierte RGBA16-Assets, vier
  Formate bleiben UNKNOWN. Die frühere pauschale UNKNOWN-Aussage ist
  `SUPERSEDED`; Details stehen in `../verified/boy-texture-resolution.md`.
- Der frühere Tabellenanfang war um acht Bytes verschoben. Header `+0x2d=2`
  und Pointer `+0x30=0x4090` beschreiben zwei 4-Byte-Records. Der Loaderpfad
  liest daraus je einen u16-Vertexindex und eine u16-Matrix-ID. Er
  transformiert `(619, Matrix 6)` und `(624, Matrix 10)` mit demselben
  Punkttransformer und speichert je drei f32 in der Modellinstanz.
  **Struktur und Laufzeitrolle als transformierte Referenzpunkte: VERIFIED.**
  `objMakeGunMtx` verwendet den ersten Record als Transform des BoyGun-Childs;
  Matrix 6 ist dadurch als BoyGun-Attachment-Socket VERIFIED. Der spätere
  fachliche Zweck des zweiten Records `(624, Matrix 10)` bleibt UNKNOWN.
- Header `+0x4f=21` und Pointer `+0x54=0x4098` führen zur eigentlichen
  21×16-Byte-Tabelle. `gen_anim_data` (`0x80073E80`) läuft mit 16-Byte-Stride.
  Byte `+1` wählt den 64-Byte-Matrixslot, Byte `+0` die Parentmatrix; die
  drei f32 bei `+4/+8/+12` werden als lokale Translation X/Y/Z in die
  Matrixslots `+0x30/+0x34/+0x38` kopiert. Byte `+2` wählt den Kanal der
  aktuellen Animation, Byte `+3` den zweiten Kanal beim Blending. In Boy
  sind die IDs `0..20`; der erste Parent ist `0xff`, alle übrigen Parents
  bilden den bereits beobachteten azyklischen Baum. Die lokale Childmatrix
  wird unter JFGs Zeilenvektorkonvention rechts mit der bereits komponierten
  Parentmatrix multipliziert. **Parent, Matrix-ID, Kanalbytes, lokale
  Translation und Kompositionsreihenfolge: VERIFIED.** Die Rotation,
  optionale Skala und Root-Translation werden auch ohne Blending aus der
  gewählten Animation dekodiert. Die Prop-Records allein bilden deshalb
  keine vollständige nachgewiesene Bind- oder Grundpose.
- Für aktive Gruppen verwendet `modMakeLimbModel` die Bytes `+1/+2/+3` als
  Matrix-IDs. Für einen lokalen Vertexindex `i` gilt: `i < byte[4]` wählt
  `byte[1]`, sonst `i < byte[5]` wählt `byte[2]`, sonst `byte[3]`.
  Die XYZ-Werte werden mit genau diesem 64-Byte-Matrixslot transformiert.
  Alle 65 Boy-Gruppen ohne Flag `0x400` besitzen gültige Grenzen und nutzen
  nur IDs aus der 21er-Tabelle. **Gruppen→Bone/Matrix und starre
  Einzelmatrix-Zuordnung: VERIFIED.** Es gibt in diesem Pfad keine Gewichte
  oder Mischung mehrerer Matrizen pro Vertex. 17 Gruppen mit gesetztem
  `0x400` werden von `makeModelGfx` übersprungen; deren Bytes `+1..+5` dürfen
  deshalb nicht als Bone-Zuordnung interpretiert werden.
- Das Dreiecksbyte `+0` wird im direkten Pfad unverändert vom RSP gelesen.
  Beim Aufbau transformierter Limb-Dreiecke setzt `modMakeLimbModel` es
  ausdrücklich auf `0x40`. Der JFG-RSP-Mikrocode liest das Byte bei IMEM
  `0x16d0`, bildet mit `xori/andi 0x40` invertiert das Statusbit `0x2000`
  (`G_CULL_BACK`) und verwendet dieses ab `0x1a98` in der Vorzeichenprüfung
  der Dreiecksorientierung. `0x00` aktiviert eine Winding-abhängige
  Reject-Bedingung; `0x40` macht beide zugehörigen Masken null und umgeht
  diese Reject-Verzweigung. **Bit `0x40` deaktiviert das Backface-Culling
  für das Dreieck / zeichnet beide Seiten: VERIFIED.** Clip- und
  Degeneratentests bleiben aktiv. Die vollständige Instruktionskette steht
  im Runtime-Validierungsbericht.
- Alle 18 Textur-IDs wurden über den tatsächlichen High-Bit-Pfad von
  `texLoadTexture`, Assettabelle 1, Assetsektion 0 und den US-ROM-Asset-LUT
  bis zu konkreten Runtime-Assets verfolgt. 14 enden exakt an Einträgen des
  bestehenden pixelvalidierten `11 00`-RGBA16-Manifests. **Diese 14
  TextureRecord→ID→ROM→RGBA16-Ketten sind VERIFIED.** Vier weitere IDs sind
  bis zum ROM aufgelöst, liegen aber außerhalb des bestätigten Formats und
  bleiben bezüglich ihres Decoders UNKNOWN.

`PowerBoy` wurde nur als minimale Strukturkontrolle angesehen: ID 221 hat
22.496 Bytes (`0x57e0`), einen gleichartig aufgebauten Header und ebenfalls
`byte[0x4f]=21`. Das stützt eine verwandte Prop-Familie, beweist aber weder
Rucksack-Ausrüstung noch gemeinsame Bones oder ein identisches Datenlayout.

## Vergleich mit alter Forschung

| Alte Aussage | Boy-Befund | Einstufung |
| --- | --- | --- |
| `Boy` ist Prop 220 und wahrscheinlich Juno | Index, interner Name und ältere Namensliste passen | ID/Name VERIFIED; Juno LIKELY |
| `docs/README.md`: Boy sei Prop `0011` | widerspricht dem aktuellen kanonischen Index 220 | alte ID für diesen Prop falsch |
| Header `0x1c` sei „Datengröße“ | `0x26c8` zeigt exakt auf Kandidaten-Vertexblock, Dateigröße steht bei `0x48` | alte Deutung für Boy widerlegt |
| Header `0x20` sei Keyframe-Offset | `0x648` zeigt auf 520 Kandidaten-Dreiecke | für Boy nicht gestützt |
| Header `0x24` sei Animationstabelle, immer `0x110` | Boy hat `0x118`; Tabelle grenzt Gruppen ab | widersprüchlich |
| Header `0x30` sei Skelett-Offset, `0x4c` Bone-Anzahl | `+0x30` zeigt auf zwei Vertexreferenzen; Bonezahl ist Byte `+0x4f`, Tabelle bei `+0x54` | alte Ausrichtung widerlegt |
| `extracted/juno_skeleton.json` beweise Parent/XYZ | JSON beginnt acht Bytes zu früh; Runtime nutzt `BBBBfff` ab `0x4098` | heuristischer, fehlorientierter Output |
| `KNEE`/`ING` kennzeichnen Boy-Skelett/Display-List | beide Marker fehlen in Boy | für Boy widerlegt |
| `docs/EXTRACTION_SUMMARY.md` suggeriert umfangreiche Mesh-Exports | `extracted/extraction_summary.json` meldet `meshes: false`, ein OBJ | alte Erfolgsdarstellung nicht belastbar |

Das JFG-Decomp-Projekt lieferte Symbole und `gen_anim_data.s`; die entscheidenden
CPU- und RSP-Zugriffe wurden gegen die lokale US-ROM mit SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023` geprüft. Das DKR-Projekt wurde nur
als Vergleich für die gleiche F3DDKR-ABI herangezogen. Die Einstufung des
Bits `0x40` beruht auf dem tatsächlichen JFG-Mikrocode, nicht auf der externen
DKR-Bezeichnung.

## Abgeschlossener Einzeltest

Die RSP-Mikrocode-Verzweigung für Bit `0x40` im US-F3DDKR-Text bei ROM
`0x9ffd0` wurde statisch bis zur orientierungsabhängigen Reject-Verzweigung
verfolgt. Damit ist diese zuvor offene ABI-Eigenschaft für JFG bestätigt.

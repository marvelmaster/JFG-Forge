# Vela Character Milestone 1

Status: **FROZEN MILESTONE BASELINE, 2026-09-25**. Dieses Dokument ist der
kanonische Einstieg in den durch Vela Milestone 1 erreichten Stand. Die
Phase-Berichte und maschinenlesbaren Maps bleiben als Evidenz und
Forschungshistorie erhalten. Widersprechende ältere Aussagen sind
`SUPERSEDED`.

Alle ROM-Aussagen gelten für die gepinnte US-Z64-ROM mit SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023` und 33.554.432 Byte.

## 1. Charakteridentität und Umfang

### VERIFIED

- `Vela` entspricht `Girl`, Prop 218.
- Objektdefinition 0 heißt technisch `playerGirl`, wird über Objekt-ID 0
  erreicht und verwendet Prop 218 als primäres Modell.
- Prop 218 trägt intern den Namen `Girl`.
- `playerGirl` besitzt genau ein Child: Objektdefinition 397 `GirlGun`.

Diese Zuordnung ist über Prop-Bank, internen Modellnamen und
Objektdefinitionskette unabhängig belegt. Sie ist keine reine Namensannahme.

Prop 219 `PowerGirl` gehört zur Objektdefinition 3 `playerGirlPower`, welche
Props 219 und 795 sowie dasselbe `GirlGun`-Child referenziert. Dies bestätigt
den Zusammenhang als Power-Vela-Variante. **PowerGirl gehört nicht zum
Produktionsumfang von Vela Milestone 1.**

Provenienz: [`../../research/vela/phase1-discovery.md`](../../research/vela/phase1-discovery.md),
[`../../research/vela/phase1-structural-map.json`](../../research/vela/phase1-structural-map.json).

## 2. Kanonischer Modellblock

### VERIFIED

| Eigenschaft | Wert |
| --- | --- |
| Prop | 218 |
| Name | `Girl` |
| relativer Prop-Bank-Bereich | `0x6efa0..0x71380` |
| komprimierter ROM-Bereich | `0x140b5d0..0x140d9b0` |
| komprimierte Größe | 9.184 Byte (`0x23e0`) |
| dekomprimierte Größe | 19.016 Byte (`0x4a48`) |
| SHA-256 | `daaff6b50ffff82d9f586109f97f4332eda450280323faa542d8ff84fd2f5409` |
| kanonisches Bin | `data/generated/props-us-verified/bins/0218_Girl.bin` |

Das kanonische Bin ist byteidentisch mit einer direkten erneuten
ROM-Dekompression.

Alle Bereiche sind halboffen:

| Bereich | Inhalt | Anzahl / Stride | Status |
| --- | --- | --- | --- |
| `0x0000..0x0088` | Header | 136 Byte | VERIFIED |
| `0x0088..0x0108` | Texturrecords | 16 × 8 Byte | VERIFIED |
| `0x0108..0x0110` | Padding/unbekannt | 8 Byte | UNKNOWN |
| `0x0110..0x0570` | 69 Gruppen plus Grenzrecord | 70 × 16 Byte | VERIFIED |
| `0x0570..0x2320` | Dreiecksrecords | 475 × 16 Byte | VERIFIED |
| `0x2320..0x3a18` | Vertexrecords | 588 × 10 Byte | VERIFIED |
| `0x3a18..0x3a20` | Vertexreferenzen | 2 × 4 Byte | VERIFIED |
| `0x3a20..0x3be0` | Transformrecords | 28 × 16 Byte | VERIFIED |
| `0x3be0..0x4a48` | nachlaufender Bereich | 3.688 Byte | UNKNOWN |

Die Headerpointer, Counts und Recordstrides schließen ohne Lücken oder
Überläufe aneinander an. Die alte pre-migration-Auslegung, nach der bei
`0x3a18` das Skelett beginne, ist `SUPERSEDED`: Dort liegen zwei
Vertexreferenzen; die Transformtabelle beginnt bei `0x3a20`.

## 3. Geometrie und Runtime-Submission

### VERIFIED

| Metrik | Ergebnis |
| --- | ---: |
| gespeicherte Vertices | 588 |
| von zugelassenen Gruppen referenzierte Vertices | 551 |
| gespeicherte Dreiecksrecords | 475 |
| Gruppen | 69 |
| zugelassene Gruppen | 51 |
| übersprungene Gruppen | 18 |
| Runtime-submittierte Faces | 452 |
| geometrisch degenerierte Faces in zugelassenen Gruppen | 0 |
| Records in übersprungenen Gruppen | 23 |
| davon geometrisch degeneriert | 15 |

Alle lokalen Dreiecksindizes liegen in ihren Gruppenbereichen. Alle 51
zugelassenen Gruppen besitzen gültige Matrixsplits. Kein aktiver Quellvertex
erhält widersprüchliche starre Matrixzuordnungen.

Aktive Geometrie verwendet die Matrix-IDs:

```text
2, 5, 8..24, 26
```

Die gespeicherte XYZ-Bounding-Box lautet `(-23, -60, -32)..(33, 42, 26)`.

`makeModelGfx` maskiert bei `0x8003df34` das Gruppenflag `0x400` und springt
bei gesetztem Bit ab `0x8003df44` zur nächsten Gruppe. Für Prop 218 werden so
genau 18 Gruppen mit 23 Records von der Submission ausgeschlossen und 51
Gruppen mit 452 nichtdegenerierten Faces zugelassen. **VERIFIED ist damit die
konkrete Ausschlusswirkung im Runtimepfad.** Die breitere fachliche Bedeutung
des Flags bleibt `UNKNOWN`.

Provenienz: [`../../research/vela/phase2-animation-runtime.md`](../../research/vela/phase2-animation-runtime.md)
§7 und `geometry_validation` in
[`../../research/vela/phase2-runtime-map.json`](../../research/vela/phase2-runtime-map.json).

## 4. Texturen

### VERIFIED

- Prop 218 besitzt 16 Texturrecords.
- Alle 16 IDs sind über die bekannten `texLoadTexture`-Tabellen bis zu ihren
  ROM-Assets aufgelöst.
- 14 Assets besitzen Marker `11 00` und stimmen mit dem bestehenden,
  pixelvalidierten RGBA16-Manifest und Decoder überein.
- Alle 16 Texturrecords werden in der gespeicherten Gruppentabelle verwendet;
  15 davon in zugelassenen Gruppen.
- Die bestätigten generischen RGBA16-, Corner-UV- und Texture-Record-Pfade
  werden von Forge für Vela wiederverwendet. Es wurde keine abweichende
  Vela-spezifische Texturregel eingeführt.

### UNKNOWN FORMATS

| Texturindex | ID | Dimension | Marker | Verwendung |
| ---: | ---: | ---: | --- | --- |
| 11 | `0x8431` | 16×8 | `33 00` | nur übersprungene Gruppen |
| 14 | `0x874a` | 16×16 | `01 00` | zugelassene Gruppe(n) |

Diese beiden Formate sind nicht dekodiert und werden nicht als RGBA16
ausgegeben. Visuelle Ähnlichkeit ist keine Formatevidenz.

Provenienz: [`../../research/vela/phase1-discovery.md`](../../research/vela/phase1-discovery.md)
§4 und `textures` in der strukturellen Map.

## 5. Transform- und Skelettstruktur

### VERIFIED

Die 28 Records ab `0x3a20` besitzen eindeutige Ziel-IDs `0..27`, genau eine
Root-ID 0, gültige Eltern, Parent-before-child-Reihenfolge und keine Zyklen.
Ihre vollständige Hierarchie lautet:

```text
root -> 0 -> 1 -> 2
2 -> 3
3 -> 4 -> 5 -> 6
3 -> 7 -> 8 -> 9
2 -> 10
10 -> 11
10 -> 12
2 -> 13
0 -> 14
14 -> 15 -> 16 -> 17 -> 18 -> 19
14 -> 20 -> 21 -> 22 -> 23 -> 24 -> 25
14 -> 26
14 -> 27
```

Jeder 16-Byte-Record enthält Parent-ID, Ziel-Matrix-ID, zwei Kanalbytes und
drei Big-Endian-`f32`-Translationen. Der generische Runtimepfad bestätigt
diese Felder als Hierarchie-, Animationskanal- und lokale
Translationsinformationen. Für alle gespeicherten Vela-Records sind die
beiden Kanalbytes zunächst `[target_id, target_id]`; die ausgewählte
Animationsmap schreibt später Kanalbyte `+2` neu.

Die beiden 4-Byte-Vertexreferenzen sind:

| Record | Vertex | Matrix | gespeichertes XYZ |
| ---: | ---: | ---: | --- |
| 0 | 567 | 6 | `(33, -18, -23)` |
| 1 | 572 | 10 | `(0, 3, -17)` |

Referenz 0 wird durch `objMakeGunMtx` tatsächlich zur Auswahl von Matrix 6
für GirlGun verwendet. Matrix 6 ist deshalb ein **VERIFIED GirlGun-Socket**.
Der Zweck der Matrix-10-Referenz bleibt `UNKNOWN`.

## 6. Animationskatalog

### VERIFIED

- 53 indexierte Animationseinträge, 52 eindeutige IDs;
- ID 1124 erscheint an den Indizes 27 und 41;
- 28 Loop- und 25 Non-Loop-Clips;
- Samplezahlen 3..70;
- deklarierte Strides 0..55 Byte;
- 35 Clips mit drei runtime-konsumierten Scale-Streams.

Die IDs in Indexreihenfolge sind:

```text
1097,1098,1099,1096,1104,1110,1111,1112,1109,1113,1114,
1102,1107,1100,1101,1115,1090,1091,1092,1093,1094,1095,
1121,1106,1141,1119,1120,1124,1123,1125,1126,1127,1128,
1129,1130,1116,1117,1118,1131,1132,1133,1124,1134,1135,
1137,1136,1138,1139,1140,1122,1103,1108,1142
```

| Quelle | Vela-Bereich |
| --- | --- |
| Asset-40-Prop-Paar | ROM `0x160ab34` |
| globale Animationsindizes | `170..223` |
| Asset-41-ID-Bereich | ROM `0x160b1f4..0x160b25e` |
| Asset-44-Map-Paar | ROM `0x16ff368` |
| Asset-45-relativer Mapbereich | `0xfe0..0x15b0` |
| Asset-45-ROM-Mapbereich | `0x1700e10..0x17013e0` |
| Mapdaten | 53 × 28 Byte plus vier Null-Alignmentbytes |

`modGenAnimMatrices` liest bei `0x8003d5cc..0x8003d618` den Transformcount
aus Modell `+0x4f` und kopiert exakt 28 Mapbytes in Transformbyte `+2`.

- Index 0 verwendet 29 Slots und die Map `0..25, 27, 28`. Er dekodiert 28
  Kanäle plus Scratchkanal 28; Kanal 26 wird nicht ausgewählt, Transform 26
  verwendet Kanal 27 und Transform 27 den Scratchkanal 28.
- Indizes 1..52 verwenden die Identitätsmap `0..27`. Sie besitzen 28 Slots:
  27 dekodierte Kanäle plus Scratchkanal 27.
- Der Blob serialisiert `slots × 3` Deskriptoren. `gen_anim_data` dekodiert
  aufgrund des expliziten `slots - 1` genau `(slots - 1) × 3`. Das letzte
  serialisierte Triplet gehört zum Null-Scratchkanal und ist selbst bei
  nichtnull gespeicherten Feldern kein gewöhnliches Animationsziel.

Zwei Non-Loop-Blobs, Indizes 17 und 22, benötigen für ihre deklarierte letzte
Stridegrenze ein einzelnes folgendes Nullbyte aus dem zusammenhängenden
Asset-43-Bereich. Dies ist in der Map ausdrücklich erfasst.

Originale Animationsnamen werden nicht erfunden; unbekannte Kontexte bleiben
technische Index-/ID-Paare.

## 7. Technische Referenzanimation

Index 0 / ID 1097 ist die kanonische technische Referenz, ohne dass ihm ein
semantischer Name oder universeller Gameplaykontext zugewiesen wird.

### VERIFIED STORED DATA

| Eigenschaft | Wert |
| --- | --- |
| ROM-Bereich | `0x16ee210..0x16ee530` |
| Blobgröße | 800 Byte |
| SHA-256 | `ba1f34a283390a3b7328a5939ecd4eb364c2e9145b69fe20c163abc91984d42d` |
| Samples / Stride | 16 / 37 Byte |
| Domain | Loop `[0,16)` |
| Framedatenoffset | `0xca` |
| Runtimedeskriptoren | 84 |
| serialisierte Deskriptoren | 87 |
| Rootbreiten X/Y/Z | `[0,3,0]` |
| runtime-konsumierte Scale-Skalare | 81, 82, 83 |

### VERIFIED ISOLATED EVALUATION

Bei technischer Zeit `t = 7.5` ergibt der reproduzierbare Decoder:

```text
sample                 = 7 -> 8
fraction10             = 512
root XYZ               = (0, -5.5, 0)
matrix count           = 28, alle endlich
transformed vertices   = 551, alle endlich
bounds minimum         = (-30.4464168548584,
                          -1.6986865997314453,
                          -62.40933609008789)
bounds maximum         = (25.72008514404297,
                          206.2480010986328,
                          60.70246505737305)
matrix SHA-256 f32be   = 919427edd9f17c3dc11863406c422236057774980aefdb881c378edf603d2ca7
```

Diese Auswertung bestätigt Decoder, Hierarchieeinfluss, Scale-Streams und
starre Geometrieauswertung im isolierten Pfad. Sie enthält keine live
Selectoren, keinen Übergangszustand und keine externe Objekt-/Worldmatrix und
ist **kein unabhängiger Live-Capture**.

## 8. Animationsdekodierung und Matrizen

### GENERIC VERIFIED

- MSB-first gepackter Animationsbitstrom;
- Deskriptorbasis und signed 11-Bit-Winkeldeltas;
- kanonischer 10-Bit-Interpolationszustand;
- Root-Q10 aus Basis, Samplewerten und Interpolation, danach `/1024`;
- gespeicherte Eulerkomponenten in `A/C/B` relativ zum Matrixhelfer;
- Übergabe an den vorhandenen Helfer als
  `[stored[0], stored[2], stored[1]]`;
- Rotation `Rx(A) * Ry(C) * Rz(B)` im Zeilenvektorpfad;
- `child_world = child_local * parent_world`;
- optionale animationsabhängige Skalierung der lokalen Matrixachsen;
- starre Matrixzuordnung der Vertices ohne Blendgewichte.

### VELA-SPECIFIC VERIFIED

- 28 Transformrecords und Vela-spezifische Hierarchie;
- 28 Mapbytes pro Animation;
- Index-0-Sondermap und Identitätsmaps der Indizes 1..52;
- 35 Clips mit runtime-konsumierten Scale-Streams;
- Root-/Sample-/Stride-/Descriptorwerte des 53-Einträge-Katalogs.

Vela ruft dieselben generischen Funktionen `modGenAnimMatrices`
(`0x8003d21c`) und `gen_anim_data` (`0x80073e80`) auf. Ein unabhängiger
Live-Capture aller 28 Vela-Runtimematrizen liegt weiterhin **nicht** vor.

## 9. GirlGun und Attachments

### VERIFIED

Objektdefinition 397 `GirlGun` ist das einzige Child von `playerGirl` und
besitzt neun Modellslots:

| Slot | Prop | Name |
| ---: | ---: | --- |
| 0 | 283 | `Pistol` |
| 1 | 284 | `Automatic` |
| 2 | 285 | `Uzi` |
| 3 | 286 | `Uzi1` |
| 4 | 287 | `ShrinkBeam` |
| 5 | 288 | `Rocket` |
| 6 | 289 | `FlameThrower` |
| 7 | 290 | `Sniper` |
| 8 | 291 | `VelaHand` |

`girlControl` ruft `objMakeGunMtx` bei `0x00f01778` mit Prop 218 auf. Der
generische Pfad:

1. lädt bei `0x8000bce0` Modell `+0x30`, den Start der Referenztabelle;
2. liest bei `0x8000bce8` Matrix-ID `+2` aus Referenzrecord 0;
3. multipliziert die ID bei `0x8000bcf8` mit dem `0x40`-Matrixstride;
4. bildet bei `0x8000bd00` die Matrixadresse und kopiert die affine Matrix.

Referenzrecord 0 ist `(Vertex 567, Matrix 6)`. Der normale `playerGirl`-Pfad
fügt keine Child-lokale Rotation, Translation oder Skalierung hinzu:

```text
GirlGun_world = Vela_matrix_6
GirlGun_local = identity
```

Alle Props 283..291 besitzen null interne Transformrecords; ihre aktiven
Gruppen verwenden lokale Matrix 0. Sie sind starre Modellgeometrie unter dem
externen GirlGun-Transform.

Prop 291 `VelaHand` ist als Slot 8 und starres Handmodell **VERIFIED**. Seine
engere Interpretation als gewöhnlicher unbewaffneter Fallback bleibt
**LIKELY**, weil nicht alle Selectorbedingungen verfolgt wurden.

## 10. Runtime Game Timing

### VERIFIED

Vela besitzt einen unabhängig aus Girl Overlay 15 abgeleiteten Timingpfad:

| Element | Adresse |
| --- | --- |
| Vela-Timingfunktion | `0x00f05328` |
| 53 Big-Endian-`f32`-Faktoren | `0x00f0823c` |
| 53-Einträge-Sprungtabelle | `0x00f08848` |
| gemeinsamer Callblock | `0x00f05e74..0x00f05e80` |
| relocatierter Call | Relocation 280: `0x00f05e7c` → `objAnimDframe` `0x8001138c` |

```text
phase_next = phase + delayDat * state_scale

clip_span = sample_count       für Loop-Clips
clip_span = sample_count - 1   für Non-Loop-Clips

sample_time = phase * clip_span
```

Die vollständige Klassifikation ist:

- 30 `FIXED`;
- 22 `MOVEMENT_DEPENDENT`;
- 1 `STATE_DEPENDENT`;
- 0 `UNKNOWN`.

Die belegten Bewegungsgrößen und Indizes sind:

```text
movement_max = max(abs(racer+0x04), abs(racer+0x10))
    Indizes 0..4, 27, 29..31, 38..41

movement_lateral = abs(racer+0x10)
    Indizes 9, 10, 32, 33, 42, 43

max(1.0, abs(object+0x20))
    Indizes 44, 52

max(movement_max, abs(object+0x20))
    Index 45
```

Index 13 verdoppelt seinen Tabellenfaktor, wenn `controlKeys` bei
`0x800f6da0` Bit `0x10` gesetzt hat. Die semantische Bedeutung dieses Bits
bleibt `UNKNOWN`.

Repräsentative Raten bei nominalen 60 VI/s:

| Index / ID | Formelkontext | Rate |
| --- | --- | ---: |
| 0 / 1097 | `movement_max = 1.0` | 13,44 Samples/s |
| 9 / 1113 | `movement_lateral = 1.0` | 11,04 Samples/s |
| 44 / 1137 | vollständiger Abhängigkeitswert `1.0` | 5,76 Samples/s |
| 45 / 1136 | vollständiger Abhängigkeitswert `1.0` | 5,76 Samples/s |
| 48 / 1140 | fest | 12,42 Samples/s |
| 13 / 1100 | Bit `0x10` clear / set | 13,2 / 26,4 Samples/s |

Der Wert `1.0` ist nur eine Referenzrechnung und keine Aussage über typische
Gameplay-Bewegungswerte. Die vollständige 53-Zeilen-Tabelle steht in
[`../../research/vela/runtime-timing.md`](../../research/vela/runtime-timing.md);
die reproduzierbare Map in
[`../../research/vela/runtime-timing-map.json`](../../research/vela/runtime-timing-map.json).

## 11. Vergleich mit Juno und Generalisierungsgrenze

### GENERIC VERIFIED

- Compact-Model-Header und Texture-/Group-/Triangle-/Vertexrecordformen;
- starre Gruppen-Matrixsplits und 4-Byte-Vertexreferenzen;
- 16-Byte-Transformrecords, Parenthierarchie und Zeilenvektorkomposition;
- `makeModelGfx`-Ausschluss von Gruppen mit Flag `0x400`;
- MSB-first gepacktes Animationsformat, Root-Q10, signed Winkeldeltas,
  A/C/B-Mapping und optionale Scale-Streams;
- Child-Waffenobjekte und Socketauswahl über Referenzrecord 0;
- `objAnimDframe`-Timingkette, `movement_max`, `movement_lateral` und das
  Bit-`0x10`-Faktorverdopplungsmuster.

### SHARED BUT CHARACTER-DATA-SPECIFIC

Die Recordschemas, Funktionsketten und Formeln sind gemeinsam; Counts,
Offsets, Props, Hierarchien, Translationen, Animations-IDs, Maps,
Timingfaktoren, Selectorlisten und Attachmentmodelle bleiben
charakterspezifische Daten.

### CHARACTER-SPECIFIC

- Vela besitzt 28 statt 21 Transforme und 53 statt 52 Animationseinträge.
- Vela besitzt eine eigene 53-Werte-Timingtabelle in Overlay 15. Sie ist
  nicht aus Juno-Konstanten kopiert.
- Vela verwendet zusätzlich `abs(object+0x20)` in den Timingfällen 44, 45 und
  52.
- GirlGun verwendet Props 283..291; BoyGun verwendet andere Props.

### UNKNOWN

Die Übereinstimmung eines Mechanismus beweist keine gemeinsame semantische
Benennung seiner Felder oder Zustände. Insbesondere sind numerische
Timingtabelle, Bewegungswerte und Selectorbedingungen nicht generisch.

## 12. JFG-Forge-Unterstützung

### IMPLEMENTED AND REGRESSION-TESTED

Vela ist neben Juno auswählbar. Der Milestone unterstützt:

- 588 Quellvertices, 551 aktive Quellvertices und 452 Faces;
- 28-Joint-Skelett und starre Matrixdeformation;
- alle 53 Animationseinträge einschließlich der vorhandenen Scale-Streams;
- GirlGun-Slots 0..8 an Matrix 6;
- Vela-spezifisches `Game Timing` und `Technical Timing`;
- den gemeinsamen `Movement / Speed`-Regler;
- Modellexport;
- Export der aktuellen Animation;
- kombinierten Modell-und-Animations-Export;
- GirlGun-Export.

Vorschau und glTF-Export verwenden denselben Timing-API-Pfad und denselben
unveränderlichen Timingkontext. Vela Game Timing stammt aus Vela-eigenen
Overlay-15-Faktoren und Fällen. Die Juno-Werte wurden nicht übernommen.

Unsupported Texturen bleiben Diagnosematerialien beziehungsweise explizit
unsupported; Forge erfindet dafür keine RGBA16-Daten. PowerGirl ist nicht
integriert.

## 13. Validierungsstand

### AUTOMATED / REPRODUCIBLE

- Das kanonische Prop-Bin stimmt mit der ROM-Dekompression überein.
- Struktur-, Bereichs-, Index-, Matrixsplit- und Texturauflösungsprüfungen
  bestehen für Prop 218.
- Der statische Runtimepfad bestätigt 51 zugelassene Gruppen und 452 Faces.
- Die technische Referenzauswertung liefert 28 endliche Matrizen und 551
  endliche transformierte Vertices mit festem SHA-256 und festen Bounds.
- Forge-Regressionen decken Modell, Referenzpose, GirlGun, Exporte sowie das
  vollständige 53-Einträge-Timingprofil ab.
- Preview und Export werden gegen denselben Timingkontext geprüft; Juno bleibt
  als numerische Regression erhalten.

### MANUAL

Der Milestone wurde laut Projektstatus manuell in JFG Forge geprüft. In den
dauerhaften Vela-Forschungsberichten ist jedoch keine konkrete visuelle
Beobachtung mit reproduzierbarem Artefakt protokolliert. Dieses Dokument
leitet deshalb keine zusätzlichen Format-, Pose- oder Texturaussagen aus der
manuellen Prüfung ab.

## 14. Explizite Restfragen

### UNKNOWN

- unabhängige Live-Reproduktion aller 28 Vela-Runtimematrizen einschließlich
  Selector-, Übergangs- und Objekt-/Worldzustand;
- semantische Gameplaynamen von `racer+0x04`, `racer+0x10` und
  `object+0x20`;
- semantische Bedeutung von `controlKeys` Bit `0x10`;
- reale Gameplaywerte dieser Bewegungsgrößen und mögliche PAL-Kompensation
  außerhalb des gepinnten US-Pfads;
- Decoder und Semantik der Texturmarker `33 00` und `01 00`;
- Zweck der Referenz `(Vertex 572, Matrix 10)`;
- breitere fachliche Bedeutung des Gruppenflags `0x400` über seine bestätigte
  Ausschlusswirkung hinaus;
- Inhalt des 8-Byte-Bereichs `0x0108..0x0110`, weitere Headersemantiken und
  der nachlaufende Modellbereich `0x3be0..0x4a48`;
- Originalnamen und Gameplaykontexte der nicht unabhängig identifizierten
  Vela-Animationen;
- alle höheren Girl-Selectorbedingungen und die vollständige Bedingung, unter
  der Slot 8 `VelaHand` als unbewaffneter Fallback gewählt wird;
- Analyse und Forge-Integration von Prop 219 `PowerGirl` / `playerGirlPower`.

Der nächste unabhängige numerische Test bleibt ein Capture an PC
`0x8003d908` mit 28 Matrixslots, Instanzzustand, Objektmatrix und Selectorliste.

## 15. Historische Aussagen, die nicht mehr den aktuellen Stand beschreiben

### SUPERSEDED

- `0x3a18` als Start des Vela-Skeletts; tatsächlich beginnt dort die
  zweirecordige Referenztabelle, die Transformtabelle beginnt bei `0x3a20`;
- die daraus erzeugte alte `vela_skeleton.json`-Interpretation und ihre
  vertauschten Felder;
- Matrix 6 lediglich als Attachment-Leitspur oder als unbekannter Socket;
  `objMakeGunMtx` bestätigt sie als GirlGun-Socket;
- 452 Faces, 51 zugelassene Gruppen und die `0x400`-Wirkung nur als `LIKELY`;
  der statisch verfolgte tatsächliche Submissionpfad bestätigt sie;
- Vela in Forge ausschließlich mit Technical Timing; alle 53 eigenen
  Game-Timingformeln sind inzwischen belegt und integriert;
- eine Vela-Timingimplementierung auf Basis kopierter Juno-Konstanten; die
  Vela-Tabelle und Fälle wurden unabhängig aus Girl Overlay 15 abgeleitet;
- die Phase-2-Scope-Aussage, Vela sei noch nicht in Forge integriert. Der
  Produktionsmilestone ist implementiert; weiterhin offen bleibt nur die
  unabhängige Live-Korrelation der 28 Matrizen.


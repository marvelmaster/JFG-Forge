# Boy/Juno Character Milestone 1

Status: **REFERENCE BASELINE, 2026-09-25**. Dieses Dokument ist der kanonische
Einstieg in den aktuellen Stand von Boy/Juno. Detailberichte bleiben als
Evidenz und Forschungshistorie erhalten; widersprechende ältere Aussagen sind
`SUPERSEDED`.

## Identität und Umfang

### VERIFIED

- `Boy` ist Prop 220 und das Juno-Basismodell dieser Referenzimplementierung.
- `PowerBoy` ist Prop 221 und besitzt zusätzliche Rücken-Upgrades. Es ist
  deshalb nicht das primäre Referenzmodell.
- Prop 220 liegt bei ROM `0x1410260`, dekomprimiert auf 20.848 Byte (`0x5170`)
  und hat SHA-256
  `2cd9e008852355d8191cf11e383de833b7ab1ea2814b3dd71583c8aa104f0baf`.

Die bekannten Aussagen sind für die gepinnte US-Z64-ROM mit SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023` belegt. Boy-spezifische Regeln
dürfen nicht ohne neue Evidenz auf andere Charaktere übertragen werden.

## Modell und Geometrie

### VERIFIED

| Bereich im dekomprimierten Prop | Inhalt |
| --- | --- |
| `0x0000..0x0087` | Header; Bytebereich bestätigt, einzelne Feldsemantiken teilweise `UNKNOWN` |
| `0x0088..0x0117` | 18 Texturrecords à 8 Byte |
| `0x0118..0x0647` | 82 Gruppenrecords à 16 Byte plus Grenzrecord |
| `0x0648..0x26c7` | 520 Dreiecksrecords à 16 Byte |
| `0x26c8..0x408f` | 660 Vertexrecords à 10 Byte |
| `0x4090..0x4097` | zwei transformierte Referenzpunkte; zweiter Zweck `UNKNOWN` |
| ab `0x4098` | 21 Transformrecords à 16 Byte |

- 65 Gruppen sind im bestätigten Runtimepfad aktiv; 17 werden durch Flag
  `0x400` übersprungen.
- 638 Quellvertices werden von aktiven Faces referenziert.
- Der Runtime-/Forge-Export enthält 502 aktive Faces und nach Corner-Expansion
  1.506 Rendervertices.
- Vertex `+0/+2/+4` ist XYZ als Big-Endian `s16`. Die vier Bytes `+6..+9`
  erreichen die F3DDKR-Vertexslots, ihre Semantik bleibt `UNKNOWN`.
- Triangle `+1/+2/+3` enthält gruppenlokale Vertexindizes. Der Vertexstart der
  Gruppe wird addiert.
- Triangle `+4..+15` enthält drei signed S10.5-S/T-Paare, jeweils eines pro
  Triangle-Corner.
- Gruppe `+6/+8` und die Werte des Folgerecords begrenzen Vertex- und
  Trianglebereiche. Gruppenbyte `+0` ist der Texturindex; `0xff` bedeutet
  keine Textur.
- Gruppenbytes `+1..+3` sind drei Matrix-IDs; `+4/+5` teilen die lokalen
  Vertices auf diese IDs auf. Jeder aktive Vertex benutzt starr genau eine
  Matrix; es gibt keine Blendgewichte.
- Aktive Geometrie benutzt Matrix-IDs `2`, `4`, `5` und `7..19`.
  IDs `0`, `1` und `3` sind reine Hierarchieknoten. Matrix 20 hat keine aktive
  Face-Geometrie. Matrix 6 hat keine aktive Boy-Geometrie, ist aber der
  bestätigte BoyGun-Socket. Matrix 10 besitzt den zweiten bekannten
  Referenzpunkt `(Vertex 624, Matrix 10)`.
- Für Triangle-Flag `0x40` gilt im tatsächlichen JFG-F3DDKR-Pfad:
  `0x00` aktiviert `G_CULL_BACK`, `0x40` deaktiviert es. Clipping- und
  Degeneratentests bleiben davon getrennt aktiv.

### UNKNOWN

- die Semantik der Vertexbytes `+6..+9`;
- mehrere Headerfelder und die Bereiche `0x41e8..0x516f`;
- die vollständige fachliche Bedeutung des Gruppenflags `0x400`;
- der Zweck des Referenzpunkts `(Vertex 624, Matrix 10)`.

Provenienz: [`../likely/boy-model-structure.md`](../likely/boy-model-structure.md),
[`../../research/boy/runtime-validation.md`](../../research/boy/runtime-validation.md),
[`f3ddkr-triangle-flag.md`](f3ddkr-triangle-flag.md).

## Texturen und UVs

### VERIFIED

- Alle 18 Boy-Textur-IDs sind über `texLoadTexture` bis zu ihren ROM-Assets
  aufgelöst.
- 14 sind pixelvalidierte RGBA16-Assets. Ihr Container hat einen 32-Byte-
  Header: Breite in Byte 0, Höhe in Byte 1, Kennung `11 00` in Byte 2–3 und
  genau `width * height * 2` Nutzdatenbytes.
- Pixel sind Big-Endian RGBA5551. Auf ungeraden Zeilen werden in jedem
  Vier-Pixel-Block die beiden Zwei-Pixel-Hälften getauscht.
- Die Forge-/OBJ-Koordinaten lauten:

  ```text
  u_forge = raw_s / (32 * width)
  v_forge = 1 - raw_t / (32 * height)
  ```

  S läuft horizontal; T wächst relativ zum pixelvalidierten PNG nach unten.
  Werte außerhalb `0..1` werden nicht begrenzt.
- An der glTF-Grenze erfolgt genau ein Konventionswechsel:

  ```text
  u_gltf = u_forge
  v_gltf = 1 - v_forge
  ```

  PNG-Pixel und Forge-UVs werden nicht verändert. Der frühere vertikal
  invertierte Blender-Import ist `SUPERSEDED`.
- Alle 14 von aktiven Boy-Gruppen verwendeten RGBA16-Assets haben im belegten
  Pfad Clamp S/T, Mask S/T `0`, Shift S/T `0` und kein Mirror. glTF-Sampler
  setzen explizit `magFilter=9729` und `minFilter=9729` (`LINEAR`).

### UNKNOWN

Die folgenden vier aufgelösten Assets haben kein bestätigtes Format und
werden nicht als RGBA16 behandelt:

| Textur-ID | Marker |
| --- | --- |
| `0x8431` | `33 00` |
| `0x9A00` | `01 00` |
| `0x874E` | `25 00` |
| `0x874C` | `00 00` |

Provenienz: [`boy-texture-resolution.md`](boy-texture-resolution.md),
[`rgba16-textures.md`](rgba16-textures.md),
[`boy-group16-uv-tile.md`](boy-group16-uv-tile.md),
[`../../research/boy/textured-static-export.md`](../../research/boy/textured-static-export.md).

## Skelett und Transformationen

### VERIFIED

Die 21 Records ab `0x4098` haben folgende Felder:

| Offset | Bedeutung |
| --- | --- |
| `+0` | Parent-Matrix-ID; `0xff` beim Root |
| `+1` | Ziel-ID des Matrixslots |
| `+2` | Kanal des aktuellen Clips |
| `+3` | zweiter Kanal beim Blending |
| `+4/+8/+12` | lokale Translation X/Y/Z als Big-Endian `f32` |

```text
root -> 0 -> 1 -> 2
2 -> 3
3 -> 4 -> 5 -> 6
3 -> 7 -> 8 -> 9
2 -> 10
0 -> 11
11 -> 12 -> 13 -> 14 -> 15
11 -> 16 -> 17 -> 18 -> 19 -> 20
```

JFG verwendet Zeilenvektoren:

```text
M_child_world = M_child_local * M_parent_world
M_root_parent = T(animation_root_translation / 1024) * M_object
```

Die gespeicherten Animationskomponenten liegen relativ zum Matrixhelfer als
`A/C/B` vor. Der Runtimepfad ist `Rx(A) * Ry(C) * Rz(B)`; der vorhandene
`_local_matrix(A, B, C)`-Helfer erhält deshalb:

```python
[stored[0], stored[2], stored[1]]
```

Die frühere direkte Übergabe der gespeicherten Reihenfolge und alle daraus
abgeleiteten Matrizen/Bounding-Boxes sind `SUPERSEDED`.

### PARTIALLY VERIFIED

Die Decoderstruktur für optionale Scale-Streams und ihre Matrixanwendung ist
belegt. Die 52 Boy-Clips besitzen keine solchen Streams; ihre allgemeine
Semantik für andere Assets ist durch Boy allein nicht vollständig validiert.

Provenienz: [`boy-transform-runtime.md`](boy-transform-runtime.md),
[`../../research/boy/player-runtime-pose-pipeline.md`](../../research/boy/player-runtime-pose-pipeline.md).

## Animationsformat

### VERIFIED

Boy besitzt 52 Einträge. IDs in Indexreihenfolge:

```text
1026,1027,1028,1025,1033,1039,1040,1041,1038,1042,1043,1031,
1036,1029,1030,1044,1019,1020,1021,1022,1023,1051,1035,1070,
1048,1050,1054,1053,1055,1056,1057,1058,1059,1060,1063,1062,
1061,1066,1067,1068,1045,1046,1047,1069,1034,1024,1052,1064,
1065,1032,1037,1071
```

- Alle benutzen 21 Slots mit Identitätsmap `0..20`, 60 Winkeldeskriptoren,
  sechs unbenutzte Bytes vor den Samples und Sampledaten ab Blob `+0x8e`.
- Bitströme sind MSB-first; Paddingbits sind null. Keiner der 52 Clips besitzt
  Scale-Streams.
- Samplezahlen liegen zwischen 3 und 76, Strides zwischen 0 und 52 Byte.
  27 Clips loopen, 25 loopen nicht.
- Winkel: `base = descriptor & 0xfff0`, Breite = Low-Nibble, Samplebits sind
  unsigned, Interpolationsdeltas signed 11 Bit, und
  `angle_index = u16(raw) >> 4`; 4096 Schritte sind ein Vollkreis.
- Samples werden direkt adressiert; es gibt keine kumulative Dekodierung
  vorheriger Frames.
- Roottranslation wird als Q10 aus Basis, aktuellem Sample und 10-Bit-
  Interpolation dekodiert und vor der Hierarchie durch `1024` geteilt.
- Index 43 / ID 1069 ist im Playerkontext `controlPlayerOpenChest` bestätigt.
  Weitere unabhängig belegte Kontexte stehen im Identifikationsbericht.

### UNKNOWN

Semantische Originalnamen und Gameplaykontexte aller nicht unabhängig
belegten Clips. Technische IDs dürfen nicht durch vermutete Namen ersetzt
werden.

Provenienz: [`boy-animation-catalog.md`](boy-animation-catalog.md),
[`boy-animation-runtime.md`](boy-animation-runtime.md),
[`../../research/boy/boy-animation-identification.md`](../../research/boy/boy-animation-identification.md).

## Runtime-Capture: Index 19 / ID 1022

### VERIFIED

- Captured state: aktueller Index 19 / ID 1022, vorheriger Index 36 / ID 1061,
  Blendstep 102, Blendcounter 0, Selectorstate und Runtime-Matrizen.
- Ein Runtime-Slot hat `0x40` Byte, enthält jedoch vier Zeilen mit je drei
  gültigen Big-Endian-`f32`; das vierte Wort jeder Zeile ist unbenutzt.
- `instance+0x38` ist der unskalierte Clip-Zeitumfang in Sampleeinheiten.
  `instance+0x28` ist die effektive Zeit für `gen_anim_data`.
- Selector `0x0044`, Wert `-15`, verändert Kanal 11, gespeicherte Komponente
  1. Terminator ist `0x1000`; die Änderung propagiert auf zehn Matrizen.
- Ohne Selector liegt der maximale Capturefehler bei ungefähr `0.0320034`.
- Mit Selector, Objektmatrix und korrigierter Komponentenreihenfolge stimmen
  21/21 Matrizen beziehungsweise alle 252 geschriebenen 4x3-Elemente überein:

  ```text
  maximum absolute error = 7.62939453125e-06
  mean absolute error    = 1.6745697293016644e-07
  ```

Provenienz: [`../../research/boy/runtime-capture-index19-validation.md`](../../research/boy/runtime-capture-index19-validation.md),
[`boy-runtime-capture-layout.md`](boy-runtime-capture-layout.md).

## Kanonischer 10-Bit-Interpolationszustand

### VERIFIED IMPLEMENTATION INVARIANT

Kontinuierliche Samplezeit wird zentral in
`src/jfg_re/animation_time.py` nach
`(current_sample, next_sample, fraction10)` überführt. Es gilt strikt:

```text
0 <= fraction10 <= 1023
```

Rundet die Fraktion auf `1024`, wird sie nicht an den Decoder weitergegeben,
sondern in das nächste Sample übertragen. Der reproduzierte Fehlerfall ist:

```text
sample_time = 6.999680000000052
alte, ungültige Ableitung: current=6, fraction10=1024
kanonisch:                 current=7, next=7, fraction10=0
```

Für ein exaktes Sample N gilt `current=N`, `next=N`, `fraction10=0`.
Am Loopende trägt der Zustand auf Sample 0 über. Ein Non-Loop-Clip trägt
unmittelbar vor seinem Endpunkt auf das letzte Sample über und bleibt dort
mit Fraktion 0. Der deterministische 10.000-Tick-Slider-Stresstest besteht;
die strikte Bereichsprüfung bleibt erhalten und die Index-19-Regression
unverändert.

## Runtime-Timing und Forge-Wiedergabe

### VERIFIED

Alle 52 Timingformeln sind belegt: 31 `FIXED`, 20
`MOVEMENT_DEPENDENT`, ein `STATE_DEPENDENT`, null unbekannte Formeln.

```text
phase_delta        = delayDat * base_factor * dependency_scale
sample_delta       = clip_span * phase_delta
samples_per_second = sample_delta * 60
```

Loop-Span ist `sample_count`, Non-Loop-Span `sample_count - 1`.

```text
movement_max     = max(abs(racer+0x04), abs(racer+0x10))
movement_lateral = abs(racer+0x10)
```

Bei Index 13 verdoppelt Bit `0x10` eines Runtimeflags den relevanten Faktor;
die Bedeutung des Flags bleibt `UNKNOWN`.

Forge startet in `Game Timing` und besitzt einen Slider `Movement / Speed`
mit Bereich `1.0..5.0`, Schritt `0.1`, Default `1.0`:

- Movement-Clips verwenden ihn genau einmal als jeweiliges Bewegungsmaß.
- Fixed-Clips multiplizieren damit die bestätigte Game-Timing-Rate.
- Bei Index 13 bleibt das Runtimeflag unabhängig; der Slider multipliziert
  die resultierende Rate.
- Technical Timing multipliziert seine technische Samplerate damit.
- Der Wert bleibt bei Clipwechsel, Pause/Play, Scrubbing und Moduswechsel
  erhalten. Eine Änderung während Pause verändert die Sampleposition nicht.

Preview und Export verwenden gemeinsam
`PlaybackTimingContext.effective_samples_per_second(clip)`. Sliderwert `1.0`
ist keine Aussage über normale Gameplay-Laufgeschwindigkeit.

### UNKNOWN

- semantische Bedeutung des Index-13-Flags;
- reale Werte von `racer+0x04/+0x10` für normales Laufen, Rennen und Strafen.

Provenienz: [`../../research/boy/boy-animation-runtime-timing.md`](../../research/boy/boy-animation-runtime-timing.md).

## BoyGun und Hand-Attachment

### VERIFIED

Boy besitzt genau ein Child, Objektdefinition 399 `BoyGun`. Es wird starr an
Matrix 6 angebunden:

```text
BoyGun_world = Boy_matrix_6
BoyGun_local = identity
```

`objMakeGunMtx` kopiert Matrix 6 und rekonstruiert die affine vierte Spalte;
spätere Referenzpunktrechnung verändert die Matrix nicht.

| Slot | Prop | Name | aktive Faces |
| ---: | ---: | --- | ---: |
| 0 | 301 | `BPistol` | 67 |
| 1 | 302 | `BAutomatic` | 116 |
| 2 | 303 | `BUzi` | 126 |
| 3 | 304 | `BUzi1` | 106 |
| 4 | 305 | `BShrinkBeam` | 110 |
| 5 | 306 | `BRocket` | 142 |
| 6 | 307 | `BFlameThrower` | 132 |
| 7 | 308 | `BSniper` | 245 |
| 8 | 309 | `JunoHand` | 32 |

Waffenprops enthalten ihre Greifhandgeometrie; Prop 309 ist der
Hand-/Fallback-Slot. Die frühere severed-limb-Erklärung des normalen
Matrix-6-Attachments ist `SUPERSEDED` und widerlegt. Separat beobachtete
severedLimb-Renderereignisse erklären diesen normalen Attachmentpfad nicht.

Forge zeigt Slots 0..8 und lässt die Auswahl während der Wiedergabe Matrix 6
folgen. Modellhaltige glTF-Exporte enthalten die Auswahl als separates,
ungeskinntes Mesh, Identity-Child von `jfg_node_06`. Es gibt keine erfundene
Attachmentanimation. Animation-only-Export enthält kein Attachment.

### PARTIALLY VERIFIED

Slot 8 ist als Hand-/Fallback-Modell belegt; die vollständige fachliche
Benennung jeder Selectorbedingung, die Slot 8 auswählt, bleibt offen.

Provenienz: [`boy-gun-attachment.md`](boy-gun-attachment.md),
[`../../research/boy/boygun-transform-validation.md`](../../research/boy/boygun-transform-validation.md).

## Aktueller Forge-/glTF-Stand

### IMPLEMENTED

Forge bietet `Export Model`, `Export Current Animation` und
`Export Model + Current Animation`. Das Ausgabeformat ist glTF 2.0 als
`.gltf`, `.bin` und kopierte, verifizierte PNG-Sidecars. FBX und GLB werden
nicht unterstützt.

Der Modellexport enthält 502 Boy-Faces, Materialzuordnung, UV-Seams,
Diagnosematerialien für unbekannte Texturen und das technische 21-Joint-Skin.
Die ausgewählte Action verwendet gebackene `STEP`-Zustände, welche die JFG-
Interpolation erhalten. Zeitstempel verwenden dieselbe effektive Rate wie
die Vorschau. Die frühere allgemeine Aussage „1 glTF-Sekunde = 1 technisches
JFG-Sample“ ist `SUPERSEDED`; sie galt nur für das alte Validierungsartefakt
beziehungsweise heute bei Technical Timing und Slider `1.0`.

Textur-URIs sind portable relative Pfade, auch bei Laufwerkswechsel. Die
frühere Cross-Drive-Fehlermeldung und der vertikal invertierte Blenderimport
sind behoben und `SUPERSEDED`.

## Explizite Restfragen

### UNKNOWN

- Bedeutung des Index-13-Timingflags;
- reale Gameplay-Bewegungswerte für Walk/Run/Strafe;
- Decoder und Semantik der vier unsupported Boy-Texturformate;
- Vertexattribute `+6..+9`, restliche Headerfelder und unbekannte Modellblöcke;
- originale Namen/Kontexte der nicht unabhängig identifizierten Clips;
- Zweck des Matrix-10-Referenzpunkts;
- vollständige Semantik des Gruppenflags `0x400`;
- vollständige Benennung aller BoyGun-Selectorbedingungen;
- konkrete Runtime-Ownership der zwei zusätzlichen Handkopien im
  unbewaffneten `boy-test-002`-Capture;
- Player-Overrides und Blending als frei editierbare Forge-Zustände;
- eine echte JFG-Bind-/Restpose; die aktuelle Identity-Inverse-Bind-Darstellung
  ist eine technische Exportrepräsentation.

## Historische Aussagen, die nicht mehr den aktuellen Stand beschreiben

### SUPERSEDED

- direkte Übergabe der gespeicherten Eulerkomponenten an `_local_matrix`;
- alte Frame-0-/Mehrframe-Matrizen und Bounding-Boxes aus dieser Reihenfolge;
- severedLimb als Erklärung für das normale Matrix-6-Handattachment;
- unbekannte BoyGun-Platzierung an Matrix 6;
- vertikal invertierte glTF-/Blendertexturen und Cross-Drive-Exportfehler;
- universelle 1:1-Abbildung von technischer Samplezeit auf glTF-Sekunden;
- getrennte Viewer-Speed-/Movement-Metric-Regler, alte `0.25x/0.5x`-Presets
  und ein `1x..32x`-Regler;
- `fraction10=1024` als verwendbarer Zustand.

## Nächster Generalisierungstest

Boy/Juno ist die Referenzimplementierung. Vela ist der nächste sinnvolle
Generalisierungstest. Dabei muss für jede Struktur erneut bestimmt werden, ob
sie zum allgemeinen JFG-Charakter-/Modell-/Animationssystem gehört oder nur
Boy-spezifisch ist. Boy-spezifische APIs werden erst mit entsprechender
Evidenz schrittweise generalisiert.

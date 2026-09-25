# Boy: Animation 0, Frame 0

> **SUPERSEDED NUMERICAL POSE:** Dieser Bericht belegt weiterhin Assetkette,
> Bitstrom, Root-Q10, Hierarchie und starre Matrixzuordnung. Seine Matrix-,
> Ursprung-, Kontrollvertex- und Bounding-Box-Zahlen wurden jedoch vor der
> Runtime-Capture-Korrektur der gespeicherten A/C/B-Komponenten erzeugt und
> sind keine aktuellen Referenzwerte. Der aktuelle Stand steht in
> [`../../knowledge/verified/boy-juno-milestone-1.md`](../../knowledge/verified/boy-juno-milestone-1.md).

> **Korrektur aus der Mehrframe-Validierung:** `func_80074B50` verschiebt den
> gepackten Root-Samplewert vor der Addition um 10 Bit. Frame 0 ist daher
> raw Q10 `(0,-9216,0)` bzw. `(0,-9,0)`, nicht `(0,-10239,0)` bzw.
> `(0,-9.9990234375,0)`. Der alte Einzelbildexport und seine abgeleiteten
> Y-Werte sind durch `animation0-temporal-validation.md` und den neuen
> Mehrframe-Report ersetzt. Kanalwinkel und die übrige Formatdekodierung
> bleiben davon unberührt.

Datum: 2026-09-23. Diese Untersuchung dekodiert ausschließlich den vom
normalen Boy-Initialzustand verwendeten Animationsindex 0 am ganzzahligen
Frame 0. Sie ist kein allgemeiner JFG-Animationsdecoder.

## Ergebnis

Die vollständige Kette von Prop-ID 220 bis zu den 21 Model-Space-Matrizen
konnte aus dem tatsächlichen JFG-Code und den lokalen US-ROM-Bytes
reproduziert werden. Der daraus erzeugte separate OBJ enthält 638
laufzeitaktive, transformierte Vertices und dieselben 502 bestätigten Faces,
UVs und Materialien wie der bisherige Runtime-Gruppenexport.

## 1. Auswahl und Assetkette

`modLoadModel` (`0x8003B9E8`) reicht die maskierte Prop-ID an
`func_8003CB04` (`0x8003CB04`) weiter. Für Prop 220 entsteht folgende Kette:

```text
Prop 220
  -> Asset 40, ROM 0x160AB38: halfwords 0x0228, 0x0290
  -> >> 1: Animationsindexbereich 276..328, also 52 Animationen
  -> Asset 41, ROM 0x160B2C8: Animation 0 = signed ID 1026 (0x0402)
  -> Asset 42, ROM 0x160DE18: Asset-43-Offsets 0xD5750..0xD5970
  -> Asset 43 / ROM 0x16E37C0..0x16E39E0
```

Der resultierende Blob ist 544 Byte groß und hat SHA-256
`0693bf4740d35faa69637a37dede4a81fc84e2d9aabc812da03fdb6164de1d78`.
`func_8003CFCC` lädt diesen Bereich direkt über den Assetloader. Es liegt
keine zusätzliche Deflate-Hülle um den Animationsblob.

Die Kanalmap wird unabhängig über Asset 44 und 45 geladen:

```text
Asset 44, ROM 0x16FF370
  -> Asset-45-Bereich 0x1B80..0x1FC8
  -> ROM 0x17019B0..0x1701DF8
  -> Animation 0: 00 01 02 ... 14
```

Damit verwendet Transformrecord `i` für diese Animation Kanal `i`, für alle
21 Records. Diese Zuordnung ist **VERIFIED**.

## 2. Frame-0-Format

Für den geladenen Blob setzt JFG den Runtimepointer auf `blob+8`. Relevante
Felder für diesen einzelnen Pfad:

| Bloboffset | Wert | Verwendung |
| --- | ---: | --- |
| `+0x02` | `0x008e` | Offset des gepackten Framebereichs |
| `+0x06` | `0x008e` | zweiter/Loop-Framebereich, hier identisch |
| `+0x09` | `21` | Kanal-Slots; Decoder verarbeitet `(21-1)*3 = 60` Skalare |
| `+0x0b` | `16` | Frameanzahl/-grenze im Runtimezustand |
| `+0x0d` | `25` | Byte-Stride eines Frames |
| `+0x0e` | `0x03` | Root-Bitbreiten X=0, Y=3 |
| `+0x0f` | `0x00` | Root-Bitbreite Z=0 |

Frame 0 liegt somit bei ROM `0x16E384E..0x16E3867` und enthält:

```text
21 0c 0e 49 3a f5 1c 0f 08 4c 7a 12 0b 81 b0 e1
81 d0 ab d7 aa df b5 62 00
```

JFG liest die Bits MSB-first. Frame 0 verbraucht 193 Bits; die letzten sieben
Bits sind Nullpadding. Da der Framewert exakt 0 ist, setzt
`modGenAnimMatrices` den Interpolationsversatz auf null. Der Decoder liest
dadurch denselben Frame als beide Interpolationsendpunkte; es findet keine
numerische Veränderung durch Interpolation statt.

### Root-Translation

Die drei signed-8-Basen sind `(0, -5, 0)` und werden zunächst um 11 Bit
verschoben. Nur Y besitzt eine variable Breite von drei Bit; Frame 0 liefert
dort den Wert 1, den der Laufzeitcode um 10 Bit verschiebt:

```text
raw_root = (0, (-5 << 11) + (1 << 10), 0) = (0, -9216, 0)
model_root = raw_root / 1024 = (0, -9, 0)
```

Diese Werte werden vor der Bonehierarchie als Translation auf die äußere
Objektmatrix angewandt. Für den Modellraumexport ist die äußere Objektmatrix
Identität. Die Root-Translation ist **VERIFIED**.

### Winkel-Skalare

Jeder 16-Bit-Deskriptor besteht für diesen Pfad aus:

```text
base       = descriptor & 0xfff0
bit_width  = descriptor & 0x000f
sample     = nächste bit_width Bits des Frames, MSB-first
raw_angle  = s16(base + (sample << 5))
angle_idx  = u16(raw_angle) >> 4
```

`angle_idx` besitzt 12 Bit; 4096 Schritte entsprechen einem Vollkreis. Der
Code verwendet JFGs Quarter-Sine-Tabelle bei ROM `0xA8994`. Die drei
gespeicherten Skalare liegen relativ zum Matrixhelfer als `A/C/B` vor. Der
Runtimepfad `Rx(A) * Ry(C) * Rz(B)` verlangt am vorhandenen
`_local_matrix(A,B,C)`-Helfer `[stored[0], stored[2], stored[1]]`. Die frühere
direkte Zuordnung in diesem Bericht ist `SUPERSEDED`.

Der Decoder verarbeitet 60 Deskriptoren für die Kanäle 0 bis 19. Die letzten
sechs Nullbytes vor `+0x8e` werden von dieser Schleife nicht gelesen. Slot 20
wird daher von Animation 0 nicht überschrieben. Der globale Scratchbereich ist
statisch mit null initialisiert; ein sauber initialisierter Lauf benutzt dort
Nullrotation und Einheitsskalierung. Da der Slot nicht pro Aufruf geschrieben
wird, ist sein numerischer Zustand nach einem hypothetischen vorherigen
Decoder mit mehr Ausgabeslots nicht unabhängig bestätigt. Matrix 20 ist ein
Leaf ohne aktive Geometrie, Referenzpunkte oder Childmatrizen; diese
Restunsicherheit beeinflusst den OBJ nicht.

Keiner der 60 tatsächlich dekodierten Skalare setzt den Scale-Sonderfall;
für Kanäle 0 bis 19 sind alle Skalenrohwerte null, was im JFG-Code Faktor 1
bedeutet.

## 3. Dekodierte Kanäle

| Kanal | gespeicherte A/C/B raw s16 | gespeicherte A/C/B in Grad | Scale XYZ |
| ---: | --- | --- | --- |
| 0 | `0, 0, 0` | `0, 0, 0` | `1,1,1` |
| 1 | `0, 0, 0` | `0, 0, 0` | `1,1,1` |
| 2 | `-1152, -416, 0` | `-6.328125, -2.285156, 0` | `1,1,1` |
| 3 | `0, 0, 0` | `0, 0, 0` | `1,1,1` |
| 4 | `-3680, -3552, -8000` | `-20.214844, -19.511719, -43.945312` | `1,1,1` |
| 5 | `2144, 3712, -1120` | `11.777344, 20.390625, -6.152344` | `1,1,1` |
| 6 | `0, 0, 0` | `0, 0, 0` | `1,1,1` |
| 7 | `96, -5728, 7328` | `0.527344, -31.464844, 40.253906` | `1,1,1` |
| 8 | `-288, -3424, 1888` | `-1.582031, -18.808594, 10.371094` | `1,1,1` |
| 9–11 | `0, 0, 0` | `0, 0, 0` | `1,1,1` |
| 12 | `4736, 0, -1824` | `26.015625, 0, -10.019531` | `1,1,1` |
| 13 | `-160, 0, 0` | `-0.878906, 0, 0` | `1,1,1` |
| 14 | `-1440, 864, 352` | `-7.910156, 4.746094, 1.933594` | `1,1,1` |
| 15 | `-2880, 0, 0` | `-15.820312, 0, 0` | `1,1,1` |
| 16 | `-3072, 0, 1600` | `-16.875, 0, 8.789062` | `1,1,1` |
| 17 | `-5888, 0, 0` | `-32.34375, 0, 0` | `1,1,1` |
| 18 | `640, 0, 0` | `3.515625, 0, 0` | `1,1,1` |
| 19 | `2464, 0, 0` | `13.535156, 0, 0` | `1,1,1` |
| 20 | `0, 0, 0` im sauberen Scratchzustand | `0, 0, 0` | `1,1,1`; Slot unbenutzt |

## 4. Matrizen und Hierarchie — numerische Tabelle SUPERSEDED

Für jeden Record wird aus dem zugeordneten Kanal und der Prop-Translation die
lokale 64-Byte-Matrix erzeugt. Anschließend gilt unverändert:

```text
M_child_world = M_child_local * M_parent_world
p_out = p_local * M_world
```

Die Rechnung rundet jede MIPS-`float`-Operation auf IEEE-754 Single Precision
und verwendet die 1025 Werte der originalen JFG-Sinustabelle. Die vollständigen
lokalen und komponierten Matrizen einschließlich Float-Bitmustern stehen im
JSON-Report.

| Matrix | Parent | Kanal | aktive Vertices | komponierter Ursprung XYZ |
| ---: | ---: | ---: | ---: | --- |
| 0 | 255 | 0 | 0 | `0.000, 127.730, 0.000` |
| 1 | 0 | 1 | 0 | `0.000, 130.933, 0.000` |
| 2 | 1 | 2 | 133 | `0.000, 130.933, 0.000` |
| 3 | 2 | 3 | 0 | `1.173, 160.336, -0.318` |
| 4 | 3 | 4 | 18 | `31.310, 158.114, -1.224` |
| 5 | 4 | 5 | 4 | `40.535, 145.107, 16.712` |
| 6 | 5 | 6 | 0 | `54.888, 137.854, 30.932` |
| 7 | 3 | 7 | 7 | `-29.941, 161.014, -1.274` |
| 8 | 7 | 8 | 15 | `-49.438, 162.726, 10.378` |
| 9 | 8 | 9 | 42 | `-63.863, 168.173, 22.700` |
| 10 | 2 | 10 | 214 | `1.668, 172.740, -4.640` |
| 11 | 0 | 11 | 41 | `0.000, 125.442, 2.462` |
| 12 | 11 | 12 | 24 | `12.813, 111.715, 2.189` |
| 13 | 12 | 13 | 16 | `22.430, 72.136, -10.165` |
| 14 | 13 | 14 | 18 | `31.175, 32.818, -30.730` |
| 15 | 14 | 15 | 23 | `36.977, 9.513, -30.430` |
| 16 | 11 | 16 | 26 | `-13.270, 112.173, 2.189` |
| 17 | 16 | 17 | 15 | `-17.919, 73.318, 20.040` |
| 18 | 17 | 18 | 19 | `-17.500, 41.451, 52.696` |
| 19 | 18 | 19 | 23 | `-12.366, 29.011, 73.919` |
| 20 | 19 | 20 | 0 | `-62.029, 28.165, 82.136` |

## 5. Konkrete Byte-zu-Vertex-Ketten

Der maschinenlesbare Report enthält je verwendeter Matrix ein vollständig
nachvollziehbares Beispiel. Drei Beispiele nach der JFG-f32-Rechnung und der
abschließenden Rundung gegen null:

```text
Vertex 45, Matrix 2:  (-30, 23, 13) -> (-29.0075, 156.4029, 10.3857) -> (-29,156,10)
Vertex 74, Matrix 10: (0, 3, 7)     -> (  1.8179, 176.4905,  1.9867) -> (1,176,1)
Vertex 23, Matrix 15: (-14,-12,-8)  -> ( 25.7709,  -3.4983,-40.8757) -> (25,-3,-40)
```

## 6. Export und Bounding Box — transformierte Werte SUPERSEDED

Der Export enthält nur die 638 Vertices der 65 aktiven Runtime-Gruppen. Die
22 Vertices der 17 mit `0x400` übersprungenen Gruppen werden nicht als
scheinbar transformierte Geometrie ausgegeben.

| Zustand | Minimum | Maximum |
| --- | --- | --- |
| aktive Roh-XYZ | `(-34,-48,-35)` | `(34,44,25)` |
| Animation 0 / Frame 0, s16 (korrigierter Q10-Root) | `(-89,-4,-63)` | `(56,216,88)` |

Alle 638 Transformationen sind endlich und liegen im `s16`-Bereich. Der OBJ
enthält 502 Faces; 478 Faces verwenden die 14 bereits bestätigten
RGBA16-Texturen. Die 24 Faces der drei UNKNOWN-Formatgruppen bleiben
untexturiert.

## 7. Status

### VERIFIED für Boy Animation 0, Frame 0

- Prop-220-Animationsbereich, Animation-ID 1026 und ROM-Blob.
- Identitäts-Kanalmap 0 bis 20.
- Ganzzahlige Frame-0-Adressierung, 25-Byte-Stride und MSB-first-Bitstrom.
- Root-Translation Q10 `(0,-9216,0)` beziehungsweise `(0,-9,0)`.
- 60 dekodierte Winkelskalare für Kanäle 0 bis 19.
- Keine aktive Skalierung dieser Kanäle; Faktor 1 auf allen Achsen.
- Alle 20 für Hierarchie beziehungsweise aktive Geometrie relevanten lokalen
  und komponierten Model-Space-Matrizen.
- Transformation und s16-Ausgabe der 638 aktiven Vertices.

### UNKNOWN beziehungsweise außerhalb dieses Schritts

- Fachliche Bezeichnung der Pose als Bindpose, Idlepose oder anderer
  Spielzustand.
- Der nicht benutzte Scratchslot 20 wird von diesem Decoder nicht neu
  geschrieben. Seine Clean-State-Nullmatrix ist für den Export folgenlos,
  aber nicht als allgemeiner Cross-Call-Zustand bestätigt.
- Semantik weiterer Frames und Animationen.
- Allgemeingültigkeit des Formats für andere Modelle.
- Die drei weiterhin nicht dekodierten Texturformate.

Das alte `decode_animation.py` und `anim_test.json` wurden erst nach dieser
Rekonstruktion verglichen. Sie nehmen 18 Quaternion-Bones und ein anderes
64-Byte-Deltaformat an und beschreiben den hier nachgewiesenen 21-Kanal-
Bitstrom nicht.

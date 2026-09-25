# Boy: Laufzeit-Transformkette und Grenze der statischen Grundpose

Datum: 2026-09-23. Gegenstand ist ausschließlich Prop 220 `Boy` der
US-ROM. Es wurden keine Animationen extrahiert oder auf das Modell angewandt.

## Ergebnis in einem Satz

JFG liest die drei `f32` eines 16-Byte-Transformrecords als lokale
Translation `(tx, ty, tz)`. Rotation, optionale Skalierung und eine zusätzliche
Root-Translation kommen jedoch aus der ausgewählten Animation. Deshalb lässt
sich die tatsächlich gerenderte Grundpose nicht aus dem Boy-Prop allein
reproduzieren.

Ein transformiertes OBJ wurde bewusst nicht erzeugt. Eine Translation-only-
oder Identity-Rotation-Pose wäre kein im JFG-Code vorhandener Defaultpfad.

## Evidenzbasis

- `modGenAnimMatrices` bei `0x8003D21C` wurde direkt aus der lokalen US-ROM
  disassembliert.
- `gen_anim_data` bei `0x80073E80` liegt zusätzlich als Assemblerquelle unter
  `research/Jet-Force-Gemini/src/hasm/gen_anim_data.s` vor.
- `modMakeLimbModel` bei `0x8003E638` und `func_80048B60` bei `0x80048B60`
  wurden direkt aus derselben ROM verfolgt.
- Die Funktionsnamen aus dem fremden Decomp dienen zur Navigation. Die hier
  beschriebenen Feldzugriffe und Formeln stammen aus den Instruktionen.

## 16-Byte-Transformrecord

| Offset | Verwendung | Status |
| --- | --- | --- |
| `+0` | Parent-Matrix-ID; `0xff` beim Rootrecord | VERIFIED |
| `+1` | Zielslot der 64-Byte-Matrix | VERIFIED |
| `+2` | Kanalindex des aktuellen Animationszustands | VERIFIED |
| `+3` | zweiter Kanalindex beim Animationsblending | VERIFIED |
| `+4` | lokale Translation X als Big-Endian `f32` | VERIFIED |
| `+8` | lokale Translation Y als Big-Endian `f32` | VERIFIED |
| `+12` | lokale Translation Z als Big-Endian `f32` | VERIFIED |

Im Boy-Binärfile sind `+1`, `+2` und `+3` zunächst jeweils `0..20`.
`modGenAnimMatrices` überschreibt `+2` bei `0x8003D5CC..0x8003D618` mit der
Kanalzuordnung der gewählten Animation. Bei Blending wird entsprechend ein
zweiter Satz verarbeitet. Die gespeicherten Bytes `+2/+3` sind daher keine
statischen Rotationen.

`gen_anim_data` kopiert die Wörter `+4/+8/+12` bei
`0x80075064..0x800750F8` unverändert nach Matrixoffset
`+0x30/+0x34/+0x38`. `func_80048B60` verwendet genau diese Slots additiv bei
der Punkttransformation. Damit ist die Translationssemantik unabhängig von
den Zahlenwerten bestätigt.

## Erzeugung der lokalen Matrix

`gen_anim_data` dekodiert für den durch Recordbyte `+2` gewählten Kanal drei
16-Bit-Winkel. Jeder Wert wird um vier Bits nach rechts verschoben. Der
verbleibende 12-Bit-Wert adressiert über Quadrantenlogik die Sinustabelle; ein
Vollkreis entspricht 4096 Schritten. Zusätzlich können drei dekodierte
16-Bit-Skalierungswerte je Kanal vorliegen. Null bedeutet Faktor 1, sonst ist
der Faktor `raw_scale / 32768`.

Die resultierende affine 64-Byte-Matrix besitzt dieses Layout:

```text
[ m00 m01 m02 0 ]
[ m10 m11 m12 0 ]
[ m20 m21 m22 0 ]
[  tx  ty  tz 1 ]
```

JFG benutzt Zeilenvektoren. Für die drei dekodierten Winkel `A`, `B`, `C`
setzt der nicht geblendete Pfad vor einer optionalen Skalierung:

```text
m00 = cos(C) cos(B)                       m01 = cos(C) sin(B)                       m02 = -sin(C)
m10 = sin(A) cos(B) sin(C) - cos(A)sin(B) m11 = sin(A) sin(B) sin(C) + cos(A)cos(B) m12 = sin(A) cos(C)
m20 = cos(A) cos(B) sin(C) + sin(A)sin(B) m21 = cos(A) sin(B) sin(C) - sin(A)cos(B) m22 = cos(A) cos(C)
```

Mit üblichen Zeilenvektor-Grundmatrizen ist dies
`Rx(A) * Ry(C) * Rz(B)`. Die drei Skalenfaktoren multiplizieren anschließend
je eine Matrixzeile und damit die lokalen X-, Y- und Z-Achsen. Die
Translationswerte des Transformrecords werden nicht aus der Animation
ersetzt.

## Hierarchie und Multiplikationsreihenfolge

Der Block `0x8007524C..0x80075528` läuft in Recordreihenfolge über die 21
Records. Byte `+1` wählt den Child-Slot, Byte `+0` den Parent-Slot. Boy ist
parent-before-child geordnet; der erste Record hat Parent `0xff`.

Die Instruktionen `0x800753BC..0x800754FC` berechnen unter JFGs
Zeilenvektor-Konvention:

```text
M_child_world = M_child_local * M_parent_world
```

Für die Translation ist der Datenfluss beispielsweise:

```text
out.tx = local.tx*parent.m00 + local.ty*parent.m10
       + local.tz*parent.m20 + parent.tx
```

Der Rootparent ist die von `modGenAnimMatrices` aufgebaute Objektmatrix.
`gen_anim_data` addiert davor noch ein aus der gewählten Animation dekodiertes
Translationstripel, skaliert mit `1/1024`, im Raum dieser Objektmatrix. Für
einen Modellraumexport wäre die äußere Objektmatrix Identität; das
animationsabhängige Roottripel bliebe trotzdem erforderlich.

## Gespeichertes XYZ bis Runtime-XYZ

Für einen Vertex `p = (x,y,z,1)` und seine durch das Gruppenrecord bestimmte
Matrix-ID gilt:

```text
p_runtime = p * M_bone_world

x' = x*m00 + y*m10 + z*m20 + m30
y' = x*m01 + y*m11 + z*m21 + m31
z' = x*m02 + y*m12 + z*m22 + m32
```

`modMakeLimbModel` führt dies bei `0x8003E930..0x8003E994` aus. Danach
konvertiert es die drei Ergebnisse bei `0x8003EA5C..0x8003EAB4` mit
Rundungsmodus „toward zero“ zurück nach `s16` und kopiert die vier übrigen
Vertexbytes unverändert.

## Verhalten ohne Animation

Die Modellinstanz erhält bei `0x8003C758..0x8003C798` zunächst einen
genullten Animationszustand; beide Matrixpuffer werden davor durch
`0x8003C0C4` als Identitätsmatrizen initialisiert. Dieser Allokationszustand
ist keine nachgewiesene Renderpose.

Beim ersten normalen Matrixlauf liest `modGenAnimMatrices` den Animationsindex
an Instanz `+0x24`. Der Initialwert ist 0. Bei `0x8003D49C..0x8003D4D0` wird
damit Animation 0 geladen, bei `0x8003D5CC..0x8003D618` ihre Kanalzuordnung in
die Transformrecords geschrieben und bei `0x8003D8E8..0x8003D904`
`gen_anim_data` aufgerufen.

Der Zweig `.L80074EDC` in `gen_anim_data` bedeutet „kein Blend“. Er dekodiert
weiterhin den aktuellen Animationszustand und baut daraus Rotationen und
Skalen. Es wurde kein Pfad gefunden, der aus den 21 Transformrecords allein
eine gerenderte statische Pose erzeugt.

### Status

- **VERIFIED:** neu erzeugte Instanzen beginnen mit Animationsindex 0 und
  Framewert 0.
- **VERIFIED:** der normale nicht geblendete Pfad benötigt dennoch die Daten
  dieser Animation.
- **UNKNOWN:** ob „Animation 0, Frame 0“ fachlich als Bindpose, Idlepose oder
  anderer Startzustand bezeichnet werden sollte.
- **UNKNOWN / nicht reproduzierbar in diesem Schritt:** die numerischen 21
  Runtime-Matrizen und die transformierte Bounding Box, weil das Dekodieren
  des benötigten Animationsframes ausdrücklich ausgeschlossen war.

## Header `+0x30`: zwei Referenzpunkte

Boy enthält bei `0x4090` zwei 4-Byte-Records:

```text
(vertex 619, matrix 6)
(vertex 624, matrix 10)
```

`modGenAnimMatrices` liest bei `0x8003D918..0x8003D99C` je Record den ersten
`u16` als Vertexindex, den zweiten `u16` als Matrix-ID, transformiert das
Vertex-XYZ mit derselben `func_80048B60` und schreibt drei `f32` in ein
separates Array der Modellinstanz. Diese Records bauen weder die Hierarchie
noch die Meshzuordnung auf. Sie definieren zwei laufzeittransformierte
Referenzpunkte. Der erste `(Vertex 619, Matrix 6)` ist inzwischen als
BoyGun-Socket VERIFIED. Der Zweck des zweiten `(Vertex 624, Matrix 10)`
bleibt **UNKNOWN**.

## Boy-Zuordnung und Diagnose

- 638 der 660 gespeicherten Vertices werden von den 502 aktiven Faces
  referenziert und besitzen dort eine eindeutige Matrix-ID.
- Verwendete IDs: `2, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19`.
- Kein aktiver referenzierter Vertex wird zwei verschiedenen Matrizen
  zugeordnet.
- Matrix 6 wird nicht von aktiven Faces verwendet, aber vom ersten
  Referenzpunktrecord.
- Die Roh-XYZ-Bounding-Box ist `(-34,-79,-35)` bis `(47,44,25)`.
- Eine transformierte Bounding Box, NaN-/Inf-Prüfung und räumliche
  Matrixgruppenverteilung sind ohne die fehlenden Animationswerte nicht
  seriös berechenbar.

Die reproduzierbaren Rohbefunde stehen in
`data/generated/boy-transform-runtime-analysis/boy-transform-runtime-analysis.json`.

## Historischer nächster Schritt — SUPERSEDED

Der damals kleinste fehlende Schritt war eine eng begrenzte Untersuchung genau von
Boy-Animation 0, Frame 0: Animation-ID-Kette, Kanalmap, drei Winkelkanäle,
optionale Skalen und Root-Translation. Erst diese Werte erlauben eine
bytegetreue Reproduktion der 21 Matrizen. Das wäre Animationsextraktion und
wurde deshalb hier nicht begonnen.

Dieser abgegrenzte Folgeschritt wurde inzwischen durchgeführt. Die Ergebnisse
stehen in `animation0-frame0-validation.md`; die hier dokumentierte Aussage,
dass die Prop-Records allein nicht genügen, bleibt unverändert gültig.

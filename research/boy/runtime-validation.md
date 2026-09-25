# Boy-Laufzeitpfad: statische Validierung

> **Historical staged report:** Später bestätigte S/T-, Tile-, Transform- und
> Attachmentbefunde stehen im kanonischen
> [`../../knowledge/verified/boy-juno-milestone-1.md`](../../knowledge/verified/boy-juno-milestone-1.md).
> Frühere `LIKELY`-/`UNKNOWN`-Grenzen unten sind dort, wo ausdrücklich
> angegeben, `SUPERSEDED`.

Datum: 2026-09-22. Untersucht wurde der Main-Code der lokalen US-ROM sowie
das vorhandene JFG-Decomp-/Disassembly-Material. Dies ist eine statische
Datenflussanalyse; Animationsextraktion war nicht Teil des Schritts.

## Vertrauensbasis

- ROM: 33.554.432 Bytes, SHA-1
  `493ced9008dbe932d6e91179b68e8630cf23a023`.
- Hauptcode-Abbildung laut `ver/splat/jfg.us.yaml`: ROM `0x1000` entspricht
  VRAM `0x80000400`.
- Symbole stammen aus `jfg_us_syms_full.txt`. Die relevanten Instruktionen
  wurden direkt aus derselben lokalen ROM dekodiert.
- `gen_anim_data` liegt als Assemblerquelle vor. Das DKR-Projekt wurde nur
  zur Benennung derselben F3DDKR-ABI verwendet.

## Relevante Funktionen

| Symbol/Adresse | Für diesen Befund relevante Aufgabe |
| --- | --- |
| `modLoadModel`, `0x8003B9E8` | lädt den Prop, relocatet interne Offsets, lädt Texturen und prüft Gruppen |
| `func_8003C1B4`, `0x8003C1B4` | erzeugt eine Modellinstanz, berechnet `vertex_count × 10` und kopiert Vertices |
| `modGenAnimMatrices`, `0x8003D21C` | stößt die 21 Transformmatrizen für die Modellinstanz an |
| `makeModelGfx`, `0x8003DDD8` | läuft mit 16-Byte-Stride über Gruppen und baut F3DDKR-Kommandos |
| `modMakeLimbModel`, `0x8003E638` | wählt Bone-Matrizen, transformiert XYZ und baut temporäre Vertices/Dreiecke |
| `gen_anim_data`, `0x80073E80` | verarbeitet 16-Byte-Bone-Records und erzeugt 64-Byte-Matrizen |
| `func_80048B60`, `0x80048B60` | transformiert einen XYZ-Punkt durch eine ausgewählte Matrix |
| `texLoadTexture`, `0x80055694` | löst eine Textur-ID in einen geladenen `TextureHeader *` auf |
| `texDPTextureX`, `0x80055C00` | bindet Textur und aus Gruppenflags abgeleiteten Renderzustand |

## Bestätigte Headerzugriffe

`modLoadModel` addiert bei `0x8003BC90..0x8003BD28` die geladene
Dateibasis zu den Feldern `+0x18`, `+0x1c`, `+0x20`, `+0x24`, `+0x30`,
`+0x34`, `+0x38`, `+0x54`, `+0x68`, `+0x6c`, `+0x70` und `+0x80`.
Damit sind dies dateirelative Offsets, die in RAM in echte Pointer umgewandelt
werden.

| Headerfeld | Boy | tatsächliche Verwendung |
| --- | ---: | --- |
| `u8 +0x10` | 18 | Anzahl 8-Byte-Texturrecords |
| `u8 +0x11` | 1 | aktiviert Instanzpuffer/transformierten Limb-Pfad |
| `s16 +0x12` | 660 | Vertexanzahl; Multiplikation mit 10 |
| `s16 +0x16` | 82 | Gruppenanzahl |
| `ptr +0x18` | `0x88` | Texturrecords |
| `ptr +0x1c` | `0x26c8` | 10-Byte-Vertices |
| `ptr +0x20` | `0x648` | 16-Byte-Dreiecke |
| `ptr +0x24` | `0x118` | 16-Byte-Gruppen |
| `u8 +0x2d` | 2 | Anzahl einer Referenzpunktliste |
| `ptr +0x30` | `0x4090` | zwei 4-Byte-Einträge; erster u16 ist Vertexindex |
| `u32 +0x48` | `0x5170` | entspricht der Dateigröße; in diesem Pfad keine semantische Nutzung gefunden |
| `u8 +0x4f` | 21 | Zahl der Bone-/Transformrecords |
| `ptr +0x54` | `0x4098` | Bone-/Transformtabelle |

Der frühere Befund hatte `0x4c..0x4f` als einen u32-Wert und die Tabelle ab
`0x4090` gelesen. Der Code greift stattdessen byte-/halfwordweise zu: `+0x4c`
ist unter anderem ein Runtime-Referenzzähler, `+0x4f` ist die 21. Dadurch
beginnt die 21er-Tabelle korrekt bei `0x4098`.

## Recordgrößen und Datenfluss

### Texturrecord: 8 Byte

`modLoadModel` liest pro Record `s16 +6`, ruft `texLoadTexture` auf, schreibt
den Rückgabepointer nach `+0` und erhöht den Recordpointer um 8. Das Bit
`0x8000` der ID wählt in `texLoadTexture` einen zweiten Offsettabellenpfad;
danach wird mit `0x7fff` maskiert.

Die 18 Boy-IDs sind:

`8431 8436 8422 9a00 8209 820d 80f8 874e 9048 80f7 852f 820a 809f 874c 80f9 852e 8089 820b`.

Gruppenbyte `+0` indexiert diese Liste. Bei `0xff` wird keine Textur gebunden.
`makeModelGfx` liest außerdem Gruppenbyte `+0xb`, skaliert es um `<<14` als
Frame-/Subtexturargument und reicht Gruppen-u32 `+0xc` als Renderflags an
`texDPTextureX` weiter. Die Texturreferenzkette ist damit VERIFIED. Die
Bytes `+4/+5` der 18 Records stimmen mit dimensionsartigen Boy-Werten
überein, werden in diesem Pfad aber nicht gelesen.

Der anschließende Boy-Einzeltest hat die ID-Kette bis zum ROM vervollständigt.
Alle IDs besitzen Bit `0x8000`; `texLoadTexture` maskiert es bei
`0x800556c0..0x800556c8`, wählt die zweite geladene Offsettabelle und setzt
den Daten-Assetindex auf 0. `texInitTextures` lädt diese Offsettabelle aus
Asset 1. Über den US-Asset-LUT bei ROM `0xb1750` und die Assetbasis
`0xb1880` wurden alle 18 IDs eindeutig auf Runtime-Texturassets abgebildet.
14 davon führen bei `asset_start+0x20` zu einem bereits vollständig
validierten `11 00`-RGBA16-Container. Die IDs `8431`, `9a00`, `874e` und
`874c` führen zu den Markern `33 00`, `01 00`, `25 00` und `00 00`; ihre
Formate bleiben außerhalb dieser Untersuchung UNKNOWN. Die konkrete
14er-Zuordnung zum bestehenden RGBA16-Bestand ist **VERIFIED**.

### Gruppenrecord: 16 Byte plus Grenzrecord

`makeModelGfx` beginnt am Pointer `header+0x24`, liest `s16 header+0x16`
Gruppen und addiert nach jedem Durchlauf 16. Vertex- und Dreiecksbereiche
werden durch den aktuellen und nächsten Record abgegrenzt:

- `u16 +6`: erster Vertex;
- `u16 next+6`: Ende;
- `u16 +8`: erstes Dreieck;
- `u16 next+8`: Ende.

Ein gesetztes Bit `0x400` im u32 bei `+0xc` überspringt eine Gruppe in diesem
Renderpfad. Boy hat 65 hier aktive und 17 übersprungene Gruppen.

### Vertexrecord: 10 Byte

`func_8003C1B4` berechnet `s16(header+0x12) × 10`, richtet nur die gesamte
Allokation nachträglich auf acht Bytes aus und kopiert jeden Record mit
`lh +0/+2/+4`, `lbu +6/+7/+8/+9`; beide Pointer steigen um 10.

`modMakeLimbModel` liest dieselben XYZ-s16, wandelt sie in float um, ruft
`func_80048B60` mit einer 64-Byte-Matrix auf und schreibt das Ergebnis wieder
als drei s16. Die Bytes `+6..+9` werden unverändert kopiert. Damit sind
Recordgröße, XYZ-Felder und die Rolle der letzten vier Bytes als an F3DDKR
weitergereichte Vertexattribute VERIFIED. Ob diese Attribute für jede Gruppe
RGBA, Normalenkomponenten oder eine renderzustandsabhängige Deutung haben,
ist weiterhin UNKNOWN.

### Dreiecksrecord: 16 Byte

`makeModelGfx` bildet den Pointer als `triangle_base + start × 16` und erzeugt
einen `G_TRIN`/`gSPPolygon`-Befehl mit `count × 16` Bytes. Im Limb-Pfad liest
der Code `u8 +1/+2/+3` als die drei lokalen Vertexindizes. Die Felder
`s16 +4/+6`, `+8/+10`, `+12/+14` werden unverändert in das temporäre
Dreieck kopiert und anschließend demselben RSP-Befehl übergeben.

Das bestätigt die sechs s16 als drei per-Corner-Paare der F3DDKR-Triangle-ABI.
Die spätere JFG-Einzelgruppenvalidierung bestätigt sie als signed S10.5-S/T-
Koordinaten. Die frühere `LIKELY`-Einstufung und unbekannte Skalierung sind
`SUPERSEDED`; Details stehen in `group16-uv-validation.md`.

## Gruppen zu Bones und starres Skinning

Die 21 Records beginnen bei `header+0x54 = 0x4098`, nicht bei `0x4090`.
`gen_anim_data` erhöht den Eingabepointer pro Element um 16. Es verwendet:

- `u8 +0`: Parent-Matrix-ID;
- `u8 +1`: Ziel-ID des 64-Byte-Matrixslots;
- Byte `+2`: von `modGenAnimMatrices` gesetzter Kanalindex der aktuellen
  Animation;
- Byte `+3`: zweiter Kanalindex beim Animationsblending;
- `f32 +4/+8/+12`: lokale Translation X/Y/Z.

Beim Aufbau der Hierarchie lädt `gen_anim_data` die Matrix `byte[0] × 64`,
schreibt beziehungsweise komponiert die Matrix `byte[1] × 64` und läuft bis
zur Zahl aus Headerbyte `+0x4f`. In Boy sind Byte 1, 2 und 3 jeweils `0..20`;
Byte 0 ist zuerst `0xff` und danach eine kleinere Parent-ID.

Die vollständige Matrixformel, Multiplikationsreihenfolge und die Grenze des
Defaultpfads sind in `transform-matrix-validation.md` dokumentiert. Der
wesentliche neue Befund: Die Translation stammt aus dem Record, Rotation,
optionale Skala und Root-Translation stammen auch im nicht geblendeten Pfad
aus der ausgewählten Animation. Die Records allein ergeben daher keine
nachgewiesene statische Grundpose.

Für jedes Dreieck entscheidet `modMakeLimbModel` anhand des lokalen
Vertexindex `i`:

```text
if i < group[4]:       matrix_id = group[1]
elif i < group[5]:     matrix_id = group[2]
else:                  matrix_id = group[3]
```

Danach wird `matrix_base + matrix_id × 64` an `func_80048B60` übergeben.
Für alle 65 nicht mit `0x400` übersprungenen Boy-Gruppen sind die Grenzen
konsistent und die tatsächlich erreichbaren IDs Teil der 21er-Tabelle.
Dies bestätigt Gruppe→Bone/Matrix und eine **starre Einzelmatrix-Zuordnung**.
Der Pfad liest keine Gewichte und mischt keine zwei Matrizen für einen Vertex.
Die Spezialgruppen mit `0x400` dürfen nicht nach demselben Schema semantisch
interpretiert werden, weil `makeModelGfx` sie hier überspringt.

## Triangle-Flag `0x00/0x40`

Im direkten Pfad prüft der CPU-Code das Dreiecksbyte `+0` nicht; der RSP erhält
es unverändert. Im Limb-Pfad setzt der Code für jedes neu erzeugte Dreieck
Byte 0 ausdrücklich auf `0x40`, unabhängig vom Original. Das bestätigt eine
RSP-seitige Renderbedeutung.

Der tatsächliche JFG-F3DDKR-Text beginnt bei ROM `0x9ffd0`. Im
Dreiecksverarbeitungspfad liegt der Recordpuffer bei RSP-DMEM `0x0870`; die
Schleife erhöht seinen Zeiger bei RSP-IMEM `0x1768..0x1778` um 16 Byte. Der
für das Flag entscheidende Block lautet:

```text
RSP-IMEM    ROM       Instruktion                 Wirkung
0x16d0      0x0a06a0  lbu   t1, 0(a2)             Recordbyte +0
0x16d4      0x0a06a4  addi  t3, zero, -0x2001     Maske ~0x2000
0x16d8      0x0a06a8  xori  a3, t1, 0x40
0x16e0      0x0a06b0  andi  a3, a3, 0x40          nur Bit 0x40
0x16e4      0x0a06b4  sll   a3, a3, 7             -> Zustandsbit 0x2000
0x16e8      0x0a06b8  and   t2, t2, t3            altes 0x2000 löschen
0x16ec      0x0a06bc  or    t2, t2, a3
0x16f0      0x0a06c0  sw    t2, 0x114(zero)        Geometriestatus sichern
```

Damit setzt Recordwert `0x00` das Statusbit `0x2000`, Recordwert `0x40`
löscht es. DMEM `0x0114` ist wegen `sp=0x0110` zugleich `4(sp)`; derselbe
Wert wird bei IMEM `0x1a40`/ROM `0x0a0a10` wieder geladen. Die JFG-Kopie von
`PR/gbi.h` bezeichnet `0x2000` als `G_CULL_BACK` und `0x1000` als
`G_CULL_FRONT`. Entscheidend ist zusätzlich der tatsächliche Datenfluss:

```text
RSP-IMEM    ROM       Instruktion                 Wirkung
0x1a98      0x0a0a68  andi  t7, t5, 0x2000        Cull-/Flagmaske
0x1aa0      0x0a0a70  andi  t6, t5, 0x1000        Auswahl Gegenorientierung
0x1ab0      0x0a0a80  sra   t6, t7, 1             ggf. Cullrichtung tauschen
0x1ab4      0x0a0a84  and   t7, zero, zero
0x1b3c      0x0a0b0c  mfc2  s1, v27[0]            Orientierungsresultat
0x1b44      0x0a0b14  mfc2  s0, v26[0]
0x1b48      0x0a0b18  sra   s1, s1, 31            Vorzeichenmaske
0x1b50      0x0a0b20  and   t7, t7, s1
0x1b5c      0x0a0b2c  beq   s0, zero, 0x1f74      degenerat: verwerfen
0x1b60      0x0a0b30  xori  s1, s1, 0xffff        Gegenorientierung
0x1b68      0x0a0b38  and   t6, t6, s1
0x1b70      0x0a0b40  or    s0, t7, t6
0x1b78      0x0a0b48  bgtz  s0, 0x1f74            gewählte Seite verwerfen
```

Ziel `0x1f74` (ROM `0x0a0f44`) führt ohne Erzeugung des normalen
Dreieckoutputs zum Rücksprung bei `0x1f78`. Bei Recordwert `0x40` ist das
aus dem Record abgeleitete `0x2000` gelöscht; dadurch werden sowohl `t7` als
auch, nach der Richtungswahl, `t6` null. Die Verzweigung `0x1b78` kann dann
nicht aufgrund der Dreiecksorientierung auslösen. Bei `0x00` bleibt genau
eine der beiden Vorzeichenrichtungen als Reject-Bedingung aktiv. Bit `0x40`
bedeutet in JFG daher **VERIFIED: orientierungsabhängiges Backface-Culling
für dieses Dreieck deaktivieren / beide Seiten zeichnen**. Der separate
Degeneratentest bei `0x1b5c` sowie Clip-Rejection bleiben aktiv; `0x40`
deaktiviert nicht die allgemeine Dreiecksverwerfung.

## Statusänderungen

### VERIFIED

- Headeroffsets werden beim Laden zu RAM-Pointern relocatiert.
- 18×8-Byte-Texturrecords; ID bei `+6`; Gruppenbyte `+0` wählt Textur.
- 82×16-Byte-Gruppen plus Grenzrecord; Bereiche über `+6/+8` und Folgerecord.
- 660×10-Byte-Vertices; XYZ sind s16 bei `+0/+2/+4`.
- 520×16-Byte-Dreiecke; lokale Indizes bei `+1/+2/+3`.
- Drei weitere s16-Paare werden pro Dreieck unverändert an F3DDKR gegeben.
- 21×16-Byte-Bone-/Transformrecords ab `0x4098`; Parent `+0`, ID `+1`,
  lokale f32-Werte `+4/+8/+12`.
- Gruppenbytes `+1..+3` wählen anhand der Grenzen `+4/+5` genau eine der
  21 Matrizen für die XYZ-Transformation.
- Vertexbytes `+6..+9` bleiben bei der Transformation unverändert.
- Dreiecksflag Bit `0x40` löscht im JFG-RSP-Mikrocode `G_CULL_BACK` und
  verhindert die orientierungsabhängige Reject-Verzweigung; `0x00` aktiviert
  sie für eine durch den Geometriestatus gewählte Winding-Richtung.
- Alle 18 Boy-Textur-IDs sind über `texLoadTexture`, Assettabelle und Asset-LUT
  auf ROM-Assets aufgelöst; 14 treffen den bestehenden VERIFIED-RGBA16-Bestand.

### LIKELY

- Texturrecordbytes `+4/+5` sind Breite und Höhe.

### HYPOTHESIS

- **SUPERSEDED:** Die frühere Rest-/Bind-Transform-Hypothese für die drei f32.
  Sie sind inzwischen als lokale Translation X/Y/Z bestätigt; Rotation und
  optionale Skala stammen aus dem Animationszustand.

### UNKNOWN

- konkrete Semantik der vier Vertexattribute für jede Boy-Gruppe;
- Decoder und Semantik der vier Boy-Texturassets außerhalb des bestätigten
  `11 00`-RGBA16-Formats;
- Zweck der 17 im untersuchten Renderpfad übersprungenen `0x400`-Gruppen;
- vollständige Bedeutung aller Gruppenflags;
- ob die drei f32 allein eine vollständige Bind Pose beschreiben.

## Abgeschlossener Mikrocode-Test

Der zuvor vorgeschlagene Einzeltest des JFG-F3DDKR-Pfads für Bit `0x40` ist
oben dokumentiert. Die Backface-Deutung benötigt nicht mehr die externe
DKR-Benennung als Beweis.

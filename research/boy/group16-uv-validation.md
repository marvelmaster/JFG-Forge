# Prop 220 Boy: UV- und Tile-Einzeltest für Gruppe 16

Dieser Schritt untersucht ausschließlich die aktive Boy-Gruppe 16. Sie wurde
gewählt, weil sie 15 nichtdegenerierte Dreiecke, eine vollständig bestätigte
RGBA16-Texturkette und besonders aussagekräftige Koordinaten besitzt:
`S=-243..520`, `T=0..512`. Damit liegen Werte innerhalb, auf und außerhalb
der 16×16-Tilegrenzen vor.

## Identität und Textur

- Gruppenrecord: `05 02 0b ff 08 10 00 67 00 49 00 00 00 00 00 03`;
- Vertexbereich: `103..118`, Dreiecksbereich: `73..87`;
- TextureRecord-Index 5, Texture-ID `0x820D`;
- `texLoadTexture`: High-Bit-Pfad über Offsettabellen-Asset 1 und Daten-Asset 0;
- Runtime-Asset: ROM `0x178650`, komprimierter RGBA16-Container `0x178670`;
- Ergebnis: das bereits pixelvalidierte `16×16`-Asset `178670_16x16.png`.

Diese Kette ist **VERIFIED**.

## Tatsächlicher Koordinatenpfad

`makeModelGfx` übergibt die 16-Byte-Dreiecksrecords an `G_TRIN`. Im
JFG-F3DDKR-RSP-Code kopieren ROM `0x0A0710..0x0A0724` / IMEM
`0x1740..0x1754` die Wörter an Triangle `+4`, `+8` und `+12` in den
jeweiligen Vertexslot `+0x14`.

Im Dreieckspfad prüft IMEM `0x1CC4` / ROM `0x0A0C94`, ob die Texturattribute
benötigt werden. IMEM `0x1CE0..0x1CE8` / ROM `0x0A0CB0..0x0A0CB8` lädt dann
die drei 4-Byte-Paare direkt von Vertex `+0x14`. Die Vektorblöcke
`0x1D10..0x1D64` und `0x1E08..0x1F6C` berechnen daraus perspektivische
Zwischenwerte und Gradienten und schreiben die Texturfelder des RDP-
Dreieckskommandos. Vor diesen Loads findet keine CPU-Normalisierung anhand
der Bilddimensionen statt.

JFGs `PR/gt.h` bezeichnet genau die s/t-Felder dieses Vertexformats als
signed `S10.5`. Gemeinsam mit dem realen Zugriff bestätigt dies:

```text
texel_s = raw_s / 32
texel_t = raw_t / 32
```

Die Breite und Höhe gehören nicht zur Umrechnung in Texel. Sie werden erst
für Tilegröße und die dimensionslose OBJ-Abbildung verwendet.

## Tilezustand

Der tatsächliche Builder bei `0x8005719C` liest für die Render-Tile:

- CMT aus Textureheader `+0x1E` bei `0x800576FC`;
- MaskT aus `+0x1F` bei `0x80057708`;
- CMS aus `+0x1C` bei `0x80057724`;
- MaskS aus `+0x1D` bei `0x80057734`.

Für `0x820D` sind CMS=2 und CMT=2, also nach JFGs `PR/gbi.h` jeweils
`G_TX_CLAMP`. MaskS, MaskT, ShiftS und ShiftT sind null; Mirror ist nicht
gesetzt. `0x80057750..0x80057780` setzt die Grenzen auf
`(16-1)<<2` in beiden Achsen. `texDPTextureX` bei `0x80055C00` bindet die
vorbereitete Displaylist und den Renderzustand; eine zusätzliche S/T-
Transformation ist in diesem Pfad nicht vorhanden.

## Achsen und OBJ

S ist die horizontale und T die Zeilenachse. Die Render-Tile hat eine
Zeilenlänge von vier 64-Bit-Wörtern, also 32 Byte beziehungsweise 16
RGBA16-Pixel. Steigendes T adressiert dadurch spätere geladene Texturzeilen.
Das vorhandene validierte PNG speichert diese ROM-Zeilen von oben nach unten.
Konventionelles OBJ-/Blender-UV verwendet dagegen steigendes V nach oben.
Für genau dieses 16×16-Asset gilt daher:

```text
u = raw_s / (32 * 16)
v = 1 - raw_t / (32 * 16)
```

Der V-Flip ist für die Orientierung dieses PNGs **VERIFIED**. Werte außerhalb
`0..1` bleiben im OBJ erhalten; die MTL fordert `-clamp on`, entsprechend dem
JFG-Tilezustand. Die vollständige Subtexel- und Filtergleichheit eines
beliebigen OBJ-Importers mit dem RDP bleibt **LIKELY**, da OBJ/MTL keinen
vollständigen N64-Sampler beschreibt.

## Grenze der Übertragung

S10.5, Achsen und V-Umrechnung sind auf andere texturierte Boy-Gruppen im
gleichen G_TRIN-Pfad übertragbar. Clamp, Mirror, Mask und Shift müssen jedoch
für jedes Texturasset aus dessen Header gelesen werden. Das Clamp-Ergebnis
der Gruppe 16 ist nicht pauschal auf alle Gruppen übertragbar.

Der maschinenlesbare Einzelnachweis und der OBJ-Test liegen unter
`data/generated/boy-group16-uv-validation/`.

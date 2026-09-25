# Prop 220 `Boy`: experimenteller statischer Export

Status: **EXPERIMENTAL**. Dies ist ein auf exakt einen SHA-256-gepinntes
Validierungswerkzeug, kein allgemeiner JFG-Modellexporter.

> Die damalige UV-/Tile-Grenze dieses Rohartefakts ist inzwischen
> `SUPERSEDED`. Der bestätigte aktuelle Stand steht in
> [`../../knowledge/verified/boy-juno-milestone-1.md`](../../knowledge/verified/boy-juno-milestone-1.md).

## Reproduktion

Vom äußeren Arbeitsverzeichnis aus:

```powershell
python -B jfg-re/tools/export_boy_experimental.py `
  --boy jfg-re/data/generated/props-us-verified/bins/0220_Boy.bin `
  --rom rom/jetforcegemini.z64 `
  --texture-manifest jfg-re/data/generated/rgba16-us-verified/textures-manifest.json `
  --output jfg-re/data/generated/boy-prop220-experimental
```

Das Zielverzeichnis darf nicht existieren. Der Exporter akzeptiert nur Prop
220 mit SHA-256
`2cd9e008852355d8191cf11e383de833b7ab1ea2814b3dd71583c8aa104f0baf`
und die bekannte US-ROM. `PowerBoy` wird aufgrund seiner abweichenden
Identität abgelehnt.

## Ausgaben

- `boy-runtime-visible.obj`: gespeicherte XYZ der 65 Gruppen, die der
  untersuchte Runtime-Pfad nicht durch Flag `0x400` überspringt;
- `boy-raw-all-groups.obj`: alle 82 Gruppen einschließlich drei
  nichtdegenerierter Flächen aus übersprungenen Gruppen;
- `boy-materials.mtl`: eindeutige Debugmaterialien und Verweise auf die 14
  nachgewiesenen RGBA16-PNGs;
- `boy-vertices.jsonl`: XYZ, unbekannte Bytes `+6..+9`, Gruppe und bestätigte
  Matrix-ID-Zuordnung für aktive Gruppen;
- `boy-triangles.jsonl`: alle 520 Records mit Flag, lokalen und absoluten
  Indizes, rohen Koordinatenpaaren, Matrix-IDs und Degenerationsprüfung;
- `boy-export-report.json`: maschinenlesbare Zusammenfassung und
  Texture-ID-Auflösung.

Die OBJ-Dateien enthalten absichtlich keine `vt`-Records. Die s16-Paare
werden vom JFG-RSP unverändert in die F3DDKR-Vertexslots kopiert, und JFGs
`PR/gt.h` bezeichnet die transformierten Werte als S10.5. Damit ist die
1/32-Texel-Grundskalierung gut belegt. Die für OBJ nötige V-Achsenkonvention
und der Boy-Tilezustand waren in diesem Schritt noch nicht nachgewiesen; diese
historische Grenze ist inzwischen `SUPERSEDED`. Die Rohwerte bleiben
vollständig in JSONL und in den OBJ-Kommentaren erhalten.

## Geometriebefund

- 660 gespeicherte Vertices;
- 520 Dreiecksrecords;
- 505 nichtdegenerierte Flächen über alle Gruppen;
- 502 nichtdegenerierte Flächen in den 65 aktiven Gruppen;
- 17 durch Flag `0x400` übersprungene Gruppen;
- 15 geometrisch degenerierte Records, alle in übersprungenen Gruppen.

Jeder der 15 Records referenziert dreimal denselben gespeicherten XYZ-Punkt.
Sie bleiben im Report erhalten, erzeugen aber keine OBJ-Fläche.

## Texture-ID-Kette

Alle 18 Boy-IDs besitzen Bit `0x8000`. `texLoadTexture` maskiert dieses Bit,
verwendet Asset 1 als Offsettabelle und lädt die Daten aus Asset 0. Mit dem
US-Asset-LUT bei ROM `0xB1750` und der Assetbasis `0xB1880` lassen sich alle
18 Runtime-Assets eindeutig bestimmen.

14 Ketten enden an bereits pixelvalidierten `11 00`-RGBA16-Containern:

`8436 8422 8209 820d 80f8 9048 80f7 852f 820a 809f 80f9 852e 8089 820b`.

Vier IDs sind als Runtime-ROM-Asset aufgelöst, gehören aber nicht zur
verifizierten RGBA16-Pipeline:

| ID | Marker | Status in diesem Schritt |
| --- | --- | --- |
| `8431` | `33 00` | UNKNOWN |
| `9a00` | `01 00` | UNKNOWN |
| `874e` | `25 00` | UNKNOWN |
| `874c` | `00 00` | UNKNOWN |

Für diese vier wurde weder ein Decoder gewählt noch eine Bildzuordnung nach
Aussehen vorgenommen.

## Visuelle Grenze

`boy-runtime-visible.obj` eignet sich in Blender zur Kontrolle von gespeicherter
Form, Topologie, Gruppen und Materialgrenzen. Eine falsche Silhouette kann
weiterhin daraus entstehen, dass die gespeicherten XYZ vor der noch nicht
verstandenen Rest-/Bind-Transformation liegen. Die verlinkten Texturen sind
identifiziert, aber ohne bestätigte OBJ-V-Achsenabbildung noch nicht korrekt
auf das Mesh projiziert.

# Prop 220 Boy: texturierter statischer Runtime-Export

Dieser auf die bekannte Boy-Binärdatei gepinnte Export erweitert den rohen
statischen Export um bestätigte per-Corner-UVs und VERIFIED RGBA16-Texturen.
Er bleibt **EXPERIMENTAL**, weil gespeicherte XYZ ohne noch nicht verstandene
Rest-/Bind-Pose-Transformationen ausgegeben werden.

## Umfang

- 65 im untersuchten Runtime-Pfad aktive Gruppen und 502 Flächen;
- 62 Gruppen beziehungsweise 478 Flächen mit 14 VERIFIED RGBA16-Texturen;
- Gruppen 79, 80 und 81 beziehungsweise 24 Flächen mit den weiterhin
  unbekannten Formaten der IDs `0x9A00`, `0x874E` und `0x874C`;
- 17 durch `0x400` übersprungene Gruppen werden nicht exportiert.

Für jede texturierte Ecke gilt:

```text
u = raw_s / (32 * width)
v = 1 - raw_t / (32 * height)
```

Es wird ein eigener OBJ-`vt`-Index pro Triangle-Corner erzeugt. Dadurch gehen
UV-Seams bei identischen XYZ-Indices nicht verloren. Werte außerhalb `0..1`
werden nicht begrenzt.

## Tilezustände

Der reale nicht-mipmapped JFG-Builder liest CMS, MaskS, CMT und MaskT aus den
Textureheaderbytes `+0x1C..+0x1F`. ShiftS und ShiftT sind in diesem Pfad null.
Alle 14 tatsächlich von aktiven Boy-Gruppen verwendeten VERIFIED-RGBA16-
Assets haben:

```text
CMS=CLAMP, CMT=CLAMP
MaskS=0, MaskT=0
ShiftS=0, ShiftT=0
MirrorS=false, MirrorT=false
```

Die MTL bildet diesen gemeinsamen Zustand mit `map_Kd -clamp on` ab. Der
Report bewahrt den vollständigen numerischen Zustand pro Material und Gruppe.
Die drei unbekannten Formate bekommen Diagnosematerialien ohne Bilddatei.

## Backface-Culling

Das Dreiecksbyte und die bestätigte Wirkung von Bit `0x40` werden pro Face im
JSON-Report gespeichert. OBJ/MTL kann gemischtes per-Triangle-Culling nicht
zuverlässig transportieren. Die Geometrie wird deshalb weder dupliziert noch
umgedreht.

## Reproduktion

```powershell
python -B jfg-re/tools/export_boy_textured_static.py `
  --boy jfg-re/data/generated/props-us-verified/bins/0220_Boy.bin `
  --rom rom/jetforcegemini.z64 `
  --texture-manifest jfg-re/data/generated/rgba16-us-verified/textures-manifest.json `
  --output jfg-re/data/generated/boy-prop220-textured-static
```

Das Ausgabeziel muss neu sein. Der bisherige Export unter
`boy-prop220-experimental/` und der Gruppe-16-Einzeltest werden nicht
überschrieben.

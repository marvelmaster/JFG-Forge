# Boy: zeitliche Validierung von Animation 0

> **SUPERSEDED NUMERICAL POSES:** Bitstrom-, Zeit-, Loop-, Root-Q10- und
> Interpolationsbefunde bleiben gültig. Die unten erhaltenen Matrix-,
> Vertex- und Bounding-Box-Zahlen wurden vor der runtimebestätigten
> A/C/B-Komponentenkorrektur erzeugt. Sie dokumentieren Forschungshistorie,
> sind aber keine aktuellen Forge-Referenzwerte.

Datum: 2026-09-23. Untersucht wurde ausschließlich Prop 220, Animationindex
0 / Animations-ID `1026`. Andere Animationen, Prop 309 und die separat
geladene Hand waren nicht Teil dieses Schritts.

## Ergebnis

Der Animationsdecoder wurde für die ganzzahligen Zeiten `0`, `1`, `8` und
`15` sowie für `7.5` reproduziert. Die drei zusätzlichen ganzzahligen
Snapshots decken frühen, mittleren und späten Bereich ab. Alle Snapshots
verwenden unverändert die bestätigten 502 Faces, Corner-UVs und Materialien;
638 aktive Vertices werden über die jeweils neu berechneten Matrizen bewegt.

## Metadaten und Zeitachse

Der Blob enthält 16 gespeicherte Samples `0..15`. Der Bereich beginnt bei
Bloboffset `0x8e`, der Stride beträgt 25 Byte. Die 400 Samplebytes enden bei
`0x21e`; der Blob ist `0x220` Byte groß.

`objAnimDframe` (`0x8001138C`) führt am Objekt eine normierte Phase. Bei
`0x80011394..0x800113B8` addiert es `caller_delta * caller_scale`; bei
gesetztem Loopflag reduziert `0x800113DC..0x80011418` Werte ab 1 wieder um 1.
`modGenAnimMatrices` multipliziert diese Phase bei
`0x8003D3F8..0x8003D428` mit dem Samplelimit 16. Damit ist die tatsächliche
Samplezeit `[0,16)`. Blobbyte `+1 = 0x14` liefert das Loopflag `0x10`; der
Low-Nibble-Wert gehört zum separaten Blend-Timer und belegt keine FPS.

Bei `0x8003D638..0x8003D708` entsteht der Samplepointer als
`blob + be16(blob+2) + floor(time) * stride`. Für einen nichtganzzahligen
letzten Samplewert setzt `0x8003D6A4..0x8003D6E0` den Zweitpointer auf Sample
0 zurück. Eine feste Abspielrate ist damit **UNKNOWN**; sie wird von den
Aufrufern des Objektplayers bestimmt und darf nicht aus den 16 Samples
abgeleitet werden.

## Interpolation

`func_80074B50` berechnet bei `0x80074B50..0x80074BAC`:

```text
fraction10 = round((time - floor(time)) * 1024)
```

Die spätere zentrale Produktionskanonisierung trägt ein gerundetes `1024`
auf das nächste Sample über und setzt `fraction10=0`. Der strikte
Runtimebereich bleibt `0..1023`.

Für Rootwerte gilt anhand `0x80074BB8..0x80074C90`:

```text
root_q10 = (signed_base << 11)
         + (current_sample << 10)
         + (next_sample - current_sample) * fraction10
root_model = root_q10 / 1024
```

Dies korrigiert die frühere Frame-0-Rechnung, welche das `sample << 10`
übersehen hatte. Frame 0 besitzt Root `(0,-9,0)`.

Winkelsamples verwenden bei `0x80074CF0..0x80074D20` ein signed 11-Bit-Delta:

```text
delta11 = sign_extend_11(next_packed - current_packed)
sample  = current_packed + ((delta11 * fraction10) >> 10)
angle   = s16(base + (sample << 5))
```

Bei `t=7.5` ist `fraction10=512`. Root Y wird exakt von `-10` nach `-9` auf
`-9.5` interpoliert. Vier Skalare überschreiten die `u16/s16`-Grenze; ihre
gepackten Deltas bleiben kurz. Bei Scalar 43 und 44 ist das Delta jeweils
`-1`. Der signed-11-Bit-Schritt verändert in dieser konkreten Animation kein
Rohdelta, weil die größte Deskriptorbreite neun Bit beträgt. Die
Grenzüberschreitung wird trotzdem ohne langen Winkelsprung verarbeitet.

Der optionale Scalezweig liegt bei `0x80074E98..0x80074EC4`. Keiner der 60
Deskriptoren dieser Animation besitzt einen Scale-Stream. Scale bleibt auf
allen getesteten Kanälen 1; eine tatsächliche Scale-Interpolation ist für
diesen Blob **nicht anwendbar**.

## Numerische Ergebnisse — SUPERSEDED für Matrix-/BBox-Werte

| Zeit | Root XYZ | Bounding Box, s16 |
| ---: | --- | --- |
| `0` | `(0,-9,0)` | `(-89,-4,-63)..(56,216,88)` |
| `1` | `(0,-6,0)` | `(-91,-5,-52)..(57,219,91)` |
| `7.5` | `(0,-9.5,0)` | `(-69,-1,-69)..(63,216,84)` |
| `8` | `(0,-9,0)` | `(-70,-2,-66)..(63,216,88)` |
| `15` | `(0,-10,0)` | `(-88,0,-71)..(55,215,79)` |

Alle 21 lokalen und Worldmatrizen, Kanalwerte einschließlich Floatbits und
Kontrollvertices der Matrix-IDs `2,4,5,7,10,12,15,16,19` stehen pro Zeitpunkt
im JSON-Report. Sämtliche Matrix- und Vertexwerte sind endlich und passen in
den JFG-`s16`-Ausgabebereich. Topologie, Matrixhierarchie, UV-Zuordnung und
Materialgrenzen bleiben über alle Snapshots identisch. Damit gibt es keinen
Hinweis auf fehlerhafte Frameadressierung. Der Vergleich `7.5 -> 8` ist als
benachbarter Halbzeitschritt besonders aussagekräftig; der größte
Matrixursprungsweg beträgt dort etwa `6.6064` Modelleinheiten.

## Artefakte und Blender

Die Ergebnisse liegen unter
`data/generated/boy-anim0-temporal-validation/`. Importreihenfolge:

1. `boy-anim0-time-00.obj`
2. `boy-anim0-time-01.obj`
3. `boy-anim0-time-07_5.obj`
4. `boy-anim0-time-08.obj`
5. `boy-anim0-time-15.obj`

Alle Dateien verwenden `boy-anim0-temporal.mtl`. Beim Import müssen Achsen
und Skalierung für alle Dateien gleich bleiben. Zu prüfen sind Gelenkanschlüsse,
Extremitätenbewegung, Texturorientierung und Materialgrenzen. Es handelt sich
um einzelne Model-Space-Snapshots ohne Armature oder Animationskurve. Die
separate Hand fehlt weiterhin absichtlich; UNKNOWN-Texturformate bleiben
untexturiert.

## Status und Grenze

**VERIFIED:** 16 Samples, Stride und Pointerrechnung, Loop `15 -> 0`,
normierte Phase, 10-Bit-Fraktion, Root-Q10-Rechnung, Winkelinterpolation,
`u16/s16`-Grenzübergänge, Matrizen und Vertextransformation für die fünf
getesteten Zeiten.

**UNKNOWN / nicht ausgeübt:** feste FPS und konkrete Aufruferdelta-Werte;
Scale-Interpolation mangels Scale-Stream; Semantik anderer Animationen.

Der kleinste nächste Schritt Richtung Rig-Export ist eine explizite
21-Knoten-Hierarchie für genau diese Animation, welche die bereits
reproduzierten lokalen Matrizen als zeitabhängige Transformkurven übernimmt,
ohne neue Bindpose oder Skinninggewichte zu erfinden.

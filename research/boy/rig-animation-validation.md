# Boy: begrenztes Rig-/Animations-Validierungsartefakt

> **HISTORICAL / PARTIALLY SUPERSEDED:** Dieser Bericht dokumentiert das
> ursprüngliche begrenzte Rig-Artefakt. Seine technische 1:1-Zeitabbildung und
> numerischen Posevergleiche sind nicht die aktuelle Forge-Exportsemantik.
> Aktuelle Exporte verwenden die runtimebestätigte A/C/B-Komponentenabbildung
> und `PlaybackTimingContext.effective_samples_per_second()`.

Datum: 2026-09-23. Das Artefakt enthält ausschließlich Prop 220 sowie die
bereits vollständig validierten Animationen 0 und 43. Es ist kein allgemeiner
JFG-Rig- oder Animationsexporter.

## Repräsentation

Gewählt wurde glTF 2.0 mit 21 Skin-Joints `jfg_node_00` bis
`jfg_node_20`. Jeder aktive Quellvertex besitzt genau eine bereits bestätigte
Matrix-ID. Im glTF wird diese als `JOINTS_0 = [id,0,0,0]` und
`WEIGHTS_0 = [1,0,0,0]` gespeichert. Wegen der Corner-UVs enthält das
Render-Mesh 1506 duplizierte Corner-Vertices; sie verweisen weiterhin auf nur
638 aktive JFG-Quellvertices.

Die 21 Inverse-Bindmatrizen sind Identität. Das ist ausdrücklich eine
**TECHNICAL REPRESENTATION**: Bei Identitäts-Inverse-Bind gilt die glTF-
Skinmatrix direkt als animierte JFG-Worldmatrix. Dadurch reproduziert ein
roher Vertex `p` exakt den bekannten Pfad `p * M_world`, ohne eine T-Pose,
JFG-Restpose oder unbekannte inverse Bindmatrix zu erfinden.

## Hierarchie

```text
00
├─01
│ └─02
│   ├─03
│   │ ├─04─05─06
│   │ └─07─08─09
│   └─10
└─11
  ├─12─13─14─15
  └─16─17─18─19─20
```

| Node | Parent | aktive Vertices | Faces berühren Node | Cornerrefs |
| ---: | ---: | ---: | ---: | ---: |
| 0 | – | 0 | 0 | 0 |
| 1 | 0 | 0 | 0 | 0 |
| 2 | 1 | 133 | 122 | 304 |
| 3 | 2 | 0 | 0 | 0 |
| 4 | 3 | 18 | 21 | 33 |
| 5 | 4 | 4 | 8 | 12 |
| 6 | 5 | 0 | 0 | 0 |
| 7 | 3 | 7 | 7 | 8 |
| 8 | 7 | 15 | 18 | 37 |
| 9 | 8 | 42 | 32 | 96 |
| 10 | 2 | 214 | 168 | 488 |
| 11 | 0 | 41 | 58 | 118 |
| 12 | 11 | 24 | 28 | 52 |
| 13 | 12 | 16 | 27 | 51 |
| 14 | 13 | 18 | 27 | 52 |
| 15 | 14 | 23 | 23 | 50 |
| 16 | 11 | 26 | 28 | 52 |
| 17 | 16 | 15 | 27 | 51 |
| 18 | 17 | 19 | 27 | 52 |
| 19 | 18 | 23 | 23 | 50 |
| 20 | 19 | 0 | 0 | 0 |

Die vollständigen lokalen Translationen stehen pro Node im JSON-Report.

## Animation und Interpolation

glTF kann JFGs komponentenweise Winkelinterpolation mit anschließendem
Sinustabellen-Matrixaufbau nicht durch gewöhnliche Quaternion-Interpolation
reproduzieren. Beide Clips verwenden daher `STEP` und enthalten jeden
Zustandsübergang des 10-Bit-Zeitrasters einschließlich MIPS-
Round-to-nearest-even an Halbgrenzen.

- Animation 0 / ID 1026: 16 Samples, Loop, 16386 gebackene Zustände,
  technische Zeit `0..16`.
- Animation 43 / ID 1069: 76 Samples, kein Loop, 76802 gebackene Zustände,
  technische Zeit `0..75`.

**SUPERSEDED als allgemeine Exportaussage:** In diesem historischen
Validierungsartefakt entsprach eine glTF-Sekunde genau einer technischen
JFG-Samplezeiteinheit. Aktuelle Forge-Exporte teilen technische Samplezeit
durch die gemeinsame effektive Vorschau-/Exportrate.

## Numerische Gegenprüfung

Verglichen wurden alle 638 aktiven Quellvertices an zehn bereits bestätigten
Zeitpunkten. Referenz war jeweils der JFG-f32-Matrixpfad; Gegenseite waren die
aus den tatsächlich als Float32 gespeicherten glTF-Quaternionen und
Translationen rekonstruierten Skinmatrizen.

| Animation | Zeit | Maximum | Mittel | innerhalb `1e-4` |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | `1.7075e-5` | `5.5269e-6` | 638/638 |
| 0 | 1 | `2.1042e-5` | `4.5549e-6` | 638/638 |
| 0 | 7.5 | `2.1263e-5` | `5.7758e-6` | 638/638 |
| 0 | 8 | `1.8894e-5` | `5.0853e-6` | 638/638 |
| 0 | 15 | `1.4906e-5` | `4.8996e-6` | 638/638 |
| 43 | 0 | `2.6964e-5` | `7.6517e-6` | 638/638 |
| 43 | 1 | `2.0488e-5` | `7.0271e-6` | 638/638 |
| 43 | 37 | `2.0488e-5` | `6.7419e-6` | 638/638 |
| 43 | 37.5 | `2.0488e-5` | `7.2219e-6` | 638/638 |
| 43 | 75 | `1.7890e-5` | `7.5668e-6` | 638/638 |

Gesamt: 6380/6380 innerhalb `1e-4`, Maximum `2.6963510e-5`, gewichtetes
Mittel `6.2051948e-6`. 25 Vergleiche waren bitnumerisch exakt. Die kleinen
Abweichungen entstehen durch Quaternionkonversion und glTF-Float32-Speicherung.
Statistiken pro Matrix-ID stehen im Report.

## Materialien und Grenzen

14 bestätigte RGBA16-PNGs werden relativ referenziert. Wrap, Mirror und Clamp
werden in glTF-Samplerzustände übertragen. Trianglebit `0x40` erzeugt
separate doppelseitige Materialvarianten. UNKNOWN-Texturformate bleiben
Diagnosematerialien. In diesem historischen Artefakt blieb die separate Hand
absichtlich abwesend; aktuelle modellhaltige Forge-Exporte können den
ausgewählten BoyGun-Slot als starres Child von `jfg_node_06` einschließen.

## Blender-5.0-Import und Accessorreparatur

Der erste manuelle Blender-Import deckte einen Writerfehler im
`inverseBindMatrices`-Accessor auf: 21 `MAT4` benötigen 1344 Byte, der
BufferView enthielt wegen einer unvollständigen Identitätsmatrix aber nur
1260 Byte. Nach der minimalen Writerkorrektur und einer vollständigen
Accessor-Bereichsprüfung importiert Blender 5.0.1 das Artefakt erfolgreich.

Blenders ausgewertetes Mesh wurde an denselben zehn Zeiten gegen den JFG-
Referenzpfad geprüft: 6380/6380 Positionen liegen innerhalb `1e-4`, Maximum
`4.383790944885713e-05`, Mittel `1.172038921678528e-05`. Animation 0 schließt
bei technischer Zeit 16 exakt auf Zeit 0; Animation 43 endet bei 75 ohne
Loop. Ursache, Bytebereiche und reproduzierbarer Blenderlauf stehen in
[`rig-gltf-import-repair.md`](rig-gltf-import-repair.md).

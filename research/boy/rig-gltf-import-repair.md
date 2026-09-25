# Boy-Rig-glTF: Blender-5.0-Importreparatur

> **HISTORICAL VALIDATION ARTIFACT:** Accessor- und Blender-Importbefunde
> bleiben gültig. Die damaligen numerischen Posen und die technische
> 1:1-Samplezeit stammen aus dem Vorgängerexport; aktuelle Forge-Exporte
> verwenden die korrigierte A/C/B-Abbildung und den gemeinsamen Timingkontext.

Datum: 2026-09-23. Gegenstand ist ausschließlich der technische glTF-Export
für Prop 220 mit Animation 0 und 43. Die Reparatur ändert keine JFG-
Modell-, Rig- oder Animationssemantik.

## Ursache des Importfehlers

Im fehlerhaften Artefakt verwies Skin-Accessor 73 auf BufferView 73:

| Wert | fehlerhaftes Artefakt |
| --- | ---: |
| BufferView-Start | `65688` |
| BufferView-Länge | `1260` Byte |
| Accessor | `FLOAT`, `MAT4`, Count `21` |
| erforderliche Länge | `21 * 16 * 4 = 1344` Byte |
| erforderliches Ende | `67032` |
| tatsächliches View-Ende | `66948` |
| Fehlbetrag | `84` Byte |

Der Writer schrieb pro Identitätsmatrix nur 15 Floatwerte. Blender forderte
entsprechend der Accessordeklaration 16 Werte pro `MAT4` an und brach mit
`ValueError: buffer is smaller than requested size` ab.

Die alte Validierung prüfte nur, ob jeder vollständige BufferView innerhalb
der `.bin`-Datei lag. Diese Bedingung war erfüllt. Sie prüfte nicht, ob der
vom Accessor deklarierte Bereich innerhalb seines BufferViews lesbar war.

## Minimale Reparatur

Der Identitätsmatrix-Tupel besitzt jetzt exakt 16 Floatwerte. Die
Inverse-Binddaten umfassen dadurch exakt 1344 Byte. Die Matrizen bleiben
Identität und ihre bisher dokumentierte Rolle als **TECHNICAL
REPRESENTATION** bleibt unverändert.

Zusätzlich validiert `validate_gltf_binary_layout` für jeden Accessor:

- Componenttyp und Elementtyp,
- Count und Accessor-/BufferView-Offsets,
- Elementgröße und optionalen Byte-Stride,
- Komponenten- und Bufferalignment,
- den tatsächlich benötigten letzten Byteoffset,
- die Grenze des BufferViews und der gesamten Binärdatei.

Ein Regressionstest bildet den alten 1260-Byte-BufferView nach und verlangt
einen Abbruch vor dem Schreiben.

## Reale Blender-5.0-Gegenprüfung

Das korrigierte Artefakt wurde mit Blender 5.0.1 im Hintergrundmodus über
Blenders glTF-Importer geladen. Das reproduzierbare Skript
`tools/blender_validate_boy_rig.py` prüft die importierte und durch den
Armature-Modifier ausgewertete Geometrie gegen den bestätigten JFG-Pfad.

- relevantes Mesh: 1506 Corner-Vertices, zurückgeführt auf 638 aktive
  Quellvertices;
- Armature: 21 Joints mit den Namen `jfg_node_00` bis `jfg_node_20` und der
  erwarteten Hierarchie;
- Actions: `boy_anim_00_id_1026` und `boy_anim_43_id_1069`;
- Blender-Zeitabbildung: 24 Blender-Frames pro technischer JFG-
  Samplezeiteinheit;
- zehn Prüfzeiten, 6380 Positionsvergleiche;
- Maximum `4.383790944885713e-05`, Mittel
  `1.172038921678528e-05`, 6380/6380 innerhalb `1e-4` und `1e-3`;
- 14 referenzierte RGBA16-Bilder wurden gefunden;
- Animation 0: Zeit 0 und gebackener Abschluss 16 sind identisch;
- Animation 43: Endpunkt 75 unterscheidet sich klar von Zeit 0 und besitzt
  keinen Cycle-Modifier.

Blender legt außerdem eine 42-Vertex-`Icosphere` als Armature-Custom-Shape an.
Sie gehört nicht zum Boy-Render-Mesh und wird vom Positionsvergleich
ausgeschlossen. Der Report führt das vollständige Szeneninventar auf.

Der maschinenlesbare Befund steht in
`data/generated/boy-rig-validation/blender-validation-report.json`. Die dort
gespeicherte `.blend`-Datei ist ein Prüfartefakt des erfolgreichen Imports.

## glTF-UV-Exportgrenze

Das rendererneutrale Boy-Mesh behält die bestätigte JFG-/OBJ-/Forge-Konvention
`u=s/(32*W)`, `v_forge=1-t/(32*H)`. glTF 2.0 definiert `(0,0)` dagegen an der
oberen linken Ecke des Bildes. Der glTF-Writer konvertiert deshalb einmalig:

```text
u_gltf = u_forge
v_gltf = 1 - v_forge = t/(32*H)
```

PNG-Pixel und RenderMesh-Werte bleiben unverändert. Drei geprüfte Boy-Corners
aus Texturindex 1 zeigen die Transformation einschließlich nicht begrenzter U:

| Raw S/T | Forge-UV | glTF `TEXCOORD_0` |
| --- | --- | --- |
| `(907, 337)` | `(3.542969, 0.341797)` | `(3.542969, 0.658203)` |
| `(877, 0)` | `(3.425781, 1.000000)` | `(3.425781, 0.000000)` |
| `(898, 337)` | `(3.507812, 0.341797)` | `(3.507812, 0.658203)` |

Ein Regressionstest liest alle 1.434 texturierten Corner-UVs aus dem erzeugten
glTF-Binärbuffer zurück. Er verlangt `u_gltf=u_forge` sowie
`v_gltf=1-v_forge` und schützt damit ausdrücklich gegen einen doppelten Flip.

Forge-glTF-Exporte setzen außerdem `magFilter=9729` und `minFilter=9729`
(`LINEAR`). Die verifizierten PNG-Pixel bleiben unverändert; Clamp, Wrap und
Mirror stammen weiterhin aus dem bestätigten JFG-Tile-State.

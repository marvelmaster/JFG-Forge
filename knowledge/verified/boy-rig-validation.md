# Prop 220 Boy: begrenzte Rig-Repräsentation

Status: **VERIFIED** für das technische glTF-Validierungsartefakt mit Boy
Animation 0 und 43.

> **HISTORICAL / PARTIALLY SUPERSEDED:** Struktur-, Skin-Accessor- und
> Blender-Importbefunde dieses Artefakts bleiben gültig. Seine damaligen
> numerischen Posevergleiche entstanden vor der runtimebestätigten
> A/C/B-Komponentenkorrektur und sind keine aktuellen Forge-Referenzwerte.

- 21 Joints bilden die bestätigte Parenthierarchie ab.
- Jeder aktive Quellvertex ist genau einer Matrix-ID zugeordnet; glTF-Gewicht
  ist exakt 1.0 für diesen Joint.
- Identitäts-Inverse-Bindmatrizen machen die glTF-Skinmatrix direkt zur
  animierten JFG-Worldmatrix.
- Diese Identitätsreferenz ist eine **TECHNICAL REPRESENTATION**, keine
  behauptete JFG-Bindpose, Restpose oder T-Pose.
- Animation 0 und 43 sind getrennte Clips.
- Sämtliche 10-Bit-Zustandsübergänge sind als STEP-Keyframes gebacken; glTF-
  Quaternioninterpolation ersetzt nicht den JFG-Pfad.
- Alle 6380 Vertexvergleiche an den zehn bestätigten Zeitpunkten liegen
  innerhalb `1e-4`; maximale Abweichung `2.6963510e-5`.
- Das korrigierte Artefakt wurde zusätzlich mit Blender 5.0.1 importiert und
  als ausgewertetes Mesh geprüft: 6380/6380 Positionen innerhalb `1e-4`,
  Maximum `4.383790944885713e-05`.
- Der Skin-Accessor enthält 21 vollständig lesbare `FLOAT/MAT4`-
  Inverse-Bindmatrizen mit insgesamt 1344 Byte. Alle Accessors werden gegen
  ihre BufferView- und Binärdateigrenzen geprüft.

Die vollständigen Node-Metadaten, Fehlerwerte pro Matrix-ID und technischen
Grenzen stehen in `research/boy/rig-animation-validation.md` sowie im
generierten JSON-Reports. Die Reparatur des ursprünglichen unvollständigen
Inverse-Bind-BufferViews ist in
`research/boy/rig-gltf-import-repair.md` dokumentiert.

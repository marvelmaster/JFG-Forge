# Boy/Juno research index

> **Canonical current status:**
> [`../../knowledge/verified/boy-juno-milestone-1.md`](../../knowledge/verified/boy-juno-milestone-1.md)
> is the Boy/Juno Character Milestone 1 baseline. The files in this directory
> preserve detailed evidence and research history. Where an older report
> conflicts with that baseline, the canonical document and explicit
> `SUPERSEDED` notices take precedence.

# Boy: einzelfallgebundener Untersuchungslog

## Umfang

Untersucht wurde ausschließlich `Boy`, Prop 220 der US-ROM, mit dem
SHA-256 `2cd9e008852355d8191cf11e383de833b7ab1ea2814b3dd71583c8aa104f0baf`.
`PowerBoy` diente nur als kurzer Header-Vergleich. Die kanonischen Props,
`extracted/index.json`, alte JSONs/Skripte/Dokumente und fremde Research-Repos
wurden nur gelesen. Keine alten Outputs wurden ersetzt.

Die Befunde und Erkenntnisstatus stehen in
[`../../knowledge/likely/boy-model-structure.md`](../../knowledge/likely/boy-model-structure.md).
Die anschließende statische Codeverfolgung ist in
[`runtime-validation.md`](runtime-validation.md) mit Funktionsadressen,
Zugriffen und Statusänderungen dokumentiert.

Der gepinnte experimentelle Rohmesh-Exporter, seine Texture-ID-Kette und die
Grenzen der UV-Darstellung stehen in
[`experimental-export.md`](experimental-export.md).

Die nachgewiesene Erzeugung und Komposition der 21 Laufzeitmatrizen sowie die
entscheidende Abhängigkeit von Animation 0, Frame 0 stehen in
[`transform-matrix-validation.md`](transform-matrix-validation.md). Da ohne
Animationsdekodierung keine echte Grundpose entsteht, wurde in diesem Schritt
kein transformiertes OBJ erzeugt.

Die anschließend ausschließlich für Animation 0, Frame 0 rekonstruierte
Assetkette, Bitstromdekodierung, Matrixmenge und der separate Poseexport stehen
in [`animation0-frame0-validation.md`](animation0-frame0-validation.md).

Die zeitliche Validierung derselben Animation über Samples `0`, `1`, `8`,
`15` und den exakten Halbzeitpunkt `7.5`, einschließlich Loop- und
Interpolationspfad, steht in
[`animation0-temporal-validation.md`](animation0-temporal-validation.md).

Der strukturelle Katalog aller 52 Boy-Animationseinträge und die vollständige
zweite Validierung von Index 43 / ID 1069 stehen in
[`animation-catalog-and-anim43-validation.md`](animation-catalog-and-anim43-validation.md).

Das begrenzte glTF-Rig mit technischer Identitäts-Bindrepräsentation,
Animation 0 und 43 sowie der numerischen Vertexgegenprüfung steht in
[`rig-animation-validation.md`](rig-animation-validation.md).

Die Reparatur des dabei durch Blender 5.0 entdeckten unvollständigen
Inverse-Bind-Accessors und die echte Blender-Auswertung stehen in
[`rig-gltf-import-repair.md`](rig-gltf-import-repair.md).

Die tatsächliche Runtime-Auswahl und variable VI-Tick-Zeitsteuerung von
Animation 0 / ID 1026, der Übergangsblend, die Boy-spezifischen
Player-Overrides beider Armketten sowie der belegte Aufruferkontext von
Animation 43 / ID 1069 stehen in
[`animation-runtime-usage.md`](animation-runtime-usage.md).

Die vollständige Selectorlisten-Struktur, die exakte additive Node-3-Formel,
die Node-6-/Node-9-Scale-Pfade und die verbleibende Grenze einer statischen
Normalpose stehen in
[`runtime-override-validation.md`](runtime-override-validation.md).

Der darauf aufbauende, emulatorunabhängige Capturepunkt, die dynamische
Player-/Raceradressierung, der persistente 21-Matrix-Double-Buffer und der
Offline-Importer stehen in
[`runtime-capture-workflow.md`](runtime-capture-workflow.md). Dieser Schritt
definiert den realen Versuch, erzeugt aber ausdrücklich keine angenommene
Gameplaypose.

Die datengetriebene Diagnose der im Poseexport fehlenden Hand, einschließlich
aller `0x400`-Gruppen und der Waffenlauf-Referenzkette, steht in
[`missing-hand-validation.md`](missing-hand-validation.md).

Die anschließende ROM-Tabellenverfolgung des separaten Objekts steht in
[`hand-object-runtime-link.md`](hand-object-runtime-link.md). Sie widerlegt die
konkrete Zuordnung `0xF7 / 0x59 -> Prop 309`: Dieser Pfad lädt Prop 343
`Cluster` und kopiert wiederholt die Waffenlaufposition in das Objekt.

Der später bestätigte normale Hand-/Waffenpfad läuft stattdessen über das
BoyGun-Child, Objektdefinition 399. Die neun Slots Props 301–309, Prop 301 als
bewaffnetes 67-Face-Hand-und-Pistolenmodell, Prop 309 als Hand-/Fallback-Slot
und Matrix 6 als Attachment-Socket sind in
[`../../knowledge/verified/boy-gun-attachment.md`](../../knowledge/verified/boy-gun-attachment.md)
dokumentiert. Die zwei zusätzlichen Handkopien des unbewaffneten
`boy-test-002` bleiben hinsichtlich ihrer konkreten Runtime-Ownership UNKNOWN.

## Reproduzierbarer Einzeltest

Vom äußeren Arbeitsverzeichnis aus:

```powershell
python -B jfg-re/tools/inspect_boy_static.py `
  --boy jfg-re/data/generated/props-us-verified/bins/0220_Boy.bin `
  --output-name boy-study-neu
```

`--output-name` muss ein **noch nicht existierendes** Verzeichnis unter
`jfg-re/data/generated/` bezeichnen; das Skript überschreibt nichts. Es
akzeptiert nur die exakt gepinnte Boy-Datei. Für den vorliegenden Lauf wurde
`boy-study` benutzt.

Der Prüfbericht
[`../../data/generated/boy-study/boy-structure-evidence.json`](../../data/generated/boy-study/boy-structure-evidence.json)
enthält die mechanisch geprüften Beziehungen: 83 Gruppenrecords einschließlich
Endrecord, 520 Dreiecksrecords, 660 Vertexkandidaten, 0 lokale Indexfehler,
15 entartete Kandidatendreiecke und 505 exportierte Flächen. Das
[`../../data/generated/boy-study/boy-static-hypothesis.obj`](../../data/generated/boy-study/boy-static-hypothesis.obj)
ist ein **HYPOTHESIS**-Validierungsartefakt, kein allgemeiner Modell-Export.

## Methodische Grenze

Exakte Abschnittslängen, zusammenpassende Startwerte und kohärente
Dreiecksindizes stützen das kompakte Geometriemodell stark. Ohne einen
nachgewiesenen Loader-Zugriff kann das statische Layout dennoch anders
interpretiert oder bei der Laufzeitdarstellung zusätzlich transformiert
werden. Insbesondere wurden keine Display-List-Pointerkette, Texturzuordnung,
Materialbefehle, Bind Pose oder Skinning-Gewichte nachgewiesen.

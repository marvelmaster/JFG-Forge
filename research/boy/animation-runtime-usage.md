# Runtime-Verwendung von Boy-Animation 0 / ID 1026

Status: gezielte statische Validierung der gepinnten US-Z64-ROM. Animation 43
/ ID 1069 wurde nur bis zu ihrem konkreten Aufrufer- und Playerkontext verfolgt.
Der numerisch validierte Animationsdecoder und die vorhandenen glTF-Dateien
wurden nicht verändert.

## 1. Auswahl von Index 0 / ID 1026

Der zentrale Boy-Zustandspfad liegt in Overlay 16 bei `0x01005120`. Er liest
den aktuellen Animationsindex aus Objektbyte `+0x3B`, berechnet aus den beiden
Playerwerten `f32 +0x04` und `f32 +0x10`

```text
movement_metric = max(abs(racer+0x04), abs(racer+0x10))
```

und verzweigt über eine 51-Eintrag-Sprungtabelle. Für den Zustand mit Index 0
multiplizieren `0x010051D8..0x010051E8` den tabellierten Faktor `0.015` mit
dieser Bewegungsgröße.

Index 0 bleibt im untersuchten Pfad erhalten, wenn die Bewegungsgröße
mindestens `0.1` und höchstens `1.75` ist, `abs(+0x04) >= abs(+0x10)` gilt und
kein vorrangiger Controlzustand einen Wechsel verlangt. Belegte Übergänge zu
Index 0 existieren außerdem aus:

- Index 1 bei `0x01005364`, wenn dessen Bewegungsgrenze `0.25` unterschritten
  wird;
- Index 3/26 bei `0x01005500` unter den dort geprüften Richtungs- und
  Controlbedingungen;
- Index 9/10/31/32/47/48 bei `0x0100569C`, wenn die passende Richtung vorliegt
  und `abs(racer+0x04) < 1.75` ist;
- Index 21/46 über einen Rückgabewert `0` von `boyCanFire`.

Belegte Ausgänge aus Index 0 sind Index 3 bei gesetztem Byte `racer+0x569`,
Index 16 bis 19 unterhalb der Bewegungsgrenze `0.1`, Index 9 oder 10 bei
dominanter Komponente `+0x10` sowie Index 1 oberhalb `1.75`.

`controlPlayerInit` wählt in den normalen untersuchten Boy-Untertypen zunächst
Index 16 oder 9. Index 0 ist damit kein nachgewiesener universeller
Initialzustand. Eine semantische Bezeichnung für ID 1026 bleibt **UNKNOWN**.
Die Blenderbeobachtung ist kein Namensbeleg.

## 2. Herkunft und Bedeutung der Zeitparameter

`viFrameSync` (`0x80054FBC`) beginnt mit einem Zählerwert 1 und erhöht ihn für
weitere wartende VI-Nachrichten bei `0x80055040`. Der Rückgabewert wird bei
`0x800457CC` in `delayDat` (`0x800A3374`) gespeichert. Der Debugpfad ersetzt
ihn durch 2; Werte ab 7 werden auf 6 begrenzt.

Der normale Aufruf lädt `delayDat` bei `0x80045288`. Derselbe Integerwert wird
über `objObjectsTick` (`0x80008FF0`) und `controlPlayer` an `boyControl`
weitergereicht. Boy konvertiert ihn zu `f32` und gibt ihn als viertes Argument
an `0x01005120`. Bei `0x01005B58` wird er unverändert als `caller_delta` für
`objAnimDframe` geladen.

Für den Zustand Index 0 gilt daher:

```text
caller_delta = delayDat                   # verstrichene VI-Ticks
caller_scale = 0.015 * movement_metric
delta_phase = delayDat * 0.015 * movement_metric
delta_sample_time = 16 * delta_phase
```

`objAnimDframe` multipliziert die beiden Werte bei `0x80011398`, addiert das
Ergebnis auf die normierte Objektphase und wickelt die loopende Animation in
`[0,1)`. `modGenAnimMatrices` bildet diese Phase anschließend auf die 16
Samples ab.

Damit ist die Geschwindigkeit **VERIFIED variabel** und von der Bewegung
abhängig. Es wurde keine PAL-/NTSC-Kompensation in dieser Kette gefunden. Die
US-ROM benutzt den NTSC-VI-Pfad; Sekunden hängen deshalb von der tatsächlichen
Videokadenz ab.

Ein konkret aus dem Code berechenbarer Fall ist `movement_metric = 1.0` und
`delayDat = 1`:

| Größe | Wert |
| --- | ---: |
| Phasenschritt pro Update | 0.015 |
| Sampleschritt pro Update | 0.24 |
| VI-Ticks pro Sample | 4.1666667 |
| VI-Ticks pro 16-Sample-Zyklus | 66.6666667 |
| Dauer bei nominal 60 Hz | 1.1111111 s |

Die Tickwerte folgen aus dem tatsächlichen Code. Die Sekundenangabe ist die
ausdrücklich als nominal gekennzeichnete Division durch 60 Hz, keine
geschätzte oder gemessene Spiel-FPS. Derselbe unveränderte Pfad ergäbe bei
nominal 50 Hz rechnerisch 1.3333333 s; dies ist nicht der normale Pfad der
gepinnten US-ROM.

## 3. Übergangsblend

`modGenAnimMatrices` liest das Low-Nibble von Animationsheaderbyte 1 bei
`0x8003D558..0x8003D568`. Bei einem Wert ungleich null setzt es:

```text
instance+0x5E = 1023
instance+0x5C = floor(1023 / header_low_nibble)
```

und stellt aktuellen und vorherigen Animationszustand für `gen_anim_data`
bereit. Sowohl Animation 0 als auch 43 besitzen das Low-Nibble `4`.

`gen_anim_data` liest den Zähler über den übergebenen Instanzzeiger bei
`+0x3E`, also effektiv `instance+0x5E`, und bildet

```text
w = blend_counter / 1024
output = current + (previous - current) * w
```

Der Zähler wird, soweit der objekt-/playerspezifische Guard dies zulässt, pro
Matrixlauf um `instance+0x5C` vermindert und bei null beendet. Winkel werden
mit dem tatsächlichen Wrap-/Signed-Delta, Multiplikation durch den
Ganzzahlzähler und `>>10` interpoliert. Root-X/Y/Z werden komponentenweise mit
demselben Gewicht gemischt, bevor die Q10-Werte in Modellkoordinaten überführt
werden. Optionale Skalen liegen ebenfalls im Zwei-Zustands-Pfad.

Animation 1026 wird daher bei einem Zustandswechsel zunächst mit dem vorherigen
Clip geblendet und danach allein dekodiert. Ein isolierter Blenderclip bildet
diesen Übergang nicht ab.

## 4. Player-Overrides und die Armketten

`controlPlayerTiltList` (`0x8003B4D8`) liefert für Playerobjekte den Pointer
`racer+0x240`. Boy baut diese Selector-/Werteliste vor dem Aufruf von
`modGenAnimMatrices` bei Overlayadresse `0x0100167C` auf. `gen_anim_data`
verarbeitet die Liste während der lokalen Animationsdekodierung.

Belegte Winkelselektoren sind:

| Selector | Kanal/Node | Achse |
| --- | ---: | ---: |
| `0x0008` | 1 | 2 |
| `0x0014` | 3 | 2 |
| `0x0006` | 1 | 0 |
| `0x003C` | 10 | 0 |
| `0x0044` | 11 | 2 |

Zusätzlich kann ein Pfad bei `0x01001128` die Skalenselektoren
`0x4024/0x4026/0x4028` für Kanal 6 X/Y/Z anhängen. Ein weiterer dynamischer
Block kann Skalenselektoren für die Kanäle `0, 6, 9, 10, 14, 18` erzeugen.

Für die beiden untersuchten Armketten folgt daraus:

- `3→4→5→6`: Node 3 erhält eine direkte lokale Winkeländerung, die sich auf
  die ganze Kette fortpflanzt; Node 6 kann zusätzlich skaliert werden. Für 4
  und 5 wurde kein direkter Boy-Selector gefunden.
- `3→7→8→9`: auch diese Kette erbt die Winkeländerung von Node 3; Node 9 kann
  durch den dynamischen Block skaliert werden. Für 7 und 8 wurde kein direkter
  Boy-Selector gefunden.

Nach `modGenAnimMatrices` folgen im untersuchten Boy-Pfad `objMakeGunMtx` und
Renderhilfen. Es gibt dort weder einen zweiten Aufruf der Animationsgenerierung
noch Writes in die Skelettmatrixslots. `objMakeGunMtx` konsumiert die erzeugten
Matrizen für Waffen-/Anhangtransforms, ersetzt die Armhierarchie aber nicht.

Ein separater Upper-Body-Clip oder ein post-generation IK-Durchlauf wurde im
untersuchten Pfad nicht gefunden. Die konkret belegten Zusatzmechanismen sind
der Übergangsblend und die lokale Aim-/Movement-/Weapon-Override-Liste.

## 5. Runtime-Kontext von Index 43 / ID 1069

`controlPlayerOpenChest` (`0x8003B6C8`) dispatcht nach Player-Subtypebyte
`+1`. Die Werte 1 und 5 erreichen `0x8003B710` und rufen

```text
objAnimSetMove(object, 43, 0)
```

auf. `controlPlayerOpeningChest` (`0x8003B740`) prüft für dieselben Subtypen,
ob Objektbyte `+0x3B` weiterhin 43 ist, und teilt die normierte Phase anhand
der Grenzen `0.15` und `0.53` in drei Rückgabebereiche. Der Gameplaykontext
**Truhe öffnen** ist damit durch Funktionssymbol, Dispatch und Datenfluss
VERIFIED. Daraus wird kein eigenständiger Clipname abgeleitet.

Animation 43 ist nicht loopend und verwendet im untersuchten Zustand den
tabellierten Basisfaktor `0.003`. Wenn der spezielle Zustandswert
`racer+0x1FA` erlischt, kann der Boy-Zweig über `boyCanFire` in einen anderen
Playerzustand wechseln; weitere Ausgänge hängen von Phase und Controlwerten
des Zweigs ab.

## 6. Roottranslation

`gen_anim_data` dekodiert und blendet die Roottranslation. Sie wird nach der
Q10-Konvertierung auf die Modellrootmatrix angewandt, bevor die Hierarchie
komponiert wird. Für Animation 43 ist der validierte Endwert
`(-26,-2,78)` Modellkoordinaten.

In `objAnimDframe`, `controlPlayerOpeningChest` und dem untersuchten
Boy-Zustand-43-Pfad existiert kein Datenfluss, der diese dekodierten Werte auf
die Weltposition des Objekts zurückschreibt oder kompensiert. Für diesen Pfad
ist daher eine Trennung zwischen visueller, modelllokaler Rootbewegung und der
anderweitig gesteuerten Gameplayposition VERIFIED. Dies wird nicht pauschal
auf fremde Objektsysteme übertragen.

## 7. Konsequenz für den Blenderbefund

Die bestehenden glTF-Actions reproduzieren weiterhin korrekt den bestätigten
Basisdecoder. Sie stellen keinen vollständigen Runtime-Playerframe dar, weil
folgende Laufzeitdaten fehlen:

- vorheriger Clip und aktueller Blendzähler beim Übergang;
- die konkreten Werte der `racer+0x240`-Override-Liste;
- Objekt-/Welttransform und bei Animation 43 der Truhenkontext.

Die auffällige Armhaltung beweist daher keinen Decoderfehler. Eine manuelle
Korrektur wäre nicht gerechtfertigt. Ebenso ist die technische glTF-Zeit eine
Samplezeit und keine Sekundenskala.

## Kleinster nächster Versuch

Einen einzigen deterministischen normalen Playerframe mit aktivem Index 0
aufzeichnen: `racer+4`, `racer+0x10`, `delayDat`, normierte Phase,
vorherigen/aktuellen Index, `instance+0x5E` und die vollständige
`racer+0x240`-Liste. Diese Werte können anschließend ohne Decoderänderung in
einem kleinen numerischen Replay gegen die Laufzeitmatrizen geprüft werden.

## Nachfolgende Eingrenzung

Die anschließende vollständige Verfolgung der Override-Liste steht in
[`runtime-override-validation.md`](runtime-override-validation.md). Sie
bestätigt die additive Node-3-Formel, die Scale-Pfade und reduziert die für
den gesetzten No-Blend-/No-Deformation-/No-Trigger-Fall offenen Rohwerte auf
`racer+0x580` sowie Bit `0x40` des Worts `racer+0x540`. Das Ergebnis ist
**B. RUNTIME CAPTURE REQUIRED**; ein angenommener Neutralwert wurde nicht
exportiert.

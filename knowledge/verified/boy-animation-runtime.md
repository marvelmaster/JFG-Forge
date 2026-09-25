# Boy-Animationslaufzeit

Status: **VERIFIED** für Prop 220 in der gepinnten US-Z64-ROM und die hier
genannten Codepfade.

- Animationindex 0 entspricht ID 1026, ist loopend und besitzt 16 Samples.
  Eine semantische Bezeichnung bleibt **UNKNOWN**.
- Der Zustandspfad bei Overlayadresse `0x01005120` steuert Index 0 anhand der
  Playerbewegungswerte `f32 +4/+0x10` und weiterer Controlbedingungen.
- Für Index 0 gilt
  `delta_phase = delayDat * 0.015 * max(abs(+4),abs(+0x10))`.
  `delayDat` zählt verstrichene VI-Ticks. Die Wiedergabegeschwindigkeit ist
  damit variabel und bewegungsabhängig.
- Bei Bewegungsgröße 1 und einem VI-Tick pro Update benötigt der vollständige
  Zyklus 66.6667 VI-Ticks, nominal bei 60 Hz 1.1111 Sekunden.
- Die vollständige 52-Einträge-Zustandstabelle wurde bis zum gemeinsamen
  `objAnimDframe`-Aufruf verfolgt. 31 Einträge verwenden einen festen
  Phasenfaktor, 20 multiplizieren ihren Faktor mit einem der zwei belegten
  Bewegungsmaße, und Index 13 verdoppelt seinen Faktor bei gesetztem Bit
  `0x10` eines geprüften Laufzeitflags. Damit ist die Timingformel für alle 52
  Boy-Indices VERIFIED; die semantische Bedeutung dieses Flags bleibt UNKNOWN.
- Beide untersuchten Animationen besitzen Header-Low-Nibble 4. Der generische
  Übergangspfad blendet den vorherigen in den aktuellen Zustand mit
  `w=(instance+0x5E)/1024` und
  `current + (previous-current)*w`.
- Boy liefert `gen_anim_data` zusätzlich eine Player-Override-Liste an
  `racer+0x240`. Node 3 erhält eine belegte lokale Winkeländerung; dadurch
  ändern sich beide Armketten. Nodes 6 und 9 können zusätzliche
  Skalierungsänderungen erhalten.
- Im untersuchten Boy-Renderpfad werden die Skelettmatrizen nach
  `modGenAnimMatrices` nicht nochmals erzeugt oder überschrieben.
- `controlPlayerOpenChest` wählt für Player-Subtypen 1 und 5 ausdrücklich
  Animationindex 43 / ID 1069. Die Animation ist nicht loopend. Dies bestätigt
  den Aufruferkontext, begründet aber keinen erfundenen Clipnamen.
- Die dekodierte Roottranslation bleibt im untersuchten Playerpfad
  modelllokal. Ein Rückschreiben auf die Gameplay-Weltposition wurde nicht
  gefunden.
- Die validierten Blenderclips stellen die Basisanimation dar. Ohne aktuelle
  Blend-, Override- und Objektkontextwerte bilden sie keinen vollständigen
  Runtime-Playerframe.
- Der reale Capture von Index 19 / ID 1022 bestätigt die gespeicherte
  Komponentenfolge A/C/B, die Übergabe
  `[stored[0], stored[2], stored[1]]`, den 4x3-Inhalt der `0x40`-Byte-
  Matrixslots und 21/21 Matrizen bei maximal
  `7.62939453125e-06` Absolutfehler.
- Kontinuierliche Samplezeit wird zentral in
  `(current_sample,next_sample,fraction10)` kanonisiert. Ein gerundetes
  `fraction10=1024` trägt auf das nächste Sample über; gültig bleiben strikt
  nur `0..1023`.

Details, Adressen und Grenzen stehen in
[`../../research/boy/animation-runtime-usage.md`](../../research/boy/animation-runtime-usage.md).

Der vollständige Timingkatalog, alle Zustandsadressen und die nominalen
60-VI/s-Raten stehen in
[`../../research/boy/boy-animation-runtime-timing.md`](../../research/boy/boy-animation-runtime-timing.md).

Die danach vollständig verfolgte Listenstruktur und die exakten
Boy-Overrideformeln stehen in
[`boy-runtime-overrides.md`](boy-runtime-overrides.md). Für einen beliebigen
gewöhnlichen Index-0-Frame bleiben der verlaufsabhängige Wert
`racer+0x580` und das Node-6-Gate in `racer+0x540` laufzeitabhängig.

Der kanonische Gesamtstatus einschließlich Capture, Timing und
Interpolationsgrenze steht in
[`boy-juno-milestone-1.md`](boy-juno-milestone-1.md).

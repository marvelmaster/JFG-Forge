# Boy / Prop 220: Runtime-Pose-Pipeline

Status: gezielte Konsolidierung und Ergänzung der bereits gegen die gepinnte
US-Z64-ROM geprüften Animations-, Override- und Matrixbefunde. Die beobachteten
Forge-Posen wurden nicht als semantische Evidenz verwendet. JFG Forge und der
Animationsdecoder wurden nicht verändert.

## Ergebnis

Die von Forge angezeigte Pose ist eine korrekte **isolierte Basispose** des
gewählten Clips mit Identitäts-Objektmatrix. Der normale Boy-Runtimepfad kann
zusätzlich folgende Daten einbringen:

1. den vorherigen Clip samt Übergangsblend;
2. die zur Laufzeit aufgebaute Selector-Liste bei `racer+0x240`;
3. die Objekt-/Weltmatrix des Players.

Damit ist es erwartet, dass ein isolierter Clip von einem vollständigen
Gameplayframe abweichen kann. Für die beobachteten Indizes 3, 32 und 35 ist
jedoch nicht bewiesen, dass diese Zusatzdaten eine bestimmte auffällige Pose
kompensieren.

## Geordnete Runtime-Pipeline

| Reihenfolge | Stufe | Befund | Status |
| ---: | --- | --- | --- |
| 1 | Playerzustand wählt Animationsindex | Boy-Overlay 16 verwaltet den aktuellen Index und ruft die vorhandene Objektanimationslogik auf. Konkrete Auswahlbedingungen sind nur für einzelne Zustände belegt. | VERIFIED für den Mechanismus; UNKNOWN für nicht verfolgte Indizes |
| 2 | Animationszeit wird fortgeschrieben | `objAnimDframe` aktualisiert die normierte Phase am Spielobjekt `+0x28` und wendet Loop-/Endpunktregeln an. `modGenAnimMatrices` multipliziert diese Phase mit dem Clip-Zeitumfang in Sample-Einheiten bei Modellinstanz `+0x38` und legt die von `gen_anim_data` konsumierte effektive Zeit bei Modellinstanz `+0x28` ab. | VERIFIED durch Code und Index-19-Runtime-Capture |
| 3 | Boy baut Runtime-Selector-Liste | Der Boy-Pfad führt einen Schreibpointer ab `racer+0x240`, hängt bedingte Einträge an und schreibt `0x1000` als Terminator, bevor `modGenAnimMatrices` bei Overlayadresse `0x0100167C` aufgerufen wird. | VERIFIED |
| 4 | `modGenAnimMatrices` richtet Auswertung ein | Aktueller Animationsblob/Kanalmap, optional vorheriger Zustand, Blendzähler und der nächste Matrix-Double-Buffer werden ausgewählt. `controlPlayerTiltList` liefert den Pointer `racer+0x240`. | VERIFIED |
| 5 | Aktueller Clip: Sampledekodierung und Interpolation | Root-Q10, Winkel und optionale Scale-Daten werden für die aktuelle technische Samplezeit dekodiert. | VERIFIED |
| 6 | Selector-Liste wird auf aktuellen Scratch angewandt | Der Consumer `0x800745CC..0x800746B0` verändert dekodierte Winkel beziehungsweise Scale-Scratch. | VERIFIED |
| 7 | Vorheriger Clip bei aktivem Blend | Bei `instance+0x5E > 0` wird der Decode-Helfer ein zweites Mal für den vorherigen Zustand aufgerufen; derselbe Listpointer bleibt gültig, daher läuft der Selector-Consumer auch für diesen Scratch vor dem Blend. | VERIFIED |
| 8 | Current/Previous-Blend | Root, Winkel und optionale Scales werden mit `w=(instance+0x5E)/1024` und `current + (previous-current)*w` zusammengeführt. Winkel benutzen den bestätigten signed/wrapped Delta-Pfad. | VERIFIED |
| 9 | Lokale Matrizen | Die finalen Winkel/Scales werden mit den statischen lokalen Translationen der 21 Transformrecords zu lokalen Matrizen kombiniert. Die gespeicherten Winkelkomponenten liegen als A/C/B vor und werden dem A/B/C-Matrixhelfer als `[stored[0], stored[2], stored[1]]` zugeführt; dies reproduziert den Index-19-Capture für 21/21 Matrizen. | VERIFIED |
| 10 | Root und Hierarchie | Rootparent ist `T(blended_root_Q10/1024) * M_object`; danach gilt unter der JFG-Zeilenvektorkonvention `M_child_world=M_child_local*M_parent_world`. | VERIFIED |
| 11 | Ausgabe und Rendering | 21 aufeinanderfolgende `0x40`-Byte-Slots werden in den gewählten Instanzpuffer geschrieben. Jeder Slot enthält 12 relevante Big-Endian-`f32` als 4x3-Affinmatrix; das vierte Wort jeder Zeile ist unbenutzt. | VERIFIED durch Index-19-Runtime-Capture |
| 12 | Kamera | View/Projection folgt im Renderpfad und schreibt die 21 Boy-Matrizen nicht um. | VERIFIED |

### Beleg für die Reihenfolge von Override und Blend

In der gepinnten US-ROM ruft `gen_anim_data` den Decode-Helfer bei
`0x80073F18` für den aktuellen Zustand auf. Nach dem Blendzähler-Test folgt
bei aktivem Blend der zweite Aufruf bei `0x80073F4C`. Der Helfer erreicht vor
seiner Rückkehr den Selector-Consumer `0x800745CC..0x800746B0`. Erst danach
folgt der Current/Previous-Winkelblend, unter anderem mit den bereits
gepinnten Instruktionen bei `0x80074030/0x80074038`.

Die genaue Ordnung ist daher:

```text
decode current -> apply selectors to current
               -> [decode previous -> apply selectors to previous]
               -> blend current/previous
               -> local matrices -> hierarchy/object composition
```

Die Selector-Liste ist kein nachträglicher Matrixpatch und kein zweiter
Skeleton-Pass.

## Runtime-bestätigte Komponentenfolge im Produktionspfad

Der reale Index-19-Capture bestätigt die gespeicherte Komponentenfolge A/C/B.
Der Forge-Pfad

```text
forge_data.sample_animation
  -> boy_anim0_frame0.build_matrices
  -> _local_matrix(channel["rotation_raw_s16_abc"], ...)
```

verwendet nun gemeinsam mit Runtime-Validator und glTF-Baker den zentralen
Helfer `_local_matrix_from_stored`. Dieser führt ausschließlich die bestätigte
Zuordnung `[stored[0], stored[2], stored[1]]` aus und übergibt das Ergebnis an
`_local_matrix(A, B, C)`. Der Capture-spezifische direkte Aufruf erreichte mit
der früheren Reihenfolge einen maximalen Fehler von `18.070096015930176`; mit
der bestätigten Zuordnung sind es `7.62939453125e-06` und 21/21 Matrizen.
Timing, Interpolation, Root-Q10, Hierarchie und Objektkomposition blieben
unverändert.

## `controlPlayerTiltList` und `racer+0x240`

`controlPlayerTiltList` (`0x8003B4D8..0x8003B4E0`) gibt exakt
`object+0x68+0x240`, also `racer+0x240`, zurück. Die Funktion interpretiert
die Liste nicht selbst; `gen_anim_data` ist der Consumer.

### Eintragsformat

```text
+0  u16_be selector
+2  s16_be value
normaler Stride: 4 Byte
```

Das obere Selector-Nibble ist die Operation. Die unteren zwölf Bits sind:

```text
byte_offset = channel * 6 + component * 2
```

| Operation | Wirkung | Status |
| --- | --- | --- |
| `0x0000` | Wert additiv auf dekodierten `s16`-Winkel, mit 16-Bit-Wrap | VERIFIED |
| `0x1000` | Listenende | VERIFIED |
| `0x2000` | dekodierten Winkel ersetzen | VERIFIED |
| `0x3000` | gewichtete Addition; konsumiert ein zusätzliches `s16`-Zielfeld | VERIFIED |
| `0x4000` | Scale-Scratch ersetzen | VERIFIED |
| `0x5000` | dekodierten Winkel in den Wertslot der Liste zurückkopieren | VERIFIED |

### Belegte Boy-Producer

| Selector/Ziel | Datenquelle und Verhalten | Status |
| --- | --- | --- |
| Node 1 und 3, zweite gespeicherte Eulerkomponente | `racer+0x342` (`s8` Pulszähler) und `+0x343` (`u8` Shift) erzeugen über `mathSin` entgegengesetzte additive Werte. Der Puls klingt ohne neuen Trigger spätestens nach 15 Delta-1-Updates ab. | VERIFIED; konkrete Gameplaybedeutung des Triggers UNKNOWN |
| Node 1 und 10, erste Eulerkomponente | Entsprechender Sinuspfad aus `racer+0x340/+0x341`, additiv. | VERIFIED; konkrete Gameplaybedeutung UNKNOWN |
| Node 11, zweite Eulerkomponente, Selector `0x0044` | `racer+0x580` wird in Richtung `-Arctanf(racer+0x10,abs(racer+4))` geglättet, sofern `abs(+0x10)<abs(+4)`, sonst in Richtung null. Der aktuelle Low-`s16` wird immer additiv emittiert. | VERIFIED bewegungsrichtungsabhängig |
| Node 6, XYZ-Scale | Bit `0x40` in `u32 racer+0x540` hängt `0x4024/0x4026/0x4028` mit Rohwert 32 an; Faktor `1/1024`. | VERIFIED Mechanismus; Bedeutung und Zustand des Bits im beliebigen Frame UNKNOWN |
| Nodes `0,6,9,10,14,18`, Scale | Spezialpfad bei `deformedchars != 0` und `s8 racer+0x189 != 2`; Node 6/9 und weitere erhalten den bereits dokumentierten Deformationsfaktor. | VERIFIED Spezialpfad |

Nur der Node-11-Pfad ist aus den untersuchten Inputs eindeutig an die beiden
Bewegungskomponenten gebunden. Eine konkrete Zuordnung der übrigen Producer zu
Zielen wie Zielen, Schießen, Waffengewicht oder Ducken wurde in diesem Audit
nicht nachgewiesen. Der Symbolname `controlPlayerTiltList` allein benennt nicht
die Semantik jedes Eintrags.

## Rolle von `gen_anim_data`

`gen_anim_data` ist nicht nur ein Matrixkonverter. Es führt innerhalb eines
Aufrufs die folgenden Arbeiten aus:

- Sampledekodierung und 10-Bit-Interpolation;
- Anwendung der vollständigen Boy-Selector-Liste auf die dekodierten Scratchwerte;
- optionales Blending des bereits modifizierten aktuellen und vorherigen Zustands;
- Umwandlung der finalen Eulerwinkel und Scale-Werte in lokale Matrizen;
- Einsetzen der statischen Transformrecord-Translationen;
- Q10-Roottranslation und Komposition mit der Objektmatrix;
- Aufbau der Parent-/Child-Hierarchie und Schreiben aller 21 Ausgabematrizen.

Forge verwendet denselben bestätigten Basisdecoder und dieselbe
Hierarchieformel, liefert ihm gegenwärtig aber weder die Live-Selector-Liste
noch vorherigen Zustand/Blendzähler noch die Player-Objektmatrix.

## Modellraum und Objekt-/Weltraum

Die Ebenen sind getrennt zu behandeln:

1. **Clip/Modell lokal:** dekodierte Roottranslation und lokale
   Jointrotationen/-scales.
2. **Boy-Runtime-Modifikationen:** Selectorwerte ändern lokale Winkel/Scales
   vor dem Matrixbau. Durch die Hierarchie wirken sie auf Nachfahren.
3. **Objekt/Welt:** `M_object` wird am Root komponiert und kann den gesamten
   Charakter drehen, neigen und verschieben, ohne die relative lokale Pose zu
   ändern.
4. **Kamera:** reine spätere Darstellung.

Die in Forge bei Identitäts-Objektmatrix sichtbare starke Ganzkörperneigung
liegt bereits in der isoliert dekodierten Skelettpose. Sie stammt dort nicht
aus Skinning oder Kamera. Im Spiel kann `M_object` diese Orientierung weiter
drehen oder in einen passenden Weltkontext setzen; eine konkrete Kompensation
für die beobachteten Clips ist ohne Runtimeframe nicht belegt. Ebenso können
Selectorwerte einzelne lokale Ketten verändern, sind aber kein nachgewiesener
allgemeiner Gegentilt für diese Clips.

## Zielclips 3, 32 und 35

| Index / ID | Statisch belegter Runtimekontext | Semantik |
| --- | --- | --- |
| `3 / 1025` | Index 0 wählt Index 3, wenn `racer+0x569 != 0`. Der gemeinsame Zustandszweig 3/26 kann bei passenden Richtungs-/Controlbedingungen bei `0x01005500` zu Index 0 zurückkehren. | Bedeutung von `racer+0x569` und Cliprolle UNKNOWN; visuelle Tilt-/Crouchdeutung ist HYPOTHESIS |
| `32 / 1059` | Ein bereits aktiver Zustand 32 liegt in der Gruppe 9/10/31/32/47/48, die bei passender Richtung und `abs(racer+4)<1.75` bei `0x0100569C` zu Index 0 wechseln kann. Ein Auswahlpfad **zu** Index 32 wurde im vorhandenen begrenzten Audit nicht belegt. | UNKNOWN; visuelle Seitwärts-/Crouchdeutung ist HYPOTHESIS |
| `35 / 1062` | In den gezielt geprüften Boy-Berichten, Symbolen und Auswahlpfaden wurde keine Referenz auf Index 35 gefunden. | UNKNOWN; visuelle Seitwärts-/Crouchdeutung ist HYPOTHESIS |

Das vorhandene Symbol `controlWalkingBack` wurde nicht mit einem dieser drei
Indizes verbunden. Die getrennten `duckshoot*`-Symbole gehören zu einem
anderen Overlay und liefern keinen Boy-Clipbeleg. Damit wurde weder eine
Strafe- noch eine Crouch-Semantik VERIFIED.

## Was Forge derzeit zeigt und auslässt

### Implementiert

- gewählter aktueller Clip und technische Samplezeit;
- bestätigte Sampleinterpolation, Root-Q10 und signed Winkeldeltas;
- statische lokale Translationen;
- bestätigte lokale Matrizen und 21-Knoten-Hierarchie;
- starre Vertexzuordnung;
- Identitäts-Objektmatrix, also eine isolierte Modellraumdarstellung.

### Ausgelassen

- vorheriger Clip und Runtime-Blendzähler;
- Live-Selector-Liste `racer+0x240` einschließlich bewegungs- und
  verlaufsabhängiger Werte;
- Player-Objekt-/Weltmatrix;
- Gameplayobjekte und Kontext, welche die Pose räumlich verständlich machen
  können.

Das Weglassen ist kein nachgewiesener Decoderfehler. Forge bezeichnet diesen
Modus weiterhin zutreffend als isolierte Clip-/Basispose.

## Minimaler Runtime-Capture-Versuch

Breakpoint:

```text
N64 RAM 0x8003D908
```

Das ist die erste Instruktion in `modGenAnimMatrices` nach der Rückkehr aus
`gen_anim_data`. Alle 21 Matrizen sind dann vollständig geschrieben. Sie
enthalten jedoch bereits die Objekt-/Weltkomposition und sind daher nicht
automatisch reine Modellraummatrizen.

### Zielzustand

Für genau einen der Indizes `3`, `32` oder `35`:

- aktueller Index bei `instance+0x24` exakt der Zielindex;
- stabiler No-Blend-Frame mit `s16 instance+0x5E == 0`;
- effektive technische Samplezeit `f32 instance+0x28` und zusätzlich die
  unskalierte Samplezeit `f32 instance+0x38`;
- alle drei Zielclips besitzen 16 Samples und loopen; `instance+0x28` muss
  deshalb für einen gültigen Capture in ihrer technischen Zeitdomäne `[0,16)` liegen;
- Bildschirm-/Gameplayzustand und Pointerprovenienz notieren, ohne daraus
  einen Clipnamen abzuleiten.

### Minimal notwendige Daten

1. `instance` ab `S4`, Länge `0x80`;
2. Objektmatrix ab `SP+0x90`, Länge `0x40`;
3. Selector-Liste ab `racer+0x240` bis einschließlich erstem `0x1000`
   Terminator; ein Dump von `0x80` Byte ist der vorhandene sichere Oberbereich;
4. aktueller Matrixpuffer, 21 × `0x40 = 0x540` Byte;
5. PC, `S4`, `SP`, `object=u32_be[SP+0xF8]`,
   `racer=u32_be[SP+0x74]` und der daraus berechnete Matrixbasis-Pointer.

Für Provenienz und spätere Semantikzuordnung zusätzlich sinnvoll:

- `racer+0x04`, `racer+0x10`;
- `racer+0x540`, `racer+0x569`, `racer+0x580`;
- `delayDat` bei `0x800A3374`.

### Drei Vergleiche

1. **Forge-Basis:** Zielclip bei exakt derselben technischen Samplezeit,
   ohne Blend, Selector oder Objektmatrix.
2. **Vollständiger Runtime-Modellraum:** Basisdecoder plus erfasste
   Selector-Liste, aber mit Identitäts-Objektmatrix. Dies isoliert den Effekt
   der Boy-spezifischen Modifikationen.
3. **Exakter Runtimevergleich:** Dasselbe Replay mit der erfassten
   Objektmatrix; die 252 geschriebenen 4x3-`f32` der 21 Slots gegen den
   `0x540`-Dump prüfen. Die vier unbenutzten Wörter pro Slot bleiben außen vor.

Alternativ könnte man die Objektmatrix aus den erfassten Runtime-Matrizen
herausrechnen. Das Replay mit derselben Objektmatrix ist numerisch weniger
fehleranfällig und wird vom vorhandenen Capture-Importer bereits unterstützt.

## Verbleibende UNKNOWNs

- Originalnamen und genaue Gameplayrollen der Indizes 3, 32 und 35;
- konkreter Auswahlpfad zu Index 32 und jeder Auswahl-/Verbrauchspfad für 35;
- Bedeutung des Feldes `racer+0x569`;
- konkrete Triggersemantik der Pulse bei `racer+0x340..+0x343`;
- Bedeutung und tatsächlicher Zustand von Bit `0x40` bei `racer+0x540` im
  gewählten Frame;
- ob Objektmatrix und Selectorwerte die auffällige isolierte Pose eines der
  drei Zielclips im realen Gameplay sichtbar kompensieren;
- numerische Übereinstimmung eines echten Zielclip-Captures mit dem Offline-
  Replay.

## Quellen innerhalb des Projekts

- [animation-runtime-usage.md](animation-runtime-usage.md)
- [runtime-override-validation.md](runtime-override-validation.md)
- [runtime-capture-workflow.md](runtime-capture-workflow.md)
- [transform-matrix-validation.md](transform-matrix-validation.md)
- `src/jfg_re/boy_runtime_animation.py`
- `src/jfg_re/boy_runtime_overrides.py`
- `src/jfg_re/boy_runtime_capture.py`
- `research/Jet-Force-Gemini/src/hasm/gen_anim_data.s` als Navigationsquelle,
  mit den entscheidenden Adressen gegen die gepinnte US-ROM geprüft

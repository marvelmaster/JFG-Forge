# Boy Animation 0: Runtime-Overrides und statische Reproduzierbarkeit

Datum: 2026-09-23. Gegenstand ist ausschließlich Prop 220 `Boy`, Animation
Index 0 / ID 1026 der gepinnten US-Z64-ROM. Der verifizierte Decoder und die
vorhandenen glTF-Dateien wurden nicht verändert.

## Ergebnis

**B. RUNTIME CAPTURE REQUIRED.**

Ein vollständig bestimmter gewöhnlicher Index-0-Frame lässt sich noch nicht
allein aus statischem Code ableiten. Der immer emittierte Selector `0x0044`
enthält den verlaufsabhängigen Akkumulator `racer+0x580`. Selbst bei Zielwinkel
null ist sein Endwert nicht eindeutig: Wegen des arithmetischen `>> 4` sind
alle Werte `-15..-1` Fixpunkte. Zusätzlich hängt die Skalierung von Node 6 an
Bit `0x40` des Laufzeitworts bei `racer+0x540`.

Darum wurde kein synthetischer Pose-Export erzeugt. Nullwerte wären an diesen
beiden Stellen Annahmen.

## Evidenz und Adressen

Die Namen des externen Decomp-Projekts dienen nur zur Navigation. Alle hier
als VERIFIED markierten Aussagen wurden gegen Instruktionen der lokalen ROM
gepinnt.

| Bereich | Adresse | Befund |
| --- | --- | --- |
| Listeninitialisierung | `controlPlayerInit` `0x8003215C..0x80032164` | schreibt `u16 0x1000` nach `racer+0x240` |
| Listenpointer | `controlPlayerTiltList` `0x8003B4D8..0x8003B4E0` | gibt `object+0x68+0x240` zurück |
| Boy-Listenaufbau | Overlay 16 `0x01000020..0x010014DC` | führt einen Schreibpointer und setzt abschließend `0x1000` |
| Listenverbrauch | `gen_anim_data` `0x800745CC..0x800746B0` | dekodiert Operation, Offset und Wert |
| Pulse | Overlay 16 `0x01002220..0x0100250C` | erzeugt Selectors 1/3/10 aus `+0x340..+0x343` |
| Movement-Tilt | Overlay 16 `0x01004840..0x01004930` | glättet `+0x580` und emittiert `0x0044` |
| Node-6-Scale | Overlay 16 `0x01001114..0x010011A8` | prüft Bit `0x40` des Worts `+0x540` |
| Deformation | Overlay 16 `0x010011B4..0x010014C0` | optionale Skalen für sechs Nodes |

Die Overlay-Relocationstabelle bindet `0x010023E4/0x01002498` an `mathSin`
`0x8004966C`, `0x0100489C` an `Arctanf` `0x80049C84`, `0x010048BC` an
`mathDiffAngle` `0x80049D80` und `0x010011B4/0x010011B8` an
`deformedchars` `0x800A5084`.

## Struktur von `racer+0x240`

**VERIFIED:** Ein normaler Eintrag ist Big Endian:

```text
+0  u16 selector
+2  s16 value
```

Der normale Stride ist vier Byte. Das obere Nibble des Selectors ist die
Operation. Die unteren 12 Bits sind ein Byteoffset:

```text
offset = channel * 6 + component_index_zero_based * 2
```

Operationen im tatsächlichen Consumer:

- `0x0000`: addiert zum dekodierten Winkel; `sh` bewirkt Modulo-65536-Wrap.
- `0x1000`: beendet die Liste.
- `0x2000`: ersetzt den dekodierten Winkel.
- `0x3000`: gewichtete Addition und ein zusätzliches `s16`-Argument.
- `0x4000`: ersetzt einen Wert im separaten Scale-Scratch.
- `0x5000`: kopiert einen dekodierten Winkel in den Wertslot der Liste.

JFG verwendet für diese Winkel 65536 Einheiten pro Vollkreis. Eine Einheit
entspricht `360/65536` Grad.

## Exakte Node-3-Formel

Der Producer liest einen signed Counter `p = s8(racer+0x342)` und den
unsigned Shift `k = u8(racer+0x343)`:

```text
q = mathSin(sign_extend_s8(p) << 11) >> k

node1.component(+2) = wrap_s16(base + q)
node3.component(+2) = wrap_s16(base - q)
```

`component(+2)` ist die zweite gespeicherte Eulerkomponente, nullbasiert
Index 1, also Winkel `B` beziehungsweise der `Rz(B)`-Term der bereits
verifizierten Matrixformel. Selector `0x0014` benutzt Operation `0x0000`:
Die Änderung ist **additiv**, kein Replace und kein Blend.

Beim vom Producer gesetzten Startwert `p=15`, `k=5` liefert die ROM-Tabelle
`mathSin(0x7800)=12686`, also `q=396` und für Node 3 Delta `-396`.
Ohne neuen Trigger subtrahiert `0x01002458..0x0100247C` pro Update den
Caller-Delta und klemmt bei null. Ein vom Producer erzeugter Puls ist bei
`delta=1` nach höchstens 15 Updates sicher beendet.

Der zweite Puls bei `racer+0x340/+0x341` erzeugt denselben additiven Wert für
die erste Komponente der Channels 1 und 10:

```text
r = (mathSin(s8(racer+0x340) << 11) >> u8(racer+0x341)) >> 1
```

## Verlaufsabhängiger Node-11-Wert

Overlayfunktion `0x01004840` liest `f32 racer+0x04` und `f32 racer+0x10`.
Wenn `abs(+0x10) < abs(+0x04)`, bildet sie:

```text
target = -Arctanf(racer+0x10, abs(racer+0x04))
```

Andernfalls bleibt `target=0`. Für jeden Caller-Delta-Tick gilt:

```text
diff = mathDiffAngle(racer+0x580, target)
racer+0x580 += diff >> 4
```

Danach wird Selector `0x0044` mit dem aktuellen `racer+0x580` immer
geschrieben. Er ändert additiv die zweite Eulerkomponente von Channel 11.
Der Wert hängt von der vorherigen Bewegungsrichtung und der Updategeschichte
ab. Die Bedingung `movement_metric=1.0` bestimmt ihn deshalb nicht.

## Nodes 6 und 9

### Node 6, separater Flagpfad

`lw racer+0x540; sll 25; bgez` prüft das ursprüngliche Bit `0x40` des
Big-Endian-`u32`, also Bit 6 von Byte `racer+0x543`. Wenn gesetzt, werden
`0x4024/0x4026/0x4028` mit Wert 32 emittiert. `gen_anim_data` ersetzt damit
die drei Scale-Scratch-Werte. Der effektive Faktor ist:

```text
32 / 32768 = 1/1024
```

No-firing und No-aim belegen den Zustand dieses Bits nicht. Sein Wert für den
gewählten Runtimeframe bleibt **UNKNOWN**.

### Nodes 6 und 9, Deformationspfad

Der Pfad ist nur aktiv, wenn `deformedchars != 0` und signed
`racer+0x189 != 2`. Die ROM initialisiert `deformedchars` auf null. Für den
ausdrücklich nicht speziellen Normalfall ist der Pfad daher inaktiv; Scale
Scratch null bedeutet Faktor 1.

Wenn aktiv, enthält die ROM die Channels `[0,6,9,10,14,18]` und Faktoren
`[0.8,1.55,1.55,1.55,1.55,1.55]`. Nach der tatsächlichen positiven
Float-zu-Integer-Konvertierung entstehen `26214` und `50790`; die effektiven
Faktoren sind `0.79998779296875` und `1.54998779296875`. Node 6 und Node 9
erhalten jeweils den zweiten Wert auf allen drei Achsen.

Die separate `1/1024`-Tripel für Node 6 wird früher in die Liste geschrieben.
Wenn zugleich der Deformationspfad aktiv ist, folgt dessen Node-6-Tripel
später und ersetzt dieselben drei Scale-Scratch-Werte mit `50790`.

## Transformebenen

1. **Animation lokal:** Animation 0 liefert lokale Rotation, optionale Scale
   und modelllokale Roottranslation.
2. **Boy-Overrides:** Die Liste verändert Winkel-/Scale-Scratch vor dem Bau
   der lokalen Matrizen. Node 3 beeinflusst dadurch beide Armketten.
3. **Objekt/Welt:** Die an `modGenAnimMatrices` übergebene Objektmatrix wird
   am Root komponiert. Sie bewegt das gesamte Modell, ändert aber nicht die
   relative lokale Armhaltung.
4. **Kamera:** View/Projection folgt im Renderpfad. Dabei werden die 21
   Boy-Skelettmatrizen nicht neu geschrieben.

## Kleinste notwendige Runtime-Aufzeichnung

Für den eingegrenzten, gesetzten No-Blend-/No-Deformation-/No-Trigger-Fall
bleiben exakt zwei Rohwerte offen:

- `s32 racer+0x580`; sein Low-`s16` wird über Selector `0x0044` verbraucht.
- `u32 racer+0x540`; Bit `0x40` entscheidet über die Node-6-Scale-Selectors.

Robuster und kaum größer ist die direkte Aufzeichnung der fertigen Liste ab
`racer+0x240` bis einschließlich Selector `0x1000`, zusammen mit der
normalisierten Animationsphase. Guards des Captureframes: Index 0 / ID 1026,
`instance+0x5E==0`, `deformedchars==0`, `racer+0x340==0` und
`racer+0x342==0`. Für einen Weltvergleich kommen Objektmatrix und als
Kontrollziel die 21 Runtime-Matrizen oder transformierten Vertices hinzu.

Der maschinenlesbare Befund liegt unter
`data/generated/boy-runtime-override-validation/boy-runtime-override-validation.json`.

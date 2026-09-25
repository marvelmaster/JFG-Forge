# Prop 220 Boy: bestätigte Runtime-Overrides

Für die gepinnte US-ROM ist bestätigt:

- `controlPlayerTiltList` liefert `racer+0x240`.
- Normale Einträge bestehen aus Big-Endian `u16 selector` und `s16 value`.
- Das obere Selector-Nibble ist die Operation; die unteren 12 Bits sind
  `channel*6 + component*2` als Byteoffset.
- `0x0000` addiert Winkel mit 16-Bit-Wrap, `0x2000` ersetzt Winkel,
  `0x4000` ersetzt Scale-Scratch, `0x1000` beendet die Liste.
- Selector `0x0014` addiert
  `- (mathSin(s8(racer+0x342)<<11) >> u8(racer+0x343))` zur zweiten
  Eulerkomponente von Node 3.
- Selector `0x0044` addiert den geglätteten, verlaufsabhängigen Wert
  `racer+0x580` zur zweiten Eulerkomponente von Node 11.
- Bei gesetztem Bit `0x40` im `u32` bei `racer+0x540` erhält Node 6 Scale
  `32/32768 = 1/1024` auf X/Y/Z.
- Der `deformedchars`-Pfad skaliert die Nodes `0,6,9,10,14,18`; Node 6 und 9
  erhalten effektiv `50790/32768 = 1.54998779296875`.
- Wenn beide Node-6-Pfade aktiv sind, überschreibt das später emittierte
  Deformations-Tripel die frühere `1/1024`-Scale.

Ein beliebiger gewöhnlicher Index-0-Runtimeframe ist damit noch nicht rein
statisch numerisch bestimmt. Offen bleiben für den eng begrenzten Normalfall
`racer+0x580` und Bit `0x40` des Worts `racer+0x540`.

Instruktionsbelege und Formeln:
[`../../research/boy/runtime-override-validation.md`](../../research/boy/runtime-override-validation.md).

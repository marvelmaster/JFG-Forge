# Prop 220 Boy: bestätigte Laufzeit-Transformregeln

Gültig für die untersuchte US-ROM mit SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023` und den gepinnten Boy-Prop mit
SHA-256 `2cd9e008852355d8191cf11e383de833b7ab1ea2814b3dd71583c8aa104f0baf`.

## VERIFIED

- Ein Transformrecord ist 16 Byte groß.
- `+0` ist die Parent-Matrix-ID; `0xff` markiert den Rootparent.
- `+1` ist die Ziel-ID eines 64-Byte-Matrixslots.
- `+2` ist der Kanalindex des aktuellen Animationszustands; `+3` dient dem
  zweiten Kanal beim Blending.
- Die Big-Endian-`f32` bei `+4/+8/+12` sind lokale Translation X/Y/Z. Sie
  werden nach Matrixoffset `+0x30/+0x34/+0x38` kopiert und dort von
  `func_80048B60` addiert.
- Rotation und optionale Skalierung werden aus dem ausgewählten
  Animationskanal dekodiert. Dies gilt auch im nicht geblendeten Pfad.
- Die drei gespeicherten Winkelkomponenten entsprechen der semantischen
  Reihenfolge A/C/B für `Rx(A) * Ry(C) * Rz(B)`. Der vorhandene
  `_local_matrix(A, B, C)`-Helfer erhält sie deshalb über den gemeinsamen
  Produktionshelfer `_local_matrix_from_stored` als
  `[stored[0], stored[2], stored[1]]`. Forge, `build_matrices`, Runtime-
  Validator und der begrenzte Boy-glTF-Baker verwenden diesen Helfer. Der reale Index-19-Capture
  reproduziert damit 21/21 Matrizen bei maximal
  `7.62939453125e-06` Absolutfehler.
- `f32 instance+0x38` ist der unskalierte Clip-Zeitumfang in Sample-Einheiten,
  keine normierte Phase und kein unabhängig fortgeschriebener Cursor.
  `objAnimDframe` aktualisiert die normierte Phase am Spielobjekt `+0x28`;
  `modGenAnimMatrices` multipliziert beide und speichert die von
  `gen_anim_data` verwendete effektive Samplezeit bei Modellinstanz `+0x28`.
- Unter JFGs Zeilenvektorkonvention gilt
  `M_child_world = M_child_local * M_parent_world`.
- Ein Runtime-Matrixslot hat den Stride `0x40`, enthält aber eine 4x3-
  Affinmatrix: pro 16-Byte-Zeile drei Big-Endian-`f32` bei `+0/+4/+8`.
  Das vierte Wort jeder Zeile ist unbenutzt und kein Matrixfloat.
- Für Punkte gilt `p_out = p_local * M_world`, konkret
  `x'=x*m00+y*m10+z*m20+m30` und entsprechend für Y/Z.
- `modMakeLimbModel` wandelt die float-Ergebnisse mit Rundung gegen null in
  drei `s16` zurück.
- Die beiden Boy-Records bei Headerpointer `+0x30` sind `(Vertexindex,
  Matrix-ID)` und erzeugen separate transformierte Runtime-Referenzpunkte.
- Der erste Record `(Vertex 619, Matrix 6)` wird von `objMakeGunMtx` als
  Transform des BoyGun-Childs verwendet. Matrix 6 ist damit der bestätigte
  Attachment-Socket für das aus Props 301–309 gewählte Hand-/Waffenmodell.

## Weiterhin UNKNOWN

- Die fachliche Bezeichnung von Animation 0, Frame 0 als Bindpose, Idlepose
  oder anderer Startzustand.
- Der spätere fachliche Zweck des zweiten Referenzpunkts
  `(Vertex 624, Matrix 10)`.

Die numerische Model-Space-Pose wurde inzwischen speziell für Animation 0,
Frame 0 reproduziert und ist in `boy-animation0-frame0.md` dokumentiert. Eine
Pose aus dem Prop allein bleibt weiterhin nicht definiert.

Die Instruktions- und Formelevidenz steht in
`research/boy/transform-matrix-validation.md`.
Die bestätigte Hand- und BoyGun-Struktur steht in
`boy-gun-attachment.md`.

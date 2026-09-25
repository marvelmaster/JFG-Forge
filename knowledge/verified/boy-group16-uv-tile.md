# Boy-Gruppe 16: S/T- und Tile-Semantik

Status: **VERIFIED** für Prop 220 der bekannten US-ROM, Gruppe 16 und
TextureRecord 5 / ID `0x820D`.

- Triangle `+4..+15` gelangt als drei geordnete S/T-Paare in Vertexslot
  `+0x14` und von dort in den JFG-RSP-Texturgradientenpfad.
- Die beiden s16 sind signed S10.5: ein Texel entspricht 32 Rohwerteinheiten.
- S ist horizontal; T wählt die Texturzeile. Steigendes T folgt späteren
  Zeilen des geladenen RGBA16-Bildes.
- Das Asset ist die 16×16-RGBA16-Textur bei Runtime-ROM `0x178650` mit
  Container bei `0x178670`.
- Der Textureheader setzt CMS=CMT=`G_TX_CLAMP`; MaskS, MaskT, ShiftS und
  ShiftT sind null. Mirror ist aus.
- Für das vorhandene top-down PNG und konventionelles OBJ-/Blender-UV lautet
  die Abbildung `u=raw_s/(32*16)`, `v=1-raw_t/(32*16)`.

Die vollständige RDP-Filterung lässt sich nicht vollständig in OBJ/MTL
ausdrücken. Pixelidentische Filterresultate in einem beliebigen Importer sind
daher nicht Teil der VERIFIED-Aussage.

Der vollständige Datenfluss steht in
[`../../research/boy/group16-uv-validation.md`](../../research/boy/group16-uv-validation.md).

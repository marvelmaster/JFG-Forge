# Boy Runtime-Capture-Layout

Für Prop 220 ist der feste RAM-Breakpoint `0x8003D908` die erste Instruktion
nach `gen_anim_data` innerhalb von `modGenAnimMatrices`. Dort gilt:

- `S4` zeigt auf die gewählte Modellinstanz;
- `u32_be[SP+0xF8]` ist das Objekt;
- `u32_be[SP+0x74]` ist dessen dynamischer Racerpointer;
- `SP+0x90` enthält die tatsächlich verwendete 4×4-Objektmatrix;
- `s8[instance+0x0B]` wählt den aktuellen Double-Buffer;
- `u32_be[instance+0x10+4*buffer_index]` zeigt auf 21 konsekutive
  Big-Endian-`f32`-Matrizen à 64 Byte.

Die Playerliste ist über die RAM-Globals `0x800F2D0C` (Pointer) und
`0x800F2D10` (Anzahl) erreichbar. Der Racer liegt nicht an einer festen
Adresse; sein Pointer steht in `object+0x68`.

Für einen vollständigen No-Blend-Replay werden Index 0, normierte Phase,
Blendzähler null, die Selector-Liste ab `racer+0x240` und die Objektmatrix
benötigt. Phase plus Selector-Liste allein reproduzieren keine finalen
Weltmatrizen. Die 21 Runtime-Matrizen können am Breakpoint als `0x540` Byte
gesichert werden und bilden das direkte Validierungsziel.

Die konkrete Pose bleibt bis zu einer echten Emulatoraufzeichnung UNKNOWN.
Es wurde kein Neutralwert für offene Racerfelder angenommen.

# Prop 220 Boy: Animation 0 über die Zeit

Status: **VERIFIED** für die gepinnte US-ROM, Animation-ID `1026` und die
hier dokumentierte Laufzeitdekodierung.

- Der 544-Byte-Blob enthält 16 gespeicherte Samples `0..15` mit jeweils
  25 Byte ab Bloboffset `0x8e`.
- Blobbyte `+1 = 0x14` setzt das Loop-Flag. Die normierte Objektphase
  `[0,1)` wird für diese Animation mit 16 multipliziert; die Samplezeit liegt
  daher in `[0,16)`. Auf Sample 15 folgt beim Interpolieren Sample 0.
- Eine feste FPS ist im Blob nicht kodiert. `objAnimDframe` addiert ein vom
  Aufrufer geliefertes Delta mal einen ebenfalls gelieferten Faktor zur
  normierten Phase.
- Jeder Samplebitstrom wird MSB-first gelesen und verbraucht 193 Bits plus
  sieben Nullbits Padding.
- Die Root-Komponenten verwenden Q10:
  `(signed_base << 11) + (sample << 10) + delta * fraction10` und danach
  Division durch 1024.
- Die Fraktion entsteht als gerundeter Integer aus
  `(sample_time - floor(sample_time)) * 1024`. Falls die Rundung `1024`
  ergibt, trägt die zentrale Kanonisierung auf das nächste Sample über und
  setzt die Fraktion auf `0`; an Decoder gelangen ausschließlich Werte
  `0..1023`.
- Winkel interpolieren die gepackten Samples mit einem signed 11-Bit-Delta;
  anschließend folgen `>>10`, `<<5`, Basisaddition und `s16`-Interpretation.
- Der Test bei `t=7.5` verwendet exakt `512/1024`. Vier Winkelwerte
  überschreiten dabei die `u16/s16`-Darstellungsgrenze, bleiben über den
  gepackten kurzen Deltaweg aber kontinuierlich.
- Animation 0 enthält in ihren 60 Skalardeskriptoren keine optionalen
  Scale-Streams. Alle Scale-Faktoren bleiben 1; eine numerische
  Scale-Interpolation wird durch diesen Datensatz nicht ausgeübt.
- Die getesteten Zeiten `0`, `1`, `7.5`, `8` und `15` ergeben jeweils 21
  lokale und Worldmatrizen, 638 endliche aktive Vertexpositionen sowie
  identische Topologie, UVs und Materialgrenzen.

Die vollständige Adress- und Instruktionsevidenz sowie alle Kanalwerte stehen in
`research/boy/animation0-temporal-validation.md` und im maschinenlesbaren
Mehrframe-Report. Dessen ältere Matrix-, Kontrollvertex- und Bounding-Box-
Zahlen aus direkter gespeicherter Komponentenreihenfolge sind `SUPERSEDED`;
aktuell gilt die A/C/B-Abbildung aus `boy-transform-runtime.md`.

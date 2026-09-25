# JFG-F3DDKR: Dreiecksflag Bit `0x40`

Status: **VERIFIED** für die US-ROM mit SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023`.

- Der RSP lädt Byte `+0` des 16-Byte-Dreiecksrecords bei IMEM `0x16d0`
  (ROM `0x0a06a0`).
- `xori/andi 0x40` und `sll 7` setzen für Recordwert `0x00` das interne
  Geometriestatusbit `0x2000`; Recordwert `0x40` löscht es.
- `0x2000` ist in JFGs `PR/gbi.h` als `G_CULL_BACK` definiert.
- Ab IMEM `0x1a98` wird das Bit mit dem Vorzeichen des berechneten
  Orientierungswerts verknüpft. Die Verzweigung bei `0x1b78` verwirft die
  gewählte Seite über den frühen Rücksprung bei `0x1f74`.
- Bei Recordwert `0x40` sind beide orientierungsabhängigen Reject-Masken
  null. Das Dreieck wird damit unabhängig von seiner Winding weitergegeben:
  Backface-Culling ist deaktiviert, beide Seiten werden gezeichnet.
- Clip-Rejection und der separate Degeneratentest bei `0x1b5c` bleiben
  wirksam. Bit `0x40` ist kein allgemeines „niemals verwerfen“-Flag.

Die vollständige Instruktions- und ROM-Adresskette ist in
[`../../research/boy/runtime-validation.md`](../../research/boy/runtime-validation.md)
dokumentiert. DKR diente nur als Vergleich; die Einstufung beruht auf dem
JFG-Mikrocode selbst.

# Boy: Texture-ID-Auflösung

Status: **VERIFIED** für Prop 220 der bekannten US-ROM.

`texLoadTexture` erkennt Bit `0x8000`, maskiert die ID mit `0x7fff`, nutzt
für diesen Pfad die aus Asset 1 geladene Offsettabelle und lädt das Runtime-
Asset aus Assetsektion 0. Alle 18 Boy-IDs verwenden diesen Pfad und wurden
über den Asset-LUT bei ROM `0xB1750` sowie die Assetbasis `0xB1880` zu einem
konkreten ROM-Bereich aufgelöst.

Folgende 14 IDs führen bei `runtime_asset_start + 0x20` zu einem Container,
der bereits im RGBA16-Manifest binär gegen die ROM und pixelweise gegen das
Referenz-PNG bestätigt ist:

`8436 8422 8209 820d 80f8 9048 80f7 852f 820a 809f 80f9 852e 8089 820b`.

Die IDs `8431`, `9a00`, `874e` und `874c` sind ebenfalls eindeutig zu
Runtime-ROM-Assets aufgelöst. Ihre Marker `33 00`, `01 00`, `25 00` und
`00 00` gehören nicht zur verifizierten `11 00`-RGBA16-Pipeline. Ihre
Decodierung bleibt **UNKNOWN**.

Der vollständige maschinenlesbare Nachweis mit ID, Tabellenindex,
ROM-Anfang, Header und RGBA16-Manifestreferenz steht in
[`../../data/generated/boy-prop220-experimental/boy-export-report.json`](../../data/generated/boy-prop220-experimental/boy-export-report.json).

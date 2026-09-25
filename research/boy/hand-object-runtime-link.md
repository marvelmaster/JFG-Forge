# Boy: Runtime-Verbindung des Objekts an Player-Control `+0x5CC`

Datum: 2026-09-23. Untersucht wurde ausschließlich die vermutete Kette
`Objekt 0xF7 / Runtime-Typ 0x59 -> Prop 309 JunoHand` in der US-ROM.

> Die Objekt-/Prop-Widerlegung und die Positionskopplung bleiben gültig. Die
> historische konkrete Animation-0-/Frame-0-Position von Matrix 6 ist wegen
> der später korrigierten Euler-Komponentenabbildung `SUPERSEDED`.

## Ergebnis

Die Hypothese ist für diesen Pfad **widerlegt**. Die tatsächliche Kette lautet:

```text
Spawn-Objekt-ID 0xF7
-> Übersetzungstabelle Asset 48, Eintrag 247 = Objektdefinition 232
-> Objektdefinition 232, Verhalten 0x59, ein Modell
-> Modellliste[0] = Prop 343
-> 0343_Cluster.bin
```

Prop 309 `JunoHand` wird von diesem Objekt weder direkt noch als alternatives
LOD geladen.

## ROM-Tabellenkette

Asset 48 liegt bei ROM `0x1747260..0x17478E0`. Der Eintrag für `0xF7` liegt
bei `0x174744E` und enthält `0x00E8` (232).

Asset 46 ist die Offsettabelle der Objektdefinitionen. Eintrag 232 liegt bei
ROM `0x1714E80` und begrenzt die Definition relativ auf
`0xE298..0xE3D0`. In Asset 47 ergibt das ROM
`0x1723A38..0x1723B70`.

Die Definition enthält:

- `u16 +0x1C = 0x0059`: Verhalten/Runtime-Typ;
- `u8 +0x1E = 0`: Modelltyp;
- `u8 +0x1F = 1`: genau eine Modellreferenz;
- `u32 +0x30 = 0xE0`: relativer Pointer auf die Modellliste;
- `u32 +0xE0 = 0x157`: Modell/Prop 343.

`objSetupObject` (`0x80005F14`) liest die Spawn-ID bei `0x80005F30`, greift
bei `0x80005FBC..0x80005FD8` auf `objindex` zu, lädt Definition 232 über
`objGetObjdef` bei `0x80006068` und reicht bei `0x800062CC` die Modell-ID 343
an `modLoadModel` weiter. `objSetup` liest bei `0x8000F03C` den Wert `0x0059`
aus Header `+0x1C` und schreibt ihn bei `0x8000F044` nach Objekt `+0x48`.

Prop 309 kommt unabhängig davon in den Objektdefinitionen 399, 564 und 653
vor. Die zugehörigen Spawn-IDs sind `0xC7`, `0x1BE` und `0x205`. Das bestätigt,
dass `JunoHand` ein tatsächlich referenziertes Asset ist, stellt aber keine
Verbindung zum untersuchten `0xF7`-Objekt her.

Eine spätere, getrennte Untersuchung hat Objektdefinition 399 als das einzige
Boy-Child `BoyGun` bestätigt. Dessen neun Modellslots umfassen Props 301–309;
Prop 309 belegt den Hand-/Fallback-Slot 8. `objMakeGunMtx` bindet dieses Child
über den ersten Boy-Referenzpunkt an Matrix 6. Dieser normale Attachmentpfad
ändert nichts an der hier bestätigten Widerlegung für das unabhängige
`0xF7`-Objekt.

## Tatsächlich geladenes Modell

Prop 343 trägt intern den Namen `Cluster` und hat SHA-256
`2b8a04547723c27def6d3145ae81a113dee745bd355bb7d22d96f3147bbd8cff`.

- 22 Vertices;
- 32 Triangle-Records, davon 24 geometrisch gültig und 8 degeneriert;
- 3 Gruppen, alle ohne Gruppenflag `0x400`;
- 1 TextureRecord mit Texture-ID `0x80FD`;
- keine Transformrecords;
- Gruppenmatrix 0;
- lokale Bounding Box `(-32,-32,-32)..(32,33,32)`.

Dies ist strukturell kein Ersatz für die 42-Vertex-/32-Face-Hand des
Boy-Grundmodells.

## Räumliche Verbindung

Der Spawnpfad liegt in `func_80039AE0` bei `0x80039D08`, im externen Decomp
als `shoot_Flares` bezeichnet. Die Bezeichnung ist Navigationshilfe und kein
Beweis für die Assetsemantik. `0x80039D7C/0x80039DA4` schreibt `0xF7` in den
Spawnrecord; `0x80039E48` ruft `objSetupObject`. Für die betreffenden
Charaktermodi wird der resultierende Objektpointer bei `0x80039E70` in
Player-Control `+0x5CC` gehalten.

Der Aufrufer holt bei `0x80038870` die XYZ-Position über
`controlGetGunBarrelPos` und ruft den Spawnpfad bei `0x80038930` auf. Im
normalen Modellpfad stammt die Position aus Boy-Referenzpunkt 0,
`Vertex 619 / Matrix 6`. Der in der ursprünglichen Untersuchung berechnete
konkrete Frame-0-Wert ist `SUPERSEDED`; die Referenzpunktkette selbst bleibt
VERIFIED.

Beim Spawn werden die drei Werte zunächst ganzzahlig in die s16-Felder
`+4/+6/+8` des Spawnrecords konvertiert. `objSetupObject` konvertiert sie in
Objektposition `+0x0C/+0x10/+0x14` zurück nach f32. Im laufenden Playerpfad
liest der Code bei `0x800330E0` erneut Player-Control `+0x5CC`; der Aufruf bei
`0x80033108` lässt `controlGetGunBarrelPos` dann direkt in diese drei
f32-Positionsfelder schreiben.

Damit ist eine wiederholte **Positionskopplung** bestätigt. Ein persistenter
Parentpointer auf Matrix 6 wurde nicht gefunden. Die Spawnroutine übergibt
außerdem Player-Control-Winkel `+0x1CA/+0x1CC` in Spawnrecord `+0x0A/+0x0C`
und weitere waffenspezifische Felder. Wie der Verhalten-Overlaycode daraus die
Orientierung bildet, bleibt UNKNOWN. Eine vollständige Matrix-6-Orientierung
wird im bestätigten Basispfad nicht kopiert.

`controlGetGunBarrelPos` besitzt zudem Alternativpfade zu gecachten
Player-Control-Koordinaten beziehungsweise zur Player-Objektposition. Der
Matrix-6-Referenzpunkt ist deshalb der normale Modellpfad, nicht eine
bedingungslose Parentbeziehung.

## Einstufung

### VERIFIED

- `0xF7 -> Objektdefinition 232 -> Verhalten 0x59 -> Prop 343 Cluster`.
- Prop 309 wird durch diesen Pfad nicht geladen.
- Das Objekt bei Player-Control `+0x5CC` erhält seine Position wiederholt über
  `controlGetGunBarrelPos`.
- Prop 309 wird in anderen Objektdefinitionen tatsächlich referenziert.

### LIKELY

- Der externe Name `shoot_Flares` beschreibt die Funktion bei `0x80039D08`.

### UNKNOWN

- vollständige Semantik der Winkel und Zusatzfelder im Verhalten-Overlay;
- exakte Semantik jeder Bedingung, die den BoyGun-Selektor auf den
  Prop-309-Slot 8 zwingt.

## Diagnoseexport

Es wurde kein OBJ erzeugt. Bedingung A ist nicht erfüllt: Das untersuchte
Objekt lädt Prop 343 statt Prop 309. Eine Verbindung von `JunoHand` mit Matrix
6 wäre daher eine erfundene Zuordnung.

## Spätere Auflösung des normalen Attachmentpfads

Der bestätigte BoyGun-Pfad ist in
[`../../knowledge/verified/boy-gun-attachment.md`](../../knowledge/verified/boy-gun-attachment.md)
zusammengefasst. Die hier untersuchte `0xF7`-/Cluster-Kette bleibt davon
getrennt.

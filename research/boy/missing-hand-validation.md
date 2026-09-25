# Boy: Diagnose der fehlenden Hand in Animation 0, Frame 0

Datum: 2026-09-23. Untersucht wurde nur Prop 220 `Boy` im bereits rekonstruierten Zustand Animation 0, ganzzahliger Frame 0.

> Die strukturelle Hand-/Attachmentanalyse bleibt gültig. Transformierte
> Positionen und Bounding Boxes aus diesem historischen Bericht beruhen auf
> der damals direkten gespeicherten Eulerreihenfolge und sind `SUPERSEDED`.

## Ergebnis

Die fehlende Geometrie liegt am modellräumlichen `+X`-Arm mit der Matrixkette `3 -> 4 -> 5 -> 6`. Der gegenüberliegende `-X`-Arm endet in Matrix 9 und besitzt dort 42 aktive Vertices und 32 Faces. Matrix 6 besitzt im normalen Boy-Mesh dagegen keine Vertices und keine Faces.

Der Exporter hat keine aktive Handgeometrie verloren. Die fehlende Seite ist
bereits im Boy-Prop strukturell anders angelegt. Der erste Referenzpunkt
`(Vertex 619, Matrix 6)` wird sowohl im Waffenlaufpfad gelesen als auch von
`objMakeGunMtx` als Transform des BoyGun-Childs verwendet. BoyGun stellt auf
dieser Seite das ausgewählte Hand-/Waffenmodell bereit.

## Vollständige Dreiecksbilanz

```text
520 Triangle-Records im Prop
- 15 geometrisch degenerierte Records (Gruppen 64-78)
= 505 geometrisch gültige Dreiecke
- 3 gültige Dreiecke in den übersprungenen Gruppen 0 und 1
= 502 Dreiecke im untersuchten makeModelGfx-Pfad
= 502 Faces im bisherigen Animation-0/Frame-0-OBJ
```

Die drei gültigen ausgeschlossenen Dreiecke bilden keine zweite Hand:

- Gruppe 0: 4 Vertices, 2 Faces, Matrix 5; die historische transformierte Bounding Box ist `SUPERSEDED`;
- Gruppe 1: 3 Vertices, 1 Face, Matrix 20; die historische transformierte Bounding Box ist `SUPERSEDED`.

Gruppen 64-78 enthalten je einen Vertex und ein Dreieck `(0,0,0)`. Ihre Felder `+1..+5` erfüllen vielfach nicht die bestätigten Matrixgrenzen. Sie sind daher keine über den normalen Gruppenpfad transformierbaren Meshteile.

## JFG-Codepfade

`makeModelGfx` testet bei `0x8003DF34` Gruppenflag `0x400`; der Sprung bei `0x8003DF44` geht direkt zur nächsten Gruppe. `modMakeLimbModel` wiederholt denselben Ausschluss bei `0x8003E72C..0x8003E738`. Damit existiert in den beiden untersuchten Modellaufbaupfaden kein alternativer Renderer für diese Gruppen. Eine weitergehende fachliche Benennung des Flags bleibt UNKNOWN.

Der erste Boy-Referenzrecord ist `(Vertex 619, Matrix 6)`. Seine hier früher
angegebene numerische Animation-0-/Frame-0-Position ist wegen der später
korrigierten Euler-Komponentenabbildung `SUPERSEDED`; seine Rolle als
BoyGun-Socket ist unabhängig davon VERIFIED.

`controlGetGunBarrelPos` bei `0x8003B418` folgt bei `0x8003B454..0x8003B4A4` dem Objekt zum Modellinstance-Pointer und liest dessen erstes XYZ-Tripel bei Instance `+0x68`. Dieses Tripel füllt `modGenAnimMatrices` zuvor aus dem ersten Referenzrecord. Die Rolle als Waffenlauf-/Gun-Barrel-Punkt ist damit VERIFIED.

Der zweite Record ist `(Vertex 624, Matrix 10)`. Seine frühere numerische
Position ist `SUPERSEDED`; ein benannter Verbraucher bleibt UNKNOWN.

Die im Decomp `controlEmptyPlayersHand` genannte Funktion bei `0x8003B820` liest aus dem Spielerzustand bei `+0x5cc` einen separaten Objektpointer, prüft dessen Typfeld `+0x48` auf `0x59`, löscht dessen Modellzustand und trennt den Pointer. Die separate Player-Equipment-Objektverwaltung ist durch den Datenfluss VERIFIED. Die engere Handbedeutung ist durch Symbolname und Aufrufe aus der Waffenwahl LIKELY, aber nicht allein durch den Namen bestätigt.

Prop 309 trägt intern den Namen `JunoHand`. Er besitzt 42 aktive Vertices und
32 aktive Faces. Die spätere BoyGun-Verfolgung weist ihn als Slot 8 der
neunteiligen Modellliste von Objektdefinition 399 nach. Der lokale Selektor
verwendet ihn als Hand-/Fallback-Modell. Seine engere Deutung als normaler
unbewaffneter Zustand bleibt LIKELY.

Der zuvor verfolgte Pfad `0xF7 / 0x59` ist davon unabhängig und lädt
nachweislich Prop 343 `Cluster`, nicht Prop 309. Einzelheiten zu dieser
Abgrenzung stehen in [`hand-object-runtime-link.md`](hand-object-runtime-link.md).

## Einstufung

### VERIFIED

- Der `+X`-Arm endet auf Matrix 6 ohne aktive Meshgeometrie.
- Der `-X`-Arm besitzt auf Matrix 9 eine Hand mit 42 Vertices und 32 Faces.
- Keine der 17 `0x400`-Gruppen enthält eine entsprechende Hand.
- `(Vertex 619, Matrix 6)` speist `controlGetGunBarrelPos`.
- `(Vertex 619, Matrix 6)` wird von `objMakeGunMtx` als BoyGun-Transform
  verwendet; Matrix 6 ist der BoyGun-Attachment-Socket.
- Objektdefinition 399 `BoyGun` wählt Props 301–309 als Hand-/Waffenmodelle.
- Prop 301 `BPistol` entspricht dem 67-Face-Attachment des bewaffneten
  SceneRipper-Captures und enthält Hand und Pistole in einer Modelleinreichung.
- Prop 309 `JunoHand` belegt BoyGun-Slot 8 und dient als Hand-/Fallback-Modell.
- Der Exporter bildet alle 502 gültigen Faces des untersuchten Runtimepfads ab.

### WIDERLEGT FÜR DEN UNTERSUCHTEN PFAD

- Objekt `0xF7` mit Runtime-Typ `0x59` lädt Prop 309 `JunoHand`.

### UNKNOWN

- eine vollständige fachliche Semantik des Gruppenflags `0x400`.
- die exakte Semantik jeder Selektorbedingung, die BoyGun-Slot 8 erzwingt;
- die Runtime-Ownership der zwei zusätzlichen Handkopien im unbewaffneten
  Capture `boy-test-002`.

## Diagnoseexport

Es wurde kein OBJ erzeugt. Keine ausgeschlossene Gruppe erklärt die fehlende Hand, und das automatische Exportieren eines separaten Attachments war für diesen Schritt ausgeschlossen.

## Späterer Attachment-Befund

Die vollständige bestätigte Hand-/BoyGun-Struktur, die neun Modellslots, der
Matrix-6-Datenfluss und die bewaffnete Capture-Zuordnung stehen in
[`../../knowledge/verified/boy-gun-attachment.md`](../../knowledge/verified/boy-gun-attachment.md).

# Prop 220 Boy: Hand- und BoyGun-Attachment

Gültig für die untersuchte US-ROM mit SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023`. Dieses Dokument fasst nur
bereits bestätigte Struktur-, Code- und Capturebefunde zusammen.

## VERIFIED: Hände im Boy-Basismodell

- Prop 220 `Boy` enthält auf der Matrix-9-Seite eine integrierte Hand:
  Gruppen 18–20, Dreiecke 89–120 und 32 aktive Faces.
- Die gegenüberliegende Matrix-6-Seite besitzt im Boy-Basismodell keine
  aktive Handgeometrie.
- Der erste Modellreferenzpunkt von Boy ist `(Vertex 619, Matrix 6)`.

Damit ist die unterschiedliche Modellierung der beiden Seiten beabsichtigt:
Matrix 9 trägt die im Basismodell enthaltene Hand; Matrix 6 dient als Socket
für ein separates Child-Attachment.

## VERIFIED: BoyGun-Child und Modellslots

Die Playerdefinition von Boy besitzt genau ein Child:

```text
Objektdefinition 399: BoyGun
```

BoyGun besitzt neun nullbasiert ausgewählte Modellslots:

| Slot | Prop | Name | aktive Faces |
| ---: | ---: | --- | ---: |
| 0 | 301 | `BPistol` | 67 |
| 1 | 302 | `BAutomatic` | 116 |
| 2 | 303 | `BUzi` | 126 |
| 3 | 304 | `BUzi1` | 106 |
| 4 | 305 | `BShrinkBeam` | 110 |
| 5 | 306 | `BRocket` | 142 |
| 6 | 307 | `BFlameThrower` | 132 |
| 7 | 308 | `BSniper` | 245 |
| 8 | 309 | `JunoHand` | 32 |

Der lokale Renderselektor verwendet den ausgerüsteten Waffenindex zur Wahl
dieses Slots. Prop 309 nimmt dabei nachweislich den Hand-/Fallback-Slot 8 ein.

## VERIFIED: Matrix-6-Attachment

`objMakeGunMtx` verwendet den ersten Boy-Modellreferenzpunkt als
BoyGun-Transform:

| Adresse | Datenfluss |
| --- | --- |
| `0x8000BCE0` | lädt den Pointer auf die Boy-Referenztabelle aus Modell `+0x30` |
| `0x8000BCE4` | lädt den Matrixpuffer-Selektor aus Laufzeitstruktur `+0x0B` |
| `0x8000BCE8` | lädt die Matrix-ID aus dem ersten Referenzrecord `+2`: Matrix 6 |
| `0x8000BCEC..0x8000BCF4` | wählt damit einen Pointer aus der Matrixpuffer-Pointerfolge ab Objekt `+0x10` |
| `0x8000BCF8` | multipliziert die Matrix-ID mit dem 64-Byte-Matrixstride |
| `0x8000BD00` | bildet die Adresse von Boy-Matrix 6 |
| `0x8000BD04..0x8000BD1C` | kopiert die 15 gelesenen Matrixwörter in den BoyGun-Ausgabetransform |
| `0x8000BD20..0x8000BD38` | setzt die affine vierte Spalte explizit auf `(0,0,0,1)` |

Matrix 6 ist damit der **VERIFIED BoyGun-Attachment-Socket**. Sie benötigt
keine eigene Handgeometrie in Prop 220, weil das ausgewählte BoyGun-Modell die
Geometrie dieser Seite bereitstellt.

## VERIFIED: vollständiger normaler BoyGun-Transform

Die erneute statische Prüfung des unmittelbar folgenden Pfads bestätigt für
den normalen Boy-Spieler:

```text
BoyGun_world = Boy_matrix_6
BoyGun_local = identity
```

Es gibt in diesem Pfad keine zusätzliche Rotation, Skalierung oder Translation
des ausgewählten Props 301–309. Der Sonderzweig ab `0x8000BD3C` kann nur für
Objekttyp `0x33` die Translation aus einem Modellreferenzpunkt ersetzen; er ist
nicht der normale Boy-Pfad. Der Aufruf von `mathMtxXFMF` bei `0x8000BE3C`
transformiert anschließend einen separaten Referenzpunkt in drei vom Aufrufer
bereitgestellte Ausgabe-Floats. Laut lokaler Funktionsdeklaration nimmt
`mathMtxXFMF(Matrix, x, y, z, *ox, *oy, *oz)` die Matrix nur als Eingabe. Er
verändert den zuvor aufgebauten BoyGun-Ausgabetransform nicht.

Damit ist auch die vollständige Platzierung der neun BoyGun-Modelle unter
Matrix 6 **VERIFIED**. Die Modellgeometrie selbst liefert die Greifhand; Forge
darf keine synthetische zweite Hand ergänzen.

## VERIFIED: bewaffneter Capture `boy-test-003`

- Der gewöhnliche Boy-Render umfasst GLR 1418–1919 mit 502 aktiven Faces.
- Die integrierte Matrix-9-Hand liegt bei GLR 1504–1535.
- Das anschließende Attachment liegt bei GLR 1920–1986 und umfasst 67 Faces.
- Seine drei Texturgruppen enthalten 51, 10 und 6 Faces.
- Diese Struktur stimmt exakt mit Prop 301 `BPistol`, BoyGun-Slot 0, überein.
- Im bewaffneten Capture existiert keine zweite Kopie der Boy-Dreiecke
  89–120.

Prop 301 wird als einzelnes kombiniertes Hand-und-Waffenmodell eingereicht.
Es ist nicht die Kombination aus Prop 309 `JunoHand` und einer separat
gerenderten Pistole. Die manuelle Blender-Prüfung identifiziert die sichtbare
Form als Greifhand mit Pistole; die Einreichung als ein Modell und ihre
Zuordnung zu Prop 301 sind durch Struktur und Capture **VERIFIED**.

## Prop 309 und der unbewaffnete Zustand

### VERIFIED

- Prop 309 `JunoHand` besitzt 32 aktive Faces.
- Prop 309 belegt BoyGun-Slot 8.
- Der lokale Selektor verwendet Slot 8 als Hand-/Fallback-Modell.

### LIKELY

- Slot 8 entspricht speziell dem normalen unbewaffneten Zustand.

Diese engere Zustandsbezeichnung bleibt LIKELY, weil die genaue Semantik
aller Bedingungen, die den Selektor auf Slot 8 zwingen, noch nicht belegt ist.

## SUPERSEDED Hypothese und Capture-Abgrenzung

Die frühere Hypothese, severedLimb könne das normale Matrix-6-Handattachment
erklären, ist widerlegt und `SUPERSEDED`. Der normale Pfad ist BoyGun an
Matrix 6. Die folgenden Capture-Fakten bleiben als getrennte Effektanalyse
erhalten.

### VERIFIED

- Der Charakterauswahl-/unbewaffnete Capture enthält die gewöhnliche
  Matrix-9-Hand und zwei zusätzliche 32-Face-Kopien der Boy-Dreiecke 89–120.
- Verhalten beziehungsweise Typ 64 ist ein frei simulierter Effekt für
  abgetrennte Körperteile und kein dauerhaft an einen Bone gebundenes
  Attachment.
- Die beiden `modMakeLimbModel`-Aufrufe mit den Werten 2 und 6 erzeugen
  Renderzustandsvarianten für ein einzelnes severedLimb-Objekt.
- Die Werte 2 und 6 sind Renderzustandseingaben und keine Matrix-IDs.
- severedLimb erklärt die beiden zusätzlichen normalen Hand-Einreichungen
  daher nicht.

### UNKNOWN

- Die konkrete Runtime-Ownership und der Grund für die zwei zusätzlichen
  Handkopien in `boy-test-002`.

## Strukturelles Modell

```text
Prop 220 Boy
  Matrix-9-Seite
    integrierte Hand: Gruppen 18–20, Dreiecke 89–120

  Matrix-6-Seite
    BoyGun-Child: Objektdefinition 399
      ausgewähltes Modell aus Props 301–309
      Waffenmodelle enthalten ihre Greifhandgeometrie
      Prop 309 stellt das Hand-/Fallback-Modell bereit
```

## Offene Grenzen

- **LIKELY:** BoyGun-Slot 8 ist konkret der normale unbewaffnete Zustand.
- **UNKNOWN:** exakte Semantik jeder Bedingung, die Slot 8 erzwingt.
- **UNKNOWN:** Ownership der zwei zusätzlichen Handkopien aus
  `boy-test-002`.
- **UNKNOWN:** nicht unterstützte Texturformate einzelner BoyGun-Materialien;
  sie dürfen nicht als RGBA16 geraten werden.

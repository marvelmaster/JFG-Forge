# Boy / Prop 220: Animationsidentifikation

Status: gezielter Audit vorhandener ROM-Metadaten, Symbole, Boy-Berichte und
bereits untersuchter Player-Codepfade. Es wurden keine Clips nach ihrem
Erscheinungsbild benannt.

## Ergebnis und Einstufung

- **VERIFIED ORIGINAL NAME:** 0 von 52. Weder der ROM-Katalog noch die
  geprüften Symbol-, Debug- oder Quelldaten enthalten einen nachweislich an
  einen dieser Clips gebundenen Originalnamen.
- **VERIFIED GAMEPLAY CONTEXT:** 10 von 52. Dies bezeichnet ausschließlich
  konkrete Auswahl- oder Zustandsdatenflüsse, keine Originalnamen.
- **LIKELY SEMANTIC ROLE:** 0 von 52. Visuelle Eindrücke wurden nicht als
  Evidenz verwendet.
- **UNKNOWN:** 42 von 52 ohne belastbaren Auswahlkontext; die Originalnamen
  bleiben bei allen 52 `UNKNOWN`.

Die numerischen IDs sind Asset-IDs. Funktionsnamen wie
`controlPlayerOpenChest` belegen den Kontext eines Aufrufers, aber nicht den
ursprünglichen Namen des Animationsassets.

## Identifikationstabelle

| Index | ID | Original Name | Gameplay Context / Semantic Evidence | Confidence | Evidence |
| ---: | ---: | --- | --- | --- | --- |
| 0 | 1026 | UNKNOWN | Bewegungsabhängiger Boy-Zustand; Fortschritt skaliert mit `max(abs(racer+4), abs(racer+0x10))`. | VERIFIED GAMEPLAY CONTEXT | Overlay 16 `0x01005120`; [animation-runtime-usage.md](animation-runtime-usage.md) §1–2 |
| 1 | 1027 | UNKNOWN | Wird aus Zustand 0 gewählt, wenn die Bewegungsgröße `1.75` überschreitet. | VERIFIED GAMEPLAY CONTEXT | Overlay-16-Zustandspfad; [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 2 | 1028 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 3 | 1025 | UNKNOWN | Wird aus Zustand 0 bei gesetztem `racer+0x569` gewählt; die Bedeutung des Feldes wurde hier nicht neu interpretiert. | VERIFIED GAMEPLAY CONTEXT | Overlay-16-Zustandspfad; [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 4 | 1033 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 5 | 1039 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 6 | 1040 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 7 | 1041 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 8 | 1038 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 9 | 1042 | UNKNOWN | Wird aus Zustand 0 gewählt, wenn `abs(racer+0x10)` dominiert; das Vorzeichen entscheidet zwischen 9 und 10. Außerdem einer der beobachteten Initialzustände. | VERIFIED GAMEPLAY CONTEXT | Overlay-16-Zustandspfad und `controlPlayerInit`; [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 10 | 1043 | UNKNOWN | Wird aus Zustand 0 gewählt, wenn `abs(racer+0x10)` dominiert; das Vorzeichen entscheidet zwischen 9 und 10. | VERIFIED GAMEPLAY CONTEXT | Overlay-16-Zustandspfad; [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 11 | 1031 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 12 | 1036 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 13 | 1029 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 14 | 1030 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 15 | 1044 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 16 | 1019 | UNKNOWN | Einer der Zustände 16–19, die aus Zustand 0 unterhalb der Bewegungsgrenze `0.1` über vorhandene Flag-/Zufallszweige gewählt werden; außerdem beobachteter Initialzustand. | VERIFIED GAMEPLAY CONTEXT | Overlay-16-Zustandspfad und `controlPlayerInit`; [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 17 | 1020 | UNKNOWN | Einer der Zustände 16–19, die aus Zustand 0 unterhalb der Bewegungsgrenze `0.1` über vorhandene Flag-/Zufallszweige gewählt werden. | VERIFIED GAMEPLAY CONTEXT | Overlay-16-Zustandspfad; [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 18 | 1021 | UNKNOWN | Einer der Zustände 16–19, die aus Zustand 0 unterhalb der Bewegungsgrenze `0.1` über vorhandene Flag-/Zufallszweige gewählt werden. | VERIFIED GAMEPLAY CONTEXT | Overlay-16-Zustandspfad; [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 19 | 1022 | UNKNOWN | Einer der Zustände 16–19, die aus Zustand 0 unterhalb der Bewegungsgrenze `0.1` über vorhandene Flag-/Zufallszweige gewählt werden. | VERIFIED GAMEPLAY CONTEXT | Overlay-16-Zustandspfad; [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 20 | 1023 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 21 | 1051 | UNKNOWN | Der vorhandene Zustand kann über `boyCanFire` zu Index 0 zurückkehren; kein belegter Auswahlpfad oder semantischer Name für Index 21. | UNKNOWN | [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 22 | 1035 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 23 | 1070 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 24 | 1048 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 25 | 1050 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 26 | 1054 | UNKNOWN | Ein vorhandener Zustand 26 kann unter Richtungs-/Controlbedingungen zu Index 0 wechseln; keine belastbare semantische Zuordnung. | UNKNOWN | [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 27 | 1053 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 28 | 1055 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 29 | 1056 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 30 | 1057 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 31 | 1058 | UNKNOWN | Ein vorhandener Zustand 31 kann unter Richtungs-/Geschwindigkeitsbedingungen zu Index 0 wechseln; keine belastbare semantische Zuordnung. | UNKNOWN | [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 32 | 1059 | UNKNOWN | Ein vorhandener Zustand 32 kann unter Richtungs-/Geschwindigkeitsbedingungen zu Index 0 wechseln; keine belastbare semantische Zuordnung. | UNKNOWN | [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 33 | 1060 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 34 | 1063 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 35 | 1062 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 36 | 1061 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 37 | 1066 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 38 | 1067 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 39 | 1068 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 40 | 1045 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 41 | 1046 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 42 | 1047 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 43 | 1069 | UNKNOWN | `controlPlayerOpenChest` wählt Index 43 für Subtypen 1/5; `controlPlayerOpeningChest` prüft Index und Phasengrenzen `0.15/0.53`. | VERIFIED GAMEPLAY CONTEXT | `0x8003B6C8`, Auswahl bei `0x8003B710`; Prüfung ab `0x8003B740`; [animation-runtime-usage.md](animation-runtime-usage.md) §5 |
| 44 | 1034 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 45 | 1024 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 46 | 1052 | UNKNOWN | Der vorhandene Zustand kann über `boyCanFire` zu Index 0 zurückkehren; kein belegter Auswahlpfad oder semantischer Name für Index 46. | UNKNOWN | [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 47 | 1064 | UNKNOWN | Ein vorhandener Zustand 47 kann unter Richtungs-/Geschwindigkeitsbedingungen zu Index 0 wechseln; keine belastbare semantische Zuordnung. | UNKNOWN | [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 48 | 1065 | UNKNOWN | Ein vorhandener Zustand 48 kann unter Richtungs-/Geschwindigkeitsbedingungen zu Index 0 wechseln; keine belastbare semantische Zuordnung. | UNKNOWN | [animation-runtime-usage.md](animation-runtime-usage.md) §1 |
| 49 | 1032 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 50 | 1037 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |
| 51 | 1071 | UNKNOWN | Keine belastbare Zuordnung gefunden. | UNKNOWN | Nur technischer ROM-Katalogeintrag. |

## Geprüfte Namensquellen

- Der erzeugte `boy-animation-catalog.json` enthält alle 52 IDs und technische
  Strukturen, aber keine Namensfelder mit Werten.
- `research/Jet-Force-Gemini/ver/symbols/` enthält relevante Funktionssymbole
  wie `animBoyEventHandler`, `controlPlayerOpenChest`,
  `controlPlayerOpeningChest`, `objAnimSetMove`, `modGenAnimMatrices` und
  `gen_anim_data`, aber keine Zuordnung der IDs 1019–1071 zu Clipnamen.
- Die gezielt geprüften Boy-/Player-Quellen und Header enthalten keine
  Animations-Enums oder Debugstrings, welche die 52 IDs benennen.
- Die externen Decomp-Symbole dienen als Navigation. Die zwei zentralen
  Laufzeitbefunde wurden in den vorhandenen Berichten bereits gegen die
  gepinnte US-ROM geprüft.

## Standalone-, Blend- und Override-Befund

1. **Keine separate Upper-/Lower-Body-Clipspur nachgewiesen.** Alle 52
   katalogisierten Blobs besitzen 21 Kanalslots, die Identitätsmap `0..20`
   und 60 Deskriptoren für Kanäle 0–19. Es wurde keine Kanalmap oder Maske
   gefunden, die einen Clip ausdrücklich auf Ober- oder Unterkörper begrenzt.
2. **Aktueller und vorheriger Clip werden geblendet.** `gen_anim_data`
   interpoliert beim Übergang den vorherigen gegen den aktuellen Zustand mit
   dem vorhandenen 10-Bit-Blendzähler. Das ist ein Übergangsblend über den
   dekodierten Zustand, kein belegtes Upper-/Lower-Body-Layering.
3. **Selektive Runtime-Overrides sind VERIFIED.** Die Liste bei
   `racer+0x240`, geliefert von `controlPlayerTiltList`, verändert ausgewählte
   lokale Winkel und Skalen innerhalb `gen_anim_data`, bevor die finalen
   Hierarchiematrizen entstehen. Belegt sind unter anderem Eingriffe an Nodes
   1, 3, 10 und 11 sowie bedingte Skalierung von Node 6 und weiteren Nodes.
4. **Kein nachträgliches Überschreiben der Boy-Matrixslots gefunden.** Im
   untersuchten Renderpfad folgen nach `modGenAnimMatrices` unter anderem
   `objMakeGunMtx` und Renderhilfen; ein zweiter Matrixaufbau oder Writes in
   die 21 Slots wurden dort nicht gefunden.
5. **Standalone ist nicht gleich vollständiger Runtimeframe.** JFG Forge zeigt
   korrekt die isolierte Basisanimation. Ein echter Playerframe kann zusätzlich
   vorherigen Clip/Blendzähler, die laufzeitabhängige Override-Liste und den
   Objekt-/Weltkontext enthalten. Gekreuzte Beine oder starke Neigung allein
   belegen weder einen Decoderfehler noch eine partielle Clipsemantik.

Damit ist kein aktuelles Forge-Poseverhalten als falsch nachgewiesen. Eine
Layering-, Maskierungs- oder Korrekturlogik darf aus diesem Audit nicht
abgeleitet werden.

## Forge-Integration

Die Kontexte bleiben zunächst Forschungsdokumentation. Eine direkte Kopplung
des GUI-Dropdowns an Markdown wurde vermieden; ein strukturiertes, getestetes
Kontext-Metadatenformat existiert noch nicht.

# Boy Runtime-Capture-Workflow

## Ergebnis

Der kleinste belastbare nächste Versuch ist eine Laufzeitaufzeichnung an
`0x8003D908`. Das ist die erste Instruktion in `modGenAnimMatrices` nach der
Rückkehr aus `gen_anim_data`. An dieser Stelle sind die 21 Boy-Matrizen im
aktuellen Instanzpuffer vollständig, während Instanzpointer, Objektpointer,
Racerpointer und die tatsächlich verwendete Objektmatrix noch eindeutig aus
Registern beziehungsweise dem Stackframe erreichbar sind.

Die Aufzeichnung ist weiterhin erforderlich. Es wurde kein realer Lauf
simuliert und kein Neutralwert für `racer+0x580` oder Bit `0x40` von
`racer+0x540` angenommen.

## Adressarten

Alle Adressen `0x800.....` in diesem Dokument sind virtuelle N64-KSEG0-
RAM-Adressen. Sie sind keine ROM-Dateioffsets. Die Aussagen wurden gegen die
lokale US-Z64-ROM mit SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023` geprüft.

## Player-, Objekt- und Raceradressierung

`objGetPlayerlist` bei `0x8000E464` liest:

```text
u32_be[0x800F2D10]  Playeranzahl
u32_be[0x800F2D0C]  Pointer auf ein Array von Object*
```

Ein Arrayeintrag ist ein dynamischer Objektpointer. Der Racerpointer steht bei
`object+0x68` und ist ebenfalls dynamisch. Die statische Playerliste ist damit
eine Navigationshilfe, aber kein sicherer Ersatz für den konkreten Boy-Aufruf.

Der untersuchte Boy-Overlaypfad wählt seine Modellinstanz so:

```text
model_index = s8[object+0x3A]
model_array = u32_be[object+0x6C]
instance    = u32_be[model_array + 4*model_index]
```

Am gewählten Breakpoint ist diese Kette bereits aufgelöst:

```text
S4              = instance
u32_be[SP+0xF8] = object
u32_be[SP+0x74] = racer
```

## Warum Animationszeit und Selector-Liste nicht allein genügen

Für einen ausdrücklich ausgewählten No-Blend-Fall bestimmen der aktuelle
Animationsindex, die effektive Zeit bei `instance+0x28` und die Selector-Liste die lokalen Animationsmatrizen. Die finalen
Runtime-Matrizen enthalten zusätzlich die Objekt-/Weltmatrix. Außerdem muss
der Capture selbst belegen, welcher Index aktiv und dass der Blendzähler null ist.

Pflichtdaten sind deshalb:

1. Instanzbytes `S4+0x00..0x7F`;
2. Selectorbytes ab `racer+0x240` bis einschließlich `0x1000`;
3. die bei diesem Aufruf verwendete 64-Byte-Objektmatrix bei `SP+0x90`;
4. Capture-PC und Pointerprovenienz.

Die finalen Matrizen sind für die direkte Gegenprüfung optional, aber stark
empfohlen. `delayDat` sowie `racer+0x540/+0x580` sind Diagnose- und
Provenienzdaten. Sie werden zur Rekonstruktion nicht benötigt, weil effektive Zeit und
fertige Selector-Liste ihren Effekt bereits enthalten.

### Dekodierte Felder des Instanzdumps

| Feld | Offset | Typ, Big Endian | Erwartung im Zielcapture |
| --- | ---: | --- | --- |
| Bufferindex | `instance+0x0B` | `s8` | `0` oder `1` |
| Matrixpointer | `instance+0x10/+0x14` | `u32` | RAM-Pointer |
| aktueller Animationsindex | `instance+0x24` | `u16` | gültiger Boy-Katalogindex |
| sekundärer/vorheriger Index | `instance+0x26` | `u16` | bei Blend live; bei No-Blend möglicherweise alt |
| effektive aktuelle Zeit | `instance+0x28` | `f32` | innerhalb der Zeitdomäne des aktuellen Clips |
| unskalierte aktuelle Zeit | `instance+0x38` | `f32` | endlich; Sample-Einheiten, keine normierte Phase |
| Blendstep | `instance+0x5C` | `s16` | Diagnosewert |
| Blendzähler | `instance+0x5E` | `s16` | exakt `0` |

Selector und Wert sind `u16`/`s16` bei `racer+0x240`, normal vier Byte pro
Eintrag. Operation `0x3000` konsumiert ein zusätzliches `s16`-Zielfeld;
`0x1000` beendet die Liste. Die Matrixdatei enthält 21 Slots à `0x40` Byte,
aber nur 252 relevante Big-Endian-`f32`: drei Werte pro 16-Byte-Zeile. Das
vierte Wort jeder Zeile ist unbenutzt und darf nicht als Matrixfloat geprüft
werden. Der erweiterte Racerdump liefert `u32 +0x540` und
`s32 +0x580`; `delayDat` ist ein Big-Endian-`s32`.

## Matrixspeicher

`modGenAnimMatrices` toggelt `s8[instance+0x0B]` mit XOR 1. Danach wählt es:

```text
buffer_index = s8[instance+0x0B]
matrix_base  = u32_be[instance+0x10 + 4*buffer_index]
```

Der an `gen_anim_data` übergebene Pointer zeigt auf diesen Basiswert. Die
Ausgabe besteht aus 21 aufeinanderfolgenden 64-Byte-Matrizen:

```text
matrix_address = matrix_base + matrix_id * 0x40
Gesamtgröße     = 21 * 0x40 = 0x540 Bytes
```

Jeder Slot enthält eine 4x3-Affinmatrix in der bestätigten
Zeilenvektor-/Row-Major-Darstellung. Die Werte liegen pro Zeile bei `+0/+4/+8`;
das vierte Wort bei `+0xC` ist unbenutzt. Es handelt sich um Heap-Puffer der
Modellinstanz. Beide Double-Buffer bleiben über den Funktionsaufruf hinaus
erhalten; am Breakpoint ist der aktuelle Puffer gerade vollständig erzeugt.

## Exakte Capture-Schritte für Marco

1. Die gepinnte US-ROM starten und Boy/Juno in den gewünschten stabilen
   No-Blend-Zustand bringen.
2. Einen Execute-Breakpoint auf RAM `0x8003D908` setzen.
3. Beim Treffer PC, `S4` und `SP` notieren.
4. `object=u32_be[SP+0xF8]` und `racer=u32_be[SP+0x74]` ablesen.
   `s16_be[object+0x48]` muss `1` sein; auf dem Bildschirm muss der
   kontrollierte Charakter Boy/Juno sein. Bei einem anderen Treffer
   weiterlaufen lassen.
5. Diese Bereiche binär dumpen:

| Datei | Start | Länge |
| --- | --- | ---: |
| Instanz | `S4` | `0x80` |
| Objektmatrix | `SP+0x90` | `0x40` |
| Selector-Liste | `racer+0x240` | `0x80` |
| Runtime-Matrizen | `matrix_base` | `0x540` |
| erweiterter Racerzustand | `racer+0x540` | `0x44` |
| `delayDat` | absolut `0x800A3374` | `4` |

6. `buffer_index=s8[S4+0x0B]` und anschließend
   `matrix_base=u32_be[S4+0x10+4*buffer_index]` bestimmen. Der Matriziendump
   muss genau dort beginnen.
7. Pointer und Capturezustand als `key=value` in `capture.txt` notieren.
8. Den verallgemeinerten Validator ausführen:

```powershell
python -B jfg-re/tools/validate_boy_runtime_capture.py `
  --rom rom/jetforcegemini.z64 `
  --boy jfg-re/data/generated/props-us-verified/bins/0220_Boy.bin `
  --capture-dir jfg-re/research/boy/runtime-captures/CAPTURE-NAME `
  --output jfg-re/research/boy/runtime-captures/CAPTURE-NAME/validation.json
```

Die `0x80` Selectorbytes sind bewusst ein leicht dumpbarer Oberbereich. Der
Importer verarbeitet nur bis einschließlich des ersten `0x1000`-Terminators.

## Offline-Prüfung

Der Validator:

- prüft ROM-, Boy-, Capture-PC- und Pointerprovenienz;
- liest Index `instance+0x24`, effektive Zeit `+0x28`, unskalierte Zeit
  `+0x38`, Blendstep `+0x5C` und
  Blendzähler `+0x5E` Big Endian;
- akzeptiert jeden katalogisierten Boy-Index, erfordert für den derzeitigen
  A/B/C-Vergleich aber `blend_counter==0`;
- dekodiert die vollständige Selector-Liste einschließlich der belegten
  Operationen `0x0000`, `0x2000`, `0x3000`, `0x4000` und `0x5000`;
- verwendet den bestehenden Decoder des aus dem Capture abgeleiteten Clips;
- ordnet die gespeicherten Eulerkomponenten als A/third/second den
  A/B/C-Eingängen des vorhandenen Matrixhelfers zu;
- komponiert die erfasste Objektmatrix und rekonstruiert alle 21 Matrizen;
- transformiert die 638 aktiven Sourcevertices;
- vergleicht die 252 geschriebenen 4x3-Matrixelemente mit maximalem,
  mittlerem und per-Matrix-Fehler.

Ohne die fünf Pflichtdateien `capture.txt`, `instance_n64.bin`,
`object_matrix_n64.bin`, `selectors_n64.bin` und `matrices_n64.bin` bricht der
Validator ab. Host-Raw- und Racerdumps sind optionale Zusatzprüfungen.

## Erkenntnisstatus

### VERIFIED

- Playerlisten-Globals, Objekt→Racer-Pointer und Boy-Aufrufpointer;
- Capturepunkt `0x8003D908` und Stack-/Registerbezüge;
- Double-Buffer-Auswahl und 21 × 64 Byte Matrixspeicher;
- effektive Zeit bei `+0x28`, unskalierte Samplezeit bei `+0x38`,
  Objektmatrix und Selector-Liste;
- 4x3-Big-Endian-Matrixdarstellung in `0x40`-Byte-Slots;
- gespeicherte Eulerkomponenten A/C/B und Übergabe als A/B/C durch
  `[stored[0], stored[2], stored[1]]`;
- numerische Übereinstimmung des Index-19-Captures: 21/21 Matrizen,
  maximaler Fehler `7.62939453125e-06`.

### Weiterhin UNKNOWN

- semantischer Gameplayname von Animation 19 / ID 1022;
- Gameplaybedeutung des Zeitmultiplikators bei `object+0x28`;
- Runtimewerte und numerische Übereinstimmung künftiger Captures der Indizes
  3, 32 und 35.

Der reale Index-19-Capture ist das Regressionfixture für Parser und Rechenweg.

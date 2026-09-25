# Boy animation runtime timing

Scope: Prop 220 Boy in the pinned US Z64 ROM. This investigation follows only
`viFrameSync`, `delayDat`, `objAnimDframe`, the Boy Overlay-16 state cases, and
the phase-to-sample conversion in `modGenAnimMatrices`.

## VERIFIED runtime time chain

The advancing cursor is the normalized phase at **game object `+0x28`**:

```text
phase_next = phase + delayDat * state_scale
```

`objAnimDframe` (`0x8001138C`) performs the multiplication at `0x80011398`,
adds it to object `+0x28` at `0x800113AC`, and then applies loop or endpoint
handling. Looping clips wrap in `[0,1)`; non-looping clips clamp at an endpoint.

`modGenAnimMatrices` then converts normalized phase to technical sample time:

```text
clip_span = sample_count       for a loop clip
clip_span = sample_count - 1   for a non-loop clip

effective_sample_time = clip_span * phase
```

At `0x8003D3F8..0x8003D428`, the clip span is read from model instance `+0x38`,
the normalized phase is read from game object `+0x28`, and their product is
stored at model instance `+0x28` for `gen_anim_data`.

This distinguishes two different fields that happen to share offset `+0x28`:

- **game object `+0x28`:** advancing normalized phase;
- **model instance `+0x28`:** effective technical sample position consumed by
  `gen_anim_data`.

Model instance `+0x38` is the unscaled clip-time span in sample units. It is a
phase-to-sample multiplier, not an independently advancing cursor. The real
index-19 capture has span `39.0`, phase approximately `0.77999956`, and
effective time `30.41998291`, exactly satisfying this relationship.

Away from wrap/clamp boundaries, one update therefore advances:

```text
delta_phase  = delayDat * state_scale
delta_sample = clip_span * delayDat * state_scale
```

## VERIFIED VI timing

`viFrameSync` starts its count at one and increments it for additional queued
VI messages. Its return value is stored in `delayDat` at RAM `0x800A3374` and
passed unchanged through the object/player tick path to Boy. Values above six
are clamped to six; a debug path forces two.

`delayDat` is an elapsed VI-tick count, so delayed game updates advance the
phase by the number of elapsed video ticks rather than by one update. No
PAL/NTSC compensation was found in this path. For the pinned US ROM, Forge's
Game Timing converts VI ticks using nominal NTSC `60 VI/s`. The tick formulas
are code facts; the 60 Hz seconds conversion is explicitly nominal.

## VERIFIED Boy state timing

The Overlay-16 function loads a per-index base factor and may modify it in the
selected state case. The complete 52-entry jump table at Overlay-16
`0x01005120..0x01005B74` was followed through its state cases to the common
`objAnimDframe` call at `0x01005B54..0x01005B60`. Index 51 bypasses the
`index < 51` switch and reaches that same call with its table factor unchanged.

The resulting catalogue contains:

- 31 `FIXED` entries;
- 20 `MOVEMENT_DEPENDENT` entries;
- one `STATE_DEPENDENT` entry;
- no `OTHER_RUNTIME_DEPENDENT` or `UNKNOWN` Boy entries.

The two movement formulas are:

```text
movement_max     = max(abs(racer+0x04), abs(racer+0x10))
movement_lateral = abs(racer+0x10)
```

Index 13 uses its fixed table factor when the tested runtime flag bit `0x10` is
clear and twice that factor when the bit is set. The exact semantic name of the
flag remains unknown; its effect on timing is directly established by the
state-case data flow.

Rates below use nominal `60 VI/s`. Movement-dependent rows show the rate for a
runtime movement input of `1.0`. Index 13 shows both flag states.

| Index | ID | Span | Category | State scale per VI tick | Samples/s at nominal input | Case |
| ---: | ---: | ---: | --- | --- | ---: | --- |
| 0 | 1026 | 16 | MOVEMENT_DEPENDENT | `0.015 * movement_max` | 14.4 | `0x010051D8` |
| 1 | 1027 | 16 | MOVEMENT_DEPENDENT | `0.009 * movement_max` | 8.64 | `0x010052FC` |
| 2 | 1028 | 16 | MOVEMENT_DEPENDENT | `0.0075 * movement_max` | 7.2 | `0x01005388` |
| 3 | 1025 | 16 | MOVEMENT_DEPENDENT | `0.014 * movement_max` | 13.44 | `0x010053F4` |
| 4 | 1033 | 16 | MOVEMENT_DEPENDENT | `0.0175 * movement_max` | 16.8 | `0x01005504` |
| 5 | 1039 | 31 | FIXED | `0.01` | 18.6 | `0x01005530` |
| 6 | 1040 | 20 | FIXED | `0.02` | 24 | `0x01005B50` |
| 7 | 1041 | 21 | FIXED | `0.0175` | 22.05 | `0x01005B50` |
| 8 | 1038 | 21 | FIXED | `0.0334` | 42.084 | `0x0100556C` |
| 9 | 1042 | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | 11.04 | `0x0100559C` |
| 10 | 1043 | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | 11.04 | `0x0100559C` |
| 11 | 1031 | 25 | FIXED | `0.0175` | 26.25 | `0x010056D4` |
| 12 | 1036 | 13 | FIXED | `0.028` | 21.84 | `0x0100571C` |
| 13 | 1029 | 14 | STATE_DEPENDENT | `0.02`, or `0.04` when flag bit `0x10` is set | 16.8 / 33.6 | `0x010057AC` |
| 14 | 1030 | 10 | FIXED | `0.005` | 3 | `0x010057F8` |
| 15 | 1044 | 5 | FIXED | `0.025` | 7.5 | `0x01005820` |
| 16 | 1019 | 49 | FIXED | `0.005` | 14.7 | `0x0100584C` |
| 17 | 1020 | 39 | FIXED | `0.005` | 11.7 | `0x0100584C` |
| 18 | 1021 | 49 | FIXED | `0.005` | 14.7 | `0x0100584C` |
| 19 | 1022 | 39 | FIXED | `0.005` | 11.7 | `0x0100584C` |
| 20 | 1023 | 39 | FIXED | `0.005` | 11.7 | `0x0100584C` |
| 21 | 1051 | 25 | FIXED | `0.017` | 25.5 | `0x01005948` |
| 22 | 1035 | 8 | FIXED | `0.005` | 2.4 | `0x010059A0` |
| 23 | 1070 | 19 | FIXED | `0.01` | 11.4 | `0x01005B50` |
| 24 | 1048 | 8 | FIXED | `0.01` | 4.8 | `0x01005B50` |
| 25 | 1050 | 10 | FIXED | `0.0334` | 20.04 | `0x01005B50` |
| 26 | 1054 | 16 | MOVEMENT_DEPENDENT | `0.014 * movement_max` | 13.44 | `0x010053F4` |
| 27 | 1053 | 5 | FIXED | `0.005` | 1.5 | `0x0100584C` |
| 28 | 1055 | 16 | MOVEMENT_DEPENDENT | `0.015 * movement_max` | 14.4 | `0x010051D8` |
| 29 | 1056 | 16 | MOVEMENT_DEPENDENT | `0.009 * movement_max` | 8.64 | `0x010052FC` |
| 30 | 1057 | 16 | MOVEMENT_DEPENDENT | `0.0075 * movement_max` | 7.2 | `0x01005388` |
| 31 | 1058 | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | 11.04 | `0x0100559C` |
| 32 | 1059 | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | 11.04 | `0x0100559C` |
| 33 | 1060 | 3 | FIXED | `0.06` | 10.8 | `0x010057F8` |
| 34 | 1063 | 16 | MOVEMENT_DEPENDENT | `0.0075 * movement_max` | 7.2 | `0x01005388` |
| 35 | 1062 | 16 | MOVEMENT_DEPENDENT | `0.009 * movement_max` | 8.64 | `0x010052FC` |
| 36 | 1061 | 16 | MOVEMENT_DEPENDENT | `0.015 * movement_max` | 14.4 | `0x010051D8` |
| 37 | 1066 | 16 | MOVEMENT_DEPENDENT | `0.006 * movement_max` | 5.76 | `0x01005A04` |
| 38 | 1067 | 16 | FIXED | `0.004` | 3.84 | `0x010059C8` |
| 39 | 1068 | 7 | FIXED | `0.01` | 4.2 | `0x01005B18` |
| 40 | 1045 | 15 | FIXED | `0.014` | 12.6 | `0x01005B50` |
| 41 | 1046 | 14 | FIXED | `0.025` | 21 | `0x01005AB0` |
| 42 | 1047 | 16 | FIXED | `0.02` | 19.2 | `0x01005AE4` |
| 43 | 1069 | 75 | FIXED | `0.003` | 13.5 | `0x01005A44` |
| 44 | 1034 | 16 | MOVEMENT_DEPENDENT | `0.0175 * movement_max` | 16.8 | `0x01005504` |
| 45 | 1024 | 54 | FIXED | `0.005` | 16.2 | `0x0100584C` |
| 46 | 1052 | 19 | FIXED | `0.017` | 19.38 | `0x01005948` |
| 47 | 1064 | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | 11.04 | `0x0100559C` |
| 48 | 1065 | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | 11.04 | `0x0100559C` |
| 49 | 1032 | 25 | FIXED | `0.0175` | 26.25 | `0x010056F8` |
| 50 | 1037 | 13 | FIXED | `0.028` | 21.84 | `0x01005764` |
| 51 | 1071 | 2 | FIXED | `0.01` | 1.2 | default to `0x01005B50` |

Index 43 is selected by `controlPlayerOpenChest`; its state case retains the
fixed `0.003` factor. Its complete 75-sample phase span therefore takes
`1 / (0.003 * 60) = 5.555...` nominal seconds at 1x.

There is no single global sample rate: a common VI-tick mechanism feeds
state-specific factors, and several states multiply those factors by live
movement. Clip span additionally converts normalized phase to sample units.

## Forge timing modes

### Technical

```text
at Movement / Speed 1.0:
1 viewer second = 1 technical JFG sample
```

The shared slider multiplies that technical rate. Therefore the 1:1 statement
is not universal and does not describe every current preview/export setting.

### Game Timing

For all 52 verified Boy states, Forge uses:

```text
samples_per_second = clip_span * state_scale * 60
```

Forge exposes one `Movement / Speed` slider from `1.0` through `5.0` in `0.1`
steps. For the 20 movement-dependent indices its value is the simulated
`movement_max` or `movement_lateral` input and is consumed exactly once by the
verified formula. For fixed indices it multiplies the verified rate. For index
13 the verified flag remains independent and the slider multiplies the result
after the clear/set flag factor. Technical mode treats the slider as a
technical-sample-rate multiplier. Fractional technical sample positions remain
available through the scrubber.

## Remaining UNKNOWN context

- The semantic name and owner of the runtime flag whose bit `0x10` doubles
  index 13. Its timing effect is VERIFIED.
- Whether a PAL build uses another caller-level compensation outside this
  traced US-ROM path.
- Live movement values for an isolated clip without a runtime capture.

## Export boundary

Current-animation glTF export receives the same immutable timing context as the
Forge preview. Technical sample positions remain the keys used to evaluate
poses, while exported timestamps are:

```text
gltf_seconds = technical_sample_position / effective_samples_per_second
```

The effective rate comes from the same shared function used by playback, so a
movement input cannot be applied a second time in the exporter. The state flag
and timing-mode selection are captured explicitly in animation metadata.

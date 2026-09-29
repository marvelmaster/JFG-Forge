# Characters and evidence levels

JFG Forge opens 25 models, in three groups. The game's object table lists 31
"player" definitions; the other six are the multiplayer versions of Juno, Vela
and Lupus, which are not included yet (see the end of this page).

## Evidence labels

Every fact JFG Forge shows about a model carries one of these labels.

| Label | Meaning |
|---|---|
| **VERIFIED** | Read from ROM data and confirmed in the game's own code (and, where noted, in runtime captures). |
| **LIKELY** | Strongly supported by ROM data and static code, but no runtime capture proves it. |
| **UNKNOWN** | Not understood yet. Forge shows it as unknown and never guesses. |

## Campaign

| Character | Prop | Model | Joints | Animations | Game Timing | Weapon set |
|---|---:|---|---:|---|---|---|
| Juno | 220 | `Boy` | 21 | 52 | VERIFIED | BoyGun, joint 6 |
| PowerBoy | 221 | `PowerBoy` | 21 | 52 (same as Juno) | VERIFIED, same as Juno | BoyGun, joint 6 |
| Vela | 218 | `Girl` | 28 | 53 entries, 52 unique | VERIFIED | GirlGun, joint 6 |
| PowerGirl | 219 | `PowerGirl` | 28 | 53 entries, 52 unique (same as Vela) | VERIFIED, same as Vela | GirlGun, joint 6 |
| Lupus | 222 | `Dog` | 27 | 24 (IDs 582 to 605) | VERIFIED | DogGun, joint 16 |
| PowerDog | 223 | `PowerDog` | 18 | 29 entries, 28 unique | VERIFIED, own table | DogGun, joint 7 |

PowerBoy and PowerGirl reuse their normal character's skeleton, animations,
timing and weapon socket, with their own model and textures. PowerDog is a
separate character with its own skeleton and animation data; it is not a Lupus
variant.

## Multiplayer characters

These are the models the game uses for its multiplayer-only characters. All 11
follow one of two existing layouts, so their rig, animations, weapons and timing
come from the campaign character they match.

### Juno's layout (21 joints, 51 animations)

| Character | Prop | Model | Active faces |
|---|---:|---|---:|
| Green Ant | 250 | `MultiGreenAnt` | 307 |
| Red Ant | 253 | `MultiRedAnt` | 307 |
| Tribal Man | 251 | `MultiTribalMan` | 115 |
| Shield Bug | 254 | `MultiShieldBug` | 231 |
| Stag Bug | 255 | `MultiStagBug` | 268 |
| Weevil | 256 | `MultiWeevil` | 232 |
| Cyborg | 257 | `MultiCyborg` | 254 |
| Zombie | 258 | `MultiZombie` | 257 |

Game Timing: Juno's table for animation indices 0 to 50. Weapons: BoyGun (the
nine Props 301 to 309), socket joint 6.

### Vela's layout (28 joints, 52 animations)

| Character | Prop | Model | Active faces |
|---|---:|---|---:|
| Blue Ant | 248 | `MultiBlueAnt` | 337 |
| Yellow Ant | 252 | `MultiYellowAnt` | 337 |
| Tribal Woman | 249 | `MultiTribalWoma` | 135 |

Game Timing: Vela's table for animation indices 0 to 51. Weapons: GirlGun (the
nine Props 283 to 291), socket joint 6.

### Why these follow Juno and Vela

- **Same animation IDs.** Each Juno-layout model's 51 animation IDs equal Juno's
  first 51, in the same order. Each Vela-layout model's 52 IDs equal Vela's
  first 52. Forge refuses to load a model whose IDs differ from the pinned list.
- **Same weapon object.** In the game's object table each player definition
  lists exactly one child object: BoyGun for the Juno-layout models, GirlGun for
  the Vela-layout models.
- **Same socket.** The first vertex-reference record of every model names
  matrix 6, the same joint Juno and Vela use, and Forge attaches the weapon the
  way the game does for them.

Nobody has captured these characters running in the game to confirm that their
controller really uses Juno's or Vela's code, so their **timing and weapon
placement are LIKELY**. Their skeleton, animations and textures decode exactly as
for the campaign characters.

## Hover ships

The four hover ship models that the game defines as player objects, each with a
low-detail version.

| Entry | Props (detailed, low detail) | Active faces |
|---|---|---|
| Yellow Ant Ship | 225, 226 | 192, 62 |
| Red Ant Ship | 228, 229 | 208, 62 |
| Blue Ant Ship | 231, 232 | 192, 62 |
| Green Ant Ship | 234, 235 | 210, 62 |

Each has 8 joints and 2 animations (IDs 779 and 780). Animation 779 is a looping
40-sample motion; animation 780 has no motion data and is just the ship's base
pose. The ships carry no weapon (their player definitions have no child
object). Their Game Timing is **UNKNOWN**: Forge plays them at the technical
rate and says so in the status text. The ship colour comes from the name of the
game's player definition for that model.

## Weapon sets

A weapon set is a child object of the character with nine interchangeable
models. The model is attached rigidly to one joint and is not skinned.

| Set | Props | Slots |
|---|---|---|
| BoyGun | 301 to 309 | Pistol, Automatic, Uzi, Uzi1, ShrinkBeam, Rocket, FlameThrower, Sniper, JunoHand |
| GirlGun | 283 to 291 | Pistol, Automatic, Uzi, Uzi1, ShrinkBeam, Rocket, FlameThrower, Sniper, VelaHand |
| DogGun | 320 to 328 | DogPistol, DogAutomatic, DogUzi, DogUzi1, DogShrinkBeam, DogRocket, DogFlameThrower, DogSniper, DogGrenade |

The weapon models already contain the gripping hand. The hand slots (Prop 309
for Juno, Prop 291 for Vela) show the character's hand on its own. The joint
numbers are specific to each character; joint 6 is not a universal weapon
socket.

## Textures

On all 25 models every texture that is actually drawn decodes. A few models
carry one extra texture record in a format Forge does not decode (the known
`0x3300` record and a few others); the game never draws it on these models, so
nothing is missing from the pictures. The model info panel still counts such a
record as "UNKNOWN".

## Not included

- The six multiplayer versions of Juno, Vela and Lupus (`MultiGirl`, `MultiBoy`,
  `MultiDog`, `MultiPowerGirl`, `MultiPowerBoy`, `MultiPowerDog`, Props 236 to
  246) with their lower-detail weapon sets.
- Shadow and low-detail copies of the campaign characters.
- Non-player characters (tribal villagers, the Mizar boss, Floyd) and the other
  ~880 props: enemies, vehicles, doors and level objects.

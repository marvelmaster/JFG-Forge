# Characters and evidence levels

## Evidence labels

Every fact JFG Forge shows about a character carries one of these labels.

| Label | Meaning |
|---|---|
| **VERIFIED** | Read from ROM data and confirmed in the game's own code (and, where noted, in runtime captures). |
| **LIKELY** | Strongly supported by ROM data and static code, but no runtime capture proves it. |
| **UNKNOWN** | Not understood yet. Forge shows it as unknown and never guesses. |

## Supported characters

| Character | Prop | Model | Joints | Animations | Game Timing | Weapon set |
|---|---:|---|---:|---|---|---|
| Juno | 220 | `Boy` | 21 | 52 | VERIFIED | BoyGun, joint 6 |
| PowerBoy | 221 | `PowerBoy` | 21 | 52 (same as Juno) | VERIFIED, same as Juno | BoyGun, joint 6 |
| Vela | 218 | `Girl` | 28 | 53 entries, 52 unique | VERIFIED | GirlGun, joint 6 |
| PowerGirl | 219 | `PowerGirl` | 28 | 53 entries, 52 unique (same as Vela) | VERIFIED, same as Vela | GirlGun, joint 6 |
| Lupus | 222 | `Dog` | 27 | 24 (IDs 582 to 605) | VERIFIED | DogGun, joint 16 |
| PowerDog | 223 | `PowerDog` | 18 | 29 entries, 28 unique | VERIFIED, own table | DogGun, joint 7 |
| Green Ant | 250 | `MultiGreenAnt` | 21 | 51 | LIKELY | BoyGun, joint 6, LIKELY |

PowerBoy and PowerGirl reuse their normal character's skeleton, animations,
timing and weapon socket, with their own model and textures. PowerDog is a
separate character with its own skeleton and animation data; it is not a Lupus
variant.

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

## The Green Ant

The Green Ant is the multiplayer ant (Prop 250, `MultiGreenAnt`). Its status is
LIKELY because it borrows Juno's data:

- Its 51 animation IDs are identical to the first 51 of Juno's 52, in the same
  order.
- It has Juno's 21-joint layout, and its weapon socket sits at the same place as
  Juno's.
- The game's object table gives its player definition a single child, the same
  BoyGun set Juno uses.
- Game Timing therefore uses Juno's per-animation speed table for those 51
  animations.

Nobody has captured the ant running in the game to confirm that its controller
really uses Juno's code, which is why these three items stay LIKELY. The other
multiplayer ants are not supported yet: the Red Ant has the same layout as the
Green Ant, while the Blue and Yellow Ants use a 28-joint, Vela-style layout.

## Not supported yet

The remaining ~900 props in the ROM (enemies, NPCs, vehicles, levels, doors)
cannot be opened in Forge. The character loader is written for the seven
models above.

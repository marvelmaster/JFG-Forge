"""Names for character animations, with the evidence behind each one.

The ROM stores no animation names. Forge names a clip only from what the game
code shows about it, and says how sure it is:

* **VERIFIED basis** - findings from reading the player controllers
  (overlays 15, 16 and 17): the clip index is chosen by a particular rule. Examples:
  index 43 is selected by the chest-opening code, indexes 16-19 are the idle
  states chosen below a movement threshold of 0.1, indexes 9 and 10 are chosen by
  the sign of the sideways speed.
* **LIKELY** - the controller runs one shared piece of code for several clip
  indexes (the jump-table cases share an address). Clips that share the code of a
  named clip get its name plus the stance set they belong to.
* **UNKNOWN** - everything else is called ``Action N``; nothing is claimed.

Names apply to the characters whose clip IDs match the controller tables: Juno
and the Juno-like multiplayer characters, Vela and the Vela-like ones, and Lupus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from jfg_forge.core.asset_types import EvidenceStatus
from jfg_forge.core.roster import TIMING_JUNO_LIKE, TIMING_VELA_LIKE
from jfg_forge.gui import runtime_timing as timing


@dataclass(frozen=True)
class AnimationName:
    name: str
    status: EvidenceStatus
    basis: str


def _action(index: int) -> AnimationName:
    return AnimationName(f"Action {index}", EvidenceStatus.UNKNOWN, "no rule found that names this clip")


def _grouped(
    case_address: Mapping[int, str] | tuple[str, ...],
    count: int,
    groups: dict[str, tuple[str, EvidenceStatus, str]],
    verified: dict[int, tuple[str, str]],
    sets: tuple[tuple[range, str], ...],
) -> dict[int, AnimationName]:
    """Name clips by their controller case; ``verified`` overrides by index."""
    addresses = case_address if isinstance(case_address, tuple) else tuple(case_address[i] for i in range(count))
    names: dict[int, AnimationName] = {}
    for index in range(count):
        if index in verified:
            label, basis = verified[index]
            names[index] = AnimationName(label, EvidenceStatus.VERIFIED, basis)
            continue
        group = groups.get(addresses[index])
        if group is None:
            names[index] = _action(index)
            continue
        label, status, basis = group
        suffix = next((f" ({name})" for span, name in sets if index in span), "")
        same = [i for i in range(count) if addresses[i] == addresses[index] and i != index]
        note = f"{basis}; shares its controller code with clip{'s' if len(same) > 1 else ''} {', '.join(map(str, same))}" if same else basis
        names[index] = AnimationName(label + suffix, status, note)
    return _number_duplicates(names)


def _number_duplicates(names: dict[int, AnimationName]) -> dict[int, AnimationName]:
    """Give clips that ended up with the same name a running number."""
    totals: dict[str, int] = {}
    for item in names.values():
        totals[item.name] = totals.get(item.name, 0) + 1
    seen: dict[str, int] = {}
    result = {}
    for index in sorted(names):
        item = names[index]
        if totals[item.name] > 1:
            seen[item.name] = seen.get(item.name, 0) + 1
            item = AnimationName(f"{item.name} {seen[item.name]}", item.status, item.basis)
        result[index] = item
    return result


_L = EvidenceStatus.LIKELY

_JUNO_GROUPS = {
    "0x010051D8": ("Walk", _L, "movement-driven base cycle, the first clip of the state machine"),
    "0x010052FC": ("Run", _L, "selected from the base state when movement exceeds 1.75"),
    "0x01005388": ("Move 3", _L, "movement-driven cycle in the same state group as walk and run"),
    "0x010053F4": ("Move 4", _L, "movement-driven cycle, selected from the base state by a flag"),
    "0x01005504": ("Move 5", _L, "movement-driven cycle in the same state group"),
    "0x0100559C": ("Strafe", _L, "sideways-speed driven"),
    "0x0100584C": ("Idle-like", _L, "same code as the verified idle clips 16-19"),
}
_JUNO_VERIFIED = {
    9: ("Strafe (side A)", "chosen from the base state when the sideways speed dominates; its sign picks 9 or 10"),
    10: ("Strafe (side B)", "chosen from the base state when the sideways speed dominates; its sign picks 9 or 10"),
    16: ("Idle 1", "one of the idle states 16-19, picked below movement threshold 0.1"),
    17: ("Idle 2", "one of the idle states 16-19, picked below movement threshold 0.1"),
    18: ("Idle 3", "one of the idle states 16-19, picked below movement threshold 0.1"),
    19: ("Idle 4", "one of the idle states 16-19, picked below movement threshold 0.1"),
    43: ("Open chest", "selected by controlPlayerOpenChest; checked at phases 0.15 and 0.53"),
}
_VELA_GROUPS = {
    "0x00F05400": ("Walk", _L, "movement-driven base cycle, the first clip of the state machine"),
    "0x00F054FC": ("Run", _L, "second movement state, same layout as Juno's run"),
    "0x00F05580": ("Move 3", _L, "movement-driven cycle in the same state group as walk and run"),
    "0x00F055E4": ("Move 4", _L, "movement-driven cycle in the same state group"),
    "0x00F056D0": ("Move 5", _L, "movement-driven cycle in the same state group"),
    "0x00F05770": ("Strafe", _L, "sideways-speed driven"),
    "0x00F059E8": ("Idle-like", _L, "shared idle-state code"),
}
_LUPUS_GROUPS = {
    "0x01104D48": ("Movement cycle", _L, "movement-driven clips 0-3 share one state group"),
}


def _juno_names() -> dict[int, AnimationName]:
    names = _grouped(timing._CASE_ADDRESS, 51, _JUNO_GROUPS, _JUNO_VERIFIED,
                     ((range(26, 33), "set B"), (range(34, 49), "set C")))
    names[51] = _action(51)
    return names


def _vela_names() -> dict[int, AnimationName]:
    return _grouped(timing._VELA_CASE_ADDRESS, 53, _VELA_GROUPS, {},
                    ((range(27, 34), "set B"), (range(38, 44), "set C")))


def _lupus_names() -> dict[int, AnimationName]:
    return _grouped(timing._LUPUS_CASE_ADDRESS, 24, _LUPUS_GROUPS, {}, ())


_TABLES = {"juno": _juno_names, "vela": _vela_names, "lupus": _lupus_names}
_CACHE: dict[str, dict[int, AnimationName]] = {}


def names_for(family: str) -> Mapping[int, AnimationName]:
    """Names by clip index for ``juno``, ``vela`` or ``lupus`` (empty for anything else)."""
    if family not in _TABLES:
        return {}
    if family not in _CACHE:
        _CACHE[family] = _TABLES[family]()
    return _CACHE[family]


def family_for(key: str, kind: str, timing_family: str) -> str:
    """Which name table a roster entry uses ('' when its clips are not covered)."""
    if key == "Juno" or timing_family == TIMING_JUNO_LIKE:
        return "juno"
    if key == "Vela" or timing_family == TIMING_VELA_LIKE:
        return "vela"
    if key == "Lupus":
        return "lupus"
    return ""


__all__ = ["AnimationName", "family_for", "names_for"]

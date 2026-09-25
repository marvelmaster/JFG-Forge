"""Qt-free technical metadata for the Boy animation browser.

Gameplay contexts are a structured transcription of the entries classified as
``VERIFIED GAMEPLAY CONTEXT`` in
``research/boy/boy-animation-identification.md``.  They are display evidence,
not animation names.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from jfg_re.forge_types import AnimationClip, EvidenceStatus, Pose


UNKNOWN_CONTEXT = "UNKNOWN"


@dataclass(frozen=True)
class AnimationResearchContext:
    text: str
    status: EvidenceStatus


VERIFIED_GAMEPLAY_CONTEXTS: Mapping[int, AnimationResearchContext] = MappingProxyType(
    {
        0: AnimationResearchContext(
            "Movement-dependent Boy state; progress scales with "
            "max(abs(racer+4), abs(racer+0x10)).",
            EvidenceStatus.VERIFIED,
        ),
        1: AnimationResearchContext(
            "Selected from state 0 when movement magnitude exceeds 1.75.",
            EvidenceStatus.VERIFIED,
        ),
        3: AnimationResearchContext(
            "Selected from state 0 when racer+0x569 is set; that field's "
            "meaning remains uninterpreted.",
            EvidenceStatus.VERIFIED,
        ),
        9: AnimationResearchContext(
            "Selected from state 0 when abs(racer+0x10) dominates; its sign "
            "chooses index 9 or 10. Also observed as an initial state.",
            EvidenceStatus.VERIFIED,
        ),
        10: AnimationResearchContext(
            "Selected from state 0 when abs(racer+0x10) dominates; its sign "
            "chooses index 9 or 10.",
            EvidenceStatus.VERIFIED,
        ),
        16: AnimationResearchContext(
            "One of states 16-19 selected below movement threshold 0.1 by "
            "established flag/random branches; also observed as an initial state.",
            EvidenceStatus.VERIFIED,
        ),
        17: AnimationResearchContext(
            "One of states 16-19 selected below movement threshold 0.1 by "
            "established flag/random branches.",
            EvidenceStatus.VERIFIED,
        ),
        18: AnimationResearchContext(
            "One of states 16-19 selected below movement threshold 0.1 by "
            "established flag/random branches.",
            EvidenceStatus.VERIFIED,
        ),
        19: AnimationResearchContext(
            "One of states 16-19 selected below movement threshold 0.1 by "
            "established flag/random branches.",
            EvidenceStatus.VERIFIED,
        ),
        43: AnimationResearchContext(
            "controlPlayerOpenChest selects index 43 for subtypes 1/5; "
            "controlPlayerOpeningChest checks this index at phase limits 0.15/0.53.",
            EvidenceStatus.VERIFIED,
        ),
    }
)


@dataclass(frozen=True)
class AnimationBrowserEntry:
    animation_index: int
    animation_id: int
    sample_count: int
    loop: bool
    sample_stride_bytes: int
    root_widths_xyz: tuple[int, int, int]
    gameplay_context: str
    context_status: EvidenceStatus

    @property
    def has_dynamic_root_translation(self) -> bool:
        return any(self.root_widths_xyz)

    @property
    def root_translation_description(self) -> str:
        widths = "/".join(str(value) for value in self.root_widths_xyz)
        kind = "dynamic" if self.has_dynamic_root_translation else "static base only"
        return f"{kind}; X/Y/Z widths {widths} bits"


@dataclass(frozen=True)
class SampleDisplay:
    technical_time: float
    current_sample: int
    next_sample: int
    fraction_10bit: int

    @property
    def fraction(self) -> float:
        return self.fraction_10bit / 1024.0


def research_context(animation_index: int) -> AnimationResearchContext:
    return VERIFIED_GAMEPLAY_CONTEXTS.get(
        animation_index,
        AnimationResearchContext(UNKNOWN_CONTEXT, EvidenceStatus.UNKNOWN),
    )


def browser_entry(
    clip: AnimationClip,
    *,
    include_boy_gameplay_context: bool = True,
) -> AnimationBrowserEntry:
    context = (
        research_context(clip.animation_index)
        if include_boy_gameplay_context
        else AnimationResearchContext(UNKNOWN_CONTEXT, EvidenceStatus.UNKNOWN)
    )
    metadata = clip.metadata
    widths = tuple(int(value) for value in metadata["root"]["bit_widths_xyz"])
    if len(widths) != 3:
        raise ValueError(f"Animation {clip.animation_index} has invalid root-width metadata.")
    return AnimationBrowserEntry(
        animation_index=clip.animation_index,
        animation_id=clip.animation_id,
        sample_count=clip.sample_count,
        loop=clip.loop,
        sample_stride_bytes=int(metadata["sample_stride_bytes"]),
        root_widths_xyz=widths,
        gameplay_context=context.text,
        context_status=context.status,
    )


def browser_entries(
    clips: Iterable[AnimationClip],
    *,
    include_boy_gameplay_context: bool = True,
) -> tuple[AnimationBrowserEntry, ...]:
    return tuple(
        browser_entry(
            clip,
            include_boy_gameplay_context=include_boy_gameplay_context,
        )
        for clip in clips
    )


def sample_display(pose: Pose) -> SampleDisplay:
    return SampleDisplay(
        technical_time=pose.time,
        current_sample=pose.current_sample,
        next_sample=pose.next_sample,
        fraction_10bit=pose.fraction_10bit,
    )


__all__ = [
    "AnimationBrowserEntry",
    "AnimationResearchContext",
    "SampleDisplay",
    "UNKNOWN_CONTEXT",
    "VERIFIED_GAMEPLAY_CONTEXTS",
    "browser_entries",
    "browser_entry",
    "research_context",
    "sample_display",
]

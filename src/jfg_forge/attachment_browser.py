"""Qt-free selection and inspection state for character attachments."""

from __future__ import annotations

from dataclasses import dataclass

from jfg_re.forge_types import AttachmentDefinition, EvidenceStatus, LoadedAttachment, SceneAttachment


@dataclass(frozen=True)
class AttachmentBrowserEntry:
    slot: int | None
    prop_id: int | None
    name: str
    expected_active_faces: int | None

    @property
    def label(self) -> str:
        if self.slot is None:
            return "None"
        return f"Slot {self.slot} — Prop{self.prop_id} — {self.name}"


@dataclass(frozen=True)
class AttachmentInspection:
    slot: int
    prop_id: int
    name: str
    active_faces: int
    verified_textures: int
    unknown_textures: int
    transform_status: EvidenceStatus
    attachment_joint_id: int


class AttachmentBrowserController:
    def __init__(self, definition: AttachmentDefinition) -> None:
        self.entries = (AttachmentBrowserEntry(None, None, "None", None),) + tuple(
            AttachmentBrowserEntry(slot.slot, slot.prop_id, slot.name, slot.expected_active_faces)
            for slot in definition.slots
        )
        self._available = {entry.slot for entry in self.entries}
        self.selected_slot: int | None = None

    def select(self, slot: int | None) -> None:
        if slot not in self._available:
            raise KeyError(f"Attachment slot {slot} is unavailable.")
        self.selected_slot = slot


def inspect_attachment(
    loaded: LoadedAttachment,
    scene_attachment: SceneAttachment,
) -> AttachmentInspection:
    if scene_attachment.attachment is not loaded:
        raise ValueError("Scene attachment and loaded attachment asset differ.")
    return AttachmentInspection(
        slot=loaded.slot.slot,
        prop_id=loaded.model.prop_id,
        name=loaded.slot.name,
        active_faces=loaded.model.active_face_count,
        verified_textures=sum(texture.supported for texture in loaded.model.textures),
        unknown_textures=sum(not texture.supported for texture in loaded.model.textures),
        transform_status=scene_attachment.transform_status,
        attachment_joint_id=scene_attachment.parent_joint_id,
    )


__all__ = [
    "AttachmentBrowserController",
    "AttachmentBrowserEntry",
    "AttachmentInspection",
    "inspect_attachment",
]

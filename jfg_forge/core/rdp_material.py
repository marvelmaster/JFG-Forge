"""The three JFG model material states verified in the US ROM.

This is a deliberately bounded translation of the texDPTextureX state table,
not a general RDP emulator.  Unknown table selections remain unknown.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelMaterialState:
    selector: int
    variant: int
    table_address: int
    combine_words: tuple[int, int]
    othermode_words: tuple[int, int]
    alpha_mode: str
    depth_compare: bool
    depth_write: bool
    blend: bool
    uses_texture_alpha: bool
    coverage_to_alpha: bool
    z_mode: int

    @property
    def color_combine(self) -> str:
        """Decode the two evidenced RGB combine-command patterns."""
        return (
            "TEXEL0 * SHADE" if self.selector == 8
            else "TEXEL0 * SHADE * PRIMITIVE"
        )

    @property
    def alpha_combine(self) -> str:
        return "TEXEL0_ALPHA * PRIMITIVE_ALPHA"

    def preview_alpha_mode(self, rgba: bytes | None = None) -> str:
        """A bounded coverage/decal approximation for ordinary image renderers.

        RDP OPA_DECAL is not a glTF alpha mode.  On a coincident model overlay,
        retaining zero-alpha texel RGB hides the underlying textured surface.
        The observed model decals have binary decoded alpha, so a cutout is the
        closest portable representation.  The recorded RDP state stays intact.
        """
        if self.z_mode == 3 and rgba is not None:
            alpha = set(rgba[3::4])
            if alpha and 0 in alpha and alpha <= {0, 255}:
                return "MASK"
        return self.alpha_mode

    def gltf_properties(self, rgba: bytes | None = None) -> dict[str, object]:
        """Represent only what glTF can express; retain RDP details in extras."""
        mode = self.preview_alpha_mode(rgba)
        return {
            "alphaMode": mode,
            **({"alphaCutoff": 0.5} if mode == "MASK" else {}),
            "extras": {
                "jfg_rdp_state_table": f"0x{self.table_address:08X}",
                "jfg_rdp_state_selector": self.selector,
                "jfg_rdp_state_variant": self.variant,
                "jfg_rdp_combine_words": [f"0x{word:08X}" for word in self.combine_words],
                "jfg_rdp_othermode_words": [f"0x{word:08X}" for word in self.othermode_words],
                "jfg_rdp_depth_compare": self.depth_compare,
                "jfg_rdp_depth_write": self.depth_write,
                "jfg_rdp_coverage_to_alpha": self.coverage_to_alpha,
                "jfg_rdp_alpha_mode": self.alpha_mode,
                "jfg_rdp_z_mode": self.z_mode,
                "jfg_rdp_color_combine": self.color_combine,
                "jfg_rdp_alpha_combine": self.alpha_combine,
                "jfg_gltf_alpha_approximation": (
                    "binary decoded-alpha cutout for a coincident decal"
                    if mode == "MASK" else "none"
                ),
                "jfg_gltf_limit": (
                    "glTF cannot encode N64 coverage, decal Z mode, or explicit depth-write state"
                ),
            },
        }


# Actual commands reached by makeModelGfx -> texDPTextureX with the initial
# global model flags 0x8 (0x800A2EC0), a2=a3=0 at the ordinary model call.
# Each entry is keyed by the table selector and the masked/base variant.
_VERIFIED_COMMANDS = {
    (0, 0xB): ((0xFC121603, 0xFFFFFFF8), (0xEF182C0F, 0xC8112078)),
    (8, 0xB): ((0xFC1217FF, 0xFFFFFE38), (0xEF182C0F, 0xC8112D58)),
    (0, 0xF): ((0xFC121603, 0xFFFFFFF8), (0xEF182C0F, 0xC81049D8)),
}


def model_material_state(
    group_flags: int,
    texture_header: bytes | None,
    *,
    global_flags: int = 0x8,
) -> ModelMaterialState | None:
    """Resolve an evidenced textured model state from JFG's selected commands.

    ``None`` explicitly means the path or state was not established.  This
    mapping applies to ordinary model submission with no caller flag override.
    """
    if texture_header is None or len(texture_header) < 28 or texture_header[27] >= 2:
        return None
    texture_flags = int.from_bytes(texture_header[6:8], "big")
    flags = group_flags | texture_flags | global_flags
    selector = ((flags & 0x70) >> 4)
    if flags & 0x80:
        selector += 8
    elif flags & 0x100:
        selector += 16
    elif flags & 0x200:
        selector += 24
    variant = ((2 if selector == 8 else 0) | (flags & 0xF))
    commands = _VERIFIED_COMMANDS.get((selector, variant))
    if commands is None:
        return None
    combine, othermode = commands
    low = othermode[1]
    coverage_to_alpha = bool(low & 0x2000)
    blend = bool(low & 0x4000)
    return ModelMaterialState(
        selector=selector,
        variant=variant,
        table_address=0x800A48E0 + selector * 16,
        combine_words=combine,
        othermode_words=othermode,
        alpha_mode="BLEND" if blend else "OPAQUE",
        depth_compare=bool(low & 0x10),
        depth_write=bool(low & 0x20),
        blend=blend,
        uses_texture_alpha=blend and not coverage_to_alpha,
        coverage_to_alpha=coverage_to_alpha,
        z_mode=(low >> 10) & 3,
    )


def primitive_material_state(model: object, primitive: object) -> ModelMaterialState | None:
    """All groups in a render primitive must have the same effective state."""
    groups = model.groups  # type: ignore[attr-defined]
    textures = {t.texture_index: t for t in model.textures}  # type: ignore[attr-defined]
    states = {
        model_material_state(
            groups[index].render_flags,
            None if primitive.texture_index is None else textures[primitive.texture_index].header,
        )
        for index in primitive.group_indices  # type: ignore[attr-defined]
    }
    if len(states) != 1:
        raise ValueError("One render primitive mixes different JFG RDP material states.")
    return next(iter(states))

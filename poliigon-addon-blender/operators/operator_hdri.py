# #### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


from bpy.types import Operator
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)

from math import pi

from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting

from ..panels import panel_hdri


class POLIIGON_OT_hdri(Operator):
    bl_idname = "poliigon.poliigon_hdri"
    bl_label = _t("HDRI Import")
    bl_description = _t("Import HDRI")
    bl_options = {"GRAB_CURSOR", "BLOCKING", "REGISTER", "INTERNAL", "UNDO"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821  # type: ignore
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821  # type: ignore
    # If do_apply is set True, the sizes are ignored and set internally
    do_apply: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821  # type: ignore
    size: EnumProperty(
        name=_t("Light Texture"),  # noqa F722
        items=panel_hdri.fill_light_size_drop_down,
        description=_t("Change size of light texture."))  # noqa F722  # type: ignore
    # This is not a pure size, but is a string like "4K_JPG"
    size_bg: EnumProperty(
        name=_t("Background Texture"),  # noqa F722
        items=panel_hdri.fill_bg_size_drop_down,
        description=_t("Change size of background texture."))  # noqa F722  # type: ignore
    hdr_strength: FloatProperty(
        name=_t("HDR Strength"),  # noqa F722
        description=_t("Strength of Light and Background textures"),  # noqa F722
        soft_min=0.0,
        step=10,
        default=1.0)  # type: ignore
    rotation: FloatProperty(
        name=_t("Z-Rotation"),  # noqa: F821
        description=_t("Z-Rotation"),  # noqa: F821
        unit="ROTATION",  # noqa: F821
        soft_min=-2.0 * pi,
        soft_max=2.0 * pi,
        # precision needed here, otherwise Redo Last and node show different values
        precision=3,
        step=10,
        default=0.0)  # type: ignore

    def __init__(self, *args, **kwargs):
        """Runs once per operator call before drawing occurs."""
        super().__init__(*args, **kwargs)

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @reporting.handle_operator()
    def execute(self, context):
        return panel_hdri.update_world_nodes(self, context, report_callback=self.report)

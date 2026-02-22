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


from math import pi
import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    PointerProperty,
    StringProperty,
    IntProperty
)

from .modules.poliigon_core.multilingual import _t
from .preferences_map_prefs import MapPrefProperties
from . import ui
from .toolbox import get_context
from .operators.utils_operator import fill_size_drop_down
from .operators import operator_material
from .panels import panel_material, panel_model, panel_hdri


def update_thumb_size(self, context):
    if ui.cTB:
        ui.cTB.settings["thumbsize"] = self.thumbnail_size


def update_assets_per_page(self, context):
    if ui.cTB:
        ui.cTB.settings["page"] = int(self.assets_per_page)


class PoliigonUserProps(bpy.types.PropertyGroup):
    vEmail: StringProperty(
        name="",  # noqa: F722
        description=_t("Your Email"),  # noqa: F722
        options={"SKIP_SAVE"}  # noqa: F821
    )  # type: ignore
    vPassShow: StringProperty(
        name="",  # noqa: F722
        description=_t("Your Password"),  # noqa: F722
        options={"SKIP_SAVE"}  # noqa: F821
    )  # type: ignore
    vPassHide: StringProperty(
        name="",  # noqa: F722
        description=_t("Your Password"),  # noqa: F722
        options={"HIDDEN", "SKIP_SAVE"},  # noqa: F821
        subtype="PASSWORD",  # noqa: F821
    )  # type: ignore
    search: StringProperty(
        name="",  # noqa: F722
        default="",  # noqa: F722
        description=_t("Search Assets"),  # noqa: F722
        options={"SKIP_SAVE"},  # noqa: F821
    )  # type: ignore

    thumbnail_size: EnumProperty(
        name="Thumbnail Size",  # noqa: F722
        description="Set the thumbnail size for assets in the asset browser",  # noqa: F722
        items=[
            ('Tiny', "Tiny", "Tiny thumbnail size", "_BLANK", 1),  # noqa: F821, F722
            ('Small', "Small", "Small thumbnail size", "_BLANK", 2),  # noqa: F821, F722
            ('Medium', "Medium", "Medium thumbnail size", "_BLANK", 3),  # noqa: F821, F722
            ('Large', "Large", "Large thumbnail size", "_BLANK", 4),  # noqa: F821, F722
            ('Huge', "Huge", "Huge thumbnail size", "_BLANK", 5),  # noqa: F821, F722
        ],
        default='Medium',  # noqa: F821
        update=update_thumb_size,
    )  # type: ignore

    assets_per_page: EnumProperty(
        name="Assets Per Page",  # noqa: F722
        description="Set the number of assets to display per page",  # noqa: F722
        items=[
            ('6', "6", "6 assets per page", "_BLANK", 1),  # noqa: F821, F722
            ('8', "8", "8 assets per page", "_BLANK", 2),  # noqa: F821, F722
            ('10', "10", "10 assets per page", "_BLANK", 3),  # noqa: F821, F722
            ('20', "20", "20 assets per page", "_BLANK", 4),  # noqa: F821, F722
        ],
        default='10',  # noqa: F821
        update=update_assets_per_page,
    )  # type: ignore

    # Onboarding survey properties
    onboarding_email_preference: BoolProperty(
        name="",  # noqa: F722
        default=True,  # noqa: F722
        description=_t("Send emails about new assets and product updates"),  # noqa: F722
        options={"SKIP_SAVE"},  # noqa: F821
    )  # type: ignore

    persist_filters: BoolProperty(
        default=False,
        name="Persist filters",
        description="Keep filters on during searches"
    )  # type: ignore


class PoliigonPropsParent(bpy.types.PropertyGroup):
    # Properties common to all asset types
    # TODO(Patrick): Keep in sync with other TODO's below until 2.8x dropped
    asset_name: StringProperty()  # type: ignore
    asset_id: IntProperty(default=-1)  # type: ignore
    asset_type: StringProperty()  # type: ignore
    updating: BoolProperty(default=False)  # type: ignore


# TODO(Andreas): Only HDRI imports or tex as well?
class PoliigonImageProps(PoliigonPropsParent):
    """Properties saved to an individual image"""
    if bpy.app.version < (2, 90):
        # TODO(Patrick): Remove once 2.8x dropped, which doesn't inherit PoliigonPropsParent correctly
        asset_name: StringProperty()  # type: ignore
        asset_id: IntProperty(default=-1)  # type: ignore
        asset_type: StringProperty()  # type: ignore
        updating: BoolProperty(default=False)  # type: ignore
    size: StringProperty()  # type: ignore
    size_bg: StringProperty()  # type: ignore
    hdr_strength: FloatProperty()  # type: ignore
    rotation: FloatProperty()  # type: ignore


def _fill_size_drop_down(self: PoliigonPropsParent, context):
    return fill_size_drop_down(cTB, self.asset_id)


def _update_size(self, context):
    if self.updating:
        return
    if self.size == "WM":
        # Not valid for enum selections currently
        return
    self.updating = True
    self.size_enum = self.size
    self.updating = False


class PoliigonMaterialProps(PoliigonPropsParent):
    """Properties saved to an individual material"""
    if bpy.app.version < (2, 90):
        # TODO(Patrick): Remove once 2.8x dropped, which doesn't inherit PoliigonPropsParent correctly
        asset_name: StringProperty()  # type: ignore
        asset_id: IntProperty(default=-1)  # type: ignore
        asset_type: StringProperty()  # type: ignore
        updating: BoolProperty(default=False)  # type: ignore

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""
        global cTB
        cTB = get_context(addon_version)

    def _update_mapping(self, context):
        if self.updating:
            return
        self.updating = True
        self.mapping_enum = self.mapping
        self.updating = False

    def _update_scale(self, context):
        if self.updating:
            return
        self.updating = True
        panel_material.update_material_scale(self, context)
        self.updating = False

    # Material specific properties
    size: StringProperty(update=_update_size)  # resolution, but kept size name to stay consistent  # type: ignore
    mapping: StringProperty(update=_update_mapping)  # type: ignore
    scale: FloatProperty(default=1, update=_update_scale)  # type: ignore
    displacement: FloatProperty()  # type: ignore
    use_16bit: BoolProperty(default=False)  # type: ignore
    mode_disp: StringProperty()  # type: ignore
    is_backplate: BoolProperty(default=False)  # type: ignore
    map_prefs: PointerProperty(type=MapPrefProperties)  # type: ignore

    # PROPERTIES FOR THE MATERIAL PANEL
    size_enum: EnumProperty(
        name=_t("Texture"),  # noqa: F821
        items=_fill_size_drop_down,
        update=panel_material.update_material_resolution,
        description=_t("Change size of assigned textures.")  # noqa: F722
    )  # type: ignore
    mapping_enum: EnumProperty(
        name=_t("Mapping"),  # noqa: F821
        items=operator_material.UV_OPTIONS,
        default="UV",  # noqa: F821
        update=panel_material.update_material_mapping
    )  # type: ignore


class PoliigonObjectProps(PoliigonPropsParent):
    """Properties saved to an individual object"""
    if bpy.app.version < (2, 90):
        # TODO(Patrick): Remove once 2.8x dropped, which doesn't inherit PoliigonPropsParent correctly
        asset_name: StringProperty()  # type: ignore
        asset_id: IntProperty(default=-1)  # type: ignore
        asset_type: StringProperty()  # type: ignore
        updating: BoolProperty(default=False)  # type: ignore
    size: StringProperty(update=_update_size)  # type: ignore
    lod: StringProperty()  # type: ignore
    use_collection: BoolProperty(default=False)  # type: ignore
    link_blend: BoolProperty(default=False)  # type: ignore

    # Properties for the tweak panel
    size_enum: EnumProperty(
        name=_t("Texture"),  # noqa: F821
        items=_fill_size_drop_down,
        update=panel_model.update_model_resolution,
        description=_t("Change size of assigned textures.")  # noqa: F722
    )  # type: ignore


class PoliigonWorldProps(PoliigonPropsParent):
    """Properties saved to an individual world shader"""
    def _update_size_bg(self, context):
        if self.updating:
            return
        self.updating = True
        self.size_bg_enum = self.size_bg
        self.updating = False

    if bpy.app.version < (2, 90):
        # TODO(Patrick): Remove once 2.8x dropped, which doesn't inherit PoliigonPropsParent correctly
        asset_name: StringProperty()  # type: ignore
        asset_id: IntProperty(default=-1)  # type: ignore
        asset_type: StringProperty()  # type: ignore
        updating: BoolProperty(default=False)  # type: ignore

    size: StringProperty(update=_update_size)  # type: ignore
    size_bg: StringProperty(update=_update_size_bg)  # type: ignore
    hdr_strength: FloatProperty(
        update=panel_hdri.update_hdr_strength,
        soft_min=0.0,
        step=10,
        default=1.0)  # type: ignore
    rotation: FloatProperty(
        update=panel_hdri.update_rotation,
        unit="ROTATION",  # noqa: F821
        soft_min=-2.0 * pi,
        soft_max=2.0 * pi,
        # precision needed here, otherwise Redo Last and node show different values
        precision=3,
        step=10,
        default=0.0)  # type: ignore

    # Properties for the tweak panel
    size_light_enum: EnumProperty(
        name=_t("Texture"),  # noqa: F821
        items=panel_hdri.fill_light_size_drop_down,
        update=panel_hdri.update_hdri_resolution,
        description=_t("Change size of assigned textures.")  # noqa: F722
    )  # type: ignore
    size_bg_enum: EnumProperty(
        name=_t("Background Texture"),  # noqa: F821
        items=panel_hdri.fill_bg_size_drop_down,
        update=panel_hdri.update_hdri_resolution,
        description=_t("Change size of background textures.")  # noqa: F722
    )  # type: ignore


classes = (
    PoliigonImageProps,
    PoliigonMaterialProps,
    PoliigonObjectProps,
    PoliigonWorldProps,
    PoliigonUserProps,
)


def register(addon_version):
    for cls in classes:
        bpy.utils.register_class(cls)
        if hasattr(cls, 'init_context') and callable(cls.init_context):
            cls.init_context(addon_version)

    bpy.types.WindowManager.poliigon_props = PointerProperty(
        type=PoliigonUserProps
    )
    bpy.types.Material.poliigon_props = PointerProperty(
        type=PoliigonMaterialProps
    )
    bpy.types.Object.poliigon_props = PointerProperty(
        type=PoliigonObjectProps
    )
    bpy.types.World.poliigon_props = PointerProperty(
        type=PoliigonWorldProps
    )
    bpy.types.Image.poliigon_props = PointerProperty(
        type=PoliigonImageProps
    )

    bpy.types.Scene.vEditText = StringProperty(default="")
    bpy.types.Scene.vEditMatName = StringProperty(default="")
    bpy.types.Scene.vDispDetail = FloatProperty(default=1.0, min=0.1, max=10.0)

    bpy.types.Material.poliigon = StringProperty(default="", options={"HIDDEN"})
    bpy.types.Object.poliigon = StringProperty(default="", options={"HIDDEN"})
    bpy.types.Object.poliigon_lod = StringProperty(default="", options={"HIDDEN"})
    bpy.types.Image.poliigon = StringProperty(default="", options={"HIDDEN"})

    bpy.context.window_manager.poliigon_props.search = ""
    bpy.context.window_manager.poliigon_props.vEmail = ""
    bpy.context.window_manager.poliigon_props.vPassShow = ""
    bpy.context.window_manager.poliigon_props.vPassHide = ""


def unregister():
    del bpy.types.Scene.vDispDetail
    del bpy.types.Scene.vEditMatName
    del bpy.types.Scene.vEditText

    del bpy.types.Image.poliigon_props
    del bpy.types.World.poliigon_props
    del bpy.types.Object.poliigon_props
    del bpy.types.Material.poliigon_props
    del bpy.types.WindowManager.poliigon_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

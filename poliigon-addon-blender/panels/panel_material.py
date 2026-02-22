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

import os

import bpy
from bpy.props import EnumProperty
from typing import List, Optional

from ..material_import_utils_nodes import create_mapping_node, create_mosaic_node, create_uv_group_node
from ..material_import_utils import create_link, set_value

from ..material_import_cycles import texture_name
from ..modules.poliigon_core.assets import (TextureMap)
from ..modules.poliigon_core.multilingual import _t

from ..operators.utils_operator import fill_size_drop_down
from ..toolbox import get_context
from .. import reporting


_MAPPING_TO_NODENAME = {
    "uv": {
        "name": ".simple_uv_mapping",
        "type": "ShaderNodeGroup"
    },
    "mosaic": {
        "name": "Mosaic_UV_Mapping",
        "type": "ShaderNodeGroup"
    },
    "flat": {
        "name": "Mapping",
        "type": "ShaderNodeMapping"
    },
    "box": {
        "name": "Mapping",
        "type": "ShaderNodeMapping"
    },
    "sphere": {
        "name": "Mapping",
        "type": "ShaderNodeMapping"
    },
    "tube": {
        "name": "Mapping",
        "type": "ShaderNodeMapping"
    }
}

NODE_NAMES_CONVENTION = 1


def update_material_resolution(self, context):
    """ Called automatically everytime material resolution (size) is changed """
    if self.updating or not context.object:
        return
    mat: bpy.types.Material = context.object.active_material
    if not mat:
        return
    self.updating = True

    new_mat_name = mat.name.replace(self.size, self.size_enum)

    asset_data = cTB._asset_index.get_asset(self.asset_id)
    asset_type_data = asset_data.get_type_data()
    workflow = asset_type_data.get_workflow("METALNESS")
    asset_name = asset_data.asset_name

    tex_maps = asset_type_data.get_maps(
        workflow=workflow,
        size=self.size_enum,
        prefer_16_bit=self.use_16bit,
        variant=None)

    if len(tex_maps) == 0:
        self.report({"WARNING"}, _t("No Textures found."))
        self.size_enum = self.size  # Cancel size change
        self.updating = False
        reporting.capture_message("apply_mat_tex_not_found", asset_name)
        return

    nodes = mat.node_tree.nodes
    for tex in tex_maps:
        _change_node_image(nodes, tex, self.size_enum)

    # Change material name
    mat.name = new_mat_name

    self.size = self.size_enum
    self.updating = False


def _change_node_image(nodes: List, tex: TextureMap, size: str):
    node_name = tex.map_type.convert_convention(NODE_NAMES_CONVENTION).name
    node: bpy.types.ShaderNodeTexImage = nodes.get(node_name)
    if not node:
        return

    # Backup previous image settings
    color_space = node.image.colorspace_settings.name

    # Get naming convention for the image
    path_tex = tex.get_path()
    filename_tex = os.path.basename(path_tex)
    file_format = tex.file_format[1:].lower()
    name_tex = texture_name(filename_tex, size, file_format)

    img: bpy.types.Image = _get_image_from_tex(tex)
    if img:
        img.colorspace_settings.name = color_space
        img.name = name_tex
        node.image = img


def _get_image_from_tex(tex: TextureMap) -> Optional[bpy.types.Image]:
    return bpy.data.images.load(tex.get_path(), check_existing=True)


def update_material_mapping(self, context):
    """ Method called everytime user changes Mapping in Material Panel """
    if self.updating or not context.object:
        return
    mat: bpy.types.Material = context.object.active_material
    if not mat:
        return
    self.updating = True

    node_tree: bpy.types.ShaderNodeTree = mat.node_tree
    nodes: List = node_tree.nodes

    # Easy case: no changes to mapping node, just the projections
    projections_array = ["flat", "box", "sphere", "tube"]
    if self.mapping.lower() in projections_array and self.mapping_enum.lower() in projections_array:
        _change_projection(nodes, self.mapping_enum)
        _rescale_mapping_node(nodes, self.scale)

    # And now the not-easy case, where we have to change the mapping node
    else:
        old_data = _MAPPING_TO_NODENAME[self.mapping.lower()]
        new_data = _MAPPING_TO_NODENAME[self.mapping_enum.lower()]

        # Backup old data
        old_mapping_node = nodes.get(old_data["name"])
        parent = old_mapping_node.parent
        location = old_mapping_node.location.copy()

        tex_coord_node = nodes.get("Texture Coordinate")

        # Delete old node
        nodes.remove(old_mapping_node)

        # Mapping Node
        if new_data["type"] == "ShaderNodeMapping":
            # Create new node
            new_node = create_mapping_node(
                group=mat,
                parent=parent,
                scale=self.scale,
                name=new_data["name"],
                location=location
            )

            # Create link between new node and Texture Coordinate
            create_link(
                node_tree=node_tree,
                node_out=tex_coord_node,
                sock_out_name="Generated",
                sock_out_bl_idname_expected="NodeSocketVector",
                node_in=new_node,
                sock_in_name="Vector",
                sock_in_bl_idname_expected="NodeSocketVector",
            )

            # Create new links between new node and all image nodes
            for node in nodes:
                if node.type == "TEX_IMAGE":
                    create_link(
                        node_tree=node_tree,
                        node_out=new_node,
                        sock_out_name="Vector",
                        sock_out_bl_idname_expected="NodeSocketVector",
                        node_in=node,
                        sock_in_name="Vector",
                        sock_in_bl_idname_expected="NodeSocketVector",
                    )

            # And finally, change projection for all image nodes
            _change_projection(nodes, self.mapping_enum)

        # Group Node
        elif new_data["type"] == "ShaderNodeGroup":
            # Mosaic
            if self.mapping_enum.lower() == "mosaic":
                new_node = create_mosaic_node(
                    group=mat,
                    parent=parent,
                    scale=self.scale,
                    name=new_data["name"],
                    location=location
                )
            # UV
            elif self.mapping_enum.lower() == "uv":
                new_node = create_uv_group_node(
                    parent_frame=parent,
                    mat=mat,
                    name=new_data["name"],
                    scale=self.scale,
                    location=location
                )

            # Revert projection type if needed
            if self.mapping.lower() in projections_array[1:]:
                _change_projection(nodes, "FLAT")

            # Link with Texture Coordinate
            create_link(
                node_tree=node_tree,
                node_out=tex_coord_node,
                sock_out_name="UV",
                sock_out_bl_idname_expected="NodeSocketVector",
                node_in=new_node,
                sock_in_name="UV",
                sock_in_bl_idname_expected="NodeSocketVector",
            )
            # Link with image nodes
            for node in nodes:
                if node.type == "TEX_IMAGE":
                    create_link(
                        node_tree=node_tree,
                        node_out=new_node,
                        sock_out_name="UV",
                        sock_out_bl_idname_expected="NodeSocketVector",
                        node_in=node,
                        sock_in_name="Vector",
                        sock_in_bl_idname_expected="NodeSocketVector",
                    )

    self.mapping = self.mapping_enum
    self.updating = False


def _change_projection(nodes: List, new_projection: str):
    """ For every image node, change the projection type """
    for node in nodes:
        if node.type == "TEX_IMAGE":
            node.projection = new_projection


def _rescale_mapping_node(nodes: List, scale: float):
    """ Change the Scale value of a Mapping node """
    # Adjust scaling
    mapping_node = nodes.get("Mapping")
    if mapping_node:
        set_value(
            node=mapping_node,
            sock_name="Scale",
            sock_bl_idname_expected="NodeSocketVectorXYZ",
            value=[scale] * 3,
        )


def update_material_scale(self, context):
    """ Method called everytime user changes the scale in Material Panel """
    if not context.object:
        return
    mat: bpy.types.Material = context.object.active_material
    if not mat:
        return

    node_tree: bpy.types.ShaderNodeTree = mat.node_tree
    nodes: bpy.types.Nodes = node_tree.nodes

    mapping = self.mapping.lower()
    if mapping in ["flat", "box", "sphere", "tube"]:
        _rescale_mapping_node(nodes, self.scale)

    else:
        mapping_node_name = _MAPPING_TO_NODENAME[mapping]["name"]
        mapping_node = nodes.get(mapping_node_name)
        if not mapping_node:
            return
        set_value(
            node=mapping_node,
            sock_name="Scale",
            sock_bl_idname_expected="NodeSocketFloat",
            value=self.scale,
        )


class POLIIGON_PT_materials(bpy.types.Panel):
    bl_label = "Poliigon"
    bl_idname = "POLIIGON_PT_materials"

    # Located in material properties of object
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from register_panels.py to init global addon context."""
        global cTB
        cTB = get_context(addon_version)

    def _fill_size_drop_down(self, context):
        return fill_size_drop_down(cTB, self.asset_id)

    size: EnumProperty(
        name=_t("Texture"),  # noqa: F821
        items=_fill_size_drop_down,
        description=_t("Change size of assigned textures.")  # noqa: F722
    )  # type: ignore

    @reporting.handle_draw()
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        obj: bpy.types.Object = context.object
        if not len(obj.material_slots):
            _not_poliigon_material(layout)
            return

        # Get active material and its properties
        mat: bpy.types.Material = obj.active_material
        if mat is None:
            _not_poliigon_material(layout)
            return
        pol_props = mat.poliigon_props

        # Not a Poliigon material
        if pol_props.asset_id == -1:
            _not_poliigon_material(layout)
            return

        # Poliigon material
        layout.label(text="Material settings")
        layout.prop(pol_props, "size_enum", text="Resolution")
        layout.prop(pol_props, "mapping_enum", text="Mapping")
        layout.prop(pol_props, "scale", text="Scale")


def _not_poliigon_material(layout):
    layout.box().label(text="Apply and select a Poliigon material above")

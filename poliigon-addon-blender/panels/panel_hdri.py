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
import re

import bpy
from typing import Any, Callable, Dict, List, Optional, Tuple
from mathutils import Vector

from .. import reporting
from ..modules.poliigon_core.assets import AssetData
from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context


def update_hdr_strength(self, context) -> None:
    """ Called automatically every time HDR Strength is changed """
    if self.updating:
        return
    world, _ = _get_world(context)
    if not world:
        return

    self.updating = True

    nodes_dict = _get_poliigon_hdri_nodes(world.node_tree.nodes)
    light_node = nodes_dict["background_light"]
    bg_node = nodes_dict["background_bg"]
    if light_node:
        light_node.inputs[1].default_value = self.hdr_strength
    if bg_node:
        bg_node.inputs[1].default_value = self.hdr_strength

    self.updating = False


def update_rotation(self, context) -> None:
    """ Called automatically every time HDRI's Z rotation is changed """
    if self.updating:
        return
    world, _ = _get_world(context)
    if not world:
        return

    self.updating = True

    # Find MAPPING node and change rotation value
    nodes_dict = _get_poliigon_hdri_nodes(world.node_tree.nodes)
    mapping_node: bpy.types.Node = nodes_dict["mapping"]
    if mapping_node:
        mapping_node.inputs[2].default_value.z = self.rotation

    self.updating = False


def get_hdri_size_common(asset_id: int, is_bg: bool) -> List[Tuple[str, str, str]]:
    """ Common logic for light and bg size drop down.
    Differences: BG includes JPG, light doesnt, and return format
    Must be outside of class, otherwise can't be called from other files
    """
    # Get list of locally available sizes
    asset_data = cTB._asset_index.get_asset(asset_id)
    asset_type_data = asset_data.get_type_data()

    asset_files = {}
    asset_type_data.get_files(asset_files)
    asset_files = list(asset_files.keys())

    # Populate dropdown items
    local_sizes = []
    for path_asset in asset_files:
        filename = os.path.basename(path_asset)
        is_exr = filename.endswith(".exr")
        is_hdr = filename.endswith(".hdr")
        is_jpg = filename.lower().endswith(".jpg")
        is_jpg &= "_JPG" in filename

        is_valid_file = is_exr or is_hdr
        if is_bg:
            is_valid_file = is_valid_file or is_jpg

        if not is_valid_file:
            continue
        match_object = re.search(r"_(\d+K)[_\.]", filename)
        if not match_object:
            continue
        size = match_object.group(1)
        if is_exr:
            local_sizes.append(f"{size}_EXR")
        elif is_hdr:
            local_sizes.append(f"{size}_HDR")
        elif is_bg and is_jpg:
            local_sizes.append(f"{size}_JPG")

    # Sort by comparing integer size without "K_JPG" or "K_EXR"
    local_sizes.sort(key=lambda s: int(s[:-5]))
    items_size = []
    for size in local_sizes:
        label = size.replace("_", " ")
        first = size
        if not is_bg:
            first = size[:2]
        items_size.append((first, label, label))
    return items_size


def fill_light_size_drop_down(self, context) -> List[Tuple[str, str, str]]:
    return get_hdri_size_common(self.asset_id, is_bg=False)


def fill_bg_size_drop_down(self, context) -> List[Tuple[str, str, str]]:
    return get_hdri_size_common(self.asset_id, is_bg=True)


def _get_world(context: bpy.types.Context, check_id: bool = True) -> Tuple[bpy.types.World, Any]:
    world = context.scene.world
    props = world.poliigon_props
    if check_id and props.asset_id == -1:
        return None, None
    return world, props


def update_hdri_resolution(self, context) -> None:
    """ Method called on each update of size_light_enum or size_bg_enum """
    if self.updating:
        return
    world, _ = _get_world(context)
    if not world:
        return
    self.updating = True
    self.size = self.size_light_enum
    self.size_bg = self.size_bg_enum

    update_world_nodes(self, context)

    self.updating = False


def update_world_nodes(self, context, report_callback: Callable = None):
    """ Delete and recreate the nodes of the HDRI """
    asset_data = cTB._asset_index.get_asset(self.asset_id)
    asset_type_data = asset_data.get_type_data()

    asset_name = asset_data.asset_name
    local_convention = asset_data.get_convention(local=True)
    addon_convention = cTB.addon_convention
    size_light = asset_type_data.get_size(
        self.size,
        local_only=True,
        addon_convention=addon_convention,
        local_convention=local_convention)

    name_light = f"{asset_name}_Light_{self.size}"
    name_bg = f"{asset_name}_Background_{self.size_bg}"

    existing = _get_imported_hdri(self.asset_id)
    if not existing:
        # Remove existing images to force loading this resolution.
        if name_light in bpy.data.images.keys():
            bpy.data.images.remove(bpy.data.images[name_light])
        if name_bg in bpy.data.images.keys():
            bpy.data.images.remove(bpy.data.images[name_bg])

    # Find if the images are already stored in data
    file_tex_bg = None
    file_tex_light = None
    for img in bpy.data.images:
        if img.name == name_light:
            file_tex_light = img.filepath
        if img.name == name_bg:
            file_tex_bg = img.filepath

    # If Light file is not in Blender storage, find it on computer
    if not file_tex_light:
        file_tex_light = _get_image_path(asset_type_data, size_light, [".hdr", ".exr"])

        # Still nothing -> error
        if not file_tex_light:
            msg = (f"Unable to locate image {name_light} with size {size_light}, "
                   f"try downloading {asset_name} again.")
            reporting.capture_message("failed_load_light_hdri", msg, "error")
            return {"CANCELLED"}

    # If BG file is not in Blender storage, find it on computer
    if not file_tex_bg:
        size_bg_eff, filetype_bg = self.size_bg.split("_")
        is_jpg = filetype_bg == "JPG"
        if size_light != size_bg_eff or is_jpg:
            formats = [".jpg"] if is_jpg else [".hdr", ".exr"]
            file_tex_bg = _get_image_path(asset_type_data, size_bg_eff, formats)

            # Still nothing -> error
            if not file_tex_bg:
                msg = (f"Unable to locate image {name_bg} with size {size_bg_eff} (JPG), "
                       f"try downloading {asset_name} again.")
                reporting.capture_message("failed_load_bg_jpg", msg, "error")
                return {"CANCELLED"}
        else:
            file_tex_bg = file_tex_light

    # Check if same texture is used for both lighting and background
    # (if they are the same, this allows us a simpler layout for nodes)
    use_simple_layout = file_tex_bg == file_tex_light
    if use_simple_layout:
        name_bg = name_light

    # And now draw the nodes depending on layout
    if use_simple_layout:
        _simple_layout(self, name_light, file_tex_light, asset_data)
    else:
        _complex_layout(self,
                        name_light,
                        file_tex_light,
                        name_bg,
                        file_tex_bg,
                        asset_data)

    _set_poliigon_props_world(self, context, asset_data)

    cTB.f_GetSceneAssets()

    if report_callback is not None:
        report_callback({"INFO"}, _t("HDRI Imported : {0}").format(asset_name))

    return {"FINISHED"}


def _get_image_path(asset_type_data, size: str, extensions: List[str]) -> Optional[str]:
    """ For a specific size and format/extension, find the file """
    local_files = {}
    asset_type_data.get_files(local_files)
    local_files = list(local_files.keys())

    for _file in local_files:
        if size in os.path.basename(_file):
            for ext in extensions:
                if _file.lower().endswith(ext):
                    return _file
    return


def _get_imported_hdri(asset_id: int) -> Optional[bpy.types.Image]:
    """ Returns the imported HDRI image (if any) """
    img_hdri = None
    for _img in bpy.data.images:
        try:
            asset_id_img = _img.poliigon_props.asset_id
            if asset_id_img != asset_id:
                continue
            img_hdri = _img
            break
        except BaseException:
            # skip non-Poliigon images (no props)
            continue
    return img_hdri


def _layout_common() -> Tuple[List[bpy.types.Node], List[bpy.types.NodeLink], object]:
    """ Common methodology for drawing both Simple and Complex layout of World nodes (HDRI) """
    if not bpy.context.scene.world:
        bpy.ops.world.new()
        bpy.context.scene.world = bpy.data.worlds[-1]
    bpy.context.scene.world.use_nodes = True
    nodes_world = bpy.context.scene.world.node_tree.nodes
    links_world = bpy.context.scene.world.node_tree.links

    # Use improved selective node management
    poliigon_nodes = _get_poliigon_hdri_nodes(nodes_world)
    _remove_poliigon_nodes(nodes_world, poliigon_nodes)
    node_output_world = _create_or_reuse_output_world(nodes_world, poliigon_nodes)
    node_output_world.location = Vector((320, 300))

    return nodes_world, links_world, node_output_world


def _remove_poliigon_nodes(nodes_world: List[bpy.types.Node], poliigon_nodes: Dict) -> None:
    """Safely remove only the identified Poliigon HDRI nodes."""
    nodes_to_remove = []

    for node_role, node in poliigon_nodes.items():
        if node is not None and node_role != 'output_world':  # Never remove output_world
            nodes_to_remove.append(node)

    # Remove nodes in a separate loop to avoid modifying collection during iteration
    for node in nodes_to_remove:
        # Additional validation before removal
        if hasattr(node, 'name') and node.name in nodes_world:
            nodes_world.remove(node)


def _create_or_reuse_output_world(nodes_world: List[bpy.types.Node], poliigon_nodes: Dict) -> object:
    """Create or reuse the output world node."""
    output_world = poliigon_nodes.get('output_world')

    if output_world is None:
        output_world = nodes_world.new("ShaderNodeOutputWorld")
        output_world.location = Vector((250, 225.0))

    return output_world


def _get_image(self, asset_data: AssetData, name: str, filepath: str,) -> bpy.types.Image:
    try:
        # Load light image
        if name in bpy.data.images.keys():
            return bpy.data.images[name]

        file_tex_norm = os.path.normpath(filepath)
        img = bpy.data.images.load(file_tex_norm)
        img.name = name
        _set_poliigon_props_image(self, img, asset_data)
        return img
    except Exception as e:
        cTB.logger.error(f"Failed to load image: {str(e)}")
        reporting.capture_message("hdri_get_image_failed", e, "error")
        raise


def _simple_layout(self,
                   name_light: str,
                   file_tex_light: str,
                   asset_data: AssetData) -> None:
    """ Draw HDRI world nodes in Simple layout (when light and bg are the same) """

    nodes_world, links_world, node_output_world = _layout_common()

    # Create new Poliigon nodes
    node_tex_coord = nodes_world.new("ShaderNodeTexCoord")
    node_tex_coord.label = "Mapping"
    node_tex_coord.location = Vector((-720, 300))

    node_mapping = nodes_world.new("ShaderNodeMapping")
    node_mapping.label = "Mapping"
    node_mapping.location = Vector((-470, 300))

    node_tex_env_light = nodes_world.new("ShaderNodeTexEnvironment")
    node_tex_env_light.label = "Lighting"
    node_tex_env_light.location = Vector((-220, 300))

    node_background_light = nodes_world.new("ShaderNodeBackground")
    node_background_light.label = "Lighting"
    node_background_light.location = Vector((120, 300))

    # Create connections with error handling
    links_world.new(node_tex_coord.outputs["Generated"], node_mapping.inputs["Vector"])
    links_world.new(node_mapping.outputs["Vector"], node_tex_env_light.inputs["Vector"])
    links_world.new(node_tex_env_light.outputs["Color"], node_background_light.inputs["Color"])
    links_world.new(node_background_light.outputs[0], node_output_world.inputs["Surface"])

    # Load image
    img_light = _get_image(self, asset_data, name_light, file_tex_light)

    # Set node properties
    if "Rotation" in node_mapping.inputs:
        node_mapping.inputs["Rotation"].default_value[2] = self.rotation
    else:
        node_mapping.rotation[2] = self.rotation

    node_tex_env_light.image = img_light
    node_background_light.inputs["Strength"].default_value = self.hdr_strength


def _complex_layout(self,
                    name_light: str,
                    file_tex_light: str,
                    name_bg: str,
                    file_tex_bg: str,
                    asset_data: AssetData) -> None:
    """ Draw HDRI world nodes in Complex layout (when light and bg are NOT the same) """

    nodes_world, links_world, node_output_world = _layout_common()

    # Create all required nodes
    node_tex_coord = nodes_world.new("ShaderNodeTexCoord")
    node_tex_coord.label = "Mapping"
    node_tex_coord.location = Vector((-950, 225))

    node_mapping = nodes_world.new("ShaderNodeMapping")
    node_mapping.label = "Mapping"
    node_mapping.location = Vector((-750, 225))

    node_tex_env_light = nodes_world.new("ShaderNodeTexEnvironment")
    node_tex_env_light.label = "Lighting"
    node_tex_env_light.location = Vector((-550, 350))

    node_tex_env_bg = nodes_world.new("ShaderNodeTexEnvironment")
    node_tex_env_bg.label = "Background"
    node_tex_env_bg.location = Vector((-550, 100))

    node_background_light = nodes_world.new("ShaderNodeBackground")
    node_background_light.label = "Lighting"
    node_background_light.location = Vector((-250, 100))

    node_background_bg = nodes_world.new("ShaderNodeBackground")
    node_background_bg.label = "Background"
    node_background_bg.location = Vector((-250, -50))

    node_mix_shader = nodes_world.new("ShaderNodeMixShader")
    node_mix_shader.location = Vector((0, 225))

    node_light_path = nodes_world.new("ShaderNodeLightPath")
    node_light_path.location = Vector((-250, 440))

    # Create all links after ensuring nodes exist
    links_world.new(node_tex_coord.outputs["Generated"], node_mapping.inputs["Vector"])
    links_world.new(node_mapping.outputs["Vector"], node_tex_env_light.inputs["Vector"])
    links_world.new(node_tex_env_light.outputs["Color"], node_background_light.inputs["Color"])
    links_world.new(node_background_light.outputs[0], node_mix_shader.inputs[1])
    links_world.new(node_mapping.outputs["Vector"], node_tex_env_bg.inputs["Vector"])
    links_world.new(node_tex_env_bg.outputs["Color"], node_background_bg.inputs["Color"])
    links_world.new(node_background_bg.outputs[0], node_mix_shader.inputs[2])
    links_world.new(node_light_path.outputs[0], node_mix_shader.inputs[0])
    links_world.new(node_mix_shader.outputs[0], node_output_world.inputs[0])

    # Load images
    img_light = _get_image(self, asset_data, name_light, file_tex_light)
    img_bg = _get_image(self, asset_data, name_bg, file_tex_bg)

    # Set node properties
    if "Rotation" in node_mapping.inputs:
        node_mapping.inputs["Rotation"].default_value[2] = self.rotation
    else:
        node_mapping.rotation[2] = self.rotation

    node_tex_env_light.image = img_light
    node_background_light.inputs["Strength"].default_value = self.hdr_strength

    node_tex_env_bg.image = img_bg
    node_background_bg.inputs["Strength"].default_value = self.hdr_strength


def _set_poliigon_props_image(self, img: bpy.types.Image, asset_data: AssetData) -> None:
    """ Sets Poliigon property of an imported image """
    img_props = img.poliigon_props
    img_props.asset_name = asset_data.asset_name
    img_props.asset_id = self.asset_id
    img_props.asset_type = asset_data.asset_type.name
    img_props.size = self.size
    img_props.size_bg = self.size_bg
    img_props.hdr_strength = self.hdr_strength
    img_props.rotation = self.rotation


def _set_poliigon_props_world(self, context, asset_data: AssetData) -> None:
    """ Sets Poliigon property of world. """
    _, world_props = _get_world(context, False)
    world_props.updating = True  # Safety so that it doesnt trigger infinite update loop

    world_props.asset_name = asset_data.asset_name
    world_props.asset_id = self.asset_id
    world_props.asset_type = asset_data.asset_type.name
    world_props.size = self.size
    world_props.size_bg = self.size_bg
    world_props.hdr_strength = self.hdr_strength
    world_props.rotation = self.rotation

    world_props.updating = False


def _get_poliigon_hdri_nodes(nodes_world: List[bpy.types.Node]) -> Dict:
    """Identify existing Poliigon HDRI nodes by their labels and types.

    Returns a dictionary mapping node roles to existing nodes, or None if not found.
    This allows us to preserve user-authored nodes while only replacing Poliigon ones.
    """
    poliigon_nodes = {
        'tex_coord': None,
        'mapping': None,
        'tex_env_light': None,
        'tex_env_bg': None,
        'background_light': None,
        'background_bg': None,
        'mix_shader': None,
        'light_path': None,
        'output_world': None
    }

    for node in nodes_world:
        # Skip invalid nodes
        if not hasattr(node, 'type') or not hasattr(node, 'label'):
            continue

        if node.type == "TEX_COORD" and node.label == "Mapping":
            poliigon_nodes['tex_coord'] = node

        elif node.type == "MAPPING" and node.label == "Mapping":
            poliigon_nodes['mapping'] = node

        elif node.type == "TEX_ENVIRONMENT":
            if node.label == "Lighting":
                poliigon_nodes['tex_env_light'] = node
            elif node.label == "Background":
                poliigon_nodes['tex_env_bg'] = node

        elif node.type == "BACKGROUND":
            if node.label == "Lighting":
                poliigon_nodes['background_light'] = node
            elif node.label == "Background":
                poliigon_nodes['background_bg'] = node
            elif poliigon_nodes['background_light'] is None:
                # If background_light isn't assigned yet, assign the
                # first one we identify. This avoids clutter in the
                # default blender world layout by reusing both nodes.
                poliigon_nodes['background_light'] = node

        elif node.type == "MIX_SHADER":
            poliigon_nodes['mix_shader'] = node

        elif node.type == "LIGHT_PATH":
            poliigon_nodes['light_path'] = node

        elif node.type == "OUTPUT_WORLD":
            poliigon_nodes['output_world'] = node

    return poliigon_nodes


class POLIIGON_PT_hdri(bpy.types.Panel):
    bl_label = "Poliigon"
    bl_idname = "POLIIGON_PT_hdri"

    # Located in World tab
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "world"

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from register_panels.py to init global addon context."""
        global cTB
        cTB = get_context(addon_version)

    @reporting.handle_draw()
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        world, props = _get_world(context)
        if not world:
            return _not_poliigon_layout(layout)

        # Poliigon model
        layout.label(text="HDRI settings")
        layout.prop(props, "size_light_enum", text=_t("Light Texture"))
        layout.prop(props, "size_bg_enum", text=_t("Background Texture"))
        layout.prop(props, "hdr_strength", text=_t("HDR Strength"))
        layout.prop(props, "rotation", text=_t("Z-Rotation"))


def _not_poliigon_layout(layout):
    layout.box().label(text="Import a Poliigon HDRI to adjust")

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

import bpy


def update_model_resolution(self, context):
    pass


class POLIIGON_PT_models(bpy.types.Panel):
    bl_label = "Poliigon"
    bl_idname = "POLIIGON_PT_models"

    # Located in Object tab
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        obj: bpy.types.Object = context.object
        if not obj:
            return _not_poliigon_layout(layout)
        props = obj.poliigon_props
        if not props:
            return _not_poliigon_layout(layout)
        if props.asset_id == -1:
            return _not_poliigon_layout(layout)

        # Poliigon model
        layout.label(text="Model settings")
        layout.prop(props, "size_enum", text="Resolution")


def _not_poliigon_layout(layout):
    layout.box().label(text="Select a Poliigon model to adjust")

"""Build a demo scene for testing Pipeline, and for shooting the store screenshots.

    Blender ▸ Scripting workspace ▸ Open ▸ this file ▸ Run Script
    or: blender --background --factory-startup --python tests/make_demo_scene.py

The scene is a small warung: a table, two stools, a crate, a kettle, a lantern, a
hanging signboard and a rigged banner. Every object is deliberately messy in a
different way, so one export exercises the whole add-on:

    Table          rotated and scaled, nowhere near the origin
    UCX_Table_01   collision that must ride along inside SM_Table.fbx
    Stool_A        a second mesh with its own collision
    Stool_B        mirrored (negative scale) — faces must not end up inside out
    Crate          clean, the control case
    kettle final v2   spaces in the name that Unreal would rename anyway
    Lantern        no UV map — Validate must catch this and block the export
    Signboard      left loose in the Scene Collection rather than in a collection
    Banner + Rig   skinned mesh, must export as SK_ with its skeleton intact

Collections are nested: "Warung" only groups "Furniture" and "Props", so it must
not re-export their contents into a third file.
"""

import bpy
import bmesh
from mathutils import Vector


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def wipe():
    """Empty the file without touching preferences."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for block in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def collection(name, parent=None):
    coll = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def box(name, size, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1),
        coll=None, uvs=True):
    """A box with real dimensions, built without operators so nothing depends on
    what happens to be selected."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vert in bm.verts:
        vert.co.x *= size[0]
        vert.co.y *= size[1]
        vert.co.z *= size[2]
    if uvs:
        bm.loops.layers.uv.new("UVMap")
        # crude but valid box mapping: project each face on its dominant axis
        uv_layer = bm.loops.layers.uv.active
        for face in bm.faces:
            normal = face.normal
            axis = max(range(3), key=lambda i: abs(normal[i]))
            u_i, v_i = [i for i in range(3) if i != axis]
            for loop in face.loops:
                co = loop.vert.co
                loop[uv_layer].uv = (co[u_i] + 0.5, co[v_i] + 0.5)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    obj.scale = scale
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def material(obj, name, colour):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = colour
    obj.data.materials.append(mat)


# --------------------------------------------------------------------------- #
# the scene
# --------------------------------------------------------------------------- #

def build():
    wipe()

    warung = collection("Warung")                    # groups only, exports nothing
    furniture = collection("Furniture", warung)
    props = collection("Props", warung)

    # --- furniture, all sitting away from the origin like a real layout ------
    table = box("Table", (1.2, 0.7, 0.05), location=(3.0, 1.5, 0.75),
                rotation=(0, 0, 0.4), scale=(1.0, 1.0, 1.0), coll=furniture)
    material(table, "Wood", (0.36, 0.22, 0.11, 1.0))

    # collision for the table: one rough box, named the way Unreal reads it
    box("UCX_Table_01", (1.25, 0.75, 0.8), location=(3.0, 1.5, 0.4),
        rotation=(0, 0, 0.4), coll=furniture, uvs=False)

    stool_a = box("Stool_A", (0.32, 0.32, 0.45), location=(4.4, 1.9, 0.225),
                  rotation=(0, 0, 1.1), scale=(1.15, 1.15, 1.0), coll=furniture)
    material(stool_a, "Plastic_Red", (0.55, 0.09, 0.08, 1.0))

    box("UCX_Stool_A_01", (0.36, 0.36, 0.46), location=(4.4, 1.9, 0.23),
        rotation=(0, 0, 1.1), coll=furniture, uvs=False)

    # mirrored on X — the classic case where normals end up inside out
    stool_b = box("Stool_B", (0.32, 0.32, 0.45), location=(1.6, 1.1, 0.225),
                  rotation=(0, 0, -0.6), scale=(-1.15, 1.15, 1.0), coll=furniture)
    material(stool_b, "Plastic_Red", (0.55, 0.09, 0.08, 1.0))

    # --- props ---------------------------------------------------------------
    crate = box("Crate", (0.5, 0.5, 0.4), location=(5.5, 0.3, 0.2), coll=props)
    material(crate, "Wood", (0.36, 0.22, 0.11, 1.0))

    # spaces in the name — Unreal would rename this on import anyway
    kettle = box("kettle final v2", (0.22, 0.22, 0.26),
                 location=(3.1, 1.4, 0.9), rotation=(0, 0, 0.9), coll=props)
    material(kettle, "Metal", (0.62, 0.63, 0.66, 1.0))

    # no UV map at all — Validate must flag this and refuse to export
    lantern = box("Lantern", (0.18, 0.18, 0.3), location=(2.2, 2.4, 1.8),
                  coll=props, uvs=False)
    material(lantern, "Glass", (0.95, 0.82, 0.45, 1.0))

    # --- loose in the Scene Collection, not in any collection ----------------
    sign = box("Signboard", (1.6, 0.06, 0.5), location=(3.0, 3.2, 2.1),
               rotation=(0, 0, 0.15), coll=bpy.context.scene.collection)
    material(sign, "Paint_Yellow", (0.85, 0.63, 0.11, 1.0))

    # --- a rigged banner, so there is something skeletal to export -----------
    banner = box("Banner", (1.4, 0.02, 0.9), location=(0.0, 4.0, 1.4),
                 coll=bpy.context.scene.collection)
    material(banner, "Cloth", (0.15, 0.35, 0.55, 1.0))

    armature_data = bpy.data.armatures.new("Rig")
    rig = bpy.data.objects.new("Rig", armature_data)
    rig.location = (0.0, 4.0, 0.95)
    bpy.context.scene.collection.objects.link(rig)

    view_layer = bpy.context.view_layer
    view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    lower = armature_data.edit_bones.new("Bone_Lower")
    lower.head = Vector((0.0, 0.0, 0.0))
    lower.tail = Vector((0.0, 0.0, 0.5))
    upper = armature_data.edit_bones.new("Bone_Upper")
    upper.head = lower.tail
    upper.tail = Vector((0.0, 0.0, 1.0))
    upper.parent = lower
    bpy.ops.object.mode_set(mode="OBJECT")

    for obj in view_layer.objects:
        obj.select_set(False)
    banner.select_set(True)
    rig.select_set(True)
    view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    for obj in view_layer.objects:
        obj.select_set(False)

    return {
        "collections": [c.name for c in bpy.data.collections],
        "objects": sorted(o.name for o in bpy.data.objects),
    }


def report(info):
    print("")
    print("Demo scene built.")
    print("  collections: " + ", ".join(info["collections"]))
    print("  objects:     " + ", ".join(info["objects"]))
    print("")
    print("Try this, in order:")
    print("  1. Pipeline ▸ Validate    → expect an error on Lantern (no UV map)")
    print("  2. Fix it: select Lantern, Edit Mode, U ▸ Smart UV Project")
    print("  3. Pipeline ▸ Validate    → expect a warning about 'kettle final v2'")
    print("  4. Split By: Collection, Export")
    print("     → SM_Furniture.fbx, SM_Props.fbx and SK_Scene.fbx, but nothing")
    print("       named Warung, because Warung only groups the other two.")
    print("       SK_Scene is not a mistake: the Signboard and the rigged Banner")
    print("       share the Scene Collection, and one rig makes the whole set")
    print("       skeletal. Validate warns you about this. Split By: Object if")
    print("       you want them as separate assets.")
    print("  5. Split By: Object, Export")
    print("     → SM_Table.fbx with its UCX inside, SM_Stool_A.fbx, SM_Stool_B.fbx,")
    print("       SM_Crate.fbx, SM_kettle_final_v2.fbx, SM_Signboard.fbx,")
    print("       SK_Banner.fbx — and no file for either UCX_ object")
    print("")


if __name__ == "__main__":
    report(build())

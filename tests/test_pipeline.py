"""Headless smoke test.

    blender --background --python tests/test_pipeline.py

Builds a small scene, exports it, and checks the files that land on disk.
Exits non-zero if anything fails, so it can be wired into CI.
"""

import os
import sys
import tempfile

import bpy
from mathutils import Vector

ADDON = "pipeline_ue"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

failures = []
checks = 0


def check(condition, message):
    global checks
    checks += 1
    print(("  PASS  " if condition else "  FAIL  ") + message)
    if not condition:
        failures.append(message)


def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def add_cube(name, location=(0, 0, 0), scale=(1, 1, 1), collection=None):
    mesh = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bm.to_mesh(mesh)
    bm.free()
    mesh.uv_layers.new(name="UVMap")
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.scale = scale
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def world_bounds(objects):
    """Min and max corner of the objects, in world space."""
    corners = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            corners.append(obj.matrix_world @ Vector(corner))
    lo = Vector(min(c[i] for c in corners) for i in range(3))
    hi = Vector(max(c[i] for c in corners) for i in range(3))
    return lo, hi


def reimport(filepath):
    """Load an exported file back into an empty scene and return its objects."""
    fresh_scene()
    bpy.ops.import_scene.fbx(filepath=filepath)
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def main():
    import pipeline_ue
    pipeline_ue.register()
    print("Registered %s v%s" % (ADDON, ".".join(map(str, pipeline_ue.bl_info["version"]))))

    # --- naming helpers ---------------------------------------------------
    check(pipeline_ue.clean_name("Wooden Chair.001") == "Wooden_Chair", "clean_name strips suffix and spaces")
    check(pipeline_ue.collision_owner_name(type("Fake", (), {"name": "UCX_Chair_01"})()) == "Chair",
          "collision_owner_name resolves UCX_Chair_01 -> Chair")

    # --- one file per collection -----------------------------------------
    fresh_scene()
    props = bpy.data.collections.new("Props")
    bpy.context.scene.collection.children.link(props)
    add_cube("Chair", location=(3, 2, 1), scale=(2, 2, 2), collection=props)
    add_cube("UCX_Chair_01", location=(3, 2, 1), collection=props)

    out = tempfile.mkdtemp(prefix="pipeline_test_")
    s = bpy.context.scene.pipeline
    s.export_root = out
    s.mode = "COLLECTION"
    s.origin_mode = "BOUNDS_BOTTOM"

    result = bpy.ops.pipeline.export()
    check(result == {"FINISHED"}, "collection export finished")
    check(os.path.isfile(os.path.join(out, "SM_Props.fbx")), "wrote SM_Props.fbx")

    # --- one file per object ---------------------------------------------
    s.mode = "OBJECT"
    s.selected_only = False
    bpy.ops.pipeline.export()
    check(os.path.isfile(os.path.join(out, "SM_Chair.fbx")), "wrote SM_Chair.fbx")
    check(not os.path.isfile(os.path.join(out, "SM_UCX_Chair_01.fbx")),
          "collision did not become its own asset")

    # --- the scene survives the export -----------------------------------
    check("Chair" in bpy.data.objects, "original object still present")
    check(len([o for o in bpy.data.objects if o.name.startswith("Chair")]) == 1,
          "no leftover duplicates")
    check(not [c for c in bpy.data.collections if "__pipeline_export__" in c.name],
          "temporary collection cleaned up")
    check(abs(bpy.data.objects["Chair"].scale.x - 2.0) < 1e-6,
          "original transform untouched")

    # --- objects left in the Scene Collection still export ----------------
    fresh_scene()
    add_cube("Loose")
    s = bpy.context.scene.pipeline
    s.export_root = out
    s.mode = "COLLECTION"
    bpy.ops.pipeline.export()
    check(os.path.isfile(os.path.join(out, "SM_Scene.fbx")),
          "object left in the Scene Collection was exported")

    # --- round trip: pivot, scale and orientation survive the FBX ---------
    fresh_scene()
    # 2 m cube, rotated and scaled, sitting away from the origin.
    add_cube("Prop", location=(5, -3, 7), scale=(2, 2, 2))
    bpy.data.objects["Prop"].rotation_euler = (0.0, 0.0, 0.7854)
    s = bpy.context.scene.pipeline
    s.export_root = out
    s.mode = "OBJECT"
    s.selected_only = False
    s.origin_mode = "BOUNDS_BOTTOM"
    s.apply_transforms = True
    bpy.ops.pipeline.export()

    meshes = reimport(os.path.join(out, "SM_Prop.fbx"))
    check(len(meshes) == 1, "round trip returned exactly one mesh")
    lo, hi = world_bounds(meshes)
    check(abs(lo.z) < 1e-3, "bounds-bottom origin puts the asset on the floor (z=%.4f)" % lo.z)
    check(abs((lo.x + hi.x) * 0.5) < 1e-3 and abs((lo.y + hi.y) * 0.5) < 1e-3,
          "asset is centred on X/Y")
    size = hi - lo
    # A 2 m cube scaled 2x is 4 m across; rotated 45 degrees its bounding box
    # widens to 4 * sqrt(2), which is what proves the rotation was baked in.
    check(abs(size.z - 4.0) < 1e-3, "height survived the export (%.3f m)" % size.z)
    check(abs(size.x - 4.0 * 2 ** 0.5) < 1e-2, "rotation was baked into the mesh (%.3f m)" % size.x)
    check(abs(meshes[0].scale.x - 1.0) < 1e-4, "asset arrives with a clean 1,1,1 transform")

    # --- mirrored objects keep their normals facing out -------------------
    fresh_scene()
    add_cube("Mirrored", scale=(-1, 1, 1))
    s = bpy.context.scene.pipeline
    s.export_root = out
    s.mode = "OBJECT"
    s.selected_only = False
    bpy.ops.pipeline.export()
    meshes = reimport(os.path.join(out, "SM_Mirrored.fbx"))
    volume = 0.0
    for poly in meshes[0].data.polygons:
        volume += poly.normal.dot(poly.center) * poly.area
    check(volume > 0.0, "negative scale did not invert the faces (signed volume %.3f)" % volume)

    # --- dry run writes nothing -------------------------------------------
    fresh_scene()
    add_cube("Ghost")
    s = bpy.context.scene.pipeline
    s.export_root = out
    s.mode = "OBJECT"
    s.selected_only = False
    s.dry_run = True
    bpy.ops.pipeline.export()
    check(not os.path.isfile(os.path.join(out, "SM_Ghost.fbx")), "dry run wrote no file")
    s.dry_run = False

    # --- glTF path ---------------------------------------------------------
    s.file_format = "GLTF"
    bpy.ops.pipeline.export()
    check(os.path.isfile(os.path.join(out, "SM_Ghost.glb")), "glTF export wrote a .glb")
    s.file_format = "FBX"

    # --- skeletal sets get the SK_ prefix ---------------------------------
    fresh_scene()
    armature_data = bpy.data.armatures.new("Rig")
    rig = bpy.data.objects.new("Rig", armature_data)
    bpy.context.scene.collection.objects.link(rig)
    body = add_cube("Body")
    modifier = body.modifiers.new("Armature", "ARMATURE")
    modifier.object = rig
    s = bpy.context.scene.pipeline
    s.export_root = out
    s.mode = "OBJECT"
    s.selected_only = False
    bpy.ops.pipeline.export()
    check(os.path.isfile(os.path.join(out, "SK_Body.fbx")),
          "skinned mesh exported with the SK_ prefix")
    check(not os.path.isfile(os.path.join(out, "SM_Body.fbx")),
          "skinned mesh did not also export as a static mesh")

    # --- validation catches a missing UV ---------------------------------
    fresh_scene()
    naked = add_cube("Naked")
    while naked.data.uv_layers:
        naked.data.uv_layers.remove(naked.data.uv_layers[0])
    bpy.context.scene.pipeline.export_root = out
    bpy.ops.pipeline.validate()
    issues = bpy.context.scene.pipeline.issues
    check(any(i.severity == "ERROR" and "UV" in i.message for i in issues),
          "validation flags the missing UV map")

    # --- a blocking issue stops the export -------------------------------
    # Blender turns an operator's ERROR report into a RuntimeError when the
    # operator is called from Python, so either outcome means it refused.
    try:
        result = bpy.ops.pipeline.export()
        refused = result == {"CANCELLED"}
    except RuntimeError as exc:
        refused = "blocking issue" in str(exc)
    check(refused, "export refuses to run with a blocking issue")
    check(not os.path.isfile(os.path.join(out, "SM_Naked.fbx")),
          "nothing was written for the invalid mesh")

    print("\n%d check(s), %d failure(s)" % (checks, len(failures)))
    if failures:
        for f in failures:
            print("FAILED: " + f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


main()

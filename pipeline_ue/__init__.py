# SPDX-License-Identifier: GPL-3.0-or-later
"""Pipeline — Blender to Unreal Engine batch exporter.

One button that turns a Blender scene into Unreal-ready FBX/glTF files with the
naming, unit scale, pivots and collision meshes Unreal expects.
"""

bl_info = {
    "name": "Pipeline — Unreal Batch Exporter",
    "author": "Luqman Hakeem",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "3D View > Sidebar (N) > Pipeline",
    "description": "Batch export collections and objects to Unreal Engine with "
                   "correct naming, unit scale, pivots and UCX collision.",
    "doc_url": "https://github.com/juslangit/pipeline",
    "category": "Import-Export",
}

import os
import re
import time

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Operator, Panel, PropertyGroup, UIList
from mathutils import Matrix, Vector

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

EXPORTABLE_TYPES = {"MESH", "ARMATURE", "EMPTY", "CURVE", "SURFACE", "FONT", "META"}
MESH_LIKE_TYPES = {"MESH", "CURVE", "SURFACE", "FONT", "META"}

# Unreal's collision prefixes. An object called UCX_Chair_01 is collision for Chair.
COLLISION_PREFIXES = ("UCX_", "UBX_", "USP_", "UCP_")

# Trailing ".001" that Blender appends to duplicated datablocks.
DUPLICATE_SUFFIX = re.compile(r"\.\d{3}$")
ILLEGAL_NAME_CHARS = re.compile(r"[^A-Za-z0-9_\-]")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def clean_name(name):
    """Strip Blender's .001 suffix and anything Unreal would rename on import."""
    name = DUPLICATE_SUFFIX.sub("", name)
    name = name.replace(" ", "_")
    name = ILLEGAL_NAME_CHARS.sub("_", name)
    name = re.sub(r"_{2,}", "_", name).strip("_")
    return name or "Asset"


def is_collision(obj):
    return obj.name.startswith(COLLISION_PREFIXES)


def collision_owner_name(obj):
    """UCX_Chair_01 -> Chair. Also matches UCX_Chair (no index)."""
    body = obj.name.split("_", 1)[1] if "_" in obj.name else ""
    body = DUPLICATE_SUFFIX.sub("", body)
    return re.sub(r"_\d+$", "", body)


def has_armature_deform(obj):
    return any(m.type == "ARMATURE" and m.object for m in obj.modifiers)


def set_is_skeletal(objects):
    return any(o.type == "ARMATURE" for o in objects)


def matches_owner(obj, owner, prefixes):
    """True if `owner` (taken from a UCX_ name) refers to this object."""
    name = clean_name(obj.name)
    return owner in {name, strip_known_prefix(name, prefixes)}


def strip_known_prefix(name, prefixes):
    for p in prefixes:
        if p and name.startswith(p):
            return name[len(p):]
    return name


def filtered_kwargs(op, kwargs):
    """Drop arguments this Blender version's exporter does not have.

    The FBX and glTF operators gain and lose properties between releases; this
    keeps one code path working from 3.6 through 5.x instead of version-testing.
    """
    try:
        valid = set(op.get_rna_type().properties.keys())
    except Exception:
        return kwargs
    return {k: v for k, v in kwargs.items() if k in valid}


def walk_collections(coll, depth=0):
    for child in coll.children:
        yield child, depth
        yield from walk_collections(child, depth + 1)


def export_collections(scene):
    """Every collection that can become a file, master collection included.

    Objects left directly in the Scene Collection are the common case, so it has
    to be a candidate — it just gets named after the scene rather than
    "Scene Collection".
    """
    master = scene.collection
    yield master, 0, clean_name(scene.name)
    for coll, depth in walk_collections(master):
        yield coll, depth + 1, clean_name(coll.name)


def deselect_all(context):
    # Iterating view_layer.objects can yield None entries when the depsgraph has
    # not caught up with objects linked earlier in the same operator, so work
    # from the selection itself, which is all this needs to clear anyway.
    for obj in context.selected_objects:
        if obj is not None:
            obj.select_set(False)


def object_is_visible(obj, view_layer):
    try:
        return obj.visible_get(view_layer=view_layer)
    except Exception:
        return not obj.hide_viewport


# --------------------------------------------------------------------------- #
# Export set
# --------------------------------------------------------------------------- #

class ExportSet:
    """One output file: a name, a subfolder and the objects that go into it."""

    __slots__ = ("name", "objects", "subpath", "skeletal")

    def __init__(self, name, objects, subpath="", skeletal=False):
        self.name = name
        self.objects = objects
        self.subpath = subpath
        self.skeletal = skeletal


def gather_sets(context, s):
    """Build the list of files to write, based on the chosen mode."""
    view_layer = context.view_layer
    sets = []

    def keep(obj):
        if obj.type not in EXPORTABLE_TYPES:
            return False
        if s.only_visible and not object_is_visible(obj, view_layer):
            return False
        return True

    if s.mode == "COLLECTION":
        for coll, _depth, label in export_collections(context.scene):
            if s.use_collection_filter and not coll.pipeline_include:
                continue
            # A collection that only groups children would otherwise duplicate
            # everything its children already export on their own.
            source = coll.objects if coll.children else coll.all_objects
            objects = [o for o in source if keep(o)]
            if not objects:
                continue
            subpath = coll.pipeline_subpath.strip()
            sets.append(ExportSet(
                name=label,
                objects=objects,
                subpath=subpath,
                skeletal=set_is_skeletal(objects),
            ))

    elif s.mode == "OBJECT":
        pool = context.selected_objects if s.selected_only else context.scene.objects
        pool = [o for o in pool if keep(o)]
        collisions = [o for o in pool if is_collision(o)]
        for obj in pool:
            if is_collision(obj):
                continue
            if obj.type == "ARMATURE":
                continue  # exported together with the mesh it deforms
            base = clean_name(strip_known_prefix(obj.name, (s.prefix_static, s.prefix_skeletal)))
            group = [obj]
            if s.include_collision:
                prefixes = (s.prefix_static, s.prefix_skeletal)
                group += [c for c in collisions
                          if matches_owner(obj, collision_owner_name(c), prefixes)]
            if has_armature_deform(obj):
                group += [m.object for m in obj.modifiers
                          if m.type == "ARMATURE" and m.object and m.object not in group]
            sets.append(ExportSet(base, group, "", set_is_skeletal(group)))

    elif s.mode == "SELECTED":
        objects = [o for o in context.selected_objects if keep(o)]
        if objects:
            name = clean_name(s.single_file_name or context.active_object.name)
            sets.append(ExportSet(name, objects, "", set_is_skeletal(objects)))

    else:  # SCENE
        objects = [o for o in context.scene.objects if keep(o)]
        if objects:
            name = clean_name(s.single_file_name or context.scene.name)
            sets.append(ExportSet(name, objects, "", set_is_skeletal(objects)))

    return sets


def final_filename(s, eset):
    name = eset.name
    if s.auto_prefix:
        prefix = s.prefix_skeletal if eset.skeletal else s.prefix_static
        name = strip_known_prefix(name, (s.prefix_static, s.prefix_skeletal))
        if prefix and not name.startswith(prefix):
            name = prefix + name
    return name


# --------------------------------------------------------------------------- #
# Baking: duplicate, apply, re-origin
# --------------------------------------------------------------------------- #

class Bake:
    """Temporary copies of the objects to export, cleaned up on exit."""

    def __init__(self, context, objects, settings, skeletal):
        self.context = context
        self.objects = objects
        self.s = settings
        self.skeletal = skeletal
        self.temp_coll = None
        self.copies = []

    def __enter__(self):
        ctx = self.context
        depsgraph = ctx.evaluated_depsgraph_get()

        self.temp_coll = bpy.data.collections.new("__pipeline_export__")
        ctx.scene.collection.children.link(self.temp_coll)

        mapping = {}
        for obj in self.objects:
            copy = self._copy_object(obj, depsgraph)
            self.temp_coll.objects.link(copy)
            self.copies.append(copy)
            mapping[obj] = copy

        self._rebuild_relationships(mapping)

        if self.skeletal:
            self._offset_skeletal()
        else:
            self._bake_static()

        return self.copies

    def _copy_object(self, obj, depsgraph):
        s = self.s
        deformed = has_armature_deform(obj)
        # Baking modifiers on a skinned mesh would freeze the armature into the
        # mesh, so those keep their modifier stack and let Unreal do the skinning.
        bake_modifiers = s.apply_modifiers and obj.type in MESH_LIKE_TYPES and not deformed

        if bake_modifiers:
            evaluated = obj.evaluated_get(depsgraph)
            mesh = bpy.data.meshes.new_from_object(
                evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
            copy = bpy.data.objects.new(obj.name, mesh)
            copy.matrix_world = obj.matrix_world.copy()
            for slot_src, slot_dst in zip(obj.material_slots, copy.material_slots):
                slot_dst.link = slot_src.link
        else:
            copy = obj.copy()
            if obj.data is not None:
                copy.data = obj.data.copy()

        if not s.export_animation:
            copy.animation_data_clear()
        return copy

    def _rebuild_relationships(self, mapping):
        """Point parents and armature modifiers at the copies, not the originals."""
        for original, copy in mapping.items():
            if original.parent in mapping:
                world = copy.matrix_world.copy()
                copy.parent = mapping[original.parent]
                copy.matrix_parent_inverse = mapping[original.parent].matrix_world.inverted()
                copy.matrix_world = world
            else:
                copy.parent = None
            for mod in copy.modifiers:
                if mod.type == "ARMATURE" and mod.object in mapping:
                    mod.object = mapping[mod.object]

    def _bake_static(self):
        """Push each object's world transform into its mesh, then re-origin."""
        for copy in self.copies:
            if copy.type not in MESH_LIKE_TYPES or copy.data is None:
                continue
            matrix = copy.matrix_world.copy()
            if self.s.apply_transforms:
                copy.data.transform(matrix)
                if matrix.determinant() < 0.0 and hasattr(copy.data, "flip_normals"):
                    copy.data.flip_normals()  # negative scale would invert the faces
                copy.matrix_world = Matrix.Identity(4)

        offset = self._pivot_offset()
        if offset.length_squared > 0.0:
            translate = Matrix.Translation(-offset)
            for copy in self.copies:
                if self.s.apply_transforms and copy.type in MESH_LIKE_TYPES and copy.data:
                    copy.data.transform(translate)
                elif copy.parent is None:
                    copy.matrix_world = translate @ copy.matrix_world

    def _offset_skeletal(self):
        offset = self._pivot_offset()
        if offset.length_squared == 0.0:
            return
        translate = Matrix.Translation(-offset)
        for copy in self.copies:
            if copy.parent is None:
                copy.matrix_world = translate @ copy.matrix_world

    def _pivot_offset(self):
        mode = self.s.origin_mode
        if mode == "NONE":
            return Vector((0.0, 0.0, 0.0))

        if mode == "ACTIVE":
            root = next((o for o in self.copies if o.parent is None), None)
            return root.matrix_world.translation.copy() if root else Vector()

        corners = []
        for copy in self.copies:
            if copy.type not in MESH_LIKE_TYPES:
                continue
            for corner in copy.bound_box:
                corners.append(copy.matrix_world @ Vector(corner))
        if not corners:
            return Vector((0.0, 0.0, 0.0))

        min_v = Vector((min(c[i] for c in corners) for i in range(3)))
        max_v = Vector((max(c[i] for c in corners) for i in range(3)))
        center = (min_v + max_v) * 0.5

        if mode == "BOUNDS_CENTER":
            return center
        if mode == "BOUNDS_BOTTOM":
            return Vector((center.x, center.y, min_v.z))
        return Vector((0.0, 0.0, 0.0))

    def __exit__(self, *exc):
        for copy in self.copies:
            data = copy.data
            bpy.data.objects.remove(copy, do_unlink=True)
            if data is None or data.users:
                continue
            for datablocks, datatype in (
                    (bpy.data.meshes, bpy.types.Mesh),
                    (bpy.data.armatures, bpy.types.Armature),
                    (bpy.data.curves, bpy.types.Curve),
                    (bpy.data.metaballs, bpy.types.MetaBall)):
                if isinstance(data, datatype):
                    datablocks.remove(data)
                    break
        if self.temp_coll is not None:
            bpy.data.collections.remove(self.temp_coll)
        return False


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #

def write_fbx(context, filepath, s, skeletal):
    kwargs = dict(
        filepath=filepath,
        check_existing=False,
        use_selection=True,
        use_visible=False,
        use_active_collection=False,
        global_scale=s.global_scale,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        use_space_transform=True,
        bake_space_transform=False,
        object_types={"MESH", "ARMATURE", "EMPTY", "OTHER"},
        use_mesh_modifiers=False,
        mesh_smooth_type="FACE",
        use_subsurf=False,
        use_mesh_edges=False,
        use_tspace=True,
        use_triangles=s.triangulate,
        use_custom_props=False,
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_armature_deform_only=True,
        armature_nodetype="NULL",
        bake_anim=bool(skeletal and s.export_animation),
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_simplify_factor=1.0,
        path_mode="COPY" if s.embed_textures else "AUTO",
        embed_textures=s.embed_textures,
        batch_mode="OFF",
        axis_forward="-Z",
        axis_up="Y",
    )
    bpy.ops.export_scene.fbx(**filtered_kwargs(bpy.ops.export_scene.fbx, kwargs))


def write_gltf(context, filepath, s, skeletal):
    kwargs = dict(
        filepath=filepath,
        check_existing=False,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_texture_dir="",
        export_animations=bool(skeletal and s.export_animation),
        export_skins=True,
        export_morph=True,
    )
    bpy.ops.export_scene.gltf(**filtered_kwargs(bpy.ops.export_scene.gltf, kwargs))


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

class PIPELINE_Issue(PropertyGroup):
    severity: EnumProperty(items=[("ERROR", "Error", ""), ("WARN", "Warning", "")],
                           default="WARN")
    object_name: StringProperty()
    message: StringProperty()


def validate_sets(sets):
    """Problems that only show up once objects are grouped into files."""
    issues = []
    for eset in sets:
        if not eset.skeletal:
            continue
        statics = [o for o in eset.objects
                   if o.type == "MESH" and not is_collision(o) and not has_armature_deform(o)]
        if statics:
            issues.append((
                "WARN", eset.name,
                "One rig here makes the whole set skeletal — %d static mesh(es) "
                "will be bundled into it. Split them out to get separate SM_ files."
                % len(statics)))
    return issues


def validate_objects(objects, s):
    issues = []

    def add(sev, obj, msg):
        issues.append((sev, obj.name if obj else "", msg))

    seen_names = {}
    for obj in objects:
        if obj.type != "MESH":
            continue
        name = clean_name(obj.name)
        seen_names.setdefault(name, []).append(obj.name)

        if is_collision(obj):
            continue

        if not obj.data.uv_layers:
            add("ERROR", obj, "No UV map — Unreal cannot build a lightmap")
        if not any(slot.material for slot in obj.material_slots):
            add("WARN", obj, "No material assigned")
        scale = obj.scale
        if any(abs(v - 1.0) > 1e-4 for v in scale) and not s.apply_transforms:
            add("WARN", obj, "Unapplied scale %.3f, %.3f, %.3f" % tuple(scale))
        if any(abs(v) > 1e-4 for v in obj.rotation_euler) and not s.apply_transforms:
            add("WARN", obj, "Unapplied rotation")
        ngons = sum(1 for p in obj.data.polygons if len(p.vertices) > 4)
        if ngons:
            add("WARN", obj, "%d n-gon(s) — triangulation may differ in Unreal" % ngons)
        if clean_name(obj.name) != obj.name:
            add("WARN", obj, "Name will be renamed to '%s' on export" % clean_name(obj.name))

    for cleaned, originals in seen_names.items():
        if len(originals) > 1:
            issues.append(("ERROR", ", ".join(originals),
                           "Names collide as '%s' — files would overwrite each other" % cleaned))

    for obj in objects:
        if is_collision(obj):
            owner = collision_owner_name(obj)
            prefixes = (s.prefix_static, s.prefix_skeletal)
            if not any(matches_owner(o, owner, prefixes) for o in objects):
                add("ERROR", obj, "Collision has no matching mesh named '%s'" % owner)

    return issues


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #

class PIPELINE_Settings(PropertyGroup):
    export_root: StringProperty(
        name="Output Folder", subtype="DIR_PATH", default="//export/",
        description="Where the exported files are written")
    mode: EnumProperty(
        name="Split By", default="COLLECTION",
        items=[
            ("COLLECTION", "Collection", "One file per collection"),
            ("OBJECT", "Object", "One file per object, collision included"),
            ("SELECTED", "Selection", "All selected objects into one file"),
            ("SCENE", "Scene", "Everything visible into one file"),
        ])
    file_format: EnumProperty(
        name="Format", default="FBX",
        items=[("FBX", "FBX", "Unreal's native import format"),
               ("GLTF", "glTF (.glb)", "For engines and viewers that prefer glTF")])
    single_file_name: StringProperty(
        name="File Name", default="",
        description="Name used by Selection and Scene modes. Leave empty to use the "
                    "active object or scene name")

    use_collection_filter: BoolProperty(
        name="Only Marked Collections", default=False,
        description="Export only collections ticked in the list below")
    selected_only: BoolProperty(name="Selected Only", default=True)
    only_visible: BoolProperty(
        name="Skip Hidden", default=True,
        description="Ignore objects hidden in the viewport")

    auto_prefix: BoolProperty(
        name="Auto Prefix", default=True,
        description="Add SM_ / SK_ to the file name following Unreal's naming convention")
    prefix_static: StringProperty(name="Static", default="SM_")
    prefix_skeletal: StringProperty(name="Skeletal", default="SK_")

    apply_modifiers: BoolProperty(
        name="Apply Modifiers", default=True,
        description="Bake modifiers into the exported mesh. Skinned meshes keep their "
                    "armature modifier so Unreal can do the deformation")
    apply_transforms: BoolProperty(
        name="Apply Transforms", default=True,
        description="Bake rotation and scale into the mesh so the asset arrives with a "
                    "clean 1,1,1 transform")
    origin_mode: EnumProperty(
        name="Origin", default="BOUNDS_BOTTOM",
        items=[
            ("NONE", "Keep World Position", "Export where the object sits in the scene"),
            ("ACTIVE", "Object Origin", "Use the object's own origin"),
            ("BOUNDS_CENTER", "Bounds Center", "Centre the asset on its bounding box"),
            ("BOUNDS_BOTTOM", "Bounds Bottom", "Centre X/Y, sit the asset on the floor"),
        ])
    include_collision: BoolProperty(
        name="Include UCX Collision", default=True,
        description="Export UCX_/UBX_/USP_ meshes alongside the mesh they belong to")
    triangulate: BoolProperty(name="Triangulate", default=False)
    embed_textures: BoolProperty(name="Embed Textures", default=False)
    export_animation: BoolProperty(
        name="Export Animation", default=False,
        description="Bake animation for skeletal sets")
    global_scale: FloatProperty(
        name="Scale", default=1.0, min=0.001, max=1000.0,
        description="Leave at 1.0 — Blender metres map to Unreal centimetres automatically")

    subfolder_per_type: BoolProperty(
        name="Subfolder Per Type", default=False,
        description="Write static meshes and skeletal meshes into separate folders")
    dry_run: BoolProperty(
        name="Dry Run", default=False,
        description="List what would be written without writing anything")

    issues: CollectionProperty(type=PIPELINE_Issue)
    last_report: StringProperty(default="")


# --------------------------------------------------------------------------- #
# Operators
# --------------------------------------------------------------------------- #

class PIPELINE_OT_validate(Operator):
    bl_idname = "pipeline.validate"
    bl_label = "Validate"
    bl_description = "Check the export sets for problems Unreal would complain about"
    bl_options = {"REGISTER"}

    def execute(self, context):
        s = context.scene.pipeline
        s.issues.clear()

        sets = gather_sets(context, s)
        if not sets:
            self.report({"WARNING"}, "Nothing to export with the current settings")
            return {"CANCELLED"}

        objects = []
        for eset in sets:
            for obj in eset.objects:
                if obj not in objects:
                    objects.append(obj)

        found = validate_objects(objects, s) + validate_sets(sets)
        for severity, name, message in found:
            item = s.issues.add()
            item.severity = severity
            item.object_name = name
            item.message = message

        errors = sum(1 for i in s.issues if i.severity == "ERROR")
        if not len(s.issues):
            self.report({"INFO"}, "%d set(s) ready, no issues" % len(sets))
        else:
            self.report({"WARNING"}, "%d issue(s), %d blocking" % (len(s.issues), errors))
        return {"FINISHED"}


class PIPELINE_OT_fix_names(Operator):
    bl_idname = "pipeline.fix_names"
    bl_label = "Fix Names"
    bl_description = "Rename objects to Unreal-safe names (no spaces, no .001 suffixes)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.pipeline
        pool = context.selected_objects if s.selected_only else context.scene.objects
        renamed = 0
        for obj in list(pool):
            new = clean_name(obj.name)
            if new != obj.name and new not in bpy.data.objects:
                obj.name = new
                renamed += 1
        self.report({"INFO"}, "Renamed %d object(s)" % renamed)
        return {"FINISHED"}


class PIPELINE_OT_mark_collections(Operator):
    bl_idname = "pipeline.mark_collections"
    bl_label = "Mark All"
    bl_description = "Tick or untick every collection at once"
    bl_options = {"REGISTER", "UNDO"}

    state: BoolProperty(default=True)

    def execute(self, context):
        for coll, _depth, _label in export_collections(context.scene):
            coll.pipeline_include = self.state
        return {"FINISHED"}


class PIPELINE_OT_open_folder(Operator):
    bl_idname = "pipeline.open_folder"
    bl_label = "Open Output Folder"
    bl_options = {"REGISTER"}

    def execute(self, context):
        path = bpy.path.abspath(context.scene.pipeline.export_root)
        if not os.path.isdir(path):
            self.report({"ERROR"}, "Folder does not exist yet")
            return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=path)
        return {"FINISHED"}


class PIPELINE_OT_export(Operator):
    bl_idname = "pipeline.export"
    bl_label = "Export to Unreal"
    bl_description = "Write every export set to disk"
    bl_options = {"REGISTER"}

    def execute(self, context):
        s = context.scene.pipeline
        started = time.time()

        root = bpy.path.abspath(s.export_root)
        if not root:
            self.report({"ERROR"}, "Set an output folder first")
            return {"CANCELLED"}

        sets = gather_sets(context, s)
        if not sets:
            self.report({"WARNING"}, "Nothing matched the current settings")
            return {"CANCELLED"}

        checked = validate_objects([o for e in sets for o in e.objects], s)
        for _severity, name, message in validate_sets(sets):
            self.report({"WARNING"}, "%s: %s" % (name, message))
        blocking = [i for i in checked if i[0] == "ERROR"]
        if blocking and not s.dry_run:
            s.issues.clear()
            for severity, name, message in blocking:
                item = s.issues.add()
                item.severity, item.object_name, item.message = severity, name, message
            self.report({"ERROR"},
                        "%d blocking issue(s) — see the Issues panel" % len(blocking))
            return {"CANCELLED"}

        previous_selection = list(context.selected_objects)
        previous_active = context.view_layer.objects.active
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        written = []
        failed = []

        for eset in sets:
            folder = root
            if s.subfolder_per_type:
                folder = os.path.join(folder, "Skeletal" if eset.skeletal else "Static")
            if eset.subpath:
                folder = os.path.join(folder, eset.subpath)

            filename = final_filename(s, eset)
            ext = ".fbx" if s.file_format == "FBX" else ".glb"
            filepath = os.path.join(folder, filename + ext)

            if s.dry_run:
                written.append(filepath)
                continue

            try:
                os.makedirs(folder, exist_ok=True)
                with Bake(context, eset.objects, s, eset.skeletal) as copies:
                    deselect_all(context)
                    for copy in copies:
                        copy.select_set(True)
                    context.view_layer.objects.active = copies[0]
                    if s.file_format == "FBX":
                        write_fbx(context, filepath, s, eset.skeletal)
                    else:
                        write_gltf(context, filepath, s, eset.skeletal)
                written.append(filepath)
            except Exception as exc:  # keep going, one bad set should not stop the batch
                failed.append("%s: %s" % (filename, exc))

        deselect_all(context)
        for obj in previous_selection:
            try:
                obj.select_set(True)
            except Exception:
                pass
        if previous_active:
            context.view_layer.objects.active = previous_active

        elapsed = time.time() - started
        verb = "Would write" if s.dry_run else "Exported"
        s.last_report = "%s %d file(s) in %.1fs" % (verb, len(written), elapsed)
        if failed:
            s.last_report += " — %d failed" % len(failed)
            for message in failed:
                self.report({"ERROR"}, message)
        for path in written:
            print("[Pipeline] %s %s" % (verb, path))

        self.report({"INFO"}, s.last_report)
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #

class PIPELINE_PT_base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Pipeline"


class PIPELINE_PT_main(PIPELINE_PT_base, Panel):
    bl_label = "Unreal Export"
    bl_idname = "PIPELINE_PT_main"

    def draw(self, context):
        layout = self.layout
        s = context.scene.pipeline

        col = layout.column(align=True)
        col.prop(s, "export_root")
        row = col.row(align=True)
        row.prop(s, "file_format", expand=True)

        layout.separator()
        layout.prop(s, "mode")
        if s.mode == "OBJECT":
            layout.prop(s, "selected_only")
        elif s.mode in {"SELECTED", "SCENE"}:
            layout.prop(s, "single_file_name")
        layout.prop(s, "only_visible")

        layout.separator()
        big = layout.column(align=True)
        big.scale_y = 1.6
        big.operator("pipeline.export", icon="EXPORT")
        row = layout.row(align=True)
        row.operator("pipeline.validate", icon="CHECKMARK")
        row.operator("pipeline.open_folder", text="", icon="FILE_FOLDER")
        layout.prop(s, "dry_run")

        if s.last_report:
            layout.label(text=s.last_report, icon="INFO")


class PIPELINE_PT_naming(PIPELINE_PT_base, Panel):
    bl_label = "Naming"
    bl_parent_id = "PIPELINE_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        s = context.scene.pipeline
        layout.prop(s, "auto_prefix")
        row = layout.row(align=True)
        row.enabled = s.auto_prefix
        row.prop(s, "prefix_static")
        row.prop(s, "prefix_skeletal")
        layout.prop(s, "subfolder_per_type")
        layout.operator("pipeline.fix_names", icon="SORTALPHA")


class PIPELINE_PT_transform(PIPELINE_PT_base, Panel):
    bl_label = "Geometry"
    bl_parent_id = "PIPELINE_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        s = context.scene.pipeline
        layout.prop(s, "origin_mode")
        layout.prop(s, "apply_transforms")
        layout.prop(s, "apply_modifiers")
        layout.prop(s, "include_collision")
        layout.prop(s, "triangulate")
        layout.prop(s, "embed_textures")
        layout.prop(s, "export_animation")
        layout.prop(s, "global_scale")


class PIPELINE_PT_collections(PIPELINE_PT_base, Panel):
    bl_label = "Collections"
    bl_parent_id = "PIPELINE_PT_main"

    @classmethod
    def poll(cls, context):
        return context.scene.pipeline.mode == "COLLECTION"

    def draw(self, context):
        layout = self.layout
        s = context.scene.pipeline
        layout.prop(s, "use_collection_filter")

        row = layout.row(align=True)
        row.operator("pipeline.mark_collections", text="Mark All").state = True
        row.operator("pipeline.mark_collections", text="Clear All").state = False

        box = layout.box()
        master = context.scene.collection
        for coll, depth, label in export_collections(context.scene):
            row = box.row(align=True)
            for _ in range(depth):
                row.label(text="", icon="BLANK1")
            row.prop(coll, "pipeline_include", text="")
            row.label(text=label,
                      icon="SCENE_DATA" if coll == master else "OUTLINER_COLLECTION")
            sub = row.row()
            sub.scale_x = 0.9
            sub.prop(coll, "pipeline_subpath", text="")


class PIPELINE_PT_issues(PIPELINE_PT_base, Panel):
    bl_label = "Issues"
    bl_parent_id = "PIPELINE_PT_main"

    @classmethod
    def poll(cls, context):
        return len(context.scene.pipeline.issues) > 0

    def draw(self, context):
        layout = self.layout
        for issue in context.scene.pipeline.issues:
            row = layout.row()
            row.label(
                text="%s: %s" % (issue.object_name, issue.message),
                icon="ERROR" if issue.severity == "ERROR" else "INFO")


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #

CLASSES = (
    PIPELINE_Issue,
    PIPELINE_Settings,
    PIPELINE_OT_validate,
    PIPELINE_OT_fix_names,
    PIPELINE_OT_mark_collections,
    PIPELINE_OT_open_folder,
    PIPELINE_OT_export,
    PIPELINE_PT_main,
    PIPELINE_PT_naming,
    PIPELINE_PT_transform,
    PIPELINE_PT_collections,
    PIPELINE_PT_issues,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pipeline = PointerProperty(type=PIPELINE_Settings)
    bpy.types.Collection.pipeline_include = BoolProperty(
        name="Export", default=True,
        description="Include this collection when Only Marked Collections is on")
    bpy.types.Collection.pipeline_subpath = StringProperty(
        name="Subfolder", default="",
        description="Optional subfolder under the output folder")


def unregister():
    del bpy.types.Collection.pipeline_subpath
    del bpy.types.Collection.pipeline_include
    del bpy.types.Scene.pipeline
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

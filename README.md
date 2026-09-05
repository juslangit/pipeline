# Pipeline — Unreal Batch Exporter

A Blender add-on that turns a scene into Unreal-ready files in one click, with the
naming, unit scale, pivots and collision meshes Unreal expects.

The tedium it removes: applying transforms by hand, renaming to `SM_` / `SK_`,
dragging pivots to the floor, keeping `UCX_` collision attached to the right mesh,
and exporting forty objects one at a time.

## Install

1. Download `pipeline_ue-1.0.0.zip`
2. Blender 4.2+ — **Edit ▸ Preferences ▸ Get Extensions ▸ ⌄ ▸ Install from Disk**
   Blender 3.6–4.1 — **Edit ▸ Preferences ▸ Add-ons ▸ Install**
3. Enable it, then press **N** in the 3D viewport and open the **Pipeline** tab

## Quick start

1. Set the **Output Folder**
2. Choose how to split the export — per collection, per object, the selection, or the whole scene
3. Press **Validate** to see what Unreal would complain about
4. Press **Export to Unreal**

## What it does for you

| | |
|---|---|
| **Naming** | Adds `SM_` to static meshes and `SK_` to skeletal meshes, strips `.001` suffixes and spaces, and blocks the export when two objects would overwrite each other's file |
| **Collision** | `UCX_Chair_01` travels with `Chair` and never becomes its own asset |
| **Pivots** | Re-origins each asset to its bounding centre, its bounding bottom (props that sit on the floor), or its own origin |
| **Transforms** | Bakes rotation and scale into the mesh so the asset lands in Unreal with a clean 1,1,1 transform — negative scale is handled, so faces don't arrive inside out |
| **Units** | Blender metres map to Unreal centimetres without you touching the FBX scale settings |
| **Skinned meshes** | Keep their armature modifier instead of having it baked into the mesh, so Unreal does the deformation |
| **Validation** | Missing UVs, missing materials, unapplied transforms, n-gons, colliding names, orphan collision |
| **Non-destructive** | Everything is baked on temporary copies. Your scene is exactly as you left it |

## Naming conventions it follows

| Prefix | Meaning |
|---|---|
| `SM_` | Static mesh |
| `SK_` | Skeletal mesh |
| `UCX_` `UBX_` `USP_` `UCP_` | Convex, box, sphere and capsule collision |

Collision is matched by name: `UCX_<MeshName>_<number>`.

## Modes

- **Collection** — one file per collection. A collection that only groups other
  collections is skipped, so nothing gets exported twice. Each collection can carry
  its own subfolder.
- **Object** — one file per object, with its collision and its armature.
- **Selection** — everything selected into a single file.
- **Scene** — everything visible into a single file.

**Dry Run** lists the files it would write without touching the disk.

## Formats

FBX (Unreal's native import) and glTF `.glb`.

## Requirements

Blender 3.6 or newer, no external dependencies. Developed and tested against
**Blender 5.2.1 LTS**; older versions are supported by filtering the exporter
arguments against whatever the running Blender declares, but have not been tested
on real hardware yet.

## Building from source

```bash
./build.sh          # writes dist/pipeline_ue-<version>.zip
```

## Tests

```bash
blender --background --python tests/test_pipeline.py
```

## Licence

GPL-3.0-or-later, as required for anything that imports `bpy`.

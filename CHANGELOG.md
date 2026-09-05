# Changelog

## 1.0.0 — 2026-09-05

First release.

- Batch export by collection, object, selection or whole scene
- FBX and glTF (.glb) output
- Automatic `SM_` / `SK_` prefixes and Unreal-safe name cleanup
- `UCX_` / `UBX_` / `USP_` / `UCP_` collision travels with its mesh
- Pivot re-origin: bounds centre, bounds bottom, or object origin
- Transforms and modifiers baked on temporary copies, scene left untouched
- Skinned meshes keep their armature modifier for Unreal to deform
- Validation pass that blocks the export on missing UVs and colliding names
- Dry run, per-collection subfolders, optional per-type subfolders

Verified on Blender 5.2.1 LTS: 25 headless checks, including a full FBX round trip
that confirms pivots, baked rotation, unit scale and mirrored normals.

---
doc: ue5-verification
project: pipeline
updated: 2026-09-05
---

# UE5 import check

Run this on whichever machine has Unreal. Clone or pull the repo there:

```bash
git clone https://github.com/juslangit/pipeline.git
```

Takes about 20 minutes. It is the last thing blocking the launch.

---

## Part 1 — make the test files (in Blender)

1. New scene. Add a cube, scale it to roughly **2 m tall**, move it away from the
   world origin and rotate it maybe 30 degrees. Name it `Chair`.
2. Add a second, simpler cube roughly wrapping it. Name it exactly `UCX_Chair_01`.
3. Add a third cube named `Body`. Add an armature, parent `Body` to it with
   automatic weights, and move one bone so you can see the mesh deform.
4. Open the **Pipeline** panel (press N).
   - Output Folder: anywhere you can find again
   - Split By: **Object**
   - Origin: **Bounds Bottom**
   - Selected Only: **off**
5. Press **Validate**, then **Export to Unreal**.

You should get `SM_Chair.fbx` and `SK_Body.fbx`. No `SM_UCX_Chair_01.fbx` — if that
file exists, stop and tell me.

---

## Part 2 — import (in UE5)

Drag `SM_Chair.fbx` into the Content Browser. In the import dialog:

- **Skeletal Mesh** — unchecked
- **Auto Generate Collision** — **unchecked** (this matters: leave it on and Unreal
  makes its own collision and you learn nothing about ours)
- **One Convex Hull per UCX** — checked
- **Combine Meshes** — unchecked

Then drag in `SK_Body.fbx` with **Skeletal Mesh checked** and no existing skeleton
selected, so it creates a new one.

---

## Part 3 — the four checks

### 1. Scale
Drop `SM_Chair` into the level. In the Details panel its height should read about
**200 units** (cm), matching the 2 m you built.

- Reads ~200 → **pass**
- Reads ~2 → unit scale is wrong, tell me
- Reads ~20000 → unit scale is wrong the other way, tell me

### 2. Pivot
Look at the move gizmo on the placed asset. It should sit at the **bottom centre**
of the chair, and the chair should rest on the floor grid rather than sinking
through it or hovering above it.

### 3. Collision
Open `SM_Chair` by double-clicking it. In the Static Mesh editor toolbar, turn on
**Collision** (or Show → Simple Collision). Then check the stats panel on the right.

- Green wireframe box around the mesh, **Collision Primitives: 1** → **pass**
- Collision Primitives: 0 → the UCX was dropped, tell me
- The UCX box appears as solid visible geometry → naming is not being read, tell me

### 4. Skeleton
Double-click `SK_Body`. It should open in the Skeletal Mesh editor with a bone
hierarchy in the tree on the left.

Then open the **Skeleton** asset and rotate a bone. The mesh should deform with it.

- Mesh deforms → **pass**
- Mesh exists but no bones, or bones do not move it → skin weights were lost, tell me
- Mesh arrives frozen in the posed shape → the armature got baked in, tell me

---

## Part 4 — report back

Tell me the result as four words, for example:

```
scale pass, pivot pass, collision fail, skeleton pass
```

Plus anything that looked odd. Every failure is fixable — that is the whole reason
for doing this before the listing goes live rather than after.

If all four pass, the listing is cleared to publish as written and I will remove
the honesty gate.

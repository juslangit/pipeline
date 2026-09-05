---
doc: store-listing
project: pipeline
updated: 2026-09-05
---

# Store listing copy — Pipeline v1.0.0

Paste-ready text for Blender Market / Gumroad / Payhip. Sections are marked with
the field they belong in. Nothing here claims anything the add-on has not been
tested doing — see the honesty gate at the bottom before publishing.

---

## PRODUCT NAME

Pipeline — Unreal Batch Exporter

## TAGLINE (under 70 characters)

Export a whole Blender scene to Unreal in one press.

## SHORT DESCRIPTION (the card blurb, ~2 sentences)

Pipeline exports your Blender scene to Unreal Engine with the naming, unit scale,
pivots and collision meshes Unreal expects — for every object at once, without
touching your scene.

---

## FULL DESCRIPTION

### The hour you lose every time

Getting assets from Blender into Unreal is the same four chores, over and over.

Rename to `SM_` or `SK_`. Apply the rotation and scale so the asset doesn't arrive
squashed. Drag the pivot to the bottom of the mesh so the prop sits on the floor
instead of hovering next to it. Keep each `UCX_` collision mesh matched to the mesh
it belongs to.

A minute per object. Forty props is your afternoon.

Then you find one of them had no UV map, and Unreal only tells you after the import.

### One press

Pipeline is a panel in Blender's sidebar. Point it at a folder, choose how you want
the scene split up, and press Export. It handles all four chores for every object in
the batch, and checks the work before it starts.

### It never touches your scene

This is the part most exporters get wrong. Pipeline does not apply transforms to
your objects, does not move your pivots, and does not rename anything. It makes
temporary copies, does the work on those, exports them, and deletes them.

Your file at the end is exactly what it was before you pressed the button — no undo
stack to unwind, no "did that just change my mesh?"

### A pre-flight check, not a surprise

Press Validate and Pipeline tells you what Unreal would reject, before you export:
missing UV maps, missing materials, unapplied transforms, n-gons, collision with no
matching mesh, and two objects whose names would collide into the same file.

Blocking problems stop the export rather than writing a broken file you discover
three days later.

---

## FEATURE LIST (bullets)

- **Four ways to split the batch** — one file per collection, one per object, the
  current selection, or the whole scene
- **FBX and glTF (.glb)** output
- **Automatic `SM_` / `SK_` prefixes** — works out which from whether the object has
  a skeleton, and cleans names Unreal would rename anyway (`Chair.003` → `Chair`)
- **`UCX_` collision travels with its mesh** — `UCX_Chair_01` exports inside
  `SM_Chair.fbx` and never becomes an asset of its own. `UBX_`, `USP_` and `UCP_`
  are handled the same way
- **Pivot placement** — bounds bottom (props that sit on the floor), bounds centre,
  the object's own origin, or leave world position alone for level layout
- **Transforms baked properly** — including mirrored objects, whose faces would
  otherwise arrive inside out
- **Blender metres map to Unreal centimetres** without touching FBX scale settings
- **Rigged meshes keep their skinning** — the armature modifier is preserved instead
  of being frozen into the mesh
- **Validation pass** that blocks the export on problems Unreal would reject
- **Dry run** — see which files it would write without writing any
- **Per-collection subfolders**, so your Unreal content folder structure comes out
  of Blender already organised
- **Non-destructive** — your scene is untouched, always

---

## WHAT IT DOES NOT DO

Stated up front so nobody buys the wrong thing:

- It writes files. It does not talk to a running Unreal editor.
- It does not build Unreal materials — it exports meshes, UVs and material slots.
- No LOD generation in 1.0.
- No animation-only export in 1.0 (planned for 1.1).

---

## REQUIREMENTS

- Blender 3.6 or newer
- No external dependencies, no account, no internet connection

Developed and tested against Blender 5.2.1 LTS. Older versions are supported by
adapting to whatever the running Blender's exporter offers, rather than assuming a
fixed set of options.

Installs as a Blender extension on 4.2+ (Preferences → Get Extensions → Install from
Disk) and as a classic add-on on 3.6–4.1, from the same download.

---

## FAQ

**Will it change my .blend file?**
No. Everything is done on temporary copies that are deleted afterwards. Your objects,
their transforms, pivots and names are exactly as you left them.

**What if my objects are just sitting loose in the Scene Collection?**
They export fine. The Scene Collection is treated as a collection like any other and
named after your scene.

**I use a nested collection structure. Will things export twice?**
No. A collection that only groups other collections exports nothing itself, so its
children don't get duplicated into a parent file.

**Does it work with rigged characters?**
Yes. A mesh with an armature modifier is detected as skeletal, gets the `SK_` prefix,
and keeps its modifier so Unreal does the deformation rather than the pose being
baked into the mesh.

**What about mirrored objects?**
Handled. A negatively-scaled object would normally arrive with its faces inside out;
Pipeline detects this and corrects the normals.

**Can I try it on one object first?**
Use Dry Run to see what it would write, or set Split By to Object with Selected Only.

---

## CHANGELOG

### 1.0.0
First release. Four export modes, FBX and glTF output, automatic Unreal naming,
`UCX_` collision matching, pivot re-origin, non-destructive transform and modifier
baking, skeletal mesh support, validation pass, dry run.

---

## SCREENSHOT SHOT LIST

Five images. Shoot them at the same window size, on Blender's default dark theme.

1. **The panel, whole.** Sidebar open on a real scene with a dozen props visible.
   This is the thumbnail — it has to say "this is a tool, not a preset pack."
2. **Before and after names.** Outliner showing `Cube.003`, `chair final v2`,
   `Untitled` beside a Finder window showing `SM_Cube.fbx`, `SM_chair_final_v2.fbx`.
3. **The Validate result.** Issues panel listing a missing UV and a name collision,
   in red. Sells the pre-flight check better than any sentence.
4. **Collision.** A chair with its `UCX_` shape visible in wireframe, next to the
   Unreal import dialog showing the collision detected.
5. **The output folder.** Forty correctly named files in one Finder window, with a
   timer or the "Exported 40 files in 3.2s" report line visible.

---

## 60-SECOND DEMO VIDEO SCRIPT

No voiceover needed — text captions over screen capture. Voiceover is better if you
are comfortable, but captions ship faster and work with the sound off, which is how
store pages get watched.

**0:00–0:08 — The pain, fast.**
Screen capture, sped up 4×: manually applying transform, renaming an object, dragging
a pivot, opening the FBX export dialog. Do it for two objects so the repetition reads.
Caption: *"Every asset. Every time."*

**0:08–0:12 — The scene.**
Pan across a scene with 40 props.
Caption: *"Now do it forty more times."*

**0:12–0:20 — The panel.**
Press N, open Pipeline, set the output folder, choose Split By: Object.
Caption: *"Or don't."*

**0:20–0:26 — Validate.**
Press Validate, an issue appears, fix it, press again, clean.
Caption: *"It checks before you export, not after Unreal complains."*

**0:26–0:34 — The export.**
Press Export. Cut to the output folder filling with correctly named files.
Caption: *"40 files. 3 seconds."*

**0:34–0:46 — The proof in Unreal.**
Drag the folder into Unreal. Show one asset: pivot at the base, 1,1,1 transform,
collision present in the mesh editor.
Caption: *"Correct pivots. Correct scale. Collision already attached."*

**0:46–0:55 — The reassurance.**
Cut back to Blender. Show the original scene untouched — names, transforms, pivots
all as they were.
Caption: *"And your scene never changed."*

**0:55–1:00 — Card.**
Product name, Blender version support, price.

---

## PRICING

Recommendation: **$19 USD** at launch (about RM 85).

Reasoning:
- Paid Blender exporters cluster in the $15–$30 band. Below $15 buyers assume it is
  a weekend script; above $30 they expect a live Unreal connection.
- $19 is an impulse purchase for a working artist — roughly one hour of the time it
  saves on a single medium project.
- It leaves room for a $29 price after 1.1 adds animation export, and existing
  customers get the update free, which is the usual model and generates goodwill.

Launch discount: 25% off for the first two weeks is standard on Blender Market and
drives the early reviews that carry the listing afterwards.

---

## HONESTY GATE — read before publishing

As of 2026-09-05 the add-on has been verified by measuring its exported files back
in Blender: pivots, baked rotation, unit scale and mirrored normals are all correct,
across 25 automated checks on Blender 5.2.1.

It has **not** been imported into Unreal Engine 5 by anyone yet.

Do not publish the UE5 claims in this listing — the collision screenshot, the video's
0:34–0:46 section, and the FAQ answer about rigged characters — until you have
imported an `SM_` and an `SK_` file into UE5 yourself and confirmed:

1. The mesh arrives at the right scale and the pivot is where you asked for it
2. `UCX_` meshes register as collision, not as visible geometry
3. The `SK_` file produces a usable skeleton and skin weights

If any of those turn out wrong, fix the add-on and re-shoot, rather than softening
the copy. A listing that overclaims earns refunds and a one-star review, which on
Blender Market is much more expensive than a two-day delay.

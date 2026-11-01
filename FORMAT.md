# File formats — version 3

All text files are UTF-8, `\n` line endings. All coordinates in v3 files are **local grid coordinates**: integers starting at 0, `x` and `z` counted from the region's north-west corner, `y` counted up from the lowest cell. (Minecraft world coordinates are `world = origin + local`, with `originX`, `originZ`, `minY` from `grid.json`; only the original v2 files use world coordinates.)
中文摘要:v3 的文件都是 UTF-8;坐标一律是局部坐标(从 0 起,y 向上)。地形是每格一个字节的类别码,问题与答案是 CSV,路径是 JSONL。

## Package layout

```
neutral/classes.json            the class table (flags of every class code)
neutral/<region>/grid.bin.gz    terrain: one byte per cell
neutral/<region>/grid.json      grid size, origin, rules version
neutral/<region>/blockmap.csv   which Minecraft block state became which class (provenance)
scenarios/<region>.csv          the problems
grav3d/costs.json               the cost table of the rules (see RULES.md)
grav3d/manifest.json            counts per region and track, solver run, checksums
grav3d/answers/<region>.csv     reference answers (both tracks)
grav3d/paths/<region>.jsonl     reference paths
tools/validate.py, tools/solver/Solve.java, tools/make_scenarios.py, tools/make_package.py
tests/conformance/              hand-built small maps with expected optimal values
terrain/<region>/               the original Minecraft region files (.mca) and terrain.properties
problems/<region>.jsonl, regions.json, manifest.json, answers.jsonl, answers-manifest.json
                                the Numen layer (Minecraft world coordinates; the answers are Numen's own search under pure physical time, not a true optimum)
```

## `neutral/classes.json`

```json
{"rules":"grav3d-1.0","classes":[
  {"code":0,"name":"air","passable":true,"support":false,"swim":false,"climb":false,"dig":0,"place":true,"about":"…"},
  …]}
```

One object per class code `0..9`. `passable`, `support`, `swim` (still water), `climb`, `place` (a block can be placed into the cell) are booleans; `dig` is the dig tier (1–3) or 0 for "cannot be dug". Code `255` is never stored: it stands for "outside the grid". The meaning of the flags is in [RULES.md](RULES.md).

## `neutral/<region>/grid.json`

```json
{"rules":"grav3d-1.0","name":"hills","sizeX":512,"sizeZ":512,"sizeY":384,"minY":-64,
 "originX":0,"originZ":0,"dimension":"numen_test:terrain","minecraft":"1.21.1"}
```

`sizeX`, `sizeZ`, `sizeY` are the grid dimensions. `originX`, `originZ`, `minY` map local to Minecraft coordinates and are irrelevant to planners.

## `neutral/<region>/grid.bin.gz`

A gzip stream of exactly `sizeX · sizeZ · sizeY` bytes. The class code of cell `(x, y, z)` is the byte at offset

```
((x · sizeZ) + z) · sizeY + y        (y is the fastest-varying index)
```

```python
import gzip, json
meta = json.load(open("neutral/hills/grid.json"))
cells = gzip.open("neutral/hills/grid.bin.gz").read()
def cell(x, y, z):
    return cells[(x * meta["sizeZ"] + z) * meta["sizeY"] + y]
```

## `neutral/<region>/blockmap.csv`

Provenance only, nothing reads it: `state,class,name,cells` — a Minecraft block state (as in the `/setblock` syntax, quoted because it contains commas), the class code and name it was mapped to, and how many cells of this region have it. The mapping is computed, not tabulated: the collision shape of the block state (height ≥ 0.5 counts as solid, higher than 1 as `tall`), its hardness (dig tier), and a few semantic tags (climbable, fluid, hazardous, openable by hand). Rules are in the Numen source (`Neutral.java`).

## `scenarios/<region>.csv`

```
version,1
id,region,bucket,split,sx,sy,sz,goal,gx,gy,gz,radius
hills-short-001,hills,short,dev,361,130,414,at,350,128,414,
hills-short-003,hills,short,held,85,152,225,near,68,143,239,4
```

The first line is the format version. Columns: `id` (unique, e.g. `<region>-<bucket>-<nnn>`); `region`; `bucket` (`short` ≤ 32, `medium` 32–128, `long` 128–400 cells of straight-line 3D distance); `split` (`dev` for tuning, `held` kept for final evaluation; the split is by hash of the id, region `mixed` is all `held`); the start feet cell `sx, sy, sz`; `goal` (`at`, `near` or `dig`); the goal cell `gx, gy, gz`; `radius` (only for `near`, otherwise empty).

## `grav3d/answers/<region>.csv`

```
id,track,status,cost,digs,places
hills-short-001,A,optimal,78607,0,0
hills-short-001,E,optimal,66339,0,2
hills-long-001,A,unsolvable,,,
```

One row per problem and track (`A` or `E`, see RULES.md). `status` is `optimal`, `unsolvable` or `n/a`. `cost` is the minimal total cost in millitick; `digs` and `places` count the edits of the reference path (they are not unique among optimal paths); all three are empty unless `optimal`.

## `grav3d/paths/<region>.jsonl`

One JSON object per line, for every `optimal` row and, as a convenience, for every `unsolvable` row:

```json
{"id":"hills-short-001","track":"E","path":[[361,130,414],[360,130,414],…]}
{"id":"hills-long-001","track":"A","status":"unsolvable"}
```

`path` is the sequence of feet cells from the start to the final cell (both included), in local coordinates. This is also the **submission format** for the validator: a planner writes one line per problem and track, either a `path` or `"status":"unsolvable"`.

## Validator output

`tools/validate.py` prints one CSV row per problem and track: `id,track,verdict,cost,digs,places,ratio_or_reason`, with `verdict` one of `valid` (then `ratio` = submitted cost / optimal cost, ≥ 1), `invalid-<i>` (step `i` is illegal, `i` counted from 1 for the move from `path[i-1]` to `path[i]`, `invalid-0` for a wrong start; the reason is in the last column), `invalid-goal`, `missing`, `unsolvable-ok`, `unsolvable-wrong`, `reference-error`, `n/a`. See the docstring of the script.

## `grav3d/manifest.json`

Rules version, number of problems per region and track by status (`optimal`, `unsolvable`, `n/a`), the solver run (wall time, threads, JVM), and the sha256 of every data file in the package.

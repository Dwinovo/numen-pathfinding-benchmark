# GRAV3D rules — version `grav3d-1.0`

GRAV3D is an abstract movement model on a 3D grid with gravity: a body two cells tall walks, climbs, swims, falls, and (on track E) digs and places blocks. It is fully defined by this page plus two small data files, so any planner can be run against it and any answer can be checked, without Minecraft.
中文摘要:GRAV3D 是三维带重力格子上的一套抽象走法,身体占上下两格,会走、爬、游、下落,E 赛道还能挖、放块。规则全部由本页和 `neutral/classes.json`、`grav3d/costs.json` 两个数据文件定义,不需要 Minecraft 就能跑求解器、验答案。

The rules are a benchmark definition, not a claim about any game's physics: the cost constants were derived once from Minecraft-like kinematics and then frozen.
"Optimal" always means optimal **under these rules**.

## 1. World

- A grid of `X × Z × Y` cells, each with a **class code** (one byte; see `neutral/classes.json` and [FORMAT.md](FORMAT.md)). Coordinates are integers `(x, y, z)`, all starting at 0; `y` is up.
- Everything outside the grid is class **out**: not passable, not support, not diggable, not placeable. There is no "beyond the region": the grid is the whole world.
- Time is measured in **millitick** (1 tick = 50 ms, 1 millitick = 0.05 ms), integers only.

## 2. Class flags

Each class has these flags (the values are in `neutral/classes.json`; this table is the version for `grav3d-1.0`):

| code | name | P passable | S support | W swim | L climb | dig tier | place | what |
|---|---|---|---|---|---|---|---|---|
| 0 | air | yes | no | no | no | – | yes | air, plants, carpets, snow layers: collision under half a block |
| 1 | soft | no | yes | no | no | 1 | no | solid, hardness < 1.5: dirt, sand, leaves, glass |
| 2 | stone | no | yes | no | no | 2 | no | solid, hardness 1.5 to < 3: stone, cobblestone, planks, logs |
| 3 | hard | no | yes | no | no | 3 | no | solid, hardness ≥ 3: deepslate, ores, obsidian |
| 4 | bedrock | no | yes | no | no | – | no | solid, cannot be dug |
| 5 | water | yes | no | yes | no | – | yes | still water (source blocks) |
| 6 | forbidden | no | no | no | no | – | no | lava, fire, cactus, powder snow, cobweb, flowing water, bubble columns: cannot enter, stand on, dig or place into |
| 7 | climb | yes | no | no | yes | – | no | ladders, vines, scaffolding |
| 8 | door | yes | no | no | no | – | no | doors a body can open by hand: passable, cannot be stood on |
| 9 | tall | no | no | no | no | 1 | no | fences, walls: block movement, cannot be stood on |

`P`, `S`, `W`, `L` are used below as predicates on a cell: `P(c)` means the cell's class is passable, and so on. "Dig tier" `n` costs `dig[n]` (section 6) to remove the cell; a cell is *diggable* if its tier is not `–`.

## 3. Body, state, standing

The body occupies two cells: the **feet cell** `F = (x, y, z)` and the **head cell** `H = (x, y+1, z)`. The cell below the feet is `B = (x, y−1, z)`. The state of a search is the feet position only.

A position is **standable** when `P(F) ∧ P(H) ∧ (S(B) ∨ W(F) ∨ L(F))`: both cells free, and the body rests on a solid cell, floats in still water, or hangs on a climbable cell.

## 4. Track A: moves without editing the world

All moves go from a standable state `s = (x, y, z)` to a standable state `t`. Directions `d` are the four axis steps `(±1, 0)` in `(x, z)`; "target" always means the feet cell of `t`. Each pair of states `(s, t)` has at most one move kind, determined by the displacement `t − s`:

| displacement | kind | condition on `t` and the world | cost |
|---|---|---|---|
| `(d, 0)` | **walk / swim** | `t` standable | `swim` if `W(F_s)` or `W(F_t)`, else `walk` |
| `(±1, 0, ±1)` | **diagonal** | `t` standable; neither `F_s` nor `F_t` is water; the two side columns `(x+dx, z)` and `(x, z+dz)` are passable at both `y` and `y+1` (no corner cutting) | `diag` |
| `(d, +1)` | **ascend** | `t` standable **on a solid** (`S(B_t)`; water/ladder do not count here); the cell `(x, y+2, z)` above the start's head is passable | `ascend` |
| `(0, +1, 0)` | **climb up** | `L(F_s)` or `L(F_t)`; `t` standable | `climbUp` |
|   | **swim up** | else `W(F_s) ∧ W(F_t)`; `t` standable | `swimVertical` |
| `(0, −1, 0)` | **climb down** | `L(F_s)` or `L(F_t)`; `t` standable | `climbDown` |
|   | **swim down** | else `W(F_s) ∧ W(F_t)`; `t` standable | `swimVertical` |
| `(d, −k)`, `k ≥ 1` | **drop** | see below | `edge + fall(k)` |

Moves that match no row do not exist on track A (in particular there is no diagonal climb, no diagonal swim, and no vertical walking).

**Drop (walking off an edge).** Let `(x', z')` be the neighbouring column in direction `d`. The body steps into it at the current height and falls:

1. `F = (x', y, z')` and `H = (x', y+1, z')` must be passable, and the position `(x', y, z')` must **not** be standable (if it were, the move would be a walk).
2. For `j = 1, 2, …` look at `(x', y−j, z')`: it must be passable (otherwise there is no drop), and if it is standable the body lands there, `k = j`. The body always lands on the **first** standable cell.
3. If it lands in still water (`W`) any `k` is allowed. Otherwise (on a solid or on a climbable cell) `k ≤ 3`.

`fall(k)` is `fall[k]` for `k ≤ 3` and `fall[3] + (k−3)·fallExtra` beyond.

## 5. Track E: the same moves, plus editing

Track E allows the body to dig out obstacles, dig down, place a block under its feet (bridge) and pillar up. **Edits are not persistent**: every step reads the **original** map only. The body's own two cells at the moment of a move (`F_s`, `H_s`) are read as air if the original cell is not passable (the body dug them to get there). A position's support is whatever the original map says; if the original map has no support there, the body is considered to be standing on a block it placed itself, and that block does not exist for later steps. A path that revisits a cell pays for it again.
Because the state is the position alone, the search is a plain shortest-path problem and "optimal" is well defined.

Track E uses every move of track A, with these changes. "Entering" a target `t` with feet cell `F_t`, head cell `H_t`, and the cell below `B_t` costs, on top of the base cost of the move:

- for `F_t` and `H_t`, each one that is not passable: if it is diggable, `dig[tier]` (and one dig is counted); otherwise the move does not exist;
- if the support condition fails (`S(B_t)`, or `W(F_t) ∨ L(F_t)` where the move allows it; for **ascend** only `S(B_t)` counts): if `B_t` is placeable, `place` (one place is counted); otherwise the move does not exist.

Additional rules of track E:

- **Ascend**: the cell above the start's head, `(x, y+2, z)`, may be dug if diggable (its dig cost is added).
- **Diagonal**: the two side columns must still be passable in the original map (they are never dug); only the target's cells and support are edited.
- **Vertical, up**, when it is neither climb nor swim: **pillar**, base cost `ascend`; the cell below the target is the start's own feet cell (read as air if it was solid), so a pillar step normally costs `ascend + place`.
- **Vertical, down**, when it is neither climb nor swim: **dig down**, base cost `fall[1]`.
- **Drop** is unchanged: the landing column is read as is, never edited.
- A walk or swim whose target has no support is a **bridge**: `walk + place` (or `swim + …`).

The two tracks are the "track A" and "track E" of the answer files. Track A is "the world as it is"; track E is "the world as it is, plus what a digging and building player could do".

## 6. Cost table

Frozen constants, in millitick (`grav3d/costs.json` holds the same numbers; that file is what tools read):

| name | value | meaning |
|---|---|---|
| `walk` | 4633 | one block on foot (4.317 blocks/s) |
| `diag` | 6553 | `⌈walk·√2⌉` |
| `ascend` | 8107 | a jump up one block until the feet are back on the ledge |
| `edge` | 3706 | clearing the edge before a drop (0.8 block at walking speed) |
| `fall[1..3]` | 4615, 6788, 8469 | free-fall time for 1, 2, 3 blocks |
| `fallExtra` | 1300 | each further block of a drop into water |
| `swim` | 10204 | one block horizontally in water (1.96 blocks/s) |
| `swimVertical` | 5000 | one block up or down in water |
| `climbUp` | 5000 | one block up a ladder |
| `climbDown` | 6667 | one block down a ladder |
| `dig[1..3]` | 5000, 10000, 20000 | breaking a block of tier 1, 2, 3 |
| `place` | 4000 | placing one block |

The goal is the **shortest time**: the total of the step costs. Reference answers also report the number of digs and places of the reference path; several paths of equal cost may exist, and they may differ in digs and places.

## 7. Goals

- `at (gx, gy, gz)`: the feet cell equals the goal cell.
- `near (gx, gy, gz) r`: the Euclidean distance between the feet cell and the goal cell (cell indices) is at most `r`.
- `dig (gx, gy, gz)` (track E only): the feet cell or the head cell is face-adjacent to the goal cell (shares a face, 6 neighbours), and the goal cell is diggable; the cost is the path cost plus `dig[tier]` of the goal cell, and one dig is counted. On track A, `dig` problems are **not applicable** (digging is editing).

## 8. Problem statuses

For a problem and a track:

- `optimal`: a path exists; the answer is its minimal total cost;
- `unsolvable`: the search exhausted every reachable state without meeting the goal. Because the grid is closed (outside is a wall) this is a proof, not a limit;
- `n/a` (not applicable): the start position is not standable (on both tracks), or the goal is a `dig` goal on track A.

A **path** is the sequence of feet cells `p0 … pn`, with `p0` the start and `pn` satisfying the goal. Every consecutive pair must be one legal move of the track; the cost of a path is the sum of the move costs (plus the final dig for `dig` goals).

## 9. What is deliberately not modelled

Breath, fall damage, dangerous neighbouring cells (only the class `forbidden` itself is excluded), tools and material limits (digging and placing are unlimited and the dig times are fixed), mobs, flowing water and currents, slabs/stairs as partial steps, doors as obstacles, and any budget on edits. Moving diagonally in water or on a ladder does not exist.

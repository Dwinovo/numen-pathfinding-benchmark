# Numen 寻路评测数据集 / Numen Pathfinding Benchmark

[Numen](https://github.com/Dwinovo/minecraft-numen) 寻路模块的评测数据:固定的原版世界生成存档,加上大量自动出的题和每道题的标准答案。
Data for evaluating the pathfinding module of [Numen](https://github.com/Dwinovo/minecraft-numen): fixed vanilla-generated terrain saves, a large set of generated problems, and a reference answer for each problem.

适用 Minecraft 1.21.1(存档的数据版本 3955)。数据放在本仓库的 Release 附件里(`numen-pathfinding-benchmark-<版本>-mc1.21.1.zip`),
Numen 的 Gradle 按"版本 + sha256"下载并核对。
For Minecraft 1.21.1 (data version 3955). The data lives in release assets (`numen-pathfinding-benchmark-<version>-mc1.21.1.zip`); Numen's Gradle downloads it by version + sha256.

## 内容 / Contents

```
regions.json            有哪几块地,哪些只进封存 / the regions, and which are held-out only
manifest.json           数据集版本、出题的 Numen 提交、两档节点上限、每块地每档实收的题数、拒绝的候选按原因的计数、第二档求解的转化与耗时、不适用于 A 的题数与理由 / dataset version, the Numen commit that generated it, the two node caps, accepted problems per region and bucket, rejected candidates by reason, how the second cap converted and how long it took, the not-applicable-to-A count and reason
answers.jsonl           标准答案,随题一次产出,每道题的每个适用规格都有 / reference answers, produced together with the problems, one for every applicable spec of every problem
answers-manifest.json   算出答案的 Numen 提交、两档节点上限、各状态的条数 / the Numen commit that produced the answers, the two node caps, count per status
terrain/<地块>/          region/r.X.Z.mca(原版区域文件,512×512 格)与 terrain.properties(种子、维度、高度范围、哨兵方块)
problems/<地块>.jsonl    题库,一行一道题 / problems, one per line
```

七块地,每块是一个区域文件 / seven regions, one region file each:

| 地块 / region | 内容 / what | 种子 / seed | 区域 / region |
|---|---|---|---|
| hills | 平地、陡坡、树林、断崖、湖 / flats, steep slopes, woods, cliffs, lakes | 0 | r.0.0 |
| mountains | 雪山:地面高 6..133,雪与粉雪占多数 / snowy peaks: ground 6..133, mostly snow | 10 | r.2.1 |
| water | 河、湖、岸线长:水面 44%,其余是草地与林 / rivers and lakes with long shores: 44% water | 1 | r.0.0 |
| forest | 黑森林密林:林冠占 62% / dark forest: 62% canopy | 8 | r.0.0 |
| caves | 地下空气格最多的一块(y −48..30 共 257 万格),地表是湖与林 / the most underground air of all candidates (2.57 M cells at y −48..30) | 5 | r.0.0 |
| nether | 下界的生成器与群系 / the nether generator and biomes | 1 | r.0.0 |
| mixed | 针叶林加水面,只进封存 / taiga and water, held out only | 13 | r.-2.-4 |

`mixed` 整块只进封存,用来检验没见过的地形 / `mixed` is held out entirely, to test terrain never seen while tuning.

## 题 / Problems

一行一道题(JSON),由地形、固定随机种子与成本模型下的精确解定出,不看生产寻路。**只收有定论的题**:候选题在每个适用的规格下,标准答案都是最优价或区域内证明的无解才收;
路伸出区域的、两档节点上限都算不动的、只有上界的、平凡的都拒掉,继续抽候选直到每块地每档凑满 40 道。所以评测里一道题失败了,说得清是寻路没做成,不会是本来就到不了,或者区域不够大。
Each line is a problem (JSON), fixed by the terrain, a fixed random seed and the exact solution under the cost model; production pathfinding plays no part. **Only conclusive problems are kept**: a candidate is kept only when its reference answer under every applicable spec is an optimal price or a proven no-route inside the region; routes that leave the region, those no node cap solves, those with only an upper bound, and trivial ones are rejected, and candidates are drawn until each region and bucket has 40. So when a problem fails in the benchmark, it is the pathfinder that failed, not an unreachable goal or a region that is too small.

```json
{"id":"hills-medium-012","region":"hills","bucket":"medium","distance":93.4,
 "from":[x,y,z],"goal":{"type":"at|near|dig","to":[x,y,z],"radius":3},
 "endClass":"surface|cave|cavity|buried","split":"dev|held","tags":["water","rough","dig","underground"]}
```

- **距离档 / bucket**:起终点的三维直线距离(含高低差),短 ≤32、中 32–128、长 128–400。与价钱模型无关,题目永远稳定。/ 3D straight-line distance (height difference included), short ≤32, medium 32–128, long 128–400; independent of the cost model.
- **目标 / goal**:走到某格(`at`)、走到某格附近 r 格内(`near`,跟随)、挖到某格(`dig`,只对封闭在实心里的一格)。/ walk to a cell, walk within r of a cell (following), dig a cell (only buried cells).
- **终点种类 / endClass**:地表(含水面)、洞穴地面(连着大片空间)、封闭的地下空腔、封闭在实心里的一格。/ surface (incl. water surface), cave floor (connected to a large open space), sealed cavity, a cell sealed in solid rock.
- **标签 / tags**:只看地形与题,不看搜索的结果:起终点之间的直线上有水或岩浆(`water`)、直线不平稳——有高于一格的台阶或没有地面的列(`rough`)、终点被封死要挖才进得去(`dig`)、终点在地下(`underground`)。/ geometric only: fluid on the straight line (`water`, lava included), a rough line with steps above one block or columns with no floor (`rough`), a sealed end that must be dug into (`dig`), an underground end (`underground`).
- **平凡题 / trivial**:起终点之间的直线明摆着一路平走过去(没有水、没有高于一格的台阶、没有无地面的列、斜着换列时不切角)的不进题库。/ problems whose straight line is plainly walkable are left out.
- **规格 / spec**:`A` 不挖不垫;`B` 出厂规格,可挖可垫、只看价钱。同一道题两种都跑。需要编辑才做得成的题(挖到某格,走到封死的一格)按构造不适用于 `A`,不给 `A` 跑,数目记在 `manifest.json`。/ `A` no digging or placing; `B` the factory spec, may dig and place, price only. Every problem runs under both, except goals that need editing (dig a cell, walk to a sealed cell), which are not applicable to `A` by construction and are not run under it; the count is in `manifest.json`.
- **dev / held**:地块 1–6 的题按题号哈希五五开,一半调参用(`dev`),一半封存(`held`,只在定版前跑);`mixed` 全部是 `held`。/ problems of regions 1–6 split 50/50 by id hash, tuning (`dev`) vs held-out (`held`, run only before a release); `mixed` is all `held`.

## 标准答案 / Reference answers

单独的文件 `answers.jsonl`(与 `answers-manifest.json`,记着算出它们的 Numen 提交与两档节点上限),与题一次产出。评测读它;没有这个文件时评测照跑,只是报表里没有次优比这一列。
A separate file `answers.jsonl` (plus `answers-manifest.json` with the Numen commit and the two node caps), produced together with the problems. The benchmark reads it; without the file the benchmark still runs, the report just has no suboptimality column.

一行一条"题 × 规格":`{"id":..,"spec":"A|B","status":"optimal|unsolvable","cost":..,"expanded":..,"startEstimate":..}`。权重 1、不分段、不限时、不带记忆的 A* 在整块区域上一次搜到底(同一套走法与成本模型),只受展开节点数上限约束:先按 2 000 000 个节点解,撞上限的再按 8 000 000 个重解。
`optimal`:区域内的最优价;`unsolvable`:能走到的都搜完了没有目标、没碰到区域边——区域内证明的无解。题库里只有这两种。求解还会得出另外三种结论,它们是出题时拒题的理由:`beyond-region`(连通块碰到了区域边,区域外没加载,这份数据里没有定论,加算力也没用)、`too-hard`(两档上限都用完了)、`best-known`(算不动,但按生产权重搜到了一条路,价钱只是上界)。
One line per problem × spec. Weight-1 A* over the whole region, same moves and cost model, no segments, no time limit, bounded only by a node cap: first 2,000,000 nodes, and those that hit it are solved again with 8,000,000. `optimal`: the optimal cost inside the region; `unsolvable`: everything reachable was searched, no goal, and the region edge was not touched, i.e. a proven no-route inside the region. Those are the only two statuses in the problem set. The solver has three more outcomes, which are the reasons a candidate is rejected: `beyond-region` (the connected component touches the region edge; what lies outside was never loaded, so there is no verdict and more compute does not help), `too-hard` (both caps used up), `best-known` (too hard, but the production weight found a route; the price is only an upper bound).

这一版(v2)的数:840 道题(7 块 × 3 档 × 40),1 551 条答案(最优 1 272、无解 279);抽了 1 158 个候选,拒掉 318 个:平凡 14、路伸出区域 218、两档都算不动 63、只有上界 23。第二档(8M)的 292 条作业里 126 条最后有了定论。每块每档的数在 `manifest.json`。
This version (v2): 840 problems (7 regions × 3 buckets × 40), 1,551 answers (1,272 optimal, 279 unsolvable). 1,158 candidates were drawn and 318 rejected (by reason, per region and bucket, in `manifest.json`): trivial 14, beyond the region 218, too hard for both caps 63, upper bound only 23. Of the 292 jobs that went to the second cap (8M), 126 ended conclusive.

出题与求解器的细节、假设(身体、垫路料、加载的区块、许可)见 [GENERATION.md](GENERATION.md) 与 Numen 仓库的 `docs/adr/pathing/0031-planning-benchmark.md`。
Generation details and the assumptions (body, materials, loaded chunks, permissions) are in [GENERATION.md](GENERATION.md) and Numen's `docs/adr/pathing/0031-planning-benchmark.md`.

## 怎么用 / Usage

在 Numen 仓库里:

```
./gradlew :numen:pathing:pathingBench                              # 下载数据集(版本与校验码在 numen/pathing/build.gradle),跑 dev 题
./gradlew :numen:pathing:pathingBench -PpathingDataset=<本地目录>   # 用本地的数据集目录
./gradlew :numen:pathing:pathingBenchDiff -PpathingOld=旧/results.jsonl -PpathingNew=新/results.jsonl
```

## 许可 / License

题目、标准答案、地图与评测记录按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 授权,全文见 [LICENSE](LICENSE):可以自由使用、修改、再发布(含商用),注明出处即可。地图是 Minecraft 原版世界生成器生成的地形;Minecraft 是 Mojang 的商标,本数据集与 Mojang、Microsoft 无关。
/ The problems, reference answers, maps and benchmark records are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); see [LICENSE](LICENSE). Use, adapt and redistribute them, commercially too, with attribution. The maps are terrain from Minecraft's vanilla world generator; Minecraft is a trademark of Mojang, and this dataset is not affiliated with Mojang or Microsoft.

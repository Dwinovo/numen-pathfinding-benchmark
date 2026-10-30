# Numen 寻路评测数据集 / Numen Pathfinding Benchmark

[Numen](https://github.com/Dwinovo/minecraft-numen) 寻路模块的评测数据:固定的原版世界生成存档,加上大量自动出的题和每道题的标准答案。
Data for evaluating the pathfinding module of [Numen](https://github.com/Dwinovo/minecraft-numen): fixed vanilla-generated terrain saves, a large set of generated problems, and a reference answer for each problem.

适用 Minecraft 1.21.1(存档的数据版本 3955)。数据放在本仓库的 Release 附件里(`numen-pathfinding-benchmark-<版本>-mc1.21.1.zip`),
Numen 的 Gradle 按"版本 + sha256"下载并核对。
For Minecraft 1.21.1 (data version 3955). The data lives in release assets (`numen-pathfinding-benchmark-<version>-mc1.21.1.zip`); Numen's Gradle downloads it by version + sha256.

## 内容 / Contents

```
regions.json            有哪几块地,哪些只进封存 / the regions, and which are held-out only
manifest.json           数据集版本、出题的 Numen 提交、每块地的题数、不适用于 A 的题数与理由 / dataset version, the Numen commit that generated the problems, counts per region, the not-applicable-to-A count and reason
answers.jsonl           标准答案,可以没有 / reference answers, optional
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

一行一道题(JSON),只由地形与固定随机种子定出,不依赖任何搜索算法:

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

单独的文件 `answers.jsonl`(与 `answers-manifest.json`,记着算出它们的 Numen 提交),**不属于出题**,可以不在:评测照跑,只是报表里没有次优比这一列。
A separate file `answers.jsonl` (plus `answers-manifest.json` with the Numen commit that produced them). It is not part of generating the problems and may be absent: the benchmark still runs, the report just has no suboptimality column.

一行一条"题 × 规格":`{"id":..,"spec":"A|B","status":"optimal|best-known|unsolvable|unknown","cost":..,"expanded":..,"startEstimate":..}`。权重 1、不分段、不限时、不带记忆的 A* 在整块区域上一次搜到底(同一套走法与成本模型),只受展开节点数上限约束。
`optimal`:最优价;`best-known`:节点上限内搜不出最优解、改用生产权重取的上界(次优比只作参考);`unsolvable`:能走到的都搜完了没有目标;`unknown`:路伸出了区域或两种搜索都没搜出路,没有答案。
One line per problem × spec. Weight-1 A* over the whole region, same moves and cost model, no segments, no time limit, bounded only by a node cap. `optimal`: the optimal cost; `best-known`: node cap hit, an upper bound from the production weight (indicative only); `unsolvable`: everything reachable was searched, no goal; `unknown`: the route leaves the region or neither search found a route.

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

尚未定。/ Not decided yet.

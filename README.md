# Numen 寻路评测数据集 / Numen Pathfinding Benchmark

[Numen](https://github.com/Dwinovo/minecraft-numen) 寻路模块的评测数据:固定的原版世界生成存档,加上大量自动出的题和每道题的标准答案。
Data for evaluating the pathfinding module of [Numen](https://github.com/Dwinovo/minecraft-numen): fixed vanilla-generated terrain saves, a large set of generated problems, and a reference answer for each problem.

适用 Minecraft 1.21.1(存档的数据版本 3955)。数据放在本仓库的 Release 附件里(`numen-pathfinding-benchmark-<版本>-mc1.21.1.zip`),
Numen 的 Gradle 按"版本 + sha256"下载并核对。
For Minecraft 1.21.1 (data version 3955). The data lives in release assets (`numen-pathfinding-benchmark-<version>-mc1.21.1.zip`); Numen's Gradle downloads it by version + sha256.

## 内容 / Contents

```
regions.json            有哪几块地,哪些只进封存 / the regions, and which are held-out only
manifest.json           数据集版本、生成它的 Numen 提交、每块地的题数 / dataset version, the Numen commit that produced it, counts per region
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

一行一道题(JSON):

```json
{"id":"hills-medium-012","region":"hills","bucket":"medium","distance":93.4,
 "from":[x,y,z],"goal":{"type":"at|near|dig","to":[x,y,z],"radius":3},
 "endClass":"surface|cave|cavity|buried","split":"dev|held",
 "ref":{"A":{"status":"optimal|best-known|unsolvable|unknown","cost":2796.889,"expanded":859468,"trivial":false,"tags":["water","dig","place","underground"]},
        "B":{ ... }}}
```

- **距离档 / bucket**:起终点的水平直线距离,短 ≤32、中 32–128、长 128–400。与价钱模型无关,题目永远稳定。/ horizontal straight-line distance, short ≤32, medium 32–128, long 128–400; independent of the cost model.
- **目标 / goal**:走到某格(`at`)、走到某格附近 r 格内(`near`,跟随)、挖到某格(`dig`,只对封闭在实心里的一格)。/ walk to a cell, walk within r of a cell (following), dig a cell (only buried cells).
- **终点种类 / endClass**:地表(含水面)、洞穴地面、封闭的地下空腔、封闭在实心里的一格。/ surface (incl. water surface), cave floor, sealed cavity, a cell sealed in solid rock.
- **规格 / spec**:`A` 不挖不垫;`B` 出厂规格,可挖可垫、只看价钱。同一道题两种都跑。/ `A` no digging or placing; `B` the factory spec, may dig and place, price only. Every problem runs under both.
- **标准答案 / ref**:权重 1、不分段、不限时、不带记忆的 A* 在整块区域上一次搜到底(同一套走法与成本模型),只受展开节点数上限约束。
  `optimal` 是最优价;`best-known` 是节点上限内搜不出最优解、改用生产权重取的上界(次优比只作参考);`unsolvable` 是无解(能走到的都搜完了,或按构造到不了);
  `unknown` 是两种搜索都没搜出路,这道题在这种规格下不进统计。`trivial` 是起点的估价已经等于最优价的平凡题。
  `expanded` 是求解器展开的节点数(难度)。/ Reference: weight-1 A* over the whole region, same moves and cost model, no segments or time limit; bounded only by a node cap. `optimal`: the optimal cost; `best-known`: node cap hit, an upper bound from the production weight (suboptimality is indicative only); `unsolvable`: nothing reachable is left to search, or unreachable by construction; `unknown`: neither search found a route, excluded from the stats for that spec. `trivial`: the start's estimate already equals the optimal cost. `expanded`: nodes the solver expanded (difficulty).
- **dev / held**:地块 1–6 的题按题号哈希五五开,一半调参用(`dev`),一半封存(`held`,只在定版前跑);`mixed` 全部是 `held`。/ problems of regions 1–6 split 50/50 by id hash, tuning (`dev`) vs held-out (`held`, run only before a release); `mixed` is all `held`.

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

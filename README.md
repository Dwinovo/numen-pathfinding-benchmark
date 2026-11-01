# Numen 寻路评测数据集 / Numen Pathfinding Benchmark

Minecraft 场景的寻路测试题:固定的地形(七块 512×512 的原版世界生成地图,Minecraft 1.21.1 的区域文件)、840 道自动出的题,以及每道题在 [Numen](https://github.com/Dwinovo/minecraft-numen) 寻路模块的物理耗时口径下的参考答案。
Pathfinding test problems for Minecraft: fixed terrain (seven 512×512 vanilla-generated regions, Minecraft 1.21.1 region files), 840 generated problems, and for each problem a reference answer under the physical-time cost of [Numen](https://github.com/Dwinovo/minecraft-numen)'s pathfinding module.

**v3.1** 相对 v3 删去了 v3 附带的 GRAV3D 层(中立格式的地形、规则、求解器与验证器及其答案),题集、地形与答案与 v3 完全相同;数据集的定位就是 Minecraft 场景的寻路测试题。v3 的题集与 v2 不同:v2 的出题只要求"身体待得住",有不少起点、终点落在岩浆湖里(Numen 的搜索认为那里站得住,岩浆只是代价与排除的问题);v3 起终点的挑选还要求身体碰到的格不是路线规格排除的种类(岩浆、火、粉雪……),所以重新出了全部 840 题,题号对应的题大多变了——v2 的题、答案与基线不能和 v3、v3.1 混用。
**v3.1** drops the GRAV3D layer that shipped with v3 (the neutral-format terrain, the rules, the solver and validator, and their answers); problems, terrain and answers are identical to v3. The dataset is Minecraft pathfinding test problems, nothing else. The v3 problem set differs from v2: v2's generator only required that the body can stand, and many starts and goals ended up inside lava lakes (Numen's search thinks the body can stand there; lava is a matter of price and exclusion); v3 also requires that the cells the body touches are not of a kind the route spec excludes (lava, fire, powder snow, ...), so all 840 problems were regenerated and most ids now name different problems — v2 problems, answers and baselines must not be mixed with v3 or v3.1.

## 内容 / Contents

```
README.md GENERATION.md CITATION.cff LICENSE (CC BY 4.0)   这几页 / these pages
terrain/<地>/            Minecraft 区域文件(.mca)与 terrain.properties / Minecraft region files and terrain.properties
problems/<地>.jsonl      题,世界坐标 / problems, world coordinates
regions.json             七块地的名字、种子、区域、维度 / names, seeds, regions and dimensions
manifest.json            出题的计数、拒绝原因 / generation counts and rejection reasons
answers.jsonl            参考答案 / reference answers
answers-manifest.json    答案的口径、算出它们的 Numen 提交、节点上限 / answer model, Numen commit, node caps
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

每块 512×512 格,高度 384(overworld,y −64..319)或 256(nether)。`mixed` 整块只进封存,用来检验没见过的地形。
Each region is 512×512 cells, 384 high (overworld, y −64..319) or 256 (nether). `mixed` is held out entirely, to test terrain never seen while tuning.

## 题 / Problems

840 道(7 块 × 3 档 × 40),文件格式见下一节。
840 problems (7 regions × 3 buckets × 40); the file format is in the next section.

- **距离档 / bucket**:起终点的三维直线距离,短 ≤32、中 32–128、长 128–400 / 3D straight-line distance, short ≤32, medium 32–128, long 128–400。
- **目标 / goal**:走到某格(`at`)、走到某格附近 r 格内(`near`)、挖到某格(`dig`,只对封闭在实心里的一格,只有可挖的规格 B 适用)/ walk to a cell, walk within r of a cell, dig a cell (a cell sealed in rock; spec B only, which may dig).
- **dev / held**:地块 1–6 的题按题号哈希五五开,一半调参用(`dev`),一半封存(`held`,只在定版前跑);`mixed` 全部是 `held` / regions 1–6 split 50/50 by id hash into tuning (`dev`) and held-out (`held`); `mixed` is all `held`.
- 题是用 Numen 的搜索按纯物理耗时挑出来的(只收在 Numen 的走法下有定论的题),所以"哪些题有趣"带着 Numen 的走法。/ The problems were selected with Numen's search under pure physical time (only those conclusive under Numen's moves were kept), so "which problems are interesting" carries Numen's moves.

## 题库与答案 / Problem files and answers

`problems/<地>.jsonl` 一行一道题(世界坐标,Numen 的评测读它),带终点种类与几何标签:
`problems/<region>.jsonl` has one problem per line (world coordinates), with end class and geometric tags:

```json
{"id":"hills-medium-012","region":"hills","bucket":"medium","distance":93.4,
 "from":[x,y,z],"goal":{"type":"at|near|dig","to":[x,y,z],"radius":3},
 "endClass":"surface|cave|cavity|buried","split":"dev|held","tags":["water","rough","dig","underground"]}
```

- **终点种类 / endClass**:地表(含水面)、洞穴地面(连着大片空间)、封闭的地下空腔、封闭在实心里的一格 / surface (incl. water surface), cave floor (connected to a large open space), sealed cavity, a cell sealed in solid rock.
- **标签 / tags**:只看地形与题:起终点之间的直线上有水或岩浆(`water`)、直线不平稳(`rough`)、终点被封死要挖才进得去(`dig`)、终点在地下(`underground`)。/ geometric only: fluid on the straight line, a rough line, a sealed end that must be dug into, an underground end.
- **规格 / spec**:Numen 的搜索有两种规格,`A` 不挖不垫,`B` 出厂规格(可挖可垫);同一道题两种都跑,需要编辑才做得成的题只给 `B` 跑。/ Numen's search has two specs, `A` no digging or placing, `B` the factory spec (may dig and place); every problem runs under both, except goals that need editing, which run under `B` only.
- **`answers.jsonl`**:一行一条"题 × 规格":`{"id":..,"spec":"A|B","status":"optimal|unsolvable","cost":..,"dug":..,"placed":..,"expanded":..,"startEstimate":..}`,是权重 1 的 A* 在整块区域上、Numen 的走法下按**纯物理耗时**(刻;放、挖、起跳、涉水、挨着伤身格走的罚分全为 0,挖掘遮挡的偏好也为 0)算出的价钱(先 2 000 000 个节点,撞上限的再 8 000 000 个),`dug`、`placed` 是那条路线挖、放了几块;`unsolvable` 是区域内证明的无解(连通块没碰到区域边)。它是"Numen 物理模型 `numen-physical-1` 的参考值",**不是真最优**(Numen 的状态抽象有混叠,见其 ADR 0036),`answers-manifest.json` 记着口径、算出它们的 Numen 提交与两档节点上限。评测的次优比是路线的物理刻数除以它,所以调罚分、权重都不必重算数据集;没有它评测照跑,只是报表里没有次优比。/ one line per problem × spec: the optimal cost from weight-1 A* over the whole region under Numen's moves and cost model (first 2,000,000 nodes, those that hit the cap again with 8,000,000); `unsolvable` is a no-route proven inside the region (the connected component did not touch the region edge). The price is **pure physical time** in ticks (penalties for placing, digging, jumping, wading and walking beside harmful blocks are all 0, and so is the sight-blocker preference of dig goals); `dug` and `placed` count the edits of that route. These are "reference values of the Numen physical model `numen-physical-1`", **not a true optimum** (Numen's state abstraction aliases states, see its ADR 0036); `answers-manifest.json` has the model, the Numen commit and the two node caps. The benchmark's suboptimality is the route's physical ticks divided by this price, so tuning penalties or weights never requires recomputing the dataset.
- **只收有定论的题 / only conclusive problems**:候选题在每个适用规格下答案都是最优价或区域内证明的无解才收;路伸出区域的(区域外没加载,没有定论)、两档上限都算不动的、只有上界的、平凡的都拒掉,继续抽候选直到每块地每档凑满 40 道。v3(v3.1 相同)抽了 1 160 个候选,拒掉 320 个(平凡 21、路伸出区域 239、两档都算不动 3、只有上界 57);1 551 条答案里最优 1 371、无解 180。出题在 20 核、90 GB 的机器上用了约 6.2 小时。每块每档的数在 `manifest.json`。/ a candidate is kept only when its answer under every applicable spec is an optimal price or a no-route proven inside the region; routes leaving the region, those no node cap solves, those with only an upper bound, and trivial ones are rejected, and candidates are drawn until each region and bucket has 40. v3 (and v3.1) drew 1,160 candidates and rejected 320 (trivial 21, beyond the region 239, too hard 3, upper bound only 57); of 1,551 answers 1,371 are optimal and 180 unsolvable. Generation took about 6.2 hours on a 20-core, 90 GB machine. Per-region and bucket counts are in `manifest.json`.

出题与求解器的细节、假设(身体、垫路料、加载的区块、许可)见 [GENERATION.md](GENERATION.md) 与 Numen 仓库的 `docs/adr/pathing/0031-planning-benchmark.md`。
Generation details and the assumptions (body, materials, loaded chunks, permissions) are in [GENERATION.md](GENERATION.md) and Numen's `docs/adr/pathing/0031-planning-benchmark.md`.

## 怎么用 / Usage

Numen 仓库里的评测(读 `problems/`、`terrain/`、`answers.jsonl`,Gradle 按版本与 sha256 下载)/ Numen's own evaluation (reads `problems/`, `terrain/` and `answers.jsonl`; downloaded by version and sha256 from Gradle):

```
./gradlew :numen:pathing:pathingBench                              # 下载数据集,跑 dev 题 / download the dataset, run dev problems
./gradlew :numen:pathing:pathingBench -PpathingDataset=<本地目录>   # 用本地的数据集目录 / use a local dataset directory
```

出题与答案的重做见 [GENERATION.md](GENERATION.md)。/ See [GENERATION.md](GENERATION.md) to regenerate problems and answers.

## 引用 / Citation

见 [CITATION.cff](CITATION.cff)。See [CITATION.cff](CITATION.cff).

## 许可 / License

数据——`.mca` 地图、题、答案与文档——按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 授权,全文见 [LICENSE](LICENSE):可以自由使用、修改、再发布(含商用),注明出处即可。地图是 Minecraft 原版世界生成器生成的地形;Minecraft 是 Mojang 的商标,本数据集与 Mojang、Microsoft 无关。
The data — `.mca` maps, problems, answers and documentation — is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (see [LICENSE](LICENSE)): use, adapt and redistribute freely, commercially too, with attribution. The maps are terrain from Minecraft's vanilla world generator; Minecraft is a trademark of Mojang, and this dataset is not affiliated with Mojang or Microsoft.

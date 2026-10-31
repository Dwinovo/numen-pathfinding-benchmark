# 怎么出的 / How it was generated

主仓库(Numen)的 `docs/adr/pathing/0031-planning-benchmark.md` 是权威的设计记录;这里只写重做数据集要跑的命令和选种的依据。
The authoritative design record is `docs/adr/pathing/0031-planning-benchmark.md` in the Numen repo; this file only has the commands and how the terrain was picked.

## 1. 制作存档 / Bake the terrain

用 Numen 的 NeoForge GameTest 服务器,种子、区域、维度自己定(详见 Numen 的 `numen/pathing/src/gametest/terrain/README.md`):

```
./gradlew --no-daemon :numen:neoforge:runGameTestServer -Pgametest=numen_pathing_terrain_bake \
    -PbakeOut=<dist>/terrain/<名字> -PgametestSeed=<种子> -PbakeRegion=<X>,<Z> [-PbakeDimension=nether]
```

挑种子与区域:在 (0,0) 附近和几个别的区域各做一块候选,按勘测表(每格地面高度、地面方块、顶面方块)看水域占比、林冠占比、地面高低、雪冰占比,再数每块地下(y −48..30)的空气格挑洞穴多的。
选中的七块见 README 的表。/ Candidates were baked at several seeds and regions; the survey table (ground height, ground block, top block per column) gave water share, canopy share, relief and snow share, and underground air cells (y −48..30) picked the cave region.

## 2. 出题与标准答案 / Problems and reference answers

题和答案一次产出,同一份求解代码,只收有定论的题(判据与理由见 README 的"题"一节、Numen 仓库的 ADR 0031)。/ Problems and answers come out together from one solver; only conclusive problems are kept (criterion and reasons: the Problems section of the README and ADR 0031 in the Numen repo).

```
./gradlew :numen:pathing:pathingGenerate -PpathingDataset=<dist>
```

每块地每个距离档 40 道,固定随机种子,同一份存档出同一份题(收题只按候选抽到的先后,与机器快慢、并行度无关)。每个候选在每个适用规格下按权重 1 的 A* 在整块区域上解到底:先 2 000 000 个节点,撞上限的再用 8 000 000 个重解;
最优或区域内无解才收,路伸出区域、两档都算不动、只有上界的都拒掉,拒绝按原因计数写进 `manifest.json`。/ Each candidate is solved with weight-1 A* over the whole region under every applicable spec: 2,000,000 nodes first, those that hit it again with 8,000,000; only an optimal price or a no-route inside the region is kept, the rest are rejected and counted by reason in `manifest.json`.

**慢**:v2 在一台 20 核、90 GB 的机器上用了约 9.5 小时(第一档的 CPU 时间约 37 小时、第二档约 65 小时),并行度按内存预算排程:求解器预留"上限 × 约 1.8 KB"的堆,堆的三分之二(并行收集器的老年代)是预算(80 GB 堆约 53 GB,第一档同时约 14 个、第二档 3 个)。
/ **Slow**: v2 took about 9.5 hours on a 20-core, 90 GB machine (about 37 h of CPU at the first cap, 65 h at the second). Jobs are scheduled by a memory budget: a solver reserves cap × ~1.8 KB of heap, and two thirds of the heap (the old generation of the parallel collector) is the budget (about 53 GB of an 80 GB heap: ~14 jobs at the first cap, 3 at the second).

断点续跑:每块地每一档收完就写进数据集目录的 `.generate/<地块>-<档>.json`(过程文件,不进发布包),重启时已有的档读回、不再求解,题库、答案文件与 manifest 总是从它们汇出来;要整个重来就删 `.generate`。
/ Resumable: each region and bucket is written to `<dataset>/.generate/<region>-<bucket>.json` when it completes (working files, not part of the release); a restart reads finished buckets back instead of solving them again, and the problem files, the answers file and the manifest are always assembled from them. Delete `.generate` to start over.

没有图形界面的机器上:本机编译,把 `numen/pathing/build/classes/java/{benchmark,main,fixtures}` 与 Numen API 的瘦 jar 放进运行类路径,`java -Xmx80g -XX:+UseParallelGC -cp <类路径> com.dwinovo.numen.pathing.benchmark.Generate <数据集目录> <Numen 提交>`。
/ On a headless machine: compile locally, put `numen/pathing/build/classes/java/{benchmark,main,fixtures}` and the Numen API slim jar on the class path, and run `java -Xmx80g -XX:+UseParallelGC -cp <class path> com.dwinovo.numen.pathing.benchmark.Generate <dataset dir> <Numen commit>`.

## 3. 成本模型变了:重算现有题的答案 / Recomputing answers after a cost-model change

题不变、只重算答案时(成本模型改了,标准答案就过期),分片、可续算,同一个求解器(两档上限、按内存预算排程):
When only the answers must be recomputed (the cost model changed, so the answers are stale), sharded and resumable, with the same solver (two caps, memory-budget scheduling):

```
# 第 i 份,共 n 份(i 从 0 起),每算完一条追加写进分片文件,重启跳过已有的
./gradlew :numen:pathing:pathingAnswers -PpathingDataset=<dist> -PpathingShards=<分片目录> -PpathingShard=i/n
# 把分片并起来,记下主仓库提交,写 answers.jsonl 与 answers-manifest.json,并报每题的 CPU 成本
./gradlew :numen:pathing:pathingAnswersMerge -PpathingDataset=<dist> -PpathingShards=<分片目录>
```

重算后某道题的结论可能不再是最优或无解(算不动了、碰到区域边了):那道题在新的成本模型下没有定论,应当换掉,重新出题。/ After a recompute a problem may no longer be conclusive (too hard now, or touching the region edge): it has no verdict under the new cost model and should be replaced, i.e. generate again.

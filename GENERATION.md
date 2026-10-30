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

## 2. 出题 / Problems

```
./gradlew :numen:pathing:pathingGenerate -PpathingDataset=<dist>
```

不需要标准答案,几十秒。每块地每个距离档 40 道,固定随机种子,同一份存档出同一份题。/ No answers needed, tens of seconds. 40 problems per region and distance bucket, fixed random seed: the same saves give the same problems.

## 3. 标准答案 / Reference answers

单独一步,慢,可分片、可续算,在哪台机器上算都行(只要 Java、Numen 仓库和数据集目录):

```
# 第 i 份,共 n 份(i 从 0 起),每算完一条追加写进分片文件,重启跳过已有的
./gradlew :numen:pathing:pathingAnswers -PpathingDataset=<dist> -PpathingShards=<分片目录> -PpathingShard=i/n
# 把分片并起来,记下主仓库提交,写 answers.jsonl 与 answers-manifest.json,并报每题的 CPU 成本
./gradlew :numen:pathing:pathingAnswersMerge -PpathingDataset=<dist> -PpathingShards=<分片目录>
```

答案文件不在时,评测照跑,报表里没有次优比这一列。/ Without the answers file the benchmark still runs; the report just has no suboptimality column.

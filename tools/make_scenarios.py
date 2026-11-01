#!/usr/bin/env python3
"""把题库(problems/<地>.jsonl,世界坐标)换成场景 CSV(局部坐标)。

用法:make_scenarios.py <题库所在的数据集目录> <输出目录>
局部坐标 = 世界坐标 - grid.json 里的原点(x、z)或最低高度(y);原点读自 <输出目录>/neutral/<地>/grid.json。
题、id、档、dev/held 原样保留,只换坐标。
"""
import csv
import json
import os
import sys

COLUMNS = ["id", "region", "bucket", "split", "sx", "sy", "sz", "goal", "gx", "gy", "gz", "radius"]


def main(src, out):
    os.makedirs(os.path.join(out, "scenarios"), exist_ok=True)
    with open(os.path.join(src, "regions.json"), encoding="utf-8") as f:
        regions = [r["name"] for r in json.load(f)]
    for name in regions:
        with open(os.path.join(out, "neutral", name, "grid.json"), encoding="utf-8") as f:
            grid = json.load(f)
        ox, oz, miny = grid["originX"], grid["originZ"], grid["minY"]
        rows = []
        with open(os.path.join(src, "problems", name + ".jsonl"), encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                p = json.loads(line)
                sx, sy, sz = p["from"]
                gx, gy, gz = p["goal"]["to"]
                rows.append([p["id"], p["region"], p["bucket"], p["split"],
                             sx - ox, sy - miny, sz - oz, p["goal"]["type"], gx - ox, gy - miny, gz - oz,
                             p["goal"].get("radius", "") if p["goal"]["type"] == "near" else ""])
        with open(os.path.join(out, "scenarios", name + ".csv"), "w", encoding="utf-8", newline="") as f:
            f.write("version,1\n")
            w = csv.writer(f, lineterminator="\n")
            w.writerow(COLUMNS)
            w.writerows(rows)
        print(name, len(rows))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

#!/usr/bin/env python3
"""把 v3 的各部分拼成发布包,写 grav3d/manifest.json,打 zip 并报 sha256。

用法:make_package.py --numen <Numen 层目录> --v3 <GRAV3D 工作目录> --solved <求解输出目录> --out <zip 路径> [--solve-seconds <region=秒,...>]
  --numen   含 regions.json、manifest.json、answers.jsonl、answers-manifest.json、problems/、terrain/(出题的输出与存档,即 Numen 层)
  --v3      含 neutral/(导出的中立地形)与 scenarios/(make_scenarios.py 的输出)
  --solved  含 <地>-answers.csv 与 <地>-paths.jsonl(参考求解器的输出)
包内容见 FORMAT.md。zip 里的文件按路径排序、时间戳固定,同样的输入打出同样的包。
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TOP_FILES = ["README.md", "RULES.md", "FORMAT.md", "GENERATION.md", "LICENSE", "CITATION.cff"]
NUMEN_FILES = ["regions.json", "manifest.json", "answers.jsonl", "answers-manifest.json"]
NUMEN_DIRS = ["terrain", "problems"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--numen", required=True)
    ap.add_argument("--v3", required=True)
    ap.add_argument("--solved", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--solve-seconds", default="", help="region=秒,region=秒:求解墙钟,写进 manifest")
    args = ap.parse_args()

    with open(os.path.join(args.numen, "regions.json"), encoding="utf-8") as f:
        regions = [r["name"] for r in json.load(f)]

    stage = tempfile.mkdtemp(prefix="pb-v3-")
    try:
        for name in TOP_FILES:
            shutil.copy(os.path.join(REPO, name), os.path.join(stage, name))
        for name in NUMEN_FILES:
            shutil.copy(os.path.join(args.numen, name), os.path.join(stage, name))
        for name in NUMEN_DIRS:
            shutil.copytree(os.path.join(args.numen, name), os.path.join(stage, name))
        shutil.copytree(os.path.join(args.v3, "neutral"), os.path.join(stage, "neutral"))
        shutil.copytree(os.path.join(args.v3, "scenarios"), os.path.join(stage, "scenarios"))
        os.makedirs(os.path.join(stage, "grav3d", "answers"))
        os.makedirs(os.path.join(stage, "grav3d", "paths"))
        shutil.copy(os.path.join(REPO, "grav3d", "costs.json"), os.path.join(stage, "grav3d", "costs.json"))
        for r in regions:
            shutil.copy(os.path.join(args.solved, r + "-answers.csv"), os.path.join(stage, "grav3d", "answers", r + ".csv"))
            shutil.copy(os.path.join(args.solved, r + "-paths.jsonl"), os.path.join(stage, "grav3d", "paths", r + ".jsonl"))
        os.makedirs(os.path.join(stage, "tools", "solver"))
        for name in ("validate.py", "make_scenarios.py", "make_package.py", "LICENSE"):
            shutil.copy(os.path.join(REPO, "tools", name), os.path.join(stage, "tools", name))
        shutil.copy(os.path.join(REPO, "tools", "solver", "Solve.java"), os.path.join(stage, "tools", "solver", "Solve.java"))
        shutil.copytree(os.path.join(REPO, "tests"), os.path.join(stage, "tests"), ignore=shutil.ignore_patterns("__pycache__"))

        counts = {}
        for r in regions:
            per = {}
            with open(os.path.join(stage, "grav3d", "answers", r + ".csv"), encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    t = per.setdefault(row["track"], {"optimal": 0, "unsolvable": 0, "n/a": 0})
                    t[row["status"]] += 1
            counts[r] = per
        totals = {}
        for per in counts.values():
            for track, by in per.items():
                t = totals.setdefault(track, {"optimal": 0, "unsolvable": 0, "n/a": 0})
                for k, v in by.items():
                    t[k] += v
        seconds = dict(kv.split("=") for kv in args.solve_seconds.split(",") if kv)
        manifest = {
            "dataset": "numen-pathfinding-benchmark",
            "version": "v3",
            "rules": "grav3d-1.0",
            "minecraft": "1.21.1",
            "problems": sum(sum(by.values()) for by in (counts[r]["A"] for r in regions)),
            "regions": counts,
            "totals": totals,
            "solveSeconds": {k: int(v) for k, v in seconds.items()},
        }
        files = {}
        for root, _, names in os.walk(stage):
            for n in names:
                p = os.path.join(root, n)
                files[os.path.relpath(p, stage).replace(os.sep, "/")] = sha256(p)
        manifest["sha256"] = dict(sorted(files.items()))
        with open(os.path.join(stage, "grav3d", "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
            f.write("\n")

        entries = []
        for root, _, names in os.walk(stage):
            for n in names:
                entries.append(os.path.relpath(os.path.join(root, n), stage).replace(os.sep, "/"))
        with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for e in sorted(entries):
                info = zipfile.ZipInfo(e, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                with open(os.path.join(stage, e), "rb") as f:
                    z.writestr(info, f.read())
        print("zip", args.out, os.path.getsize(args.out), "bytes")
        print("sha256", sha256(args.out))
        print(json.dumps(totals))
    finally:
        shutil.rmtree(stage)


if __name__ == "__main__":
    sys.exit(main())

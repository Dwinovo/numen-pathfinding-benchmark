#!/usr/bin/env python3
"""一致性测试:cases.txt 里每张小图,各赛道上
  1. 参考求解器(tools/solver/Solve.java)的结论与期望一致:无解 / 不适用 / 最优价与挖、放块数;
  2. 求解器给的路径过验证器(tools/validate.py)且代价相同;
  3. 给定的非法路径被验证器在指定步判非法。
期望的价钱用 grav3d/costs.json 的名字写成表达式,所以这些图验证的是规则,不是某个数字。

用法:run.py [--only 图名,图名]      需要 python 3 与 JDK(javac、java)。全部通过退出码 0。
"""
import argparse
import csv
import gzip
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import validate  # noqa: E402

SYMBOLS = {".": "air", "s": "soft", "#": "stone", "h": "hard", "B": "bedrock", "~": "water",
           "X": "forbidden", "H": "climb", "D": "door", "T": "tall"}


def parse_cases(path):
    cases = []
    for block in open(path, encoding="utf-8").read().split("\n=====\n"):
        lines = [ln for ln in block.split("\n") if not ln.startswith("//")]
        case = {"bad": [], "layers": {}}
        layer = None
        for ln in lines:
            if not ln.strip():
                continue
            if ln.startswith("y="):
                layer = int(ln[2:])
                case["layers"][layer] = []
            elif layer is not None:
                case["layers"][layer].append(ln)
            else:
                key, _, value = ln.partition(":")
                value = value.strip()
                if key == "bad":
                    step, _, path_json = value.partition("|")
                    case["bad"].append((int(step), json.loads(path_json)))
                else:
                    case[key] = value
        cases.append(case)
    return cases


def cost_names(costs):
    f = costs["fall"]
    return {"walk": costs["walk"], "diag": costs["diag"], "ascend": costs["ascend"], "edge": costs["edge"],
            "fall1": f[0], "fall2": f[1], "fall3": f[2], "fallExtra": costs["fallExtra"], "swim": costs["swim"],
            "swimV": costs["swimVertical"], "climbUp": costs["climbUp"], "climbDown": costs["climbDown"],
            "dig1": costs["dig"][0], "dig2": costs["dig"][1], "dig3": costs["dig"][2], "place": costs["place"]}


def expectation(text, names):
    """'unsolvable' | 'n/a' | (代价, 挖, 放)。"""
    if text in ("unsolvable", "n/a"):
        return text
    parts = [p.strip() for p in text.split(";")]
    extra = dict(p.split("=") for p in parts[1:])
    return (eval(parts[0], {"__builtins__": {}}, names), int(extra.get("digs", 0)), int(extra.get("places", 0)))


def write_map(directory, case, codes):
    layers = case["layers"]
    sizey = max(layers) + 1
    sizez = len(layers[0])
    sizex = len(layers[0][0])
    data = bytearray(sizex * sizez * sizey)
    for y in range(sizey):
        rows = layers[y]
        assert len(rows) == sizez and all(len(r) == sizex for r in rows), "%s: y=%d 的尺寸不齐" % (case["name"], y)
        for z, row in enumerate(rows):
            for x, ch in enumerate(row):
                data[(x * sizez + z) * sizey + y] = codes[SYMBOLS[ch]]
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "grid.json"), "w", encoding="utf-8") as f:
        json.dump({"sizeX": sizex, "sizeZ": sizez, "sizeY": sizey}, f)
    with gzip.open(os.path.join(directory, "grid.bin.gz"), "wb") as f:
        f.write(bytes(data))


def write_scenario(path, case):
    sx, sy, sz = case["start"].split()
    kind, *rest = case["goal"].split()
    gx, gy, gz = rest[:3]
    radius = rest[3] if kind == "near" else ""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("version,1\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "region", "bucket", "split", "sx", "sy", "sz", "goal", "gx", "gy", "gz", "radius"])
        w.writerow([case["name"], "conformance", "short", "dev", sx, sy, sz, kind, gx, gy, gz, radius])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    rules = validate.Rules(os.path.join(ROOT, "neutral", "classes.json"), os.path.join(ROOT, "grav3d", "costs.json"))
    with open(os.path.join(ROOT, "neutral", "classes.json"), encoding="utf-8") as f:
        codes = {c["name"]: c["code"] for c in json.load(f)["classes"]}
    names = cost_names(rules.cost)
    cases = parse_cases(os.path.join(HERE, "cases.txt"))
    if args.only:
        cases = [c for c in cases if c["name"] in args.only.split(",")]
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        classes_dir = os.path.join(tmp, "solver")
        subprocess.run(["javac", "-d", classes_dir, os.path.join(ROOT, "tools", "solver", "Solve.java")], check=True)
        for case in cases:
            name = case["name"]
            work = os.path.join(tmp, name)
            write_map(os.path.join(work, "map"), case, codes)
            write_scenario(os.path.join(work, "scenario.csv"), case)
            subprocess.run(["java", "-cp", classes_dir, "Solve", "--classes", os.path.join(ROOT, "neutral", "classes.json"),
                            "--costs", os.path.join(ROOT, "grav3d", "costs.json"), "--map", os.path.join(work, "map"),
                            "--scenarios", os.path.join(work, "scenario.csv"), "--tracks", "A,E",
                            "--answers", os.path.join(work, "answers.csv"), "--paths", os.path.join(work, "paths.jsonl")],
                           check=True, capture_output=True)
            answers = validate.read_answers(os.path.join(work, "answers.csv"))
            paths = validate.read_submission(os.path.join(work, "paths.jsonl"))
            problem = validate.read_scenarios(os.path.join(work, "scenario.csv"))[0]
            grid = validate.Grid(os.path.join(work, "map"))
            for track in ("A", "E"):
                want = expectation(case[track], names)
                got = answers[(name, track)]
                tag = "%s %s" % (name, track)
                if want in ("unsolvable", "n/a"):
                    if got["status"] != want:
                        failures.append("%s:期望 %s,求解器给 %s" % (tag, want, got["status"]))
                    continue
                if got["status"] != "optimal" or (int(got["cost"]), int(got["digs"]), int(got["places"])) != want:
                    failures.append("%s:期望 (代价,挖,放)=%s,求解器给 %s %s,%s,%s" % (tag, want, got["status"], got["cost"], got["digs"], got["places"]))
                    continue
                try:
                    checked = validate.check_path(validate.World(grid, rules, track), problem, paths[(name, track)]["path"])
                except validate.Invalid as e:
                    failures.append("%s:验证器不认求解器的路径:%s" % (tag, e))
                    continue
                if checked != want:
                    failures.append("%s:验证器算出 %s,期望 %s" % (tag, checked, want))
            for step, bad in case["bad"]:
                try:
                    validate.check_path(validate.World(grid, rules, "A"), problem, bad)
                    failures.append("%s:非法路径被验证器放过了" % name)
                except validate.Invalid as e:
                    if not str(e).startswith("%d:" % step):
                        failures.append("%s:非法路径应在第 %d 步判非法,验证器说 %s" % (name, step, e))
    for f in failures:
        print("FAIL", f)
    print("%d 张图,%d 个失败" % (len(cases), len(failures)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

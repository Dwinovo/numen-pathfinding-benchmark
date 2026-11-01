#!/usr/bin/env python3
"""GRAV3D 验证器 / validator:检查提交的路径合不合 RULES.md,算代价,与参考答案比。只用 Python 3 标准库。

用法 / usage:
  validate.py --map neutral/<地> --scenarios scenarios/<地>.csv --answers answers/<地>.csv --paths <提交的 jsonl>
              [--rules <含 neutral/classes.json 与 grav3d/costs.json 的目录,默认是本脚本的上一级>]
              [--tracks A,E] [--only id,id] [--out verdicts.csv]

提交文件每行一个 JSON:{"id":..., "track":"A|E", "path":[[x,y,z], ...]}(脚格的位置序列,含起点与终点),
或 {"id":..., "track":..., "status":"unsolvable"}(声称无解)。每道题每个赛道的结论:
  valid          路径合法、到了目标;给出代价、挖、放块数和与参考最优价的比(cost / optimal)
  invalid-<i>    第 i 步(从 path[i-1] 到 path[i],i 从 1 起)非法,附原因;invalid-0 是起点不对
  invalid-goal   走完了没到目标
  missing        没有提交
  unsolvable-ok / unsolvable-wrong   声称无解,与参考答案相符 / 不符
  n/a            这道题在这个赛道不适用(参考答案里是 n/a),不看提交
  reference-error  参考答案说无解,提交却是合法路径(参考答案有错)
退出码:有任何 invalid-*、missing、unsolvable-wrong、reference-error 就是 1。
"""
import argparse
import csv
import gzip
import json
import os
import sys

OUT = 255  # 图外的类别:所有标志为否


class Invalid(Exception):
    pass


class Rules:
    def __init__(self, classes_path, costs_path):
        with open(classes_path, encoding="utf-8") as f:
            table = json.load(f)
        with open(costs_path, encoding="utf-8") as f:
            self.cost = json.load(f)
        self.pass_ = [False] * 256
        self.support = [False] * 256
        self.swim = [False] * 256
        self.climb = [False] * 256
        self.place = [False] * 256
        self.dig_cost = [0] * 256
        self.air = None
        for c in table["classes"]:
            code = c["code"]
            self.pass_[code] = c["passable"]
            self.support[code] = c["support"]
            self.swim[code] = c["swim"]
            self.climb[code] = c["climb"]
            self.place[code] = c["place"]
            tier = c["dig"]
            self.dig_cost[code] = self.cost["dig"][tier - 1] if tier else 0
            if c["name"] == "air":
                self.air = code

    def fall(self, k):
        f = self.cost["fall"]
        return f[k - 1] if k <= 3 else f[2] + (k - 3) * self.cost["fallExtra"]


class Grid:
    def __init__(self, directory):
        with open(os.path.join(directory, "grid.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.x, self.z, self.y = meta["sizeX"], meta["sizeZ"], meta["sizeY"]
        with gzip.open(os.path.join(directory, "grid.bin.gz"), "rb") as f:
            self.data = f.read()
        if len(self.data) != self.x * self.z * self.y:
            raise ValueError("grid.bin.gz 的长度与 grid.json 不符")

    def cls(self, x, y, z):
        if x < 0 or x >= self.x or z < 0 or z >= self.z or y < 0 or y >= self.y:
            return OUT
        return self.data[(x * self.z + z) * self.y + y]


class World:
    """一个赛道下的世界:格子 + 规则 + 赛道。step() 判一步,返回 (代价, 挖, 放)。"""

    def __init__(self, grid, rules, track):
        self.g = grid
        self.r = rules
        self.edit = track == "E"

    # ---- 站得住 ----
    def standable(self, x, y, z):
        r, g = self.r, self.g
        f = g.cls(x, y, z)
        return (r.pass_[f] and r.pass_[g.cls(x, y + 1, z)]
                and (r.support[g.cls(x, y - 1, z)] or r.swim[f] or r.climb[f]))

    # ---- 一步 ----
    def step(self, a, b):
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        if dy == 0 and abs(dx) + abs(dz) == 1:
            return self.horizontal(a, b)
        if dy == 0 and abs(dx) == 1 and abs(dz) == 1:
            return self.diagonal(a, b)
        if dy == 1 and abs(dx) + abs(dz) == 1:
            return self.ascend(a, b)
        if dx == 0 and dz == 0 and abs(dy) == 1:
            return self.vertical(a, b)
        if dy < 0 and abs(dx) + abs(dz) == 1:
            return self.drop(a, b, -dy)
        raise Invalid("位移 (%d,%d,%d) 不是任何一种走法" % (dx, dy, dz))

    def view(self, s, x, y, z):
        """编辑赛道:身体此刻占的两格,原图不可通行的当作空气(已挖开)。"""
        c = self.g.cls(x, y, z)
        if self.edit and x == s[0] and z == s[2] and y in (s[1], s[1] + 1) and not self.r.pass_[c]:
            return self.r.air
        return c

    def enter(self, s, t, base, solid):
        """走进脚格 t:脚头两格可通行(编辑赛道可挖),脚下有支撑(编辑赛道可放)。返回 (代价, 挖, 放)。"""
        r = self.r
        f = self.view(s, t[0], t[1], t[2])
        h = self.view(s, t[0], t[1] + 1, t[2])
        bc = self.view(s, t[0], t[1] - 1, t[2])
        cost, digs, places = base, 0, 0
        for cell, name in ((f, "脚格"), (h, "头格")):
            if not r.pass_[cell]:
                if not self.edit:
                    raise Invalid("目标的%s不可通行(类别 %d)" % (name, cell))
                if r.dig_cost[cell] == 0:
                    raise Invalid("目标的%s挖不动(类别 %d)" % (name, cell))
                cost += r.dig_cost[cell]
                digs += 1
        if not (r.support[bc] or (not solid and (r.swim[f] or r.climb[f]))):
            if not self.edit:
                raise Invalid("目标脚下没有支撑(类别 %d)" % bc)
            if not r.place[bc]:
                raise Invalid("目标脚下没有支撑,也放不了块(类别 %d)" % bc)
            cost += r.cost["place"]
            places += 1
        return cost, digs, places

    def horizontal(self, a, b):
        r = self.r
        fs = self.view(a, a[0], a[1], a[2])
        ft = self.view(a, b[0], b[1], b[2])
        base = r.cost["swim"] if (r.swim[fs] or r.swim[ft]) else r.cost["walk"]
        return self.enter(a, b, base, False)

    def diagonal(self, a, b):
        r, g = self.r, self.g
        if r.swim[self.view(a, a[0], a[1], a[2])] or r.swim[self.view(a, b[0], b[1], b[2])]:
            raise Invalid("水里没有斜走")
        dx, dz = b[0] - a[0], b[2] - a[2]
        for cx, cz in ((a[0] + dx, a[2]), (a[0], a[2] + dz)):
            for y in (a[1], a[1] + 1):
                if not r.pass_[g.cls(cx, y, cz)]:
                    raise Invalid("斜走切角:相邻列 (%d,%d,%d) 不可通行" % (cx, y, cz))
        return self.enter(a, b, r.cost["diag"], False)

    def ascend(self, a, b):
        r, g = self.r, self.g
        clear = g.cls(a[0], a[1] + 2, a[2])
        extra, extra_digs = 0, 0
        if not r.pass_[clear]:
            if not self.edit or r.dig_cost[clear] == 0:
                raise Invalid("上一级:起点头顶上方那格不空(类别 %d)" % clear)
            extra, extra_digs = r.dig_cost[clear], 1
        cost, digs, places = self.enter(a, b, r.cost["ascend"], True)
        return cost + extra, digs + extra_digs, places

    def vertical(self, a, b):
        r = self.r
        c = r.cost
        fs = self.view(a, a[0], a[1], a[2])
        if b[1] > a[1]:
            other = self.view(a, a[0], a[1] + 1, a[2])
            if r.climb[fs] or r.climb[other]:
                return self.enter(a, b, c["climbUp"], False)
            if r.swim[fs] and r.swim[other]:
                return self.enter(a, b, c["swimVertical"], False)
            if self.edit:
                return self.enter(a, b, c["ascend"], False)  # 垫柱
            raise Invalid("向上一格:这里既不是爬也不是游")
        other = self.view(a, a[0], a[1] - 1, a[2])
        if r.climb[fs] or r.climb[other]:
            return self.enter(a, b, c["climbDown"], False)
        if r.swim[fs] and r.swim[other]:
            return self.enter(a, b, c["swimVertical"], False)
        if self.edit:
            return self.enter(a, b, c["fall"][0], False)  # 挖下去
        raise Invalid("向下一格:这里既不是爬也不是游")

    def drop(self, a, b, k):
        r, g = self.r, self.g
        x, z = b[0], b[2]
        y = a[1]
        f0 = g.cls(x, y, z)
        if not (r.pass_[f0] and r.pass_[g.cls(x, y + 1, z)]):
            raise Invalid("走出边沿:列 (%d,%d) 在脚高处过不去" % (x, z))
        if r.support[g.cls(x, y - 1, z)] or r.swim[f0] or r.climb[f0]:
            raise Invalid("走出边沿:那一格站得住,那是平走,不是下落")
        for j in range(1, k + 1):
            f = g.cls(x, y - j, z)
            if not r.pass_[f]:
                raise Invalid("下落途中 (%d,%d,%d) 不可通行" % (x, y - j, z))
            landing = r.support[g.cls(x, y - j - 1, z)] or r.swim[f] or r.climb[f]
            if j < k and landing:
                raise Invalid("下落要落到第一个站得住的格,这里 (%d,%d,%d) 就站得住" % (x, y - j, z))
            if j == k:
                if not landing:
                    raise Invalid("下落的终点 (%d,%d,%d) 站不住" % (x, y - j, z))
                if k > 3 and not r.swim[f]:
                    raise Invalid("下落 %d 格,超过 3 格只许落进水" % k)
        return r.cost["edge"] + r.fall(k), 0, 0


def reached(grid, rules, goal, gx, gy, gz, radius, pos):
    x, y, z = pos
    if goal == "at":
        return (x, y, z) == (gx, gy, gz)
    if goal == "near":
        return (x - gx) ** 2 + (y - gy) ** 2 + (z - gz) ** 2 <= radius * radius
    # dig:脚格或头格与目标格面相邻
    def adjacent(px, py, pz):
        return abs(px - gx) + abs(py - gy) + abs(pz - gz) == 1
    return adjacent(x, y, z) or adjacent(x, y + 1, z)


def check_path(world, problem, path):
    """返回 (代价, 挖, 放);非法时抛 Invalid,消息以 'i:' 开头带步号('0:' 起点,'goal:' 没到目标)。"""
    start = (problem["sx"], problem["sy"], problem["sz"])
    if not path or tuple(path[0]) != start:
        raise Invalid("0: 路径不是从起点 %s 开始" % (start,))
    cost = digs = places = 0
    prev = tuple(path[0])
    for i in range(1, len(path)):
        cur = tuple(path[i])
        try:
            c, d, p = world.step(prev, cur)
        except Invalid as e:
            raise Invalid("%d: %s" % (i, e))
        cost, digs, places = cost + c, digs + d, places + p
        prev = cur
    if not reached(world.g, world.r, problem["goal"], problem["gx"], problem["gy"], problem["gz"], problem["radius"], prev):
        raise Invalid("goal: 走完了没到目标")
    if problem["goal"] == "dig":
        dc = world.r.dig_cost[world.g.cls(problem["gx"], problem["gy"], problem["gz"])]
        if dc == 0:
            raise Invalid("goal: 目标格挖不动")
        cost, digs = cost + dc, digs + 1
    return cost, digs, places


def read_scenarios(path):
    with open(path, encoding="utf-8", newline="") as f:
        first = f.readline()
        if not first.startswith("version,"):
            raise ValueError("场景文件首行应是 version,<n>")
        out = []
        for row in csv.DictReader(f):
            for k in ("sx", "sy", "sz", "gx", "gy", "gz"):
                row[k] = int(row[k])
            row["radius"] = int(row["radius"]) if row["radius"] else 0
            out.append(row)
        return out


def read_answers(path):
    with open(path, encoding="utf-8", newline="") as f:
        return {(r["id"], r["track"]): r for r in csv.DictReader(f)}


def read_submission(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                out[(row["id"], row["track"])] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--answers", required=True)
    ap.add_argument("--paths", required=True)
    ap.add_argument("--rules", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    ap.add_argument("--tracks", default="A,E")
    ap.add_argument("--only", help="只验这几个题号,逗号分隔")
    ap.add_argument("--out")
    args = ap.parse_args()
    rules = Rules(os.path.join(args.rules, "neutral", "classes.json"), os.path.join(args.rules, "grav3d", "costs.json"))
    grid = Grid(args.map)
    scenarios = read_scenarios(args.scenarios)
    if args.only:
        scenarios = [p for p in scenarios if p["id"] in args.only.split(",")]
    answers = read_answers(args.answers)
    submission = read_submission(args.paths)
    bad = 0
    rows = []
    for track in args.tracks.split(","):
        world = World(grid, rules, track)
        for p in scenarios:
            key = (p["id"], track)
            ref = answers.get(key)
            if ref is None:
                raise SystemExit("答案文件里没有 %s %s" % key)
            if ref["status"] == "n/a":
                rows.append((p["id"], track, "n/a", "", "", "", ""))
                continue
            sub = submission.get(key)
            if sub is None:
                verdict, bad = "missing", bad + 1
                rows.append((p["id"], track, verdict, "", "", "", ""))
                continue
            if sub.get("status") == "unsolvable":
                ok = ref["status"] == "unsolvable"
                bad += 0 if ok else 1
                rows.append((p["id"], track, "unsolvable-ok" if ok else "unsolvable-wrong", "", "", "", ""))
                continue
            try:
                cost, digs, places = check_path(world, p, sub["path"])
            except Invalid as e:
                where, _, why = str(e).partition(": ")
                verdict = "invalid-goal" if where == "goal" else "invalid-" + where
                bad += 1
                rows.append((p["id"], track, verdict, "", "", "", why))
                continue
            if ref["status"] != "optimal":
                # 参考说无解,提交却是合法路径:参考答案错了,要查
                bad += 1
                rows.append((p["id"], track, "reference-error", cost, digs, places, "参考答案说无解"))
                continue
            rows.append((p["id"], track, "valid", cost, digs, places, "%.4f" % (cost / int(ref["cost"]))))
    with (open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout) as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "track", "verdict", "cost", "digs", "places", "ratio_or_reason"])
        w.writerows(rows)
    counts = {}
    for r in rows:
        kind = "invalid" if r[2].startswith("invalid") else r[2]
        counts[kind] = counts.get(kind, 0) + 1
    print("summary:", json.dumps(counts, sort_keys=True), file=sys.stderr)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

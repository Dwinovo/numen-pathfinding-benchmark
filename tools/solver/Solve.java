import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.zip.GZIPInputStream;

/**
 * GRAV3D 的参考求解器:读中立地形(grid.bin.gz + classes.json)、代价表(costs.json)与场景 CSV,
 * 对每道题在指定赛道上用权重 1 的 A* 求最短时间,写答案 CSV 与参考路径 JSONL。规则的权威文本是 RULES.md,这里只是它的一份实现;
 * 与 Numen 的寻路没有任何代码关系。无依赖,{@code javac Solve.java} 即可。
 *
 * <pre>
 * java Solve --classes neutral/classes.json --costs grav3d/costs.json --map neutral/hills \
 *            --scenarios scenarios/hills.csv --tracks A,E --answers out/answers.csv --paths out/paths.jsonl [--threads N] [--only id,id] [--no-heuristic true]
 * </pre>
 */
public final class Solve {

    /** 圈外的"类别":所有标志都是否,码 255。 */
    private static final int OUT = 255;

    // ==================== 规则(读自 classes.json 与 costs.json) ====================

    /** 类别标志与代价表,按类别码索引,圈外是 {@link #OUT}。 */
    static final class Rules {
        final boolean[] pass = new boolean[256];
        final boolean[] support = new boolean[256];
        final boolean[] swim = new boolean[256];
        final boolean[] climb = new boolean[256];
        final boolean[] placeable = new boolean[256];
        /** 挖开这类格子的代价;0 是挖不动(可通行的格子不用挖,也记 0)。 */
        final int[] digCost = new int[256];
        int air;
        int walk, diag, ascend, edge, fallExtra, swimH, swimV, climbUp, climbDown, place;
        final int[] fall = new int[3];

        static Rules load(Path classes, Path costs) throws IOException {
            Rules r = new Rules();
            Map<?, ?> cost = (Map<?, ?>) Json.parse(Files.readString(costs, StandardCharsets.UTF_8));
            r.walk = num(cost, "walk");
            r.diag = num(cost, "diag");
            r.ascend = num(cost, "ascend");
            r.edge = num(cost, "edge");
            r.fallExtra = num(cost, "fallExtra");
            r.swimH = num(cost, "swim");
            r.swimV = num(cost, "swimVertical");
            r.climbUp = num(cost, "climbUp");
            r.climbDown = num(cost, "climbDown");
            r.place = num(cost, "place");
            List<?> fall = (List<?>) cost.get("fall");
            for (int i = 0; i < 3; i++) {
                r.fall[i] = ((Number) fall.get(i)).intValue();
            }
            List<?> dig = (List<?>) cost.get("dig");
            Map<?, ?> table = (Map<?, ?>) Json.parse(Files.readString(classes, StandardCharsets.UTF_8));
            for (Object o : (List<?>) table.get("classes")) {
                Map<?, ?> c = (Map<?, ?>) o;
                int code = num(c, "code");
                r.pass[code] = (Boolean) c.get("passable");
                r.support[code] = (Boolean) c.get("support");
                r.swim[code] = (Boolean) c.get("swim");
                r.climb[code] = (Boolean) c.get("climb");
                r.placeable[code] = (Boolean) c.get("place");
                int tier = num(c, "dig");
                r.digCost[code] = tier == 0 ? 0 : ((Number) dig.get(tier - 1)).intValue();
                if ("air".equals(c.get("name"))) {
                    r.air = code;
                }
            }
            return r;
        }

        /** 落 k 格(k ≥ 1)的下落时间。 */
        int fall(int k) {
            return k <= 3 ? fall[k - 1] : fall[2] + (k - 3) * fallExtra;
        }

        private static int num(Map<?, ?> m, String key) {
            return ((Number) m.get(key)).intValue();
        }
    }

    // ==================== 地图 ====================

    static final class Grid {
        final int sizeX, sizeZ, sizeY;
        final byte[] cell;

        Grid(Path dir) throws IOException {
            Map<?, ?> meta = (Map<?, ?>) Json.parse(Files.readString(dir.resolve("grid.json"), StandardCharsets.UTF_8));
            sizeX = ((Number) meta.get("sizeX")).intValue();
            sizeZ = ((Number) meta.get("sizeZ")).intValue();
            sizeY = ((Number) meta.get("sizeY")).intValue();
            cell = new byte[Math.multiplyExact(Math.multiplyExact(sizeX, sizeZ), sizeY)];
            try (InputStream in = new GZIPInputStream(Files.newInputStream(dir.resolve("grid.bin.gz")), 1 << 16)) {
                int off = 0;
                while (off < cell.length) {
                    int n = in.read(cell, off, cell.length - off);
                    if (n < 0) {
                        throw new IOException("grid.bin.gz 比 grid.json 说的短");
                    }
                    off += n;
                }
                if (in.read() >= 0) {
                    throw new IOException("grid.bin.gz 比 grid.json 说的长");
                }
            }
        }

        int index(int x, int y, int z) {
            return (x * sizeZ + z) * sizeY + y;
        }

        int cls(int x, int y, int z) {
            return x < 0 || x >= sizeX || z < 0 || z >= sizeZ || y < 0 || y >= sizeY ? OUT : cell[(x * sizeZ + z) * sizeY + y] & 0xFF;
        }
    }

    // ==================== 题 ====================

    record Problem(String id, int sx, int sy, int sz, String goal, int gx, int gy, int gz, int radius) {}

    static List<Problem> readScenarios(Path file) throws IOException {
        List<Problem> out = new ArrayList<>();
        try (BufferedReader in = Files.newBufferedReader(file, StandardCharsets.UTF_8)) {
            String line = in.readLine();
            if (line == null || !line.startsWith("version,")) {
                throw new IOException("场景文件首行应是 version,<n>:" + file);
            }
            String[] head = in.readLine().split(",", -1);
            for (line = in.readLine(); line != null; line = in.readLine()) {
                if (line.isBlank()) {
                    continue;
                }
                String[] f = line.split(",", -1);
                java.util.Map<String, String> row = new java.util.HashMap<>();
                for (int i = 0; i < head.length; i++) {
                    row.put(head[i], f[i]);
                }
                out.add(new Problem(row.get("id"), Integer.parseInt(row.get("sx")), Integer.parseInt(row.get("sy")), Integer.parseInt(row.get("sz")),
                        row.get("goal"), Integer.parseInt(row.get("gx")), Integer.parseInt(row.get("gy")), Integer.parseInt(row.get("gz")),
                        row.get("radius").isEmpty() ? 0 : Integer.parseInt(row.get("radius"))));
            }
        }
        return out;
    }

    /** 一道题在一个赛道上的结论。 */
    record Result(String status, int cost, int digs, int places, int expanded, int[] path) {}

    // ==================== 搜索 ====================

    /** 一个线程一份:代价与来路两个与格子同大的数组、开放表、一次展开的出边。 */
    static final class Searcher {
        private static final int INF = Integer.MAX_VALUE;
        /** 估价里每格垂直位移的最小代价:任何一步的代价都不低于 walk×水平位移 + 这个×垂直位移(见 RULES.md)。 */
        private static final int VERTICAL = 1300;

        final Grid grid;
        final Rules r;
        final boolean edit;
        /** 估价恒为 0(即 Dijkstra),只用来核对估价没有高估:同一道题两种算出来的最优价必须相同。 */
        private final boolean blind;
        private final int[] best;
        private final int[] parent;
        private long[] heap = new long[1 << 20];
        private int heapSize;

        // 当前展开的状态与它的出边
        private int curX, curY, curZ;
        private final int[] edgeTo = new int[32];
        private final int[] edgeCost = new int[32];
        private final int[] edgeDigs = new int[32];
        private final int[] edgePlaces = new int[32];
        private int edges;
        private int tCost, tDigs, tPlaces;

        // 目标
        private String goal;
        private int gx, gy, gz, radius;

        Searcher(Grid grid, Rules rules, boolean edit, boolean blind) {
            this.grid = grid;
            this.r = rules;
            this.edit = edit;
            this.blind = blind;
            this.best = new int[grid.cell.length];
            this.parent = new int[grid.cell.length];
        }

        /** 起点站得住:脚头两格可通行,脚下是支撑,或脚在水里、可攀爬格里。两个赛道同一个判据。 */
        boolean standable(int x, int y, int z) {
            int f = grid.cls(x, y, z);
            return r.pass[f] && r.pass[grid.cls(x, y + 1, z)] && (r.support[grid.cls(x, y - 1, z)] || r.swim[f] || r.climb[f]);
        }

        Result solve(Problem p) {
            goal = p.goal();
            gx = p.gx();
            gy = p.gy();
            gz = p.gz();
            radius = p.radius();
            if (!standable(p.sx(), p.sy(), p.sz()) || (!edit && goal.equals("dig"))) {
                return new Result("n/a", 0, 0, 0, 0, null);
            }
            int finalDig = 0;
            if (goal.equals("dig")) {
                finalDig = r.digCost[grid.cls(gx, gy, gz)];
                if (finalDig == 0) {
                    return new Result("unsolvable", 0, 0, 0, 0, null);
                }
            }
            Arrays.fill(best, INF);
            heapSize = 0;
            int start = grid.index(p.sx(), p.sy(), p.sz());
            best[start] = 0;
            parent[start] = -1;
            push(heuristic(p.sx(), p.sy(), p.sz()), start);
            int expanded = 0;
            while (heapSize > 0) {
                long top = pop();
                int s = (int) top;
                int f = (int) (top >>> 32);
                int sy = s % grid.sizeY;
                int column = s / grid.sizeY;
                int sz = column % grid.sizeZ;
                int sx = column / grid.sizeZ;
                int g = best[s];
                if (f != g + heuristic(sx, sy, sz)) {
                    continue; // 已被更便宜的路径取代的旧条目
                }
                expanded++;
                if (reached(sx, sy, sz)) {
                    return finish(s, g + finalDig, finalDig > 0, expanded);
                }
                expand(sx, sy, sz);
                for (int i = 0; i < edges; i++) {
                    int t = edgeTo[i];
                    int cost = g + edgeCost[i];
                    if (cost < best[t]) {
                        best[t] = cost;
                        parent[t] = s;
                        int ty = t % grid.sizeY;
                        int tcol = t / grid.sizeY;
                        push(cost + heuristic(tcol / grid.sizeZ, ty, tcol % grid.sizeZ), t);
                    }
                }
            }
            return new Result("unsolvable", 0, 0, 0, expanded, null);
        }

        private Result finish(int goalState, int cost, boolean digGoal, int expanded) {
            List<Integer> chain = new ArrayList<>();
            for (int s = goalState; s >= 0; s = parent[s]) {
                chain.add(s);
            }
            int n = chain.size();
            int[] path = new int[n];
            for (int i = 0; i < n; i++) {
                path[i] = chain.get(n - 1 - i);
            }
            // 挖、放块数:沿路径对每一步重新展开,取到下一个状态的那条出边
            int digs = digGoal ? 1 : 0;
            int places = 0;
            for (int i = 0; i + 1 < n; i++) {
                int s = path[i];
                int sy = s % grid.sizeY;
                int column = s / grid.sizeY;
                expand(column / grid.sizeZ, sy, column % grid.sizeZ);
                int pick = -1;
                for (int e = 0; e < edges; e++) {
                    if (edgeTo[e] == path[i + 1] && (pick < 0 || edgeCost[e] < edgeCost[pick])) {
                        pick = e;
                    }
                }
                digs += edgeDigs[pick];
                places += edgePlaces[pick];
            }
            return new Result("optimal", cost, digs, places, expanded, path);
        }

        private boolean reached(int x, int y, int z) {
            switch (goal) {
                case "at":
                    return x == gx && y == gy && z == gz;
                case "near": {
                    long dx = x - gx, dy = y - gy, dz = z - gz;
                    return dx * dx + dy * dy + dz * dz <= (long) radius * radius;
                }
                default: {
                    // 脚格或头格与目标格面相邻
                    return adjacent(x, y, z) || adjacent(x, y + 1, z);
                }
            }
        }

        private boolean adjacent(int x, int y, int z) {
            return Math.abs(x - gx) + Math.abs(y - gy) + Math.abs(z - gz) == 1;
        }

        /** 一致、可采纳的估价,向上取整成整数(取整保持一致性,见 RULES.md)。 */
        private int heuristic(int x, int y, int z) {
            if (blind) {
                return 0;
            }
            double horizontal = Math.hypot(x - gx, z - gz);
            int vertical;
            switch (goal) {
                case "at":
                    return (int) Math.ceil(r.walk * horizontal + VERTICAL * Math.abs(y - gy));
                case "near":
                    return (int) Math.ceil(r.walk * Math.max(0, horizontal - radius) + VERTICAL * Math.max(0, Math.abs(y - gy) - radius));
                default:
                    // 目标格的面邻位:脚在水平距离 1 之内,脚高在 [gy-2, gy+1]
                    vertical = Math.max(0, Math.max(y - (gy + 1), (gy - 2) - y));
                    return (int) Math.ceil(r.walk * Math.max(0, horizontal - 1) + VERTICAL * vertical);
            }
        }

        // ---------- 出边 ----------

        /** 展开时的格子类别:编辑赛道里,身体此刻占的两格若原图不可通行,视为空气(已经挖开)。 */
        private int view(int x, int y, int z) {
            int c = grid.cls(x, y, z);
            if (edit && x == curX && z == curZ && (y == curY || y == curY + 1) && !r.pass[c]) {
                return r.air;
            }
            return c;
        }

        /**
         * 走进脚格 (x, y, z):脚头两格要可通行(编辑赛道可挖开),脚下要有支撑(编辑赛道可放一块)。
         * 水里、可攀爬格里不要支撑,除非 {@code solid},此时必须落在实心上。结果在 tCost、tDigs、tPlaces。
         */
        private boolean enter(int x, int y, int z, int base, boolean solid) {
            int f = view(x, y, z);
            int h = view(x, y + 1, z);
            int b = view(x, y - 1, z);
            int cost = base;
            int digs = 0;
            int places = 0;
            if (!r.pass[f]) {
                if (!edit || r.digCost[f] == 0) {
                    return false;
                }
                cost += r.digCost[f];
                digs++;
            }
            if (!r.pass[h]) {
                if (!edit || r.digCost[h] == 0) {
                    return false;
                }
                cost += r.digCost[h];
                digs++;
            }
            if (!(r.support[b] || (!solid && (r.swim[f] || r.climb[f])))) {
                if (!edit || !r.placeable[b]) {
                    return false;
                }
                cost += r.place;
                places++;
            }
            tCost = cost;
            tDigs = digs;
            tPlaces = places;
            return true;
        }

        private void emit(int x, int y, int z, int cost, int digs, int places) {
            edgeTo[edges] = grid.index(x, y, z);
            edgeCost[edges] = cost;
            edgeDigs[edges] = digs;
            edgePlaces[edges] = places;
            edges++;
        }

        private static final int[][] FOUR = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        private static final int[][] DIAGONAL = {{1, 1}, {1, -1}, {-1, 1}, {-1, -1}};

        private void expand(int x, int y, int z) {
            edges = 0;
            curX = x;
            curY = y;
            curZ = z;
            int fs = view(x, y, z);
            for (int[] d : FOUR) {
                int tx = x + d[0];
                int tz = z + d[1];
                // 平走或水平游
                int ft = view(tx, y, tz);
                if (enter(tx, y, tz, r.swim[fs] || r.swim[ft] ? r.swimH : r.walk, false)) {
                    emit(tx, y, tz, tCost, tDigs, tPlaces);
                }
                // 上一级:起点头顶上方那格也要空(编辑赛道可挖),落在实心上
                int clear = grid.cls(x, y + 2, z);
                int extra = 0;
                int extraDigs = 0;
                boolean room = true;
                if (!r.pass[clear]) {
                    if (edit && r.digCost[clear] > 0) {
                        extra = r.digCost[clear];
                        extraDigs = 1;
                    } else {
                        room = false;
                    }
                }
                if (room && enter(tx, y + 1, tz, r.ascend, true)) {
                    emit(tx, y + 1, tz, tCost + extra, tDigs + extraDigs, tPlaces);
                }
                drop(x, y, z, tx, tz);
            }
            if (!r.swim[fs]) {
                for (int[] d : DIAGONAL) {
                    int tx = x + d[0];
                    int tz = z + d[1];
                    if (r.swim[view(tx, y, tz)] || !r.pass[grid.cls(tx, y, z)] || !r.pass[grid.cls(tx, y + 1, z)]
                            || !r.pass[grid.cls(x, y, tz)] || !r.pass[grid.cls(x, y + 1, tz)]) {
                        continue;
                    }
                    if (enter(tx, y, tz, r.diag, false)) {
                        emit(tx, y, tz, tCost, tDigs, tPlaces);
                    }
                }
            }
            vertical(x, y, z, fs);
        }

        /** 走出边沿下落:列 (tx, tz) 在脚高处能过但站不住,往下落到第一个站得住的格;落在实心或可攀爬格上最多 3 格,落进水不限。 */
        private void drop(int x, int y, int z, int tx, int tz) {
            int f0 = grid.cls(tx, y, tz);
            if (!r.pass[f0] || !r.pass[grid.cls(tx, y + 1, tz)]) {
                return;
            }
            if (r.support[grid.cls(tx, y - 1, tz)] || r.swim[f0] || r.climb[f0]) {
                return; // 站得住,那是平走
            }
            for (int k = 1; ; k++) {
                int f = grid.cls(tx, y - k, tz);
                if (!r.pass[f]) {
                    return;
                }
                if (r.support[grid.cls(tx, y - k - 1, tz)] || r.swim[f] || r.climb[f]) {
                    if (k <= 3 || r.swim[f]) {
                        emit(tx, y - k, tz, r.edge + r.fall(k), 0, 0);
                    }
                    return;
                }
            }
        }

        /** 垂直一格:有可攀爬格参与是爬,两格都是水是游,否则编辑赛道里向上是垫柱、向下是挖下去。 */
        private void vertical(int x, int y, int z, int fs) {
            int up = view(x, y + 1, z);
            if (r.climb[fs] || r.climb[up]) {
                if (enter(x, y + 1, z, r.climbUp, false)) {
                    emit(x, y + 1, z, tCost, tDigs, tPlaces);
                }
            } else if (r.swim[fs] && r.swim[up]) {
                if (enter(x, y + 1, z, r.swimV, false)) {
                    emit(x, y + 1, z, tCost, tDigs, tPlaces);
                }
            } else if (edit && enter(x, y + 1, z, r.ascend, false)) {
                emit(x, y + 1, z, tCost, tDigs, tPlaces);
            }
            int down = view(x, y - 1, z);
            if (r.climb[fs] || r.climb[down]) {
                if (enter(x, y - 1, z, r.climbDown, false)) {
                    emit(x, y - 1, z, tCost, tDigs, tPlaces);
                }
            } else if (r.swim[fs] && r.swim[down]) {
                if (enter(x, y - 1, z, r.swimV, false)) {
                    emit(x, y - 1, z, tCost, tDigs, tPlaces);
                }
            } else if (edit && enter(x, y - 1, z, r.fall[0], false)) {
                emit(x, y - 1, z, tCost, tDigs, tPlaces);
            }
        }

        // ---------- 开放表:键 = 估价总价(高 32 位)与状态下标(低 32 位) ----------

        private void push(int f, int s) {
            if (heapSize == heap.length) {
                heap = Arrays.copyOf(heap, heap.length * 2);
            }
            long key = ((long) f << 32) | (s & 0xFFFFFFFFL);
            int i = heapSize++;
            while (i > 0) {
                int up = (i - 1) >>> 1;
                if (heap[up] <= key) {
                    break;
                }
                heap[i] = heap[up];
                i = up;
            }
            heap[i] = key;
        }

        private long pop() {
            long top = heap[0];
            long last = heap[--heapSize];
            int i = 0;
            int half = heapSize >>> 1;
            while (i < half) {
                int child = 2 * i + 1;
                if (child + 1 < heapSize && heap[child + 1] < heap[child]) {
                    child++;
                }
                if (heap[child] >= last) {
                    break;
                }
                heap[i] = heap[child];
                i = child;
            }
            heap[i] = last;
            return top;
        }
    }

    // ==================== 命令行 ====================

    public static void main(String[] argv) throws Exception {
        Map<String, String> args = new java.util.HashMap<>();
        for (int i = 0; i + 1 < argv.length; i += 2) {
            args.put(argv[i], argv[i + 1]);
        }
        Rules rules = Rules.load(Path.of(args.get("--classes")), Path.of(args.get("--costs")));
        Grid grid = new Grid(Path.of(args.get("--map")));
        List<Problem> problems = readScenarios(Path.of(args.get("--scenarios")));
        if (args.containsKey("--only")) {
            List<String> only = List.of(args.get("--only").split(","));
            problems = problems.stream().filter(p -> only.contains(p.id())).toList();
        }
        String[] tracks = args.getOrDefault("--tracks", "A,E").split(",");
        int threads = Integer.parseInt(args.getOrDefault("--threads", "1"));
        boolean blind = Boolean.parseBoolean(args.getOrDefault("--no-heuristic", "false"));
        List<ThreadLocal<Searcher>> local = new ArrayList<>();
        for (String name : tracks) {
            boolean edit = name.equals("E");
            local.add(ThreadLocal.withInitial(() -> new Searcher(grid, rules, edit, blind)));
        }
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        List<Future<Result>> futures = new ArrayList<>();
        List<long[]> timings = new ArrayList<>();
        for (Problem p : problems) {
            for (int t = 0; t < tracks.length; t++) {
                int track = t;
                futures.add(pool.submit(() -> {
                    long t0 = System.nanoTime();
                    Result res = local.get(track).get().solve(p);
                    System.err.printf("%s %s %s cost=%d expanded=%d %.1fs%n", p.id(), tracks[track], res.status(), res.cost(), res.expanded(),
                            (System.nanoTime() - t0) / 1e9);
                    return res;
                }));
            }
        }
        try (BufferedWriter answers = Files.newBufferedWriter(Path.of(args.get("--answers")), StandardCharsets.UTF_8);
                BufferedWriter paths = Files.newBufferedWriter(Path.of(args.get("--paths")), StandardCharsets.UTF_8)) {
            answers.write("id,track,status,cost,digs,places\n");
            int k = 0;
            for (Problem p : problems) {
                for (int t = 0; t < tracks.length; t++) {
                    Result res = futures.get(k++).get();
                    boolean solved = res.status().equals("optimal");
                    answers.write(p.id() + "," + tracks[t] + "," + res.status() + "," + (solved ? res.cost() : "") + ","
                            + (solved ? res.digs() : "") + "," + (solved ? res.places() : "") + "\n");
                    if (solved) {
                        StringBuilder sb = new StringBuilder("{\"id\":\"" + p.id() + "\",\"track\":\"" + tracks[t] + "\",\"path\":[");
                        for (int i = 0; i < res.path().length; i++) {
                            int s = res.path()[i];
                            int y = s % grid.sizeY;
                            int column = s / grid.sizeY;
                            sb.append(i == 0 ? "" : ",").append('[').append(column / grid.sizeZ).append(',').append(y).append(',')
                                    .append(column % grid.sizeZ).append(']');
                        }
                        paths.write(sb.append("]}\n").toString());
                    } else if (res.status().equals("unsolvable")) {
                        paths.write("{\"id\":\"" + p.id() + "\",\"track\":\"" + tracks[t] + "\",\"status\":\"unsolvable\"}\n");
                    }
                }
            }
        }
        pool.shutdown();
    }

    // ==================== 最小的 JSON 读取(classes.json、costs.json、grid.json 用) ====================

    static final class Json {
        private final String s;
        private int i;

        private Json(String s) {
            this.s = s;
        }

        static Object parse(String text) {
            Json j = new Json(text);
            Object v = j.value();
            j.skip();
            if (j.i != text.length()) {
                throw new IllegalArgumentException("JSON 末尾多余内容");
            }
            return v;
        }

        private void skip() {
            while (i < s.length() && Character.isWhitespace(s.charAt(i))) {
                i++;
            }
        }

        private Object value() {
            skip();
            char c = s.charAt(i);
            if (c == '{') {
                i++;
                Map<String, Object> m = new java.util.LinkedHashMap<>();
                skip();
                if (s.charAt(i) == '}') {
                    i++;
                    return m;
                }
                while (true) {
                    skip();
                    String key = string();
                    skip();
                    i++; // ':'
                    m.put(key, value());
                    skip();
                    if (s.charAt(i++) == '}') {
                        return m;
                    }
                }
            }
            if (c == '[') {
                i++;
                List<Object> l = new ArrayList<>();
                skip();
                if (s.charAt(i) == ']') {
                    i++;
                    return l;
                }
                while (true) {
                    l.add(value());
                    skip();
                    if (s.charAt(i++) == ']') {
                        return l;
                    }
                }
            }
            if (c == '"') {
                return string();
            }
            if (s.startsWith("true", i)) {
                i += 4;
                return Boolean.TRUE;
            }
            if (s.startsWith("false", i)) {
                i += 5;
                return Boolean.FALSE;
            }
            int start = i;
            while (i < s.length() && "+-0123456789.eE".indexOf(s.charAt(i)) >= 0) {
                i++;
            }
            return Double.parseDouble(s.substring(start, i));
        }

        private String string() {
            StringBuilder sb = new StringBuilder();
            i++; // 开引号
            while (s.charAt(i) != '"') {
                char c = s.charAt(i++);
                if (c == '\\') {
                    char e = s.charAt(i++);
                    switch (e) {
                        case 'n' -> sb.append('\n');
                        case 't' -> sb.append('\t');
                        case 'u' -> {
                            sb.append((char) Integer.parseInt(s.substring(i, i + 4), 16));
                            i += 4;
                        }
                        default -> sb.append(e);
                    }
                } else {
                    sb.append(c);
                }
            }
            i++;
            return sb.toString();
        }
    }
}

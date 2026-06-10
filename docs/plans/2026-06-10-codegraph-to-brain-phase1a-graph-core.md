# Codegraph → Brain, Phase 1a: Graph Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `wicked-brain` answer code-relationship queries (blast-radius, callers, lineage) from a codegraph-built static graph it owns — with zero `wicked-garden` dependency.

**Architecture:** Brain shells the external `@colbymchenry/codegraph` CLI to *build* a per-repo SQLite graph at `<source>/.codegraph/codegraph.db`, then reads that DB **directly** via `better-sqlite3` (no query-time subprocess) to serve new `graph-*` API actions, exposed through a new `wicked-brain:graph` skill. Freshness is lazy: every query carries a "N commits behind HEAD" staleness stamp and rebuilds on demand — never coupled to the file watcher (Decision D5).

**Tech Stack:** Node ≥18 ESM (`.mjs`), `better-sqlite3` v12 (read codegraph DB), `node:child_process` (shell codegraph CLI), `node:test` + `node:assert/strict`. The codegraph CLI itself requires **Node ≥22.5** (`node:sqlite`); brain runs on Node 26.

**Repo:** `/Users/michael.parcewski/Projects/wicked-brain` (server source under `server/`). This plan does NOT touch wicked-garden.

---

## Subsequent plans (sequenced after this one)

- **Phase 1b — injected edges + extractor framework** (brain): built-in extractors (bus producer→consumer, command→agent, hooks, agent→tool) + the drop-in extractor registry (Decision D3). Enriches this plan's graph; independently testable.
- **Phase 2 — garden-side** (wicked-garden): repoint wicked-patch to brain's DB, ship the archetype extractor as a drop-in, alias/remove `search:*` commands, amend ADR 0001, update CLAUDE.md.

Reference spec: `wicked-garden/docs/specs/2026-06-10-codegraph-to-brain-migration.md` (Decisions D1–D6).

---

## File structure

| File | New/Mod | Responsibility |
|---|---|---|
| `server/lib/codegraph-resolver.mjs` | Create | Resolve the codegraph CLI argv (env → brain config → PATH → node_modules → npx); kill-switch. Port of garden's `_codegraph.py::resolve_codegraph`. |
| `server/lib/codegraph-index.mjs` | Create | `dbPath(source)`, `staleness(source)` (commits-behind HEAD), `runIndex(source)` (spawn `codegraph index`). |
| `server/lib/codegraph-client.mjs` | Create | Open `.codegraph/codegraph.db` readonly; `blastRadius`, `callers`, `lineage` via BFS over the `edges` table; attaches staleness to every result. |
| `server/bin/wicked-brain-server.mjs` | Modify (actions object ~L135–306) | Register `graph-index`, `graph-blast-radius`, `graph-callers`, `graph-lineage`; add the write one to `WRITE_ACTIONS`. |
| `skills/wicked-brain-graph/SKILL.md` | Create | New `wicked-brain:graph` skill documenting the graph queries. |
| `skills/wicked-brain-lsp/SKILL.md` | Modify (frontmatter) | Remove "blast radius" / "architecture map" trigger phrases (they were never implemented in LSP; they move here). |
| `server/test/codegraph-resolver.test.mjs` | Create | Resolver ladder + kill-switch. |
| `server/test/codegraph-index.test.mjs` | Create | dbPath + staleness (present/absent/behind). |
| `server/test/codegraph-client.test.mjs` | Create | blastRadius/callers/lineage over a hand-built fixture DB. |
| `docs/codegraph-contract.md` | Create (Task 1) | Pinned codegraph schema + edge-direction findings the client relies on. |

**Edge-direction constant:** the client centralizes the dependents-traversal direction in ONE constant (`DEPENDENTS_BY`), set from Task 1's empirical finding, so a wrong guess is a one-line flip, not a rewrite.

---

## Task 1: Characterization spike — pin codegraph's schema + edge direction

**Why:** Garden's `_codegraph.py` says the `nodes`/`edges` schema is `nodes(id,kind,name,qualified_name,file_path,language,start_line,end_line,start_column,end_column,updated_at,signature)` and `edges(source,target,kind,metadata,provenance)`, but its `inject_edges.py` comment is self-contradictory about blast-radius edge direction ("walk incoming edges" vs. an inserted producer→consumer edge that only resolves walking *outgoing*). We must observe the real behavior before writing traversal SQL.

**Files:**
- Create: `docs/codegraph-contract.md`

- [ ] **Step 1: Build a graph on a tiny fixture**

```bash
cd /tmp && rm -rf cg-spike && mkdir cg-spike && cd cg-spike
git init -q && printf '%s\n' "def base(): pass" > a.py
printf '%s\n' "from a import base" "def caller(): return base()" > b.py
git add -A && git commit -qm init
npx -y @colbymchenry/codegraph index .
```
Expected: `.codegraph/codegraph.db` created; output reports nodes/edges counts.

- [ ] **Step 2: Dump the real schema**

```bash
cd /tmp/cg-spike
sqlite3 .codegraph/codegraph.db ".schema nodes" ".schema edges"
sqlite3 .codegraph/codegraph.db "SELECT id,kind,name,file_path FROM nodes;"
sqlite3 .codegraph/codegraph.db "SELECT source,target,kind FROM edges;"
```
Record the exact column lists for `nodes` and `edges`.

- [ ] **Step 3: Determine blast-radius edge direction empirically**

`b.py::caller` calls/imports `a.py::base`. So `base`'s dependents (blast radius) must include `caller`. Inspect the edge row for that relationship:
- If the edge is `(source=<caller/b.py>, target=<base/a.py>)` → **dependents-of-X = rows WHERE target=X, collect `source`** → set `DEPENDENTS_BY = "target"`.
- If reversed → `DEPENDENTS_BY = "source"`.

```bash
sqlite3 .codegraph/codegraph.db \
  "SELECT source,target,kind FROM edges WHERE kind IN ('calls','imports','references');"
```

- [ ] **Step 4: Capture the index CLI contract**

```bash
npx -y @colbymchenry/codegraph index --help 2>&1 | head -40
```
Record: exact subcommand + flags for indexing a directory, and whether it accepts a path arg or uses cwd. (Used by `runIndex` in Task 3.)

- [ ] **Step 5: Write the contract doc**

Create `docs/codegraph-contract.md` with: the `nodes` columns, the `edges` columns, the resolved `DEPENDENTS_BY` value (with the evidence row), the index command form, and the codegraph version (`npx -y @colbymchenry/codegraph --version`). This is the single reference Tasks 3–4 cite.

- [ ] **Step 6: Commit**

```bash
cd /Users/michael.parcewski/Projects/wicked-brain
git add docs/codegraph-contract.md
git commit -m "docs(codegraph): pin schema + blast-radius edge direction from spike"
```

---

## Task 2: `codegraph-resolver.mjs` — resolve the CLI

**Files:**
- Create: `server/lib/codegraph-resolver.mjs`
- Test: `server/test/codegraph-resolver.test.mjs`

- [ ] **Step 1: Write the failing test**

```javascript
// server/test/codegraph-resolver.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { resolveCodegraph } from "../lib/codegraph-resolver.mjs";

test("env override wins and is split into argv", () => {
  const argv = resolveCodegraph({ env: { WICKED_CODEGRAPH_BIN: "/opt/cg" } });
  assert.deepEqual(argv, ["/opt/cg"]);
});

test("a .mjs/.js env target is invoked via node", () => {
  const argv = resolveCodegraph({ env: { WICKED_CODEGRAPH_BIN: "/x/cg.mjs" } });
  assert.deepEqual(argv, ["node", "/x/cg.mjs"]);
});

test("set-but-empty env is the kill switch -> null", () => {
  assert.equal(resolveCodegraph({ env: { WICKED_CODEGRAPH_BIN: "" } }), null);
});

test("brain config _meta/codegraph.json bin is honored", () => {
  const brain = mkdtempSync(join(tmpdir(), "cg-cfg-"));
  mkdirSync(join(brain, "_meta"), { recursive: true });
  writeFileSync(join(brain, "_meta", "codegraph.json"), JSON.stringify({ bin: "/cfg/cg" }));
  try {
    const argv = resolveCodegraph({ env: {}, brainPath: brain, which: () => null });
    assert.deepEqual(argv, ["/cfg/cg"]);
  } finally {
    rmSync(brain, { recursive: true, force: true });
  }
});

test("falls back to npx when nothing else resolves", () => {
  const argv = resolveCodegraph({ env: {}, which: (c) => (c === "npx" ? "/usr/bin/npx" : null) });
  assert.deepEqual(argv, ["npx", "-y", "@colbymchenry/codegraph"]);
});

test("no npx and nothing resolves -> null", () => {
  assert.equal(resolveCodegraph({ env: {}, which: () => null }), null);
});
```

- [ ] **Step 2: Run it, verify failure**

Run: `cd /Users/michael.parcewski/Projects/wicked-brain/server && node --test test/codegraph-resolver.test.mjs`
Expected: FAIL — `Cannot find module '../lib/codegraph-resolver.mjs'`.

- [ ] **Step 3: Implement**

```javascript
// server/lib/codegraph-resolver.mjs
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { platform } from "node:os";

const PACKAGE = "@colbymchenry/codegraph";

function argvFor(target) {
  // A .mjs/.js path is a script -> invoke via node; else run directly.
  return /\.(mjs|js)$/.test(target) ? ["node", target] : [target];
}

function whichDefault(command) {
  try {
    const cmd = platform() === "win32" ? "where" : "which";
    const out = execFileSync(cmd, [command], { encoding: "utf-8", timeout: 5000,
      stdio: ["pipe", "pipe", "pipe"] });
    return out.trim().split("\n")[0] || null;
  } catch {
    return null;
  }
}

function configBin(brainPath) {
  if (!brainPath) return null;
  try {
    const cfg = JSON.parse(readFileSync(join(brainPath, "_meta", "codegraph.json"), "utf-8"));
    return typeof cfg.bin === "string" && cfg.bin.trim() ? cfg.bin.trim() : null;
  } catch {
    return null;
  }
}

/**
 * Resolve the argv prefix that invokes codegraph, or null.
 * Ladder: WICKED_CODEGRAPH_BIN (set-but-empty = kill switch) -> brain
 * _meta/codegraph.json {bin} -> PATH -> source node_modules/.bin -> `npx`.
 * @param {{env?:object, brainPath?:string, sourcePath?:string, which?:Function, allowNpx?:boolean}} opts
 */
export function resolveCodegraph(opts = {}) {
  const { env = process.env, brainPath, sourcePath, which = whichDefault,
    allowNpx = true } = opts;

  if (Object.prototype.hasOwnProperty.call(env, "WICKED_CODEGRAPH_BIN")) {
    const v = (env.WICKED_CODEGRAPH_BIN || "").trim();
    return v ? argvFor(v) : null; // empty == kill switch
  }
  const cfg = configBin(brainPath);
  if (cfg) return argvFor(cfg);

  const onPath = which("codegraph");
  if (onPath) return [onPath];

  if (sourcePath) {
    const local = join(sourcePath, "node_modules", ".bin", "codegraph");
    if (existsSync(local)) return [local];
  }
  if (allowNpx && which("npx")) return ["npx", "-y", PACKAGE];
  return null;
}

/** True iff a CONCRETE install resolves (not the npx last resort). */
export function codegraphAvailable(opts = {}) {
  return resolveCodegraph({ ...opts, allowNpx: false }) !== null;
}
```

- [ ] **Step 4: Run, verify pass**

Run: `node --test test/codegraph-resolver.test.mjs`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add server/lib/codegraph-resolver.mjs server/test/codegraph-resolver.test.mjs
git commit -m "feat(codegraph): CLI resolution ladder + kill switch"
```

---

## Task 3: `codegraph-index.mjs` — dbPath, staleness, runIndex

**Files:**
- Create: `server/lib/codegraph-index.mjs`
- Test: `server/test/codegraph-index.test.mjs`

- [ ] **Step 1: Write the failing test**

```javascript
// server/test/codegraph-index.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, utimesSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { dbPath, staleness } from "../lib/codegraph-index.mjs";

test("dbPath points at <source>/.codegraph/codegraph.db", () => {
  assert.equal(dbPath("/repo"), join("/repo", ".codegraph", "codegraph.db"));
});

test("staleness reports not-present when db is missing", () => {
  const s = staleness("/no/such/repo");
  assert.equal(s.present, false);
  assert.equal(s.stale, null);
});

test("staleness reports commits behind HEAD", () => {
  const repo = mkdtempSync(join(tmpdir(), "cg-stale-"));
  try {
    const git = (...a) => execFileSync("git", ["-C", repo, ...a], { stdio: "pipe" });
    git("init"); git("config", "user.email", "t@t"); git("config", "user.name", "t");
    writeFileSync(join(repo, "f.txt"), "1"); git("add", "-A"); git("commit", "-m", "c1");
    // build the db, then backdate it before a second commit
    mkdirSync(join(repo, ".codegraph"), { recursive: true });
    const db = join(repo, ".codegraph", "codegraph.db");
    writeFileSync(db, "x");
    const past = new Date(Date.now() - 60_000);
    utimesSync(db, past, past);
    writeFileSync(join(repo, "g.txt"), "2"); git("add", "-A"); git("commit", "-m", "c2");

    const s = staleness(repo);
    assert.equal(s.present, true);
    assert.equal(s.stale, true);
    assert.ok(s.commits_behind >= 1);
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});
```

- [ ] **Step 2: Run, verify failure**

Run: `node --test test/codegraph-index.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```javascript
// server/lib/codegraph-index.mjs
import { execFileSync, spawn } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { join } from "node:path";
import { resolveCodegraph } from "./codegraph-resolver.mjs";

export function dbPath(sourcePath) {
  return join(sourcePath, ".codegraph", "codegraph.db");
}

/**
 * How far the graph has drifted from HEAD. Fail-open: errors report
 * present-but-unknown, never throw. Port of garden _codegraph.py::staleness.
 * @returns {{present:boolean, stale:boolean|null, commits_behind:number|null, indexed_at:string|null}}
 */
export function staleness(sourcePath) {
  const db = dbPath(sourcePath);
  if (!existsSync(db)) {
    return { present: false, stale: null, commits_behind: null, indexed_at: null };
  }
  try {
    const mtimeMs = statSync(db).mtimeMs;
    const iso = new Date(mtimeMs).toISOString();
    const out = execFileSync("git",
      ["-C", sourcePath, "rev-list", "--count", `--since=${iso}`, "HEAD"],
      { encoding: "utf-8", timeout: 10_000, stdio: ["pipe", "pipe", "pipe"] }).trim();
    const behind = out ? parseInt(out, 10) : 0;
    return { present: true, stale: behind > 0, commits_behind: behind, indexed_at: iso };
  } catch {
    return { present: true, stale: null, commits_behind: null, indexed_at: null };
  }
}

/**
 * Build/refresh the graph by shelling `codegraph index`. Resolves nothing ->
 * returns {ok:false, error}. Never throws.
 * NOTE: the index subcommand/flags are pinned in docs/codegraph-contract.md (Task 1).
 */
export function runIndex(sourcePath, opts = {}) {
  return new Promise((resolve) => {
    const argv = resolveCodegraph({ ...opts, sourcePath });
    if (!argv) { resolve({ ok: false, error: "codegraph not resolvable" }); return; }
    const [cmd, ...prefix] = argv;
    const proc = spawn(cmd, [...prefix, "index", "."], {
      cwd: sourcePath, stdio: ["ignore", "pipe", "pipe"],
    });
    let stderr = "";
    proc.stderr.on("data", (d) => { stderr += d.toString(); });
    proc.on("error", (e) => resolve({ ok: false, error: e.message }));
    proc.on("close", (code) =>
      resolve(code === 0 ? { ok: true } : { ok: false, error: stderr.trim() || `exit ${code}` }));
  });
}
```

- [ ] **Step 4: Run, verify pass**

Run: `node --test test/codegraph-index.test.mjs`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add server/lib/codegraph-index.mjs server/test/codegraph-index.test.mjs
git commit -m "feat(codegraph): dbPath + staleness stamp + index runner"
```

---

## Task 4: `codegraph-client.mjs` — blast-radius / callers / lineage

**Files:**
- Create: `server/lib/codegraph-client.mjs`
- Test: `server/test/codegraph-client.test.mjs`

> The client reads codegraph's DB directly (no query-time subprocess). Schema from Task 1: `nodes(id,kind,name,qualified_name,file_path,language,start_line,end_line,start_column,end_column,updated_at,signature)`, `edges(source,target,kind,metadata,provenance)`. `DEPENDENTS_BY` is set from Task 1, Step 3 (default `"target"` — dependents of X are edge rows WHERE target=X, collecting `source`).

- [ ] **Step 1: Write the failing test (hand-built fixture DB)**

```javascript
// server/test/codegraph-client.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import Database from "better-sqlite3";
import { CodegraphClient } from "../lib/codegraph-client.mjs";

function makeRepo() {
  const repo = mkdtempSync(join(tmpdir(), "cg-client-"));
  mkdirSync(join(repo, ".codegraph"), { recursive: true });
  const db = new Database(join(repo, ".codegraph", "codegraph.db"));
  db.exec(`
    CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, name TEXT, qualified_name TEXT,
      file_path TEXT, language TEXT, start_line INT, end_line INT,
      start_column INT, end_column INT, updated_at INT, signature TEXT);
    CREATE TABLE edges (source TEXT, target TEXT, kind TEXT, metadata TEXT, provenance TEXT);
  `);
  const n = db.prepare(`INSERT INTO nodes
    (id,kind,name,qualified_name,file_path,language,start_line,end_line,start_column,end_column,updated_at,signature)
    VALUES (?,?,?,?,?,?,?,?,0,0,0,?)`);
  n.run("file:a.py", "file", "a.py", "a.py", "a.py", "python", 1, 1, null);
  n.run("file:b.py", "file", "b.py", "b.py", "b.py", "python", 1, 2, null);
  n.run("file:c.py", "file", "c.py", "c.py", "c.py", "python", 1, 2, null);
  // b and c depend on a  (edge source=dependent, target=dependency)
  const e = db.prepare("INSERT INTO edges (source,target,kind,metadata,provenance) VALUES (?,?,?,?,?)");
  e.run("file:b.py", "file:a.py", "imports", null, "static");
  e.run("file:c.py", "file:b.py", "calls", null, "static");
  db.close();
  return repo;
}

test("blastRadius returns transitive dependents of a node", () => {
  const repo = makeRepo();
  try {
    const c = new CodegraphClient(repo);
    const r = c.blastRadius({ node: "file:a.py" });
    const ids = r.dependents.map((d) => d.id).sort();
    assert.deepEqual(ids, ["file:b.py", "file:c.py"]); // c depends on b depends on a
    assert.equal(r.staleness.present, true);
    c.close();
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("callers returns direct dependents only", () => {
  const repo = makeRepo();
  try {
    const c = new CodegraphClient(repo);
    const r = c.callers({ node: "file:a.py" });
    assert.deepEqual(r.callers.map((d) => d.id), ["file:b.py"]);
    c.close();
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("lineage returns transitive dependencies (downstream)", () => {
  const repo = makeRepo();
  try {
    const c = new CodegraphClient(repo);
    const r = c.lineage({ node: "file:c.py" });
    const ids = r.dependencies.map((d) => d.id).sort();
    assert.deepEqual(ids, ["file:a.py", "file:b.py"]);
    c.close();
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("missing db -> engine unavailable, not an empty graph", () => {
  const repo = mkdtempSync(join(tmpdir(), "cg-empty-"));
  try {
    const c = new CodegraphClient(repo);
    const r = c.blastRadius({ node: "file:a.py" });
    assert.equal(r.engine, "unavailable");
    c.close();
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});
```

- [ ] **Step 2: Run, verify failure**

Run: `node --test test/codegraph-client.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```javascript
// server/lib/codegraph-client.mjs
import { existsSync } from "node:fs";
import Database from "better-sqlite3";
import { dbPath, staleness } from "./codegraph-index.mjs";

// Set from Task 1, Step 3. "target": dependents-of-X are edges WHERE target=X
// (collect `source`); dependencies-of-X are edges WHERE source=X (collect `target`).
const DEPENDENTS_BY = "target";
const DEPENDENCIES_BY = DEPENDENTS_BY === "target" ? "source" : "target";

export class CodegraphClient {
  #sourcePath;
  #db = null;

  constructor(sourcePath) { this.#sourcePath = sourcePath; }

  #open() {
    if (this.#db) return this.#db;
    const p = dbPath(this.#sourcePath);
    if (!existsSync(p)) return null;
    this.#db = new Database(p, { readonly: true });
    return this.#db;
  }

  close() { if (this.#db) { this.#db.close(); this.#db = null; } }

  #nodeRows(ids) {
    if (ids.length === 0) return [];
    const db = this.#db;
    const ph = ids.map(() => "?").join(",");
    return db.prepare(
      `SELECT id, kind, name, file_path, start_line, end_line FROM nodes WHERE id IN (${ph})`
    ).all(...ids);
  }

  // Generic BFS over edges. fromCol = the column we match the frontier on;
  // toCol = the column we collect as the next frontier.
  #walk(start, { fromCol, toCol, maxDepth }) {
    const db = this.#db;
    const stmt = db.prepare(`SELECT DISTINCT ${toCol} AS next FROM edges WHERE ${fromCol} = ?`);
    const seen = new Set();
    let frontier = [start];
    let depth = 0;
    while (frontier.length && depth < maxDepth) {
      const nextFrontier = [];
      for (const node of frontier) {
        for (const row of stmt.all(node)) {
          if (row.next && row.next !== start && !seen.has(row.next)) {
            seen.add(row.next);
            nextFrontier.push(row.next);
          }
        }
      }
      frontier = nextFrontier;
      depth += 1;
    }
    return [...seen];
  }

  #unavailable() {
    return { engine: "unavailable", reason: `no graph at ${dbPath(this.#sourcePath)} — run graph-index`,
      staleness: staleness(this.#sourcePath) };
  }

  /** Transitive dependents of a node — "what breaks if I change X". */
  blastRadius({ node, maxDepth = 25 }) {
    if (!this.#open()) return this.#unavailable();
    const ids = this.#walk(node, { fromCol: DEPENDENTS_BY,
      toCol: DEPENDENTS_BY === "target" ? "source" : "target", maxDepth });
    return { node, dependents: this.#nodeRows(ids), staleness: staleness(this.#sourcePath) };
  }

  /** Direct dependents only (depth 1). */
  callers({ node }) {
    if (!this.#open()) return this.#unavailable();
    const ids = this.#walk(node, { fromCol: DEPENDENTS_BY,
      toCol: DEPENDENTS_BY === "target" ? "source" : "target", maxDepth: 1 });
    return { node, callers: this.#nodeRows(ids), staleness: staleness(this.#sourcePath) };
  }

  /** Transitive dependencies of a node — downstream lineage. */
  lineage({ node, maxDepth = 25 }) {
    if (!this.#open()) return this.#unavailable();
    const ids = this.#walk(node, { fromCol: DEPENDENCIES_BY,
      toCol: DEPENDENCIES_BY === "target" ? "source" : "target", maxDepth });
    return { node, dependencies: this.#nodeRows(ids), staleness: staleness(this.#sourcePath) };
  }
}
```

> Note for the implementer: `#walk`'s `toCol` is derived inline so dependents collect the opposite column from the one matched. If Task 1 flips `DEPENDENTS_BY` to `"source"`, the derivations follow automatically — no other change needed.

- [ ] **Step 4: Run, verify pass**

Run: `node --test test/codegraph-client.test.mjs`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add server/lib/codegraph-client.mjs server/test/codegraph-client.test.mjs
git commit -m "feat(codegraph): graph client — blast-radius/callers/lineage over edges"
```

---

## Task 5: Wire the `graph-*` server actions

**Files:**
- Modify: `server/bin/wicked-brain-server.mjs` (the `actions` object ~L135–306; `WRITE_ACTIONS` set ~L311–321)
- Test: `server/test/codegraph-actions.test.mjs` (Create)

> The server constructs collaborators once at startup (`db`, `lsp`) from `brainPath`/`sourcePath`. Add a codegraph client + index runner the same way and register four actions. `graph-index` mutates → add to `WRITE_ACTIONS`.

- [ ] **Step 1: Write the failing test (handlers are pure functions of params)**

```javascript
// server/test/codegraph-actions.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import Database from "better-sqlite3";
import { makeGraphActions } from "../lib/codegraph-actions.mjs";

function repoWithGraph() {
  const repo = mkdtempSync(join(tmpdir(), "cg-act-"));
  mkdirSync(join(repo, ".codegraph"), { recursive: true });
  const db = new Database(join(repo, ".codegraph", "codegraph.db"));
  db.exec(`CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, name TEXT, qualified_name TEXT,
    file_path TEXT, language TEXT, start_line INT, end_line INT, start_column INT,
    end_column INT, updated_at INT, signature TEXT);
    CREATE TABLE edges (source TEXT, target TEXT, kind TEXT, metadata TEXT, provenance TEXT);`);
  db.prepare(`INSERT INTO nodes (id,kind,name,qualified_name,file_path,language,start_line,end_line,start_column,end_column,updated_at,signature)
    VALUES (?,?,?,?,?,?,1,1,0,0,0,NULL)`).run("file:a.py","file","a.py","a.py","a.py","python");
  db.prepare(`INSERT INTO nodes (id,kind,name,qualified_name,file_path,language,start_line,end_line,start_column,end_column,updated_at,signature)
    VALUES (?,?,?,?,?,?,1,1,0,0,0,NULL)`).run("file:b.py","file","b.py","b.py","b.py","python");
  db.prepare("INSERT INTO edges (source,target,kind,metadata,provenance) VALUES (?,?,?,?,?)")
    .run("file:b.py","file:a.py","imports",null,"static");
  db.close();
  return repo;
}

test("graph-blast-radius action returns dependents", () => {
  const repo = repoWithGraph();
  try {
    const actions = makeGraphActions({ sourcePath: repo });
    const r = actions["graph-blast-radius"]({ node: "file:a.py" });
    assert.deepEqual(r.dependents.map((d) => d.id), ["file:b.py"]);
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("graph-blast-radius on a graphless repo reports unavailable", () => {
  const repo = mkdtempSync(join(tmpdir(), "cg-none-"));
  try {
    const actions = makeGraphActions({ sourcePath: repo });
    assert.equal(actions["graph-blast-radius"]({ node: "x" }).engine, "unavailable");
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});
```

- [ ] **Step 2: Run, verify failure**

Run: `node --test test/codegraph-actions.test.mjs`
Expected: FAIL — `Cannot find module '../lib/codegraph-actions.mjs'`.

- [ ] **Step 3: Implement the action factory**

```javascript
// server/lib/codegraph-actions.mjs
import { CodegraphClient } from "./codegraph-client.mjs";
import { runIndex, staleness } from "./codegraph-index.mjs";

/**
 * Build the graph-* action handlers bound to a source repo. A fresh client per
 * call keeps the readonly DB handle short-lived and always reopens after a rebuild.
 */
export function makeGraphActions({ sourcePath, brainPath } = {}) {
  const withClient = (fn) => {
    const c = new CodegraphClient(sourcePath);
    try { return fn(c); } finally { c.close(); }
  };
  return {
    "graph-blast-radius": (p = {}) => withClient((c) => c.blastRadius({ node: p.node, maxDepth: p.maxDepth })),
    "graph-callers": (p = {}) => withClient((c) => c.callers({ node: p.node })),
    "graph-lineage": (p = {}) => withClient((c) => c.lineage({ node: p.node, maxDepth: p.maxDepth })),
    "graph-index": async () => {
      const r = await runIndex(sourcePath, { brainPath, sourcePath });
      return { ...r, staleness: staleness(sourcePath) };
    },
  };
}
```

- [ ] **Step 4: Run, verify pass**

Run: `node --test test/codegraph-actions.test.mjs`
Expected: PASS (2 tests).

- [ ] **Step 5: Register actions in the server**

In `server/bin/wicked-brain-server.mjs`, near where `lsp`/`db` are constructed, add:

```javascript
import { makeGraphActions } from "../lib/codegraph-actions.mjs";
// ... after sourcePath/brainPath are known:
const graphActions = makeGraphActions({ sourcePath, brainPath });
```

Then spread the handlers into the `actions` object (alongside the `lsp-*` block ~L238–248):

```javascript
  ...graphActions,   // graph-index, graph-blast-radius, graph-callers, graph-lineage
```

And add the mutating one to the `WRITE_ACTIONS` set (~L311–321):

```javascript
const WRITE_ACTIONS = new Set([
  /* ...existing... */
  "graph-index",
]);
```

- [ ] **Step 6: Smoke the live server action**

```bash
cd /Users/michael.parcewski/Projects/wicked-brain/server
# in repo /tmp/cg-spike from Task 1, with .codegraph already built:
node bin/wicked-brain-server.mjs --brain /tmp/cg-spike-brain --port 4399 --source /tmp/cg-spike &
SRV=$!; sleep 1
curl -s -XPOST localhost:4399/api -H 'content-type: application/json' \
  -d '{"action":"graph-blast-radius","params":{"node":"file:a.py"}}'
kill $SRV
```
Expected: JSON with a `dependents` array containing `file:b.py` and a `staleness` object.

- [ ] **Step 7: Commit**

```bash
git add server/lib/codegraph-actions.mjs server/test/codegraph-actions.test.mjs server/bin/wicked-brain-server.mjs
git commit -m "feat(codegraph): register graph-* server actions"
```

---

## Task 6: `wicked-brain:graph` skill + trim the LSP skill

**Files:**
- Create: `skills/wicked-brain-graph/SKILL.md`
- Modify: `skills/wicked-brain-lsp/SKILL.md` (frontmatter description only)

- [ ] **Step 1: Create the graph skill**

```markdown
---
name: wicked-brain:graph
description: |
  Code-relationship graph queries — blast radius, callers, and lineage — backed
  by a codegraph static graph the brain owns. Answers "what breaks if I change X",
  "who calls X", and "what does X depend on" across the whole repo, including
  relationships a grep or single-file LSP lookup cannot see.

  Use when: "blast radius", "what breaks if I change", "impact of changing X",
  "who calls X", "what depends on X", "lineage", "what does X depend on",
  "architecture map", "code relationship graph".
---

# wicked-brain:graph

Relationship-graph intelligence over a codegraph-built SQLite graph. Distinct from
`wicked-brain:lsp` (live, single-symbol def/ref/hover/diagnostics) — this is the
whole-repo relationship graph and the home of blast-radius / lineage.

## Queries (via `npx wicked-brain-call`)

- `graph-index` — build/refresh the graph (`codegraph index .`). Run once per repo,
  then on demand when results report they are stale.
- `graph-blast-radius {node}` — transitive dependents of `node` ("what breaks if I change it").
- `graph-callers {node}` — direct dependents only.
- `graph-lineage {node}` — transitive dependencies (downstream).

`node` ids follow codegraph's convention (e.g. `file:src/app.py`, or a symbol id).
Every result carries a `staleness` stamp (`commits_behind`, `indexed_at`); if
`stale` is true, re-run `graph-index`.

## Freshness

Lazy by design — the graph is never auto-rebuilt by a file watcher. Results tell you
when they are behind HEAD; rebuild with `graph-index` (or wire the optional commit hook).
```

- [ ] **Step 2: Trim the LSP skill description**

In `skills/wicked-brain-lsp/SKILL.md` frontmatter, remove the `"blast radius"` and `"architecture map"` trigger phrases from the `Use when:` line (they were never implemented in LSP and now live in `wicked-brain:graph`). Add a one-line pointer in the body:

```markdown
> For blast-radius / lineage / architecture (whole-repo relationships), use `wicked-brain:graph`.
```

- [ ] **Step 3: Verify install picks up the new skill**

```bash
cd /Users/michael.parcewski/Projects/wicked-brain
node install.mjs 2>&1 | grep -i "skills installed"
ls ~/.claude/skills/wicked-brain-graph/SKILL.md
```
Expected: install reports the skill count incremented by one; the file exists.

- [ ] **Step 4: Commit**

```bash
git add skills/wicked-brain-graph/SKILL.md skills/wicked-brain-lsp/SKILL.md
git commit -m "feat(codegraph): wicked-brain:graph skill; move blast-radius off lsp skill"
```

---

## Task 7: End-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Full suite green**

Run: `cd /Users/michael.parcewski/Projects/wicked-brain/server && npm test`
Expected: all tests pass, including the four new files.

- [ ] **Step 2: Real-repo blast-radius**

```bash
# Point at a real repo (e.g. wicked-brain itself), build, query.
cd /Users/michael.parcewski/Projects/wicked-brain
npx -y @colbymchenry/codegraph index .
node server/bin/wicked-brain-server.mjs --brain ~/.wicked-brain/projects/cg-e2e --port 4398 --source "$PWD" &
SRV=$!; sleep 1
curl -s -XPOST localhost:4398/api -H 'content-type: application/json' \
  -d '{"action":"graph-callers","params":{"node":"file:server/lib/sqlite-search.mjs"}}' | head -c 400
kill $SRV
```
Expected: a `callers` array (non-empty if anything imports that module) + a `staleness` stamp with `stale:false` right after indexing.

- [ ] **Step 3: Commit (if any doc tweaks)**

```bash
git add -A && git commit -m "test(codegraph): phase-1a e2e verification notes" || echo "nothing to commit"
```

---

## Self-review (done at write time)

- **Spec coverage:** D1 (brain owns queries) → Tasks 4–6. D2 (zero garden dep) → all code is brain-native `.mjs`, imports nothing from garden. D4 (codegraph=graph of record, LSP=live) → Task 6 moves blast-radius off LSP. D5 (lazy staleness, no watcher) → Task 3 staleness + Task 5 `graph-index` on demand, watcher untouched. D6 (DB stays codegraph-native) → `dbPath` = `<source>/.codegraph/codegraph.db`, opened readonly. D3 (extractor registry) + injected edges are **Phase 1b** — explicitly out of this plan.
- **Placeholder scan:** none — every step has runnable code/commands. The one empirical unknown (edge direction) is isolated to Task 1 + the `DEPENDENTS_BY` constant.
- **Type consistency:** `resolveCodegraph`, `dbPath`, `staleness`, `runIndex`, `CodegraphClient.{blastRadius,callers,lineage,close}`, `makeGraphActions` names are consistent across tasks and tests. Result shapes (`{dependents|callers|dependencies, staleness}` / `{engine:"unavailable"}`) match between client, actions, and their tests.
- **Scope:** single shippable subsystem (graph-core); injected edges and garden-side work deferred to named follow-on plans.

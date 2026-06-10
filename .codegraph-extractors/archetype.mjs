// archetype.mjs — wicked-garden's PROPRIETARY injected-edge extractor, discovered
// and run by wicked-brain's codegraph extractor registry (drop-in mechanism, ADR
// 0004 / spec D3). It materializes archetype → playbook edges that no grep or
// static call-graph can see: an archetype is wired to its playbook by a *naming
// convention* (.claude-plugin/archetypes.json key ↔ skills/archetype/refs/<name>.md),
// never by a symbol reference.
//
// Contract (brain's runExtractors): `export function extract({ db, sourcePath, nodes })`
//   - db        : an open read-write better-sqlite3 Database for <repo>/.codegraph/codegraph.db
//   - sourcePath: the repo root
//   - nodes     : { ensureFileNode(db, relpath, lang?), ensureVirtualNode(db, id, kind, name) }
//     (passed BY brain so this file imports NOTHING from brain or garden — the
//      dependency arrow only ever points garden→brain.)
// Returns a counts object with `edges_added`. Idempotent. Fail-open on a missing
// catalog (returns zero) — brain works fine on repos without archetypes.
//
// Direction: an archetype DEPENDS ON its playbook (change refs/<name>.md → the
// archetype's behavior changes). With brain's DEPENDENTS_BY="target", the edge is
// source=archetype, target=playbook, so blast-radius(playbook) surfaces the archetype.

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const PROVENANCE = "injected:archetype";
const NODE_KIND = "archetype";

export function extract({ db, sourcePath, nodes }) {
  // idempotent: clear this extractor's own edges + the synthetic nodes it owns
  db.prepare("DELETE FROM edges WHERE provenance = ?").run(PROVENANCE);
  db.prepare("DELETE FROM nodes WHERE kind = ?").run(NODE_KIND);

  const catalogPath = join(sourcePath, ".claude-plugin", "archetypes.json");
  if (!existsSync(catalogPath)) {
    return { edges_added: 0, archetypes: 0, skipped: 0 };
  }
  let catalog;
  try {
    catalog = JSON.parse(readFileSync(catalogPath, "utf-8"));
  } catch {
    return { edges_added: 0, archetypes: 0, skipped: 0 };
  }
  const archetypes = catalog && catalog.archetypes;
  if (!archetypes || typeof archetypes !== "object") {
    return { edges_added: 0, archetypes: 0, skipped: 0 };
  }

  const insert = db.prepare(
    "INSERT INTO edges (source, target, kind, metadata, provenance) VALUES (?,?,?,?,?)"
  );
  let added = 0;
  let skipped = 0;
  let count = 0;
  for (const name of Object.keys(archetypes)) {
    const playbookRel = `skills/archetype/refs/${name}.md`;
    if (!existsSync(join(sourcePath, playbookRel))) {
      skipped += 1; // archetype declared with no playbook on disk — flag, don't fabricate
      continue;
    }
    const src = nodes.ensureVirtualNode(db, `archetype:${name}`, NODE_KIND, name);
    const tgt = nodes.ensureFileNode(db, playbookRel);
    insert.run(src, tgt, "references",
      JSON.stringify({ injected: "archetype", archetype: name }), PROVENANCE);
    added += 1;
    count += 1;
  }
  return { edges_added: added, archetypes: count, skipped };
}

#!/usr/bin/env python3
"""Build ONE data-shape proposal for estate's review queue (DES-KNOWLEDGE-DATA-001 §10.1), checked before it is sent.

A data shape is a recommendation, like a memory or a policy: it lands in the one review queue as an INERT
`knowledge` proposal and becomes knowledge only when a person approves it (studio: Understand -> Knowledge map).
This script turns a small spec into the exact estate call, refusing what estate would accept at submit and refuse
at approve (an Approve the person clicks and that fails), and what looks like a value:

  {"sourceId": "<registry id>", "source": "<name>", "relation": "schema.table",
   "summary": "what the table is, in words; structure only, never a value",
   "joins":       [{"to": "schema.other", "columns": ["a_id"], "references": ["id"], "basis": "fk|name_type|judgment"}],
   "describes":   [{"code_id": "<symbol id from SearchEntity>", "repo": "<repo id>", "name": "Ticket"}],
   "governed_by": [{"code_id": "<rule node id>", "repo": "<repo id>", "label": "the rule in a few words"}],
   "measures":    [{"code_id": "<metric node id>", "repo": "<repo id>", "label": "what it measures"}]}

usage: shape_proposal.py <spec.json | -> --catalog <catalog.json>
  catalog.json: what `knowledge.source_catalog` answered for the source (one page object, or a list of every page).
  Prints the estate call `{"tool": "proposal.submit", "arguments": {...}}`, ready for
  `wicked-garden run scripts/_estate_client.py call -` on stdin. Exit 2 with the reason on a bad spec.

The proposer never declares deps: estate derives them from the endpoints at approve (the source of every catalog
document, the repo of every code endpoint) and refuses a declared set that differs.
"""
import json
import re
import sys

TOP_FIELDS = {"sourceId", "source", "relation", "summary", "joins", "describes", "governed_by", "measures"}
JOIN_FIELDS = {"to", "columns", "references", "basis"}
CODE_FIELDS = {"code_id", "repo", "name", "label"}
REL_CODE = ("describes", "governed_by", "measures")
BASES = ("fk", "name_type", "judgment")
# Estate's bounds (wicked-estate-knowledge: shape.rs, source.rs, plane.rs).
MAX_LINKS = 200
MAX_EVIDENCE_BYTES = 1024
MAX_ID_BYTES = 4096
MAX_KEY_BYTES = 512
MAX_REPO_BYTES = 128
MAX_SUMMARY_BYTES = 2000
SOURCE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
# What a value read from a row looks like in prose: a quoted literal (an apostrophe inside a word is not a quote),
# an email, a URL, a date, or a number of four or more digits. A backstop only: the control is that this pass reads
# no rows at all (refs/shapes.md).
VALUE_LIKE = re.compile(
    r"(?<![A-Za-z0-9])'[^']+'(?![A-Za-z0-9])"
    r"|\"[^\"]+\""
    r"|[\w.+-]+@[\w-]+\.[\w.-]+"
    r"|\bhttps?://"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{4,}\b"
)


class SpecError(ValueError):
    pass


def encode_key(key):
    """Estate's id segment encoding (source.rs encode_key): every UTF-8 byte outside [A-Za-z0-9._-] as %XX."""
    out = []
    for b in key.encode("utf-8"):
        c = chr(b)
        out.append(c if (c.isascii() and (c.isalnum() or c in "._-")) else "%%%02X" % b)
    return "".join(out)


def catalog_doc_id(source_id, key):
    """The knowledge node id of a source's catalog document (estate doc_symbol)."""
    return "kdoc synthetic source:%s/%s:" % (source_id, encode_key(key))


def _closed(obj, allowed, at):
    if not isinstance(obj, dict):
        raise SpecError("%s must be an object" % at)
    extra = sorted(set(obj) - allowed)
    if extra:
        raise SpecError("%s has unknown field(s) %s (allowed: %s)" % (at, ", ".join(extra), ", ".join(sorted(allowed))))


def _text(obj, field, at, max_bytes, required=True):
    v = obj.get(field)
    if v is None and not required:
        return None
    if not isinstance(v, str) or not v.strip() or len(v.encode("utf-8")) > max_bytes or any(ord(ch) < 32 or ord(ch) == 127 for ch in v):
        raise SpecError("%s.%s must be a non-empty one-line string of at most %d bytes" % (at, field, max_bytes))
    return v


def _names(obj, field, at):
    v = obj.get(field, [])
    if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() and len(x.encode("utf-8")) <= 256 for x in v):
        raise SpecError("%s.%s must be a list of column names" % (at, field))
    return v


def _size(v):
    return len(json.dumps(v, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def catalog_keys(catalog, source_id):
    """The relation keys of the source's catalog, from what knowledge.source_catalog answered (pages must agree)."""
    pages = catalog if isinstance(catalog, list) else [catalog]
    keys, generations = set(), set()
    for p in pages:
        if not isinstance(p, dict) or p.get("sourceId") != source_id:
            raise SpecError("the catalog is not source %s's (pass what knowledge.source_catalog answered for it)" % source_id)
        generations.add(p.get("generation"))
        for d in p.get("docs") or []:
            if isinstance(d, dict) and isinstance(d.get("key"), str):
                keys.add(d["key"])
    if len(generations) > 1:
        raise SpecError("the catalog pages are from different generations: read every page again from page 0")
    return keys


def build(spec, catalog):
    _closed(spec, TOP_FIELDS, "spec")
    sid = _text(spec, "sourceId", "spec", 128)
    if not SOURCE_ID.match(sid):
        raise SpecError("spec.sourceId is the source's registry id ([A-Za-z0-9._-], at most 128)")
    keys = catalog_keys(catalog, sid)
    source = _text(spec, "source", "spec", 256)
    relation = _text(spec, "relation", "spec", MAX_KEY_BYTES)
    if relation not in keys:
        raise SpecError("spec.relation %r is not a table of the source's catalog" % relation)
    summary = _text(spec, "summary", "spec", MAX_SUMMARY_BYTES)
    self_doc = catalog_doc_id(sid, relation)
    relate = [{"rel": "derived_from", "to": self_doc, "confidence": 1}]
    relate_code = []
    words = []
    # Joins: one edge per related table (estate keeps one typed edge per rel and endpoints), every condition in its
    # evidence; a self-join is said in words only (estate refuses an edge that loops).
    by_target = {}
    for i, j in enumerate(spec.get("joins") or []):
        at = "spec.joins[%d]" % i
        _closed(j, JOIN_FIELDS, at)
        to = _text(j, "to", at, MAX_KEY_BYTES)
        if to not in keys:
            raise SpecError("%s.to %r is not a table of the source's catalog" % (at, to))
        basis = j.get("basis", "judgment")
        if basis not in BASES:
            raise SpecError("%s.basis is one of %s" % (at, "|".join(BASES)))
        cols, refs = _names(j, "columns", at), _names(j, "references", at)
        if len(cols) != len(refs):
            raise SpecError("%s.columns and .references pair up: they must be the same length" % at)
        on = " on %s = %s.%s" % (", ".join(cols), to, ", ".join(refs)) if cols else ""
        if to == relation:
            words.append("It joins itself%s." % (" on %s = %s" % (", ".join(cols), ", ".join(refs)) if cols else ""))
            continue
        words.append("It joins %s%s." % (to, on))
        by_target.setdefault(to, []).append({"columns": cols, "references": refs, "basis": basis})
    for to, conds in by_target.items():
        best = "fk" if any(c["basis"] == "fk" for c in conds) else "name_type" if any(c["basis"] == "name_type" for c in conds) else "judgment"
        evidence = {"basis": best, "on": conds}
        if _size(evidence) > MAX_EVIDENCE_BYTES:
            raise SpecError("the joins to %s do not fit estate's %d-byte evidence bound: propose fewer conditions" % (to, MAX_EVIDENCE_BYTES))
        relate.append({"rel": "joins", "from": self_doc, "to": catalog_doc_id(sid, to),
                       "confidence": {"fk": 0.95, "name_type": 0.75}.get(best, 0.6), "evidence": evidence})
    repos = set()
    for rel in REL_CODE:
        for i, c in enumerate(spec.get(rel) or []):
            at = "spec.%s[%d]" % (rel, i)
            _closed(c, CODE_FIELDS, at)
            code_id = _text(c, "code_id", at, MAX_ID_BYTES)
            repo = _text(c, "repo", at, MAX_REPO_BYTES)
            if not all(33 <= b <= 126 and b != ord(",") for b in repo.encode("utf-8")):
                raise SpecError("%s.repo is the repo's id (printable ASCII, no comma or space)" % at)
            repos.add(repo)
            label = _text(c, "label", at, 200, required=False) or _text(c, "name", at, 200, required=False) or code_id.rstrip(":#.").split("/")[-1]
            evidence = {"basis": "judgment", "label": label}
            if _size(evidence) > MAX_EVIDENCE_BYTES:
                raise SpecError("%s does not fit estate's evidence bound" % at)
            relate_code.append({"rel": rel, "from": self_doc, "code_id": code_id, "repo": repo, "confidence": 0.7, "evidence": evidence})
            words.append("%s %s in %s." % ({"describes": "Code that describes it:", "governed_by": "Governed by", "measures": "Measured by"}[rel], label, repo))
    # A shape filed from a governed run may link only that run's repo (crew binds the proposal to it).
    if len(repos) > 1:
        raise SpecError("a shape links code in ONE repo (yours); propose a shape per repo: %s" % ", ".join(sorted(repos)))
    if len(relate) + len(relate_code) > MAX_LINKS:
        raise SpecError("at most %d links per shape" % MAX_LINKS)
    content = ("%s in data source %s: %s %s" % (relation, source, summary.strip(), " ".join(words))).strip()
    hit = VALUE_LIKE.search(content)
    if hit:
        raise SpecError("the shape looks like it holds a value (%r): a shape says what a table IS, never what is in it" % hit.group(0)[:40])
    return {
        "tool": "proposal.submit",
        "arguments": {
            "kind_type": "knowledge",
            "payload": {
                "content": content,
                "source": "garden:data-shapes/%s/%s" % (source, relation),
                "class": "concept",
                "scope": "source:%s" % sid,
                "capture": "shapes",
                "relate": relate,
                "relate_code": relate_code,
            },
        },
    }


def main(argv):
    args = argv[1:]
    if len(args) != 3 or args[1] != "--catalog":
        sys.stderr.write(__doc__)
        return 2
    try:
        raw = sys.stdin.read() if args[0] == "-" else open(args[0], encoding="utf-8").read()
        with open(args[2], encoding="utf-8") as f:
            catalog = json.load(f)
        sys.stdout.write(json.dumps(build(json.loads(raw), catalog), ensure_ascii=False) + "\n")
        return 0
    except (SpecError, json.JSONDecodeError, OSError) as e:
        sys.stderr.write("shape_proposal: %s\n" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

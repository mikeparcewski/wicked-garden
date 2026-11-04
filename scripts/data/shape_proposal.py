#!/usr/bin/env python3
"""Build ONE data-shape proposal for estate's review queue (DES-KNOWLEDGE-DATA-001 §10.1), checked before it is sent.

A data shape is a recommendation, like a memory or a policy: it lands in the one review queue as an INERT
`knowledge` proposal and becomes knowledge only when a person approves it (studio: Understand -> Knowledge map).
This script turns a small spec into the exact `proposal.submit` arguments, refusing what estate would refuse later
(and what would leak a value):

  {"sourceId": "<registry id>", "source": "<name>", "relation": "schema.table",
   "summary": "what the table is, in words; structure only, never a value",
   "joins":       [{"to": "schema.other", "columns": ["a_id"], "references": ["id"], "basis": "fk|name_type|judgment"}],
   "describes":   [{"code_id": "<symbol id from SearchEntity>", "repo": "<repo id>", "name": "Ticket"}],
   "governed_by": [{"code_id": "<rule node id>", "repo": "<repo id>", "label": "the rule in a few words"}]}

usage: shape_proposal.py <spec.json | ->   (prints the JSON for `proposal.submit`; exit 2 with the reason on a bad spec)

The proposer never declares deps: estate derives them from the endpoints at approve (the source of every catalog
document, the repo of every code endpoint) and refuses a declared set that differs.
"""
import json
import re
import sys

REL_CODE = ("describes", "governed_by", "measures")
BASES = ("fk", "name_type", "judgment")
MAX_SUMMARY = 2000
MAX_LINKS = 50
MAX_EVIDENCE = 1024
SOURCE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
REPO_ID = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
# A quoted literal or a long digit run in a summary is most likely a value read from a row: refused.
VALUE_LIKE = re.compile(r"'[^']*'|\"[^\"]*\"|\b\d{5,}\b")


class SpecError(ValueError):
    pass


def encode_key(key):
    """Estate's id segment encoding (source.rs encode_key): every byte outside [A-Za-z0-9._-] as %XX."""
    out = []
    for b in key.encode("utf-8"):
        c = chr(b)
        out.append(c if (c.isascii() and (c.isalnum() or c in "._-")) else "%%%02X" % b)
    return "".join(out)


def catalog_doc_id(source_id, key):
    """The knowledge node id of a source's catalog document (estate doc_symbol)."""
    return "kdoc synthetic source:%s/%s:" % (source_id, encode_key(key))


def _str(spec, field, at, limit=256):
    v = spec.get(field)
    if not isinstance(v, str) or not v.strip() or len(v) > limit or any(ord(ch) < 32 for ch in v):
        raise SpecError("%s.%s must be a non-empty one-line string of at most %d characters" % (at, field, limit))
    return v


def _evidence(ev):
    text = json.dumps(ev, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_EVIDENCE:
        raise SpecError("a link's evidence is at most %d bytes" % MAX_EVIDENCE)
    return ev


def build(spec):
    if not isinstance(spec, dict):
        raise SpecError("the spec is a JSON object")
    if "deps" in spec:
        raise SpecError("never declare deps: estate derives them from the endpoints at approve")
    sid = _str(spec, "sourceId", "spec", 128)
    if not SOURCE_ID.match(sid):
        raise SpecError("spec.sourceId is the source's registry id ([A-Za-z0-9._-], at most 128)")
    source = _str(spec, "source", "spec")
    relation = _str(spec, "relation", "spec")
    summary = _str(spec, "summary", "spec", MAX_SUMMARY)
    if VALUE_LIKE.search(summary):
        raise SpecError("spec.summary looks like it holds a value (a quoted literal or a long number): a shape says what a table IS, never what is in it")
    self_doc = catalog_doc_id(sid, relation)
    relate = [{"rel": "derived_from", "to": self_doc, "confidence": 1}]
    relate_code = []
    links_text = []
    for i, j in enumerate(spec.get("joins") or []):
        at = "spec.joins[%d]" % i
        if not isinstance(j, dict):
            raise SpecError("%s is an object" % at)
        to = _str(j, "to", at)
        basis = j.get("basis", "judgment")
        if basis not in BASES:
            raise SpecError("%s.basis is one of %s" % (at, "|".join(BASES)))
        cols = j.get("columns") or []
        refs = j.get("references") or []
        if not all(isinstance(c, str) and c for c in cols + refs):
            raise SpecError("%s.columns and .references are column names" % at)
        relate.append({
            "rel": "joins", "from": self_doc, "to": catalog_doc_id(sid, to),
            "confidence": 0.95 if basis == "fk" else 0.75 if basis == "name_type" else 0.6,
            "evidence": _evidence({"basis": basis, "columns": cols, "references": refs}),
        })
        links_text.append("It joins %s%s." % (to, " on %s = %s.%s" % (", ".join(cols), to, ", ".join(refs)) if cols and refs else ""))
    for rel in REL_CODE:
        for i, c in enumerate(spec.get(rel) or []):
            at = "spec.%s[%d]" % (rel, i)
            if not isinstance(c, dict):
                raise SpecError("%s is an object" % at)
            code_id = _str(c, "code_id", at, 4096)
            repo = _str(c, "repo", at, 128)
            if not REPO_ID.match(repo):
                raise SpecError("%s.repo is the repo's id" % at)
            label = c.get("label") or c.get("name") or code_id.rstrip(":#.").split("/")[-1]
            if not isinstance(label, str) or len(label) > 200:
                raise SpecError("%s.label is at most 200 characters" % at)
            relate_code.append({
                "rel": rel, "from": self_doc, "code_id": code_id, "repo": repo, "confidence": 0.7,
                "evidence": _evidence({"basis": "judgment", "label": label}),
            })
            links_text.append("%s %s (%s)." % ({"describes": "Code that describes it:", "governed_by": "Governed by", "measures": "Measured by"}[rel], label, repo))
    if len(relate) + len(relate_code) > MAX_LINKS:
        raise SpecError("at most %d links per shape" % MAX_LINKS)
    content = "%s in data source %s: %s %s" % (relation, source, summary.strip(), " ".join(links_text))
    return {
        "kind_type": "knowledge",
        "payload": {
            "content": content.strip(),
            "source": "garden:data-shapes/%s/%s" % (source, relation),
            "class": "concept",
            "scope": "source:%s" % sid,
            "capture": "shapes",
            "relate": relate,
            "relate_code": relate_code,
        },
    }


def main(argv):
    if len(argv) != 2:
        sys.stderr.write(__doc__)
        return 2
    try:
        raw = sys.stdin.read() if argv[1] == "-" else open(argv[1], encoding="utf-8").read()
        sys.stdout.write(json.dumps(build(json.loads(raw)), indent=1) + "\n")
        return 0
    except (SpecError, json.JSONDecodeError, OSError) as e:
        sys.stderr.write("shape_proposal: %s\n" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

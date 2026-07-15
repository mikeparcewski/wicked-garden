#!/usr/bin/env python3
"""validate_domain_model — validate a document against the vendored schema.

Two layers, **stdlib-only** (this repo is stdlib-only; only pytest is installed
in CI, and it hand-rolls its schema validators — see ``scripts/qe/verdict_schema.py``.
A third-party ``jsonschema`` dependency would make CI red, so the schema layer is
a focused draft-07 *subset* validator that covers exactly the keywords the
vendored ``domain-model.schema.json`` uses):

1. **Schema layer** — a self-contained draft-07 subset validator run against the
   vendored ``skills/domain/vendor/domain-model.schema.json`` (@wicked/domain-
   model-schema@1.0.0). It resolves local ``$ref`` pointers against ``$defs`` and
   supports: ``type`` (object/array/string/integer/number), ``required``,
   ``properties``, ``additionalProperties`` (``false`` or a sub-schema), ``items``,
   ``enum``, ``const``, ``pattern``, ``minItems``, ``minLength``,
   ``minimum``/``maximum``, and the ``if``/``then`` conditional. This covers the
   hard invariants the schema expresses: required fields, business_rules minItems
   1, numeric confidence in [0,1], provenance shape, the disposition-drop ->
   disposition_reason if/then, and the id patterns.

2. **Extra-invariant layer** — the invariants JSON Schema draft-07 cannot express:
   id uniqueness WITHIN a requirement, the validation.error_ref -> ErrorPath
   round-trip join, and the SymbolId-reference shape of legacy_components /
   provenance.ref (a reference, never a bare copy of the symbol's body).

Usage:
    validate_domain_model.py doc.json [doc2.json ...]

Exit 0 iff every document is conformant; prints one line per error otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _REPO_ROOT / "skills" / "domain" / "vendor" / "domain-model.schema.json"
VERSION_PATH = _REPO_ROOT / "skills" / "domain" / "vendor" / "VERSION"


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def pinned_version() -> str:
    return VERSION_PATH.read_text(encoding="utf-8").strip()


# --- stdlib draft-07 subset validator ---------------------------------------
#
# Deliberately small: it validates ONE fixed, vendored schema, not arbitrary
# JSON Schema. Every keyword it handles is one the domain-model schema actually
# uses; anything else in a schema node is ignored (there is none). Keeping it
# here (vs pulling jsonschema) preserves the repo's stdlib-only, pytest-only CI.

def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    """Resolve a local ``#/$defs/<name>`` pointer against the root schema."""
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref is supported, got {ref!r}")
    node: Any = root
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[token]
    return node


def _type_ok(instance: Any, type_name: str) -> bool:
    if type_name == "object":
        return isinstance(instance, dict)
    if type_name == "array":
        return isinstance(instance, list)
    if type_name == "string":
        return isinstance(instance, str)
    if type_name == "integer":
        # bool is a subclass of int in Python — exclude it.
        return isinstance(instance, int) and not isinstance(instance, bool)
    if type_name == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if type_name == "boolean":
        return isinstance(instance, bool)
    if type_name == "null":
        return instance is None
    raise ValueError(f"unsupported type keyword {type_name!r}")


def _validate(instance: Any, schema: dict[str, Any], path: str,
              root: dict[str, Any], errors: list[str]) -> None:
    # $ref: replace this node's schema with the referenced one.
    if "$ref" in schema:
        _validate(instance, _resolve_ref(schema["$ref"], root), path, root, errors)
        return

    def err(msg: str) -> None:
        errors.append(f"schema@{path or '<root>'}: {msg}")

    # type
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(instance, tn) for tn in types):
            err(f"is not of type {t!r}")
            return  # further keyword checks assume the type matched

    # const / enum (any type)
    if "const" in schema and instance != schema["const"]:
        err(f"{instance!r} != const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        err(f"{instance!r} is not one of {schema['enum']!r}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            err(f"string shorter than minLength {schema['minLength']}")
        pat = schema.get("pattern")
        if pat is not None and not re.search(pat, instance):
            err(f"{instance!r} does not match pattern {pat!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            err(f"{instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            err(f"{instance} > maximum {schema['maximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            err(f"array shorter than minItems {schema['minItems']}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(instance):
                _validate(item, item_schema, f"{path}/{i}", root, errors)

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                err(f"missing required property {req!r}")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in instance:
                _validate(instance[key], sub, f"{path}/{key}", root, errors)
        addl = schema.get("additionalProperties", True)
        if addl is not True:
            for key, val in instance.items():
                if key in props:
                    continue
                if addl is False:
                    err(f"additional property {key!r} is not allowed")
                elif isinstance(addl, dict):
                    _validate(val, addl, f"{path}/{key}", root, errors)

        # if / then (the disposition-drop conditional). Only the forms the
        # domain-model schema uses are supported: an object `if`/`then`.
        if "if" in schema:
            if _conforms(instance, schema["if"], root):
                then = schema.get("then")
                if isinstance(then, dict):
                    _validate(instance, then, path, root, errors)


def _conforms(instance: Any, schema: dict[str, Any], root: dict[str, Any]) -> bool:
    """True iff ``instance`` validates against ``schema`` (used by ``if``)."""
    scratch: list[str] = []
    _validate(instance, schema, "", root, scratch)
    return not scratch


def _schema_errors(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _validate(doc, load_schema(), "", load_schema(), errors)
    # Stable order for deterministic output / diffs.
    return sorted(errors)


# --- extra-invariant layer (what draft-07 cannot express) -------------------

def _looks_like_reference(value: str) -> bool:
    """A SymbolId reference or a file#anchor — never an embedded code copy."""
    if not isinstance(value, str) or not value.strip():
        return False
    # Reject obvious embedded-body copies (newlines / very long blobs).
    if "\n" in value or len(value) > 512:
        return False
    return True


def _extra_invariants(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    domains = doc.get("domains")
    if not isinstance(domains, dict):
        return errors  # schema layer already reported the shape problem
    for dkey, domain in domains.items():
        if not isinstance(domain, dict):
            continue
        reqs = domain.get("requirements", {})
        if not isinstance(reqs, dict):
            continue
        for rkey, req in reqs.items():
            where = f"domains/{dkey}/requirements/{rkey}"
            if not isinstance(req, dict):
                continue
            rules = req.get("business_rules", []) or []
            vals = req.get("validations", []) or []
            errs = req.get("error_paths", []) or []

            # id uniqueness within the requirement
            seen: set[str] = set()
            for item in list(rules) + list(vals) + list(errs):
                if not isinstance(item, dict):
                    continue
                iid = item.get("id")
                if iid in seen:
                    errors.append(f"{where}: duplicate id {iid} within requirement")
                elif iid is not None:
                    seen.add(iid)

            # validation.error_ref -> ErrorPath round-trip
            err_ids = {e.get("id") for e in errs if isinstance(e, dict)}
            for v in vals:
                if isinstance(v, dict) and v.get("error_ref") is not None:
                    if v["error_ref"] not in err_ids:
                        errors.append(
                            f"{where}: validation {v.get('id')} error_ref "
                            f"{v['error_ref']} has no matching ErrorPath (round-trip)"
                        )

            # SymbolId-reference shape (invariant 5): references, never copies
            for comp in req.get("legacy_components", []) or []:
                if not _looks_like_reference(comp):
                    errors.append(
                        f"{where}: legacy_components entry is not a valid "
                        f"reference (looks like an embedded copy): {comp!r:.60}"
                    )
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                prov = rule.get("provenance", {})
                ref = prov.get("ref") if isinstance(prov, dict) else None
                if ref is not None and not _looks_like_reference(ref):
                    errors.append(
                        f"{where}/{rule.get('id')}: provenance.ref is not a valid "
                        f"reference (looks like an embedded copy)"
                    )
    return errors


def validate_document(doc: Any) -> list[str]:
    """Return a list of human-readable errors; empty == conformant."""
    if not isinstance(doc, dict):
        return ["document root must be a JSON object"]
    # Reject an unknown schema_version rather than best-efforting it.
    sv = doc.get("metadata", {}).get("schema_version") if isinstance(doc.get("metadata"), dict) else None
    if sv is not None and sv != pinned_version():
        return [
            f"metadata.schema_version {sv!r} has no validator here (pinned "
            f"{pinned_version()!r}); a consumer rejects an unknown version"
        ]
    return _schema_errors(doc) + _extra_invariants(doc)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        sys.stderr.write("usage: validate_domain_model.py doc.json [doc.json ...]\n")
        return 2
    total = 0
    for path in argv:
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{path}: unreadable/invalid JSON: {exc}")
            total += 1
            continue
        errors = validate_document(doc)
        if errors:
            for e in errors:
                print(f"{path}: {e}")
            total += len(errors)
        else:
            print(f"{path}: OK — conforms to domain-model@{pinned_version()}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())

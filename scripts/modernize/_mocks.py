"""Disjoint-build mocks for the modernize extraction slice.

The Domain-Brain contract runs four per-product build workflows in parallel,
each mocking the other three. This module is garden's mock of the *other three*:

- ``EstateClient`` — the frozen six-method estate read/write surface, backed by
  canned fixtures. Records annotation/requirement writes so a test can assert the
  write actually happened with a real SymbolId (never a bare name — the
  anti-legacy silent-no-op scar).
- ``BrainClient`` — brain's domain-model engine surface, backed by the vendored
  schema validator.

NO other-product code is imported. When the real CLIs land, a CLI-backed impl
with the identical interface swaps in and the skills do not change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --- estate fixtures --------------------------------------------------------

# A deterministic name -> SymbolId map. Real SymbolIds are estate's opaque
# interned identity (stable across rename); these fixtures stand in for them.
# Note the duplicated simple name ("Charge") mapping to distinct SymbolIds —
# that is exactly why a write MUST key on the SymbolId, not the name.
_FIXTURE_SYMBOLS: dict[str, list[str]] = {
    "Invoice.assessLateFee": ["sym::billing::Invoice.assessLateFee::a1"],
    "Invoice.close": ["sym::billing::Invoice.close::a2"],
    "LateFee.calc": ["sym::billing::LateFee.calc::a3"],
    "Payment.charge": ["sym::payments::Payment.charge::b1"],
    "Payment.refund": ["sym::payments::Payment.refund::b2"],
    "Charge": [
        "sym::payments::Charge.entity::b3",
        "sym::billing::Charge.legacy::a9",
    ],
}

# Two Louvain communities (largest-first), each with full member SymbolIds —
# the shape of ``clusters --json --summary``.
_FIXTURE_CLUSTERS: list[dict[str, Any]] = [
    {
        "id": 0,
        "size": 3,
        "members": [
            "sym::billing::Invoice.assessLateFee::a1",
            "sym::billing::Invoice.close::a2",
            "sym::billing::LateFee.calc::a3",
        ],
        "label_candidates": ["sym::billing::Invoice.assessLateFee::a1"],
        "dominant_files": ["src/billing/invoice.py"],
        "modularity_contribution": 0.071,
    },
    {
        "id": 1,
        "size": 2,
        "members": [
            "sym::payments::Payment.charge::b1",
            "sym::payments::Payment.refund::b2",
        ],
        "label_candidates": ["sym::payments::Payment.charge::b1"],
        "dominant_files": ["src/payments/payment.py"],
        "modularity_contribution": 0.058,
    },
]


@dataclass
class EstateClient:
    """Mock of estate's frozen read/write surface (contract §5)."""

    #: Records ``(symbol_id, requirement, validated)`` — assert real SymbolIds.
    requirement_writes: list[tuple[str, str, bool]] = field(default_factory=list)
    #: Records k/v annotation writes.
    annotation_writes: list[dict[str, Any]] = field(default_factory=list)

    def read_clusters(self, params: dict | None = None) -> list[dict[str, Any]]:
        # Deep-ish copy so callers can't mutate the fixture.
        return [dict(c, members=list(c["members"])) for c in _FIXTURE_CLUSTERS]

    def resolve(self, name: str, file: str | None = None,
                kind: str | None = None) -> list[str]:
        hits = _FIXTURE_SYMBOLS.get(name, [])
        if file is not None:
            hits = [s for s in hits if file.split("/")[-1].split(".")[0] in s]
        return list(hits)

    def annotate(self, symbol_id: str, type: str, key: str, value: str,
                 confidence: float | None = None, provenance: str | None = None,
                 replace: bool = True) -> None:
        if not _looks_like_symbol_id(symbol_id):
            raise ValueError(
                f"refusing annotate on non-SymbolId {symbol_id!r} — a bare name "
                "is a silent no-op in estate; resolve() first"
            )
        self.annotation_writes.append({
            "symbol_id": symbol_id, "type": type, "key": key, "value": value,
            "confidence": confidence, "provenance": provenance, "replace": replace,
        })

    def set_requirement(self, symbol_id: str, requirement: str,
                        validated: bool) -> None:
        if not _looks_like_symbol_id(symbol_id):
            raise ValueError(
                f"refusing set_requirement on non-SymbolId {symbol_id!r} — a bare "
                "name is a silent no-op in estate; resolve() first"
            )
        self.requirement_writes.append((symbol_id, requirement, validated))

    def read_annotations(self, symbol_id: str) -> list[dict[str, Any]]:
        return [a for a in self.annotation_writes if a["symbol_id"] == symbol_id]

    def find_by_annotation(self, key: str,
                           value: str | None = None) -> list[str]:
        return [
            a["symbol_id"] for a in self.annotation_writes
            if a["key"] == key and (value is None or a["value"] == value)
        ]


@dataclass
class BrainClient:
    """Mock of brain's domain-model engine surface (contract §3 Seam B)."""

    build_calls: list[dict[str, Any]] = field(default_factory=list)

    def validate(self, doc: dict[str, Any]) -> bool:
        # brain rejects an unknown schema_version rather than best-efforting it.
        from modernize.validate_domain_model import validate_document
        errors = validate_document(doc)
        return not errors

    def build_domain_graph(self, doc: dict[str, Any]) -> dict[str, Any]:
        if not self.validate(doc):
            raise ValueError("brain refuses to build from a non-conformant document")
        domains = doc.get("domains", {})
        req_count = sum(len(d.get("requirements", {})) for d in domains.values())
        dropped = sum(
            1
            for d in domains.values()
            for r in d.get("requirements", {}).values()
            if r.get("disposition") == "drop"
        )
        summary = {
            "domains": len(domains),
            "requirements": req_count,
            "dropped": dropped,
        }
        self.build_calls.append({"summary": summary})
        return summary


def _looks_like_symbol_id(value: str) -> bool:
    """A SymbolId reference, never a bare name. Fixtures use the ``sym::`` form."""
    return isinstance(value, str) and value.startswith("sym::") and "::" in value[5:]

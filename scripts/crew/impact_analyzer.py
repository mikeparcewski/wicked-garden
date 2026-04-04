#!/usr/bin/env python3
"""
Cross-Phase Impact Analyzer — wicked-crew issue #357.

Analyzes downstream impact of changing an artifact across crew phases.
Combines traceability links, knowledge graph relationships, and phase
metadata to produce a risk-scored impact report.

Usage:
    python3 impact_analyzer.py analyze --source-id req-123 --project P [--depth 3]
    python3 impact_analyzer.py analyze --source-id design-456 --type design --project P
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup — allow sibling imports from scripts/
# ---------------------------------------------------------------------------
_SCRIPTS_ROOT = str(Path(__file__).resolve().parents[1])
if _SCRIPTS_ROOT not in sys.path:
    sys.path.insert(0, _SCRIPTS_ROOT)

_CREW_ROOT = str(Path(__file__).resolve().parent)
if _CREW_ROOT not in sys.path:
    sys.path.insert(0, _CREW_ROOT)


# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

def classify_risk(direct_count: int, transitive_count: int) -> str:
    """Classify risk level based on impact breadth."""
    total = direct_count + transitive_count
    if total == 0:
        return "none"
    if total <= 2:
        return "low"
    if total <= 5:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# Phase extraction
# ---------------------------------------------------------------------------

_PHASE_KEYWORDS = [
    "clarify", "design", "build", "test", "test-strategy",
    "deploy", "review", "deliver", "operate",
]


def get_affected_phases(impacts: List[Dict]) -> List[str]:
    """Extract unique phases from impacted artifacts."""
    phases = set()
    for item in impacts:
        # Try explicit phase field first
        phase = item.get("phase", "")
        if phase:
            phases.add(phase)
            continue
        # Infer from source_type or type
        artifact_type = item.get("source_type", item.get("type", "")).lower()
        if artifact_type in ("requirement", "requirements"):
            phases.add("clarify")
        elif artifact_type in ("design", "architecture"):
            phases.add("design")
        elif artifact_type in ("code", "implementation"):
            phases.add("build")
        elif artifact_type in ("test", "test-case", "scenario"):
            phases.add("test")
        elif artifact_type in ("evidence", "deliverable"):
            phases.add("deliver")
        # Check name/id for phase keywords
        name = item.get("name", item.get("id", "")).lower()
        for kw in _PHASE_KEYWORDS:
            if kw in name:
                phases.add(kw)
                break
    return sorted(phases)


# ---------------------------------------------------------------------------
# Layer 1: Artifact traceability
# ---------------------------------------------------------------------------

def _gather_traceability(
    source_id: str,
    project_id: Optional[str],
) -> tuple:
    """Walk forward/reverse trace links via traceability module.

    Returns (forward_links, reverse_links) — each a list of dicts.
    """
    try:
        from traceability import forward_trace, reverse_trace  # type: ignore
        forward_links = forward_trace(source_id, project_id)
        reverse_links = reverse_trace(source_id, project_id)
        if not isinstance(forward_links, list):
            forward_links = []
        if not isinstance(reverse_links, list):
            reverse_links = []
        return forward_links, reverse_links
    except ImportError:
        return [], []
    except Exception as exc:
        print(
            "[impact_analyzer] traceability error: %s" % exc,
            file=sys.stderr,
        )
        return [], []


# ---------------------------------------------------------------------------
# Layer 2: Knowledge graph
# ---------------------------------------------------------------------------

def _gather_knowledge_graph(
    source_id: str,
    depth: int,
) -> Dict:
    """Query the knowledge graph for related entities.

    Returns a subgraph dict with 'entities' and 'relationships'.
    """
    try:
        _smaht_root = str(Path(__file__).resolve().parents[1] / "smaht")
        if _smaht_root not in sys.path:
            sys.path.insert(0, _smaht_root)
        from knowledge_graph import KnowledgeGraph  # type: ignore
        kg = KnowledgeGraph()
        subgraph = kg.get_subgraph(source_id, depth=depth)
        if not isinstance(subgraph, dict):
            return {"entities": [], "relationships": []}
        return subgraph
    except ImportError:
        return {"entities": [], "relationships": []}
    except Exception as exc:
        print(
            "[impact_analyzer] knowledge_graph error: %s" % exc,
            file=sys.stderr,
        )
        return {"entities": [], "relationships": []}


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_impacts(items: List[Dict]) -> List[Dict]:
    """Remove duplicate artifacts by id, keeping the first occurrence."""
    seen = set()
    result = []
    for item in items:
        item_id = item.get("id", "")
        if item_id and item_id in seen:
            continue
        if item_id:
            seen.add(item_id)
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze_impact(
    source_id: str,
    source_type: str = "auto",
    project_id: Optional[str] = None,
    depth: int = 3,
) -> Dict:
    """Analyze the downstream impact of changing an artifact.

    Combines traceability links, knowledge graph relationships, and phase
    metadata to produce a risk-scored impact report.

    Args:
        source_id: Identifier of the artifact being changed.
        source_type: Artifact type (auto-detect, requirement, design,
                     code, test, evidence).
        project_id: Optional crew project id for scoping.
        depth: How many hops to follow in the knowledge graph.

    Returns:
        Impact report dict with direct impacts, transitive impacts,
        and risk summary.
    """
    direct = []
    transitive = []

    # --- Layer 1: Traceability links ---
    forward_links, reverse_links = _gather_traceability(source_id, project_id)

    # Separate 1-hop (direct) from 2+ hop (transitive) links.
    # forward_trace returns BFS-ordered links; links whose source_id
    # matches the query source_id are direct (1-hop), others are transitive.
    # The depth parameter limits how many hops to include.
    hop_targets: dict = {}  # target_id -> hop distance
    for link in forward_links:
        link_source = link.get("source_id", "")
        link_target = link.get("target_id", "")
        link_rel = link.get("link_type", link.get("relationship", "TRACES_TO"))

        # Calculate hop distance
        if link_source == source_id:
            hop = 1
        elif link_source in hop_targets:
            hop = hop_targets[link_source] + 1
        else:
            hop = 2  # unknown intermediate, treat as transitive

        # Skip if beyond depth limit
        if hop > depth:
            continue

        hop_targets[link_target] = hop

        entry = {
            "id": link_target,
            "type": link.get("target_type", link.get("source_type", "")),
            "name": link.get("name", link_target),
            "relationship": link_rel,
        }
        if link.get("phase"):
            entry["phase"] = link["phase"]
        if link.get("source_type"):
            entry["source_type"] = link["source_type"]

        if hop == 1:
            direct.append(entry)
        else:
            entry["via"] = link_source
            transitive.append(entry)

    for link in reverse_links:
        entry = {
            "id": link.get("source_id", link.get("id", "")),
            "type": link.get("source_type", link.get("type", "")),
            "name": link.get("name", link.get("source_id", "")),
            "relationship": link.get("link_type", link.get("relationship", "TRACED_FROM")),
        }
        if link.get("phase"):
            entry["phase"] = link["phase"]
        if link.get("source_type"):
            entry["source_type"] = link["source_type"]
        direct.append(entry)

    # --- Layer 2: Knowledge graph ---
    subgraph = _gather_knowledge_graph(source_id, depth)
    kg_entities = subgraph.get("entities", [])
    kg_relationships = subgraph.get("relationships", [])

    # Build a set of already-known ids for dedup
    known_ids = {item.get("id") for item in direct if item.get("id")}
    known_ids.add(source_id)

    for entity in kg_entities:
        ent_id = entity.get("id", "")
        if not ent_id or ent_id in known_ids:
            continue
        known_ids.add(ent_id)
        # Determine if this is a direct neighbor or transitive
        is_direct = False
        via_id = ""
        rel_type = ""
        for rel in kg_relationships:
            if rel.get("source") == source_id and rel.get("target") == ent_id:
                is_direct = True
                rel_type = rel.get("type", "RELATED_TO")
                break
            if rel.get("target") == source_id and rel.get("source") == ent_id:
                is_direct = True
                rel_type = rel.get("type", "RELATED_TO")
                break
        if not is_direct:
            # Find the intermediary
            for rel in kg_relationships:
                if rel.get("target") == ent_id and rel.get("source") in known_ids:
                    via_id = rel.get("source", "")
                    rel_type = rel.get("type", "RELATED_TO")
                    break
                if rel.get("source") == ent_id and rel.get("target") in known_ids:
                    via_id = rel.get("target", "")
                    rel_type = rel.get("type", "RELATED_TO")
                    break

        entry = {
            "id": ent_id,
            "type": entity.get("type", ""),
            "name": entity.get("name", ent_id),
            "relationship": rel_type or "RELATED_TO",
        }
        if entity.get("phase"):
            entry["phase"] = entity["phase"]

        if is_direct:
            direct.append(entry)
        else:
            entry["via"] = via_id
            transitive.append(entry)

    # --- Dedup ---
    direct = _dedup_impacts(direct)
    transitive = _dedup_impacts(transitive)

    # Remove any transitive items that also appear in direct
    direct_ids = {item.get("id") for item in direct if item.get("id")}
    transitive = [t for t in transitive if t.get("id") not in direct_ids]

    # --- Layer 3: Phase impact ---
    all_impacts = direct + transitive
    phases_affected = get_affected_phases(all_impacts)

    # --- Risk summary ---
    direct_count = len(direct)
    transitive_count = len(transitive)
    risk_level = classify_risk(direct_count, transitive_count)

    return {
        "source": {"id": source_id, "type": source_type},
        "impact": {
            "direct": direct,
            "transitive": transitive,
        },
        "risk_summary": {
            "direct_count": direct_count,
            "transitive_count": transitive_count,
            "total_affected": direct_count + transitive_count,
            "phases_affected": phases_affected,
            "risk_level": risk_level,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Cross-phase impact analysis for crew artifacts"
    )
    sub = parser.add_subparsers(dest="command")

    analyze_cmd = sub.add_parser("analyze", help="Analyze impact of changing an artifact")
    analyze_cmd.add_argument("--source-id", required=True, help="Artifact identifier")
    analyze_cmd.add_argument("--type", dest="source_type", default="auto",
                             help="Artifact type (auto, requirement, design, code, test, evidence)")
    analyze_cmd.add_argument("--project", dest="project_id", default=None,
                             help="Crew project id for scoping")
    analyze_cmd.add_argument("--depth", type=int, default=3,
                             help="Knowledge graph traversal depth (default: 3)")

    args = parser.parse_args()

    if args.command != "analyze":
        parser.print_help()
        sys.exit(1)

    report = analyze_impact(
        source_id=args.source_id,
        source_type=args.source_type,
        project_id=args.project_id,
        depth=args.depth,
    )

    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

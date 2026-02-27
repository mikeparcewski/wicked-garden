#!/usr/bin/env python3
"""
Coverage Reporter for wicked-search.

Analyzes lineage completeness and reports on coverage gaps.
Identifies symbols without full source-to-sink traceability.
"""

import argparse
import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class CoverageStatus(Enum):
    """Coverage status for a symbol."""
    FULL = "full"           # Complete lineage from UI to DB
    PARTIAL = "partial"     # Some lineage but gaps exist
    ORPHAN = "orphan"       # No lineage connections
    UNKNOWN = "unknown"     # Not yet analyzed


@dataclass
class SymbolCoverage:
    """Coverage information for a single symbol."""
    symbol_id: str
    symbol_type: str
    name: str
    file_path: Optional[str]
    line_start: Optional[int]
    status: CoverageStatus
    upstream_count: int = 0
    downstream_count: int = 0
    lineage_paths: int = 0
    gaps: list[str] = field(default_factory=list)


@dataclass
class CoverageReport:
    """Overall coverage report."""
    total_symbols: int
    full_coverage: int
    partial_coverage: int
    orphan_symbols: int
    coverage_percentage: float
    by_type: dict[str, dict]
    symbols: list[SymbolCoverage]
    gaps_summary: list[dict]


class CoverageReporter:
    """Analyzes and reports on lineage coverage."""

    # Symbol types that should have lineage (UI -> DB flow)
    UI_TYPES = {'form_binding', 'el_expression', 'data_binding', 'ui_field'}
    ENTITY_TYPES = {'entity_field', 'entity', 'dto_field'}
    DB_TYPES = {'column', 'table'}

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def analyze(self, symbol_type: Optional[str] = None) -> CoverageReport:
        """Analyze coverage for all or specific symbol types."""
        symbols = self._get_symbols(symbol_type)
        coverage_data = []

        for symbol in symbols:
            coverage = self._analyze_symbol(symbol)
            coverage_data.append(coverage)

        return self._build_report(coverage_data)

    def _get_symbols(self, symbol_type: Optional[str] = None) -> list[dict]:
        """Get symbols to analyze."""
        query = "SELECT id, type, name, file_path, line_start FROM symbols"
        params = []

        if symbol_type:
            query += " WHERE type = ?"
            params.append(symbol_type)

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def _analyze_symbol(self, symbol: dict) -> SymbolCoverage:
        """Analyze coverage for a single symbol."""
        symbol_id = symbol['id']

        # Count upstream references (things that point TO this symbol)
        upstream = self.conn.execute(
            "SELECT COUNT(*) FROM refs WHERE target_id = ?",
            (symbol_id,)
        ).fetchone()[0]

        # Count downstream references (things this symbol points TO)
        downstream = self.conn.execute(
            "SELECT COUNT(*) FROM refs WHERE source_id = ?",
            (symbol_id,)
        ).fetchone()[0]

        # Check for lineage paths involving this symbol
        lineage_paths = self._count_lineage_paths(symbol_id)

        # Determine coverage status
        status = self._determine_status(symbol, upstream, downstream, lineage_paths)

        # Find gaps
        gaps = self._find_gaps(symbol, upstream, downstream)

        return SymbolCoverage(
            symbol_id=symbol_id,
            symbol_type=symbol['type'],
            name=symbol['name'],
            file_path=symbol.get('file_path'),
            line_start=symbol.get('line_start'),
            status=status,
            upstream_count=upstream,
            downstream_count=downstream,
            lineage_paths=lineage_paths,
            gaps=gaps
        )

    def _count_lineage_paths(self, symbol_id: str) -> int:
        """Count lineage paths involving this symbol."""
        # Check if lineage_paths table exists
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='lineage_paths'"
        )
        if not cursor.fetchone():
            return 0

        count = self.conn.execute(
            """SELECT COUNT(*) FROM lineage_paths
               WHERE source_id = ? OR sink_id = ?
               OR path_nodes LIKE ?""",
            (symbol_id, symbol_id, f'%{symbol_id}%')
        ).fetchone()[0]

        return count

    def _determine_status(
        self,
        symbol: dict,
        upstream: int,
        downstream: int,
        lineage_paths: int
    ) -> CoverageStatus:
        """Determine coverage status based on connections."""
        symbol_type = symbol['type']

        # UI types should have downstream connections
        if symbol_type in self.UI_TYPES:
            if downstream > 0 and lineage_paths > 0:
                return CoverageStatus.FULL
            elif downstream > 0:
                return CoverageStatus.PARTIAL
            else:
                return CoverageStatus.ORPHAN

        # DB types should have upstream connections
        elif symbol_type in self.DB_TYPES:
            if upstream > 0 and lineage_paths > 0:
                return CoverageStatus.FULL
            elif upstream > 0:
                return CoverageStatus.PARTIAL
            else:
                return CoverageStatus.ORPHAN

        # Entity types should have both
        elif symbol_type in self.ENTITY_TYPES:
            if upstream > 0 and downstream > 0:
                if lineage_paths > 0:
                    return CoverageStatus.FULL
                return CoverageStatus.PARTIAL
            elif upstream > 0 or downstream > 0:
                return CoverageStatus.PARTIAL
            else:
                return CoverageStatus.ORPHAN

        # Other types - check for any connections
        else:
            if upstream > 0 or downstream > 0:
                return CoverageStatus.PARTIAL
            return CoverageStatus.ORPHAN

    def _find_gaps(self, symbol: dict, upstream: int, downstream: int) -> list[str]:
        """Identify coverage gaps for a symbol."""
        gaps = []
        symbol_type = symbol['type']

        if symbol_type in self.UI_TYPES and downstream == 0:
            gaps.append("No binding to entity/model")

        if symbol_type in self.DB_TYPES and upstream == 0:
            gaps.append("No entity mapping found")

        if symbol_type in self.ENTITY_TYPES:
            if upstream == 0:
                gaps.append("No UI binding found")
            if downstream == 0:
                gaps.append("No database mapping found")

        return gaps

    def _build_report(self, coverage_data: list[SymbolCoverage]) -> CoverageReport:
        """Build the coverage report from analyzed data."""
        total = len(coverage_data)
        full = sum(1 for c in coverage_data if c.status == CoverageStatus.FULL)
        partial = sum(1 for c in coverage_data if c.status == CoverageStatus.PARTIAL)
        orphan = sum(1 for c in coverage_data if c.status == CoverageStatus.ORPHAN)

        coverage_pct = (full / total * 100) if total > 0 else 0

        # Group by type
        by_type: dict[str, dict] = {}
        for c in coverage_data:
            if c.symbol_type not in by_type:
                by_type[c.symbol_type] = {
                    'total': 0, 'full': 0, 'partial': 0, 'orphan': 0
                }
            by_type[c.symbol_type]['total'] += 1
            if c.status == CoverageStatus.FULL:
                by_type[c.symbol_type]['full'] += 1
            elif c.status == CoverageStatus.PARTIAL:
                by_type[c.symbol_type]['partial'] += 1
            elif c.status == CoverageStatus.ORPHAN:
                by_type[c.symbol_type]['orphan'] += 1

        # Summarize gaps
        gap_counts: dict[str, int] = {}
        for c in coverage_data:
            for gap in c.gaps:
                gap_counts[gap] = gap_counts.get(gap, 0) + 1

        gaps_summary = [
            {'gap': gap, 'count': count}
            for gap, count in sorted(gap_counts.items(), key=lambda x: -x[1])
        ]

        return CoverageReport(
            total_symbols=total,
            full_coverage=full,
            partial_coverage=partial,
            orphan_symbols=orphan,
            coverage_percentage=coverage_pct,
            by_type=by_type,
            symbols=coverage_data,
            gaps_summary=gaps_summary
        )

    def format_table(self, report: CoverageReport, show_orphans: bool = False) -> str:
        """Format report as markdown table."""
        lines = [
            "## Coverage Report",
            "",
            "### Summary",
            f"- **Total Symbols**: {report.total_symbols}",
            f"- **Full Coverage**: {report.full_coverage} ({report.coverage_percentage:.1f}%)",
            f"- **Partial Coverage**: {report.partial_coverage}",
            f"- **Orphan Symbols**: {report.orphan_symbols}",
            "",
            "### Coverage by Type",
            "",
            "| Type | Total | Full | Partial | Orphan | Coverage |",
            "|------|-------|------|---------|--------|----------|"
        ]

        for sym_type, counts in sorted(report.by_type.items()):
            pct = (counts['full'] / counts['total'] * 100) if counts['total'] > 0 else 0
            lines.append(
                f"| {sym_type} | {counts['total']} | {counts['full']} | "
                f"{counts['partial']} | {counts['orphan']} | {pct:.1f}% |"
            )

        if report.gaps_summary:
            lines.extend([
                "",
                "### Common Gaps",
                "",
                "| Gap | Count |",
                "|-----|-------|"
            ])
            for gap in report.gaps_summary[:10]:
                lines.append(f"| {gap['gap']} | {gap['count']} |")

        if show_orphans and report.orphan_symbols > 0:
            lines.extend([
                "",
                "### Orphan Symbols (No Lineage)",
                "",
                "| Symbol | Type | File | Line |",
                "|--------|------|------|------|"
            ])
            orphans = [s for s in report.symbols if s.status == CoverageStatus.ORPHAN]
            for s in orphans[:50]:  # Limit to 50
                file_path = s.file_path or "N/A"
                if len(file_path) > 40:
                    file_path = "..." + file_path[-37:]
                lines.append(
                    f"| {s.name} | {s.symbol_type} | {file_path} | {s.line_start or 'N/A'} |"
                )
            if len(orphans) > 50:
                lines.append(f"| ... and {len(orphans) - 50} more | | | |")

        return "\n".join(lines)

    def format_json(self, report: CoverageReport) -> str:
        """Format report as JSON."""
        return json.dumps({
            'summary': {
                'total_symbols': report.total_symbols,
                'full_coverage': report.full_coverage,
                'partial_coverage': report.partial_coverage,
                'orphan_symbols': report.orphan_symbols,
                'coverage_percentage': report.coverage_percentage
            },
            'by_type': report.by_type,
            'gaps_summary': report.gaps_summary,
            'symbols': [
                {
                    'id': s.symbol_id,
                    'type': s.symbol_type,
                    'name': s.name,
                    'file': s.file_path,
                    'line': s.line_start,
                    'status': s.status.value,
                    'upstream': s.upstream_count,
                    'downstream': s.downstream_count,
                    'lineage_paths': s.lineage_paths,
                    'gaps': s.gaps
                }
                for s in report.symbols
            ]
        }, indent=2)

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze lineage coverage and report gaps"
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Path to the symbol graph database"
    )
    parser.add_argument(
        "--type",
        help="Filter to specific symbol type"
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)"
    )
    parser.add_argument(
        "--show-orphans",
        action="store_true",
        help="Include list of orphan symbols in output"
    )

    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Error: Database not found: {args.db}")
        print("Run /wicked-search:index first to create the symbol graph.")
        return 1

    reporter = CoverageReporter(args.db)

    try:
        report = reporter.analyze(args.type)

        if args.format == "json":
            print(reporter.format_json(report))
        else:
            print(reporter.format_table(report, args.show_orphans))

        return 0
    finally:
        reporter.close()


if __name__ == "__main__":
    exit(main())

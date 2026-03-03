#!/usr/bin/env python3
"""
Accuracy Validator for wicked-search.

Uses consistency-based validation: verifies that indexed symbols exist in source files
and that references point to valid targets. Adapts validation strategies based on
detected language/framework.

Validation approaches:
1. Symbol Existence - verify indexed symbols exist at stated locations
2. Reference Validity - verify ref targets exist in the graph
3. Cross-Layer Traceability - verify lineage paths have valid endpoints
4. Framework-Specific - validate ORM mappings, form bindings, etc.
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Try to import adapters from the same codebase
try:
    from adapters import AdapterRegistry
    HAS_ADAPTERS = True
except ImportError:
    HAS_ADAPTERS = False
    AdapterRegistry = None


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    check_name: str
    category: str  # existence, reference, traceability, framework
    total_checked: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    accuracy: float = 0.0
    passed: bool = False
    details: List[str] = field(default_factory=list)

    def compute(self):
        """Compute accuracy."""
        if self.total_checked > 0:
            self.accuracy = self.valid_count / self.total_checked
            self.passed = self.accuracy >= 0.95
        else:
            # No items to check - consider it passed (nothing to fail)
            self.accuracy = 1.0
            self.passed = True


@dataclass
class ValidationReport:
    """Overall validation report."""
    project_root: str
    detected_stack: Dict[str, Any] = field(default_factory=dict)
    total_checks: int = 0
    passed_checks: int = 0
    overall_accuracy: float = 0.0
    results: List[ValidationResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def compute_overall(self):
        """Compute overall metrics."""
        if not self.results:
            return

        total_valid = sum(r.valid_count for r in self.results)
        total_checked = sum(r.total_checked for r in self.results)

        self.overall_accuracy = total_valid / total_checked if total_checked > 0 else 1.0
        self.total_checks = len(self.results)
        self.passed_checks = sum(1 for r in self.results if r.passed)


# Framework detection patterns
FRAMEWORK_INDICATORS = {
    'spring': {
        'files': ['pom.xml', 'build.gradle'],
        'patterns': [r'@Controller', r'@Service', r'@Repository', r'@Entity'],
        'extensions': ['.java'],
    },
    'django': {
        'files': ['manage.py', 'settings.py'],
        'patterns': [r'from django', r'models\.Model', r'class.*\(models\.Model\)'],
        'extensions': ['.py'],
    },
    'rails': {
        'files': ['Gemfile', 'config/routes.rb'],
        'patterns': [r'class.*<\s*ApplicationRecord', r'class.*<\s*ActiveRecord::Base'],
        'extensions': ['.rb'],
    },
    'express': {
        'files': ['package.json'],
        'patterns': [r'express\(\)', r"require\(['\"]express['\"]\)"],
        'extensions': ['.js', '.ts'],
    },
    'fastapi': {
        'files': ['requirements.txt', 'pyproject.toml'],
        'patterns': [r'from fastapi', r'FastAPI\(\)'],
        'extensions': ['.py'],
    },
    'nestjs': {
        'files': ['package.json', 'nest-cli.json'],
        'patterns': [r'@Controller', r'@Injectable', r'@Module'],
        'extensions': ['.ts'],
    },
}


class AccuracyValidator:
    """Validates wicked-search index accuracy using consistency checks."""

    def __init__(self, db_path: str, project_root: str):
        self.db_path = db_path
        self.project_root = Path(project_root)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.report = ValidationReport(project_root=project_root)

        # Detection results
        self.detected_languages: List[str] = []
        self.detected_frameworks: List[str] = []
        self.symbol_types: Counter = Counter()
        self.ref_types: Counter = Counter()

    def validate_all(self, sample_size: int = 100, deep: bool = False) -> ValidationReport:
        """Run all validation checks based on detected codebase."""
        print("Starting accuracy validation...")
        print(f"  Project: {self.project_root}")
        print(f"  Database: {self.db_path}")
        print(f"  Sample size: {sample_size}")
        print(f"  Mode: {'deep (completeness check)' if deep else 'standard (consistency check)'}")
        print()

        # Step 1: Analyze index
        self._analyze_index()

        # Step 2: Detect stack
        self._detect_stack()

        print(f"Languages: {', '.join(self.detected_languages) or 'unknown'}")
        print(f"Frameworks: {', '.join(self.detected_frameworks) or 'none detected'}")
        print(f"Symbol types: {dict(self.symbol_types.most_common(5))}")
        print()

        self.report.detected_stack = {
            'languages': self.detected_languages,
            'frameworks': self.detected_frameworks,
            'symbol_types': dict(self.symbol_types),
        }

        # Step 3: Run validation checks
        self._validate_symbol_existence(sample_size)
        self._validate_reference_targets(sample_size)
        self._validate_lineage_endpoints(sample_size)

        # Step 4: Framework-specific validation
        for framework in self.detected_frameworks:
            self._validate_framework(framework, sample_size)

        # Step 5: Deep completeness check (if enabled)
        if deep:
            self._validate_completeness(sample_size)

        self.report.compute_overall()
        return self.report

    def _analyze_index(self) -> None:
        """Analyze the index to understand what's present."""
        # Symbol types
        cursor = self.conn.execute("""
            SELECT type, COUNT(*) as count
            FROM symbols
            GROUP BY type
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            self.symbol_types[row['type']] = row['count']

        # Reference types
        cursor = self.conn.execute("""
            SELECT ref_type, COUNT(*) as count
            FROM refs
            GROUP BY ref_type
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            self.ref_types[row['ref_type']] = row['count']

    def _detect_stack(self) -> None:
        """Detect languages and frameworks."""
        # Detect languages from file extensions in index
        cursor = self.conn.execute("""
            SELECT DISTINCT file_path FROM symbols WHERE file_path IS NOT NULL LIMIT 500
        """)
        ext_counts: Counter = Counter()
        for row in cursor.fetchall():
            ext = Path(row['file_path']).suffix.lower()
            ext_counts[ext] += 1

        ext_to_lang = {
            '.java': 'java', '.py': 'python', '.ts': 'typescript', '.tsx': 'typescript',
            '.js': 'javascript', '.jsx': 'javascript', '.go': 'go', '.rb': 'ruby',
            '.cs': 'csharp', '.php': 'php', '.rs': 'rust', '.kt': 'kotlin',
        }
        for ext, count in ext_counts.most_common(5):
            if ext in ext_to_lang and count > 10:
                lang = ext_to_lang[ext]
                if lang not in self.detected_languages:
                    self.detected_languages.append(lang)

        # Detect frameworks
        for framework, indicators in FRAMEWORK_INDICATORS.items():
            # Check for indicator files
            for filename in indicators['files']:
                if list(self.project_root.glob(f"**/{filename}"))[:1]:
                    if framework not in self.detected_frameworks:
                        self.detected_frameworks.append(framework)
                    break

    def _validate_symbol_existence(self, sample_size: int) -> None:
        """Validate that indexed symbols actually exist at their stated locations."""
        print("Validating symbol existence...")

        cursor = self.conn.execute("""
            SELECT id, name, type, file_path, line_start
            FROM symbols
            WHERE file_path IS NOT NULL AND line_start IS NOT NULL
            ORDER BY RANDOM()
            LIMIT ?
        """, (sample_size,))

        result = ValidationResult(
            check_name="symbol_existence",
            category="existence"
        )

        for row in cursor.fetchall():
            file_path = Path(row['file_path'])
            if not file_path.exists():
                result.invalid_count += 1
                result.details.append(f"File not found: {file_path}")
                result.total_checked += 1
                continue

            try:
                content = file_path.read_text(errors='ignore')
                lines = content.split('\n')
                line_num = row['line_start']

                # Check if symbol name appears near the stated line
                search_range = range(max(0, line_num - 3), min(len(lines), line_num + 3))
                found = False
                for i in search_range:
                    if row['name'] in lines[i]:
                        found = True
                        break

                if found:
                    result.valid_count += 1
                else:
                    result.invalid_count += 1
                    result.details.append(
                        f"Symbol '{row['name']}' not found near line {line_num} in {file_path.name}"
                    )
            except Exception as e:
                result.invalid_count += 1
                result.details.append(f"Error reading {file_path}: {e}")

            result.total_checked += 1

        result.compute()
        self.report.results.append(result)
        print(f"  Symbol existence: {result.accuracy:.1%} ({result.valid_count}/{result.total_checked})")

    def _validate_reference_targets(self, sample_size: int) -> None:
        """Validate that reference targets exist in the symbol graph."""
        print("Validating reference targets...")

        cursor = self.conn.execute("""
            SELECT source_id, target_id, ref_type
            FROM refs
            ORDER BY RANDOM()
            LIMIT ?
        """, (sample_size,))

        result = ValidationResult(
            check_name="reference_targets",
            category="reference"
        )

        for row in cursor.fetchall():
            result.total_checked += 1

            # Check if target exists (either as symbol or as a valid ID pattern)
            target_cursor = self.conn.execute(
                "SELECT 1 FROM symbols WHERE id = ?",
                (row['target_id'],)
            )

            if target_cursor.fetchone():
                result.valid_count += 1
            else:
                # Some targets are synthetic (db::TABLE.COLUMN) - validate pattern
                target = row['target_id']
                if target.startswith('db::') or target.startswith('column::'):
                    # Database references are valid by convention
                    result.valid_count += 1
                else:
                    result.invalid_count += 1
                    result.details.append(
                        f"Dangling reference: {row['source_id']} -> {target}"
                    )

        result.compute()
        self.report.results.append(result)
        print(f"  Reference targets: {result.accuracy:.1%} ({result.valid_count}/{result.total_checked})")

    def _validate_lineage_endpoints(self, sample_size: int) -> None:
        """Validate lineage path endpoints exist."""
        print("Validating lineage endpoints...")

        # Check if lineage_paths table exists
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='lineage_paths'"
        )
        if not cursor.fetchone():
            print("  Lineage table not found (run lineage tracer first)")
            return

        cursor = self.conn.execute("""
            SELECT source_id, sink_id, path_nodes
            FROM lineage_paths
            ORDER BY RANDOM()
            LIMIT ?
        """, (sample_size,))

        result = ValidationResult(
            check_name="lineage_endpoints",
            category="traceability"
        )

        for row in cursor.fetchall():
            result.total_checked += 1
            valid = True

            # Validate source exists
            src_cursor = self.conn.execute(
                "SELECT 1 FROM symbols WHERE id = ?", (row['source_id'],)
            )
            if not src_cursor.fetchone():
                valid = False
                result.details.append(f"Invalid source: {row['source_id']}")

            # Validate sink exists or is a valid pattern
            sink = row['sink_id']
            if sink.startswith('db::') or sink.startswith('column::'):
                pass  # Valid database reference
            else:
                sink_cursor = self.conn.execute(
                    "SELECT 1 FROM symbols WHERE id = ?", (sink,)
                )
                if not sink_cursor.fetchone():
                    valid = False
                    result.details.append(f"Invalid sink: {sink}")

            if valid:
                result.valid_count += 1
            else:
                result.invalid_count += 1

        result.compute()
        self.report.results.append(result)
        print(f"  Lineage endpoints: {result.accuracy:.1%} ({result.valid_count}/{result.total_checked})")

    def _validate_framework(self, framework: str, sample_size: int) -> None:
        """Run framework-specific validation."""
        if framework == 'spring':
            self._validate_spring(sample_size)
        elif framework == 'django':
            self._validate_django(sample_size)
        # Add more frameworks as needed

    def _validate_spring(self, sample_size: int) -> None:
        """Validate Spring-specific patterns."""
        print("Validating Spring patterns...")

        # Check entity -> column mappings
        cursor = self.conn.execute("""
            SELECT s.id, s.name, s.file_path, s.line_start, r.target_id
            FROM symbols s
            JOIN refs r ON s.id = r.source_id
            WHERE s.type = 'entity_field'
            AND r.ref_type = 'maps_to'
            ORDER BY RANDOM()
            LIMIT ?
        """, (sample_size,))

        result = ValidationResult(
            check_name="spring_entity_mappings",
            category="framework"
        )

        for row in cursor.fetchall():
            result.total_checked += 1
            file_path = Path(row['file_path'])

            if not file_path.exists():
                result.invalid_count += 1
                continue

            try:
                content = file_path.read_text(errors='ignore')

                # Check for @Column annotation near field
                field_name = row['name']
                target_col = row['target_id'].split('.')[-1] if '.' in row['target_id'] else row['target_id']

                # Simple validation: field name exists and @Column annotation present
                if field_name in content and ('@Column' in content or '@JoinColumn' in content or '@Id' in content):
                    result.valid_count += 1
                else:
                    result.invalid_count += 1
                    result.details.append(f"Missing annotation for {field_name}")
            except Exception:
                result.invalid_count += 1

        result.compute()
        self.report.results.append(result)
        print(f"  Spring entity mappings: {result.accuracy:.1%} ({result.valid_count}/{result.total_checked})")

    def _validate_django(self, sample_size: int) -> None:
        """Validate Django-specific patterns."""
        print("Validating Django patterns...")

        cursor = self.conn.execute("""
            SELECT s.id, s.name, s.file_path
            FROM symbols s
            WHERE s.type = 'entity_field'
            AND s.file_path LIKE '%.py'
            ORDER BY RANDOM()
            LIMIT ?
        """, (sample_size,))

        result = ValidationResult(
            check_name="django_model_fields",
            category="framework"
        )

        for row in cursor.fetchall():
            result.total_checked += 1
            file_path = Path(row['file_path'])

            if not file_path.exists():
                result.invalid_count += 1
                continue

            try:
                content = file_path.read_text(errors='ignore')

                # Check for Django field pattern
                field_name = row['name']
                django_patterns = [
                    f'{field_name} = models.',
                    f'{field_name}=models.',
                    f'{field_name} = db.Column',
                ]

                if any(p in content for p in django_patterns):
                    result.valid_count += 1
                else:
                    result.invalid_count += 1
            except Exception:
                result.invalid_count += 1

        result.compute()
        if result.total_checked > 0:
            self.report.results.append(result)
            print(f"  Django model fields: {result.accuracy:.1%} ({result.valid_count}/{result.total_checked})")

    def _validate_completeness(self, sample_size: int) -> None:
        """
        Deep completeness check: discover symbols in source files and compare
        with what's indexed. This finds MISSING items, not just validates existing ones.
        """
        print("\nRunning deep completeness check...")
        print("  (This discovers what's missing from the index)")

        # Symbol extraction patterns by language
        symbol_patterns = {
            'java': {
                'class': r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?(?:class|interface|enum)\s+(\w+)',
                'method': r'(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\(',
                'field': r'(?:private|protected|public)\s+(?:static\s+)?(?:final\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*[;=]',
            },
            'python': {
                'class': r'^class\s+(\w+)',
                'function': r'^(?:async\s+)?def\s+(\w+)',
            },
            'typescript': {
                'class': r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)',
                'interface': r'(?:export\s+)?interface\s+(\w+)',
                'function': r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',
                'const': r'(?:export\s+)?const\s+(\w+)\s*=',
            },
            'javascript': {
                'class': r'class\s+(\w+)',
                'function': r'(?:async\s+)?function\s+(\w+)',
                'const': r'(?:export\s+)?const\s+(\w+)\s*=',
            },
            'go': {
                'type': r'^type\s+(\w+)\s+(?:struct|interface)',
                'func': r'^func\s+(?:\([^)]+\)\s+)?(\w+)',
            },
            'ruby': {
                'class': r'^class\s+(\w+)',
                'module': r'^module\s+(\w+)',
                'def': r'^\s*def\s+(\w+)',
            },
        }

        ext_to_lang = {
            '.java': 'java', '.py': 'python', '.ts': 'typescript', '.tsx': 'typescript',
            '.js': 'javascript', '.jsx': 'javascript', '.go': 'go', '.rb': 'ruby',
        }

        # Get indexed files grouped by extension
        cursor = self.conn.execute("""
            SELECT DISTINCT file_path FROM symbols
            WHERE file_path IS NOT NULL
        """)
        indexed_files = {row['file_path'] for row in cursor.fetchall()}

        # Sample files from project for completeness check
        sampled_files = self._sample_project_files(sample_size, ext_to_lang.keys())

        result = ValidationResult(
            check_name="completeness",
            category="completeness"
        )

        total_found_in_files = 0
        total_indexed_in_files = 0
        missing_symbols: List[Tuple[str, str, str]] = []  # (file, type, name)

        for file_path in sampled_files:
            try:
                file_path = Path(file_path).resolve()  # Normalize to absolute
                ext = file_path.suffix.lower()
                lang = ext_to_lang.get(ext)
                if not lang or lang not in symbol_patterns:
                    continue

                content = file_path.read_text(errors='ignore')
                patterns = symbol_patterns[lang]

                # Find all symbols in this file using patterns
                found_symbols: Set[str] = set()
                for sym_type, pattern in patterns.items():
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        name = match.group(1)
                        # Filter out noise (short names, common keywords)
                        if len(name) > 2 and name not in {'if', 'for', 'try', 'get', 'set', 'new'}:
                            found_symbols.add(name)

                # Get indexed symbols for this file (try both absolute path and filename match)
                file_str = str(file_path)
                cursor = self.conn.execute("""
                    SELECT name FROM symbols
                    WHERE file_path = ? OR file_path LIKE ?
                """, (file_str, f'%{file_path.name}'))
                indexed_symbols = {row['name'] for row in cursor.fetchall()}

                # Calculate coverage for this file
                file_found = len(found_symbols)
                file_indexed = len(found_symbols & indexed_symbols)

                total_found_in_files += file_found
                total_indexed_in_files += file_indexed

                # Track missing symbols (limit to avoid explosion)
                missing = found_symbols - indexed_symbols
                for name in list(missing)[:3]:
                    missing_symbols.append((str(file_path), lang, name))

            except Exception as e:
                result.details.append(f"Error scanning {file_path}: {e}")

        # Compute completeness
        if total_found_in_files > 0:
            result.total_checked = total_found_in_files
            result.valid_count = total_indexed_in_files
            result.invalid_count = total_found_in_files - total_indexed_in_files
            result.compute()

            print(f"  Files sampled: {len(sampled_files)}")
            print(f"  Symbols found in source: {total_found_in_files}")
            print(f"  Symbols in index: {total_indexed_in_files}")
            print(f"  Completeness: {result.accuracy:.1%}")

            if missing_symbols and result.accuracy < 0.95:
                result.details.append("Sample of potentially missing symbols:")
                for file_path, lang, name in missing_symbols[:10]:
                    short_path = Path(file_path).name
                    result.details.append(f"  {short_path}: {name} ({lang})")

            self.report.results.append(result)
        else:
            print("  No scannable files found for completeness check")

    def _sample_project_files(self, sample_size: int, extensions: set) -> List[Path]:
        """Sample files from the project for completeness checking."""
        # Try to use ignore handler if available
        try:
            from ignore_handler import IgnoreHandler
            ignore_handler = IgnoreHandler(self.project_root)
        except ImportError:
            ignore_handler = None

        candidate_files: List[Path] = []

        for ext in extensions:
            pattern = f"**/*{ext}"
            for f in self.project_root.glob(pattern):
                # Skip common vendor directories
                path_str = str(f)
                if any(skip in path_str for skip in [
                    'node_modules', '.venv', 'venv', '__pycache__',
                    'vendor', 'target', 'build', 'dist', '.git'
                ]):
                    continue

                if ignore_handler:
                    try:
                        if ignore_handler.should_ignore(f):
                            continue
                    except Exception:
                        pass

                if f.is_file():
                    candidate_files.append(f)

                if len(candidate_files) >= sample_size * 10:
                    break

        # Random sample
        import random
        if len(candidate_files) > sample_size:
            return random.sample(candidate_files, sample_size)
        return candidate_files

    def format_report(self, format: str = "table") -> str:
        """Format the validation report."""
        if format == "json":
            return json.dumps({
                "project": self.report.project_root,
                "detected_stack": self.report.detected_stack,
                "summary": {
                    "overall_accuracy": self.report.overall_accuracy,
                    "total_checks": self.report.total_checks,
                    "passed": self.report.passed_checks,
                    "target_met": self.report.overall_accuracy >= 0.95
                },
                "checks": [
                    {
                        "name": r.check_name,
                        "category": r.category,
                        "accuracy": r.accuracy,
                        "valid": r.valid_count,
                        "invalid": r.invalid_count,
                        "total": r.total_checked,
                        "passed": r.passed,
                        "issues": r.details[:5] if r.details else []
                    }
                    for r in self.report.results
                ],
                "errors": self.report.errors
            }, indent=2)

        # Table format
        lines = [
            "## Accuracy Validation Report",
            "",
            f"**Project**: {self.report.project_root}",
            f"**Languages**: {', '.join(self.report.detected_stack.get('languages', ['unknown']))}",
            f"**Frameworks**: {', '.join(self.report.detected_stack.get('frameworks', ['none']))}",
            "",
            "### Summary",
            "",
            f"- **Overall Accuracy**: {self.report.overall_accuracy:.1%}",
            f"- **Target (95%)**: {'✓ MET' if self.report.overall_accuracy >= 0.95 else '✗ NOT MET'}",
            f"- **Checks Passed**: {self.report.passed_checks}/{self.report.total_checks}",
            "",
            "### Validation Results",
            "",
            "| Check | Category | Accuracy | Valid | Invalid | Status |",
            "|-------|----------|----------|-------|---------|--------|"
        ]

        for r in self.report.results:
            status = "✓" if r.passed else "✗"
            lines.append(
                f"| {r.check_name} | {r.category} | {r.accuracy:.1%} | "
                f"{r.valid_count} | {r.invalid_count} | {status} |"
            )

        # Show issues for failing checks
        failing = [r for r in self.report.results if not r.passed and r.details]
        if failing:
            lines.extend(["", "### Issues Found", ""])
            for r in failing:
                lines.append(f"**{r.check_name}** ({r.accuracy:.1%}):")
                for detail in r.details[:5]:
                    lines.append(f"  - {detail}")
                if len(r.details) > 5:
                    lines.append(f"  - ... and {len(r.details) - 5} more")

        lines.extend([
            "",
            "### Validation Categories",
            "",
            "- **existence**: Symbols exist at stated file/line locations",
            "- **reference**: Reference targets exist in the graph",
            "- **traceability**: Lineage paths have valid endpoints",
            "- **framework**: Framework-specific patterns are correct",
            "- **completeness**: Symbols found in source are indexed (--deep mode)",
        ])

        return "\n".join(lines)

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Validate wicked-search accuracy using consistency checks"
    )
    parser.add_argument("--db", required=True, help="Path to the symbol graph database")
    parser.add_argument("--project", required=True, help="Project root directory")
    parser.add_argument("--sample-size", type=int, default=100, help="Samples per check (default: 100)")
    parser.add_argument("--format", choices=["table", "json"], default="table", help="Output format")
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Run deep completeness check (discovers what's missing from index)"
    )

    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Error: Database not found: {args.db}")
        return 1

    if not Path(args.project).exists():
        print(f"Error: Project not found: {args.project}")
        return 1

    validator = AccuracyValidator(args.db, args.project)

    try:
        validator.validate_all(args.sample_size, deep=args.deep)
        print()
        print(validator.format_report(args.format))
        return 0 if validator.report.overall_accuracy >= 0.95 else 1
    finally:
        validator.close()


if __name__ == "__main__":
    sys.exit(main())

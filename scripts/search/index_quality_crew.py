#!/usr/bin/env python3
"""
Index Quality Crew for wicked-search.

Uses coordinated subagents to intelligently validate and improve index quality.
Unlike pattern-matching approaches, agents analyze the codebase to understand
its structure and create targeted extraction strategies.

Agent Workflow:
1. Scout Agent - Explores codebase, discovers actual structure
2. Strategy Agent - Creates extraction plan based on discoveries
3. Validator Agent - Reviews plan to prevent plateau/loops
4. Executor - Runs approved extraction scripts

The crew runs until ≥95% quality or detects no further progress possible.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class Discovery:
    """A discovered pattern or structure in the codebase."""
    category: str  # services, database, ui, objects
    pattern_type: str  # file_location, annotation, naming_convention
    description: str
    examples: List[str] = field(default_factory=list)
    file_patterns: List[str] = field(default_factory=list)
    regex_patterns: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class ExtractionPlan:
    """A plan for extracting symbols."""
    plan_id: str
    discoveries: List[Discovery]
    scripts_to_generate: List[Dict[str, Any]]
    expected_symbols: int
    rationale: str
    approved: bool = False
    rejection_reason: Optional[str] = None


@dataclass
class QualityState:
    """Current quality state."""
    iteration: int
    services_accuracy: float = 0.0
    database_accuracy: float = 0.0
    ui_accuracy: float = 0.0
    objects_accuracy: float = 0.0
    overall_accuracy: float = 0.0
    total_symbols: int = 0
    previous_hash: str = ""  # To detect plateau


class ScoutAgent:
    """Explores codebase to discover actual structure and patterns."""

    def __init__(self, project_root: Path, conn: sqlite3.Connection):
        self.project_root = project_root
        self.conn = conn
        self.skip_dirs = {'.venv', 'venv', 'node_modules', '.git', 'dist',
                         'build', 'target', '__pycache__', 'vendor'}

    def scout(self, category: str) -> List[Discovery]:
        """Scout for patterns in a specific category."""
        if category == 'services':
            return self._scout_services()
        elif category == 'database':
            return self._scout_database()
        elif category == 'ui':
            return self._scout_ui()
        else:
            return self._scout_objects()

    def _scout_services(self) -> List[Discovery]:
        """Discover service layer patterns."""
        discoveries = []

        # Strategy 1: Find files with service-related annotations
        annotation_findings = self._find_annotated_files([
            '@Service', '@Controller', '@RestController', '@Component',
            '@RequestMapping', '@GetMapping', '@PostMapping',
            '@app.route', '@router.', 'app.get(', 'app.post(',
        ])

        if annotation_findings:
            # Analyze what directories these are in
            dirs = self._extract_common_directories(annotation_findings)
            discoveries.append(Discovery(
                category='services',
                pattern_type='annotation_based',
                description=f"Found {len(annotation_findings)} files with service annotations",
                examples=annotation_findings[:5],
                file_patterns=[f"**/{d}/**/*" for d in dirs],
                regex_patterns=self._build_service_patterns(annotation_findings),
                confidence=0.9
            ))

        # Strategy 2: Find by directory naming convention
        service_dirs = self._find_directories_by_name([
            'service', 'services', 'controller', 'controllers',
            'api', 'rest', 'endpoint', 'endpoints', 'routes', 'handlers'
        ])

        if service_dirs:
            discoveries.append(Discovery(
                category='services',
                pattern_type='directory_convention',
                description=f"Found {len(service_dirs)} service-related directories",
                examples=[str(d) for d in service_dirs[:5]],
                file_patterns=[f"{d.relative_to(self.project_root)}/**/*" for d in service_dirs],
                confidence=0.7
            ))

        return discoveries

    def _scout_database(self) -> List[Discovery]:
        """Discover database/entity layer patterns."""
        discoveries = []

        # Strategy 1: Find @Entity, models.Model, etc.
        entity_findings = self._find_annotated_files([
            '@Entity', '@Table', '@Column', '@Id',
            'models.Model', 'db.Model', 'Base = declarative_base',
            'class.*ActiveRecord', 'belongs_to', 'has_many',
        ])

        if entity_findings:
            dirs = self._extract_common_directories(entity_findings)
            discoveries.append(Discovery(
                category='database',
                pattern_type='orm_annotations',
                description=f"Found {len(entity_findings)} files with ORM patterns",
                examples=entity_findings[:5],
                file_patterns=[f"**/{d}/**/*" for d in dirs],
                regex_patterns=self._build_entity_patterns(entity_findings),
                confidence=0.9
            ))

        # Strategy 2: Find by directory naming
        entity_dirs = self._find_directories_by_name([
            'entity', 'entities', 'model', 'models', 'domain',
            'dao', 'repository', 'repositories', 'schema'
        ])

        if entity_dirs:
            discoveries.append(Discovery(
                category='database',
                pattern_type='directory_convention',
                description=f"Found {len(entity_dirs)} entity-related directories",
                examples=[str(d) for d in entity_dirs[:5]],
                file_patterns=[f"{d.relative_to(self.project_root)}/**/*" for d in entity_dirs],
                confidence=0.7
            ))

        return discoveries

    def _scout_ui(self) -> List[Discovery]:
        """Discover UI layer patterns."""
        discoveries = []

        # Find component files
        component_patterns = ['*.tsx', '*.jsx', '*.vue', '*.svelte']
        component_dirs = set()

        for pattern in component_patterns:
            for f in self.project_root.rglob(pattern):
                if not any(skip in f.parts for skip in self.skip_dirs):
                    # Check if it's a component (PascalCase name or in components dir)
                    if f.stem[0].isupper() or 'component' in str(f.parent).lower():
                        component_dirs.add(f.parent)

        if component_dirs:
            discoveries.append(Discovery(
                category='ui',
                pattern_type='component_files',
                description=f"Found {len(component_dirs)} component directories",
                examples=[str(d) for d in list(component_dirs)[:5]],
                file_patterns=[f"{d.relative_to(self.project_root)}/*" for d in list(component_dirs)[:10]],
                regex_patterns={
                    'component': r'(?:export\s+)?(?:function|const)\s+([A-Z]\w+)',
                    'hook': r'(?:export\s+)?(?:function|const)\s+(use\w+)',
                },
                confidence=0.8
            ))

        return discoveries

    def _scout_objects(self) -> List[Discovery]:
        """Discover general object/class patterns."""
        discoveries = []

        # Sample files to understand the language mix
        lang_samples = self._sample_by_language()

        for lang, files in lang_samples.items():
            if files:
                discoveries.append(Discovery(
                    category='objects',
                    pattern_type=f'{lang}_classes',
                    description=f"Found {len(files)} {lang} files to index",
                    examples=files[:5],
                    file_patterns=self._get_lang_patterns(lang),
                    regex_patterns=self._get_lang_class_patterns(lang),
                    confidence=0.95
                ))

        return discoveries

    def _find_annotated_files(self, patterns: List[str]) -> List[str]:
        """Find files containing specific annotations/patterns."""
        found = []
        file_patterns = ['*.java', '*.py', '*.ts', '*.js', '*.rb']

        for fp in file_patterns:
            for f in self.project_root.rglob(fp):
                if any(skip in f.parts for skip in self.skip_dirs):
                    continue
                try:
                    content = f.read_text(errors='ignore')[:5000]  # Only check first 5KB
                    if any(p in content for p in patterns):
                        found.append(str(f))
                        if len(found) >= 50:  # Limit sample
                            return found
                except Exception:
                    pass

        return found

    def _find_directories_by_name(self, keywords: List[str]) -> List[Path]:
        """Find directories containing keywords."""
        found = []
        for d in self.project_root.rglob('*'):
            if d.is_dir() and not any(skip in d.parts for skip in self.skip_dirs):
                name_lower = d.name.lower()
                if any(kw in name_lower for kw in keywords):
                    found.append(d)
        return found

    def _extract_common_directories(self, files: List[str]) -> List[str]:
        """Extract common directory patterns from file list."""
        dir_counts: Dict[str, int] = {}
        for f in files:
            parts = Path(f).parts
            for i, part in enumerate(parts):
                # Look for meaningful directory names
                if part.lower() in ('src', 'main', 'java', 'python', 'app', 'lib'):
                    continue
                if len(part) > 2 and not part.startswith('.'):
                    dir_counts[part] = dir_counts.get(part, 0) + 1

        # Return most common directories
        sorted_dirs = sorted(dir_counts.items(), key=lambda x: -x[1])
        return [d for d, _ in sorted_dirs[:5] if dir_counts[d] >= 2]

    def _build_service_patterns(self, files: List[str]) -> Dict[str, str]:
        """Build regex patterns for service extraction."""
        # Detect language from files
        langs = set(Path(f).suffix for f in files)

        patterns = {}
        if '.java' in langs:
            patterns['service_class'] = r'@(?:Service|Component|RestController|Controller)[^)]*\s*public\s+class\s+(\w+)'
            patterns['endpoint_method'] = r'@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)[^)]*\s*public\s+\w+\s+(\w+)'
        if '.py' in langs:
            patterns['view_class'] = r'class\s+(\w+).*(?:View|ViewSet|APIView)'
            patterns['route_func'] = r'@(?:app|router)\.\w+\([^)]*\)\s*(?:async\s+)?def\s+(\w+)'
        if '.ts' in langs or '.js' in langs:
            patterns['controller'] = r'@Controller\([^)]*\)\s*export\s+class\s+(\w+)'
            patterns['handler'] = r'(?:app|router)\.(?:get|post|put|delete)\([^,]+,\s*(\w+)'

        return patterns

    def _build_entity_patterns(self, files: List[str]) -> Dict[str, str]:
        """Build regex patterns for entity extraction."""
        langs = set(Path(f).suffix for f in files)

        patterns = {}
        if '.java' in langs:
            patterns['entity'] = r'@Entity[^)]*\s*(?:public\s+)?class\s+(\w+)'
            patterns['field'] = r'(?:@Column|@Id|@JoinColumn)[^)]*\s*(?:private|protected)\s+\w+\s+(\w+)'
        if '.py' in langs:
            patterns['model'] = r'class\s+(\w+)\s*\(.*(?:Model|Base).*\)'
            patterns['field'] = r'(\w+)\s*=\s*(?:models|db)\.\w+Field'

        return patterns

    def _sample_by_language(self) -> Dict[str, List[str]]:
        """Sample files by language."""
        samples: Dict[str, List[str]] = {}
        ext_lang = {'.java': 'java', '.py': 'python', '.ts': 'typescript',
                    '.tsx': 'typescript', '.js': 'javascript', '.go': 'go'}

        for ext, lang in ext_lang.items():
            files = []
            for f in self.project_root.rglob(f'*{ext}'):
                if not any(skip in f.parts for skip in self.skip_dirs):
                    files.append(str(f))
                    if len(files) >= 20:
                        break
            if files:
                samples[lang] = files

        return samples

    def _get_lang_patterns(self, lang: str) -> List[str]:
        """Get file patterns for a language."""
        return {
            'java': ['**/*.java'],
            'python': ['**/*.py'],
            'typescript': ['**/*.ts', '**/*.tsx'],
            'javascript': ['**/*.js', '**/*.jsx'],
            'go': ['**/*.go'],
        }.get(lang, [])

    def _get_lang_class_patterns(self, lang: str) -> Dict[str, str]:
        """Get class extraction patterns for a language."""
        return {
            'java': {
                'class': r'(?:public|private)?\s*(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)',
                'method': r'(?:public|private|protected)\s+(?:static\s+)?(?:\w+)\s+(\w+)\s*\(',
            },
            'python': {
                'class': r'^class\s+(\w+)',
                'function': r'^(?:async\s+)?def\s+(\w+)',
            },
            'typescript': {
                'class': r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)',
                'interface': r'(?:export\s+)?interface\s+(\w+)',
                'function': r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',
            },
            'javascript': {
                'class': r'class\s+(\w+)',
                'function': r'(?:async\s+)?function\s+(\w+)',
            },
            'go': {
                'type': r'^type\s+(\w+)\s+(?:struct|interface)',
                'func': r'^func\s+(?:\([^)]+\)\s+)?(\w+)',
            },
        }.get(lang, {})


class StrategyAgent:
    """Creates extraction plans based on scout discoveries."""

    def __init__(self, conn: sqlite3.Connection, scripts_dir: Path):
        self.conn = conn
        self.scripts_dir = scripts_dir

    def create_plan(self, discoveries: List[Discovery], current_state: QualityState) -> ExtractionPlan:
        """Create an extraction plan from discoveries."""
        plan_id = hashlib.md5(
            f"{current_state.iteration}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8]

        scripts = []
        expected_symbols = 0

        for discovery in discoveries:
            if discovery.confidence >= 0.5 and discovery.regex_patterns:
                script_spec = {
                    'name': f"{discovery.category}_{discovery.pattern_type}_extractor.py",
                    'category': discovery.category,
                    'file_patterns': discovery.file_patterns,
                    'regex_patterns': discovery.regex_patterns,
                    'description': discovery.description,
                }
                scripts.append(script_spec)
                # Estimate symbols based on example count
                expected_symbols += len(discovery.examples) * 10

        rationale = self._build_rationale(discoveries, current_state)

        return ExtractionPlan(
            plan_id=plan_id,
            discoveries=discoveries,
            scripts_to_generate=scripts,
            expected_symbols=expected_symbols,
            rationale=rationale
        )

    def _build_rationale(self, discoveries: List[Discovery], state: QualityState) -> str:
        """Build rationale for the plan."""
        parts = [f"Iteration {state.iteration + 1}:"]

        for d in discoveries:
            parts.append(f"- {d.category}: {d.description} (confidence: {d.confidence:.0%})")

        parts.append(f"Current accuracy: {state.overall_accuracy:.1%}")
        parts.append(f"Target: 95%")

        return '\n'.join(parts)


class ValidatorAgent:
    """Reviews and validates extraction plans."""

    def __init__(self, history: List[Tuple[str, float]]):
        self.history = history  # (plan_hash, accuracy_after)

    def validate(self, plan: ExtractionPlan, current_state: QualityState) -> Tuple[bool, Optional[str]]:
        """Validate a plan. Returns (approved, rejection_reason)."""

        # Check 1: Must have actionable scripts
        if not plan.scripts_to_generate:
            return False, "No extraction scripts to generate"

        # Check 2: Check for plateau (same state hash)
        plan_hash = self._compute_plan_hash(plan)
        recent_hashes = [h for h, _ in self.history[-3:]]
        if plan_hash in recent_hashes:
            return False, f"Plan appears to repeat previous iteration (hash: {plan_hash})"

        # Check 3: Check discoveries have sufficient confidence
        avg_confidence = sum(d.confidence for d in plan.discoveries) / len(plan.discoveries) if plan.discoveries else 0
        if avg_confidence < 0.5:
            return False, f"Low confidence discoveries (avg: {avg_confidence:.0%})"

        # Check 4: Ensure we're not stuck (accuracy not improving)
        if len(self.history) >= 2:
            recent_accuracies = [acc for _, acc in self.history[-2:]]
            if all(abs(acc - current_state.overall_accuracy) < 0.01 for acc in recent_accuracies):
                # Accuracy hasn't changed in 2 iterations
                # But approve if we have new discovery types
                existing_types = set()
                for h, _ in self.history:
                    existing_types.add(h.split(':')[0] if ':' in h else h)

                new_types = {d.pattern_type for d in plan.discoveries}
                if not (new_types - existing_types):
                    return False, "Accuracy plateau detected with no new discovery types"

        return True, None

    def _compute_plan_hash(self, plan: ExtractionPlan) -> str:
        """Compute hash of plan for plateau detection."""
        parts = [f"{d.category}:{d.pattern_type}" for d in plan.discoveries]
        return hashlib.md5(':'.join(sorted(parts)).encode()).hexdigest()[:8]


class Executor:
    """Executes approved extraction plans."""

    def __init__(self, project_root: Path, db_path: str, scripts_dir: Path):
        self.project_root = project_root
        self.db_path = db_path
        self.scripts_dir = scripts_dir
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, plan: ExtractionPlan) -> int:
        """Execute a plan. Returns number of symbols added."""
        total_added = 0

        for script_spec in plan.scripts_to_generate:
            script_path = self._generate_script(script_spec)
            added = self._run_script(script_path)
            total_added += added

        return total_added

    def _generate_script(self, spec: Dict[str, Any]) -> Path:
        """Generate extraction script from spec."""
        script_path = self.scripts_dir / spec['name']

        script = f'''#!/usr/bin/env python3
"""
Auto-generated extraction script.
Category: {spec['category']}
Description: {spec['description']}
"""

import re
import sqlite3
import sys
from pathlib import Path


def extract_symbols(project_root: Path, db_path: str):
    conn = sqlite3.connect(db_path)
    skip_dirs = {{'.venv', 'venv', 'node_modules', '.git', 'dist', 'build', 'target', '__pycache__'}}
    count = 0

    file_patterns = {repr(spec['file_patterns'])}
    regex_patterns = {repr(spec['regex_patterns'])}

    for file_pattern in file_patterns:
        for file_path in project_root.glob(file_pattern):
            if any(skip in file_path.parts for skip in skip_dirs):
                continue

            try:
                content = file_path.read_text(errors='ignore')

                for pattern_name, regex in regex_patterns.items():
                    for match in re.finditer(regex, content, re.MULTILINE):
                        name = match.group(1)
                        if len(name) > 2:
                            line = content[:match.start()].count('\\n') + 1
                            sym_id = f"{{pattern_name}}:{{file_path.name}}:{{name}}:{{line}}"

                            try:
                                conn.execute(
                                    "INSERT OR IGNORE INTO symbols VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (sym_id, name, pattern_name, str(file_path), line, line, name)
                                )
                                count += 1
                            except sqlite3.Error:
                                pass
            except Exception:
                pass

    conn.commit()
    conn.close()
    print(f"Added {{count}} symbols")
    return count


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: script.py <project_root> <db_path>")
        sys.exit(1)
    extract_symbols(Path(sys.argv[1]), sys.argv[2])
'''
        script_path.write_text(script)
        return script_path

    def _run_script(self, script_path: Path) -> int:
        """Run extraction script."""
        try:
            result = subprocess.run(
                ['python3', str(script_path), str(self.project_root), self.db_path],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                # Parse "Added X symbols" from output
                import re
                match = re.search(r'Added (\d+) symbols', result.stdout)
                return int(match.group(1)) if match else 0
            return 0
        except Exception:
            return 0


class IndexQualityCrew:
    """Coordinates agents to achieve quality threshold."""

    QUALITY_THRESHOLD = 0.95
    MAX_ITERATIONS = 10

    def __init__(self, db_path: str, project_root: str):
        self.db_path = db_path
        self.project_root = Path(project_root)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        self.scripts_dir = Path.home() / "something-wicked" / "wicked-search" / "tmp_scripts"

        # Initialize agents
        self.scout = ScoutAgent(self.project_root, self.conn)
        self.strategy = StrategyAgent(self.conn, self.scripts_dir)
        self.executor = Executor(self.project_root, db_path, self.scripts_dir)

        # History for plateau detection
        self.history: List[Tuple[str, float]] = []

    def run(self, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """Run the crew until quality threshold met."""
        max_iter = max_iterations or self.MAX_ITERATIONS

        print("=== Index Quality Crew ===")
        print(f"Project: {self.project_root}")
        print(f"Target: ≥{self.QUALITY_THRESHOLD:.0%}")
        print()

        for iteration in range(1, max_iter + 1):
            print(f"--- Iteration {iteration} ---")

            # 1. Get current state
            state = self._get_current_state(iteration)
            print(f"Current: {state.overall_accuracy:.1%} ({state.total_symbols} symbols)")

            if state.overall_accuracy >= self.QUALITY_THRESHOLD:
                print(f"\n✓ Quality threshold met!")
                return self._build_report(state, 'PASSED')

            # 2. Scout for discoveries
            print("Scouting...")
            all_discoveries = []
            for category in ['services', 'database', 'ui', 'objects']:
                discoveries = self.scout.scout(category)
                all_discoveries.extend(discoveries)
                for d in discoveries:
                    print(f"  Found: {d.category}/{d.pattern_type} ({d.confidence:.0%})")

            if not all_discoveries:
                print("No discoveries - stopping")
                return self._build_report(state, 'NO_DISCOVERIES')

            # 3. Create plan
            print("Planning...")
            plan = self.strategy.create_plan(all_discoveries, state)
            print(f"  Plan: {len(plan.scripts_to_generate)} scripts, ~{plan.expected_symbols} symbols")

            # 4. Validate plan
            validator = ValidatorAgent(self.history)
            approved, reason = validator.validate(plan, state)

            if not approved:
                print(f"  Plan rejected: {reason}")
                # Try to recover by forcing new discovery approach
                if 'plateau' in (reason or '').lower():
                    return self._build_report(state, 'PLATEAU')
                continue

            print("  Plan approved")

            # 5. Execute plan
            print("Executing...")
            symbols_added = self.executor.execute(plan)
            print(f"  Added {symbols_added} symbols")

            # 6. Update history
            self.history.append((
                hashlib.md5(plan.plan_id.encode()).hexdigest()[:8],
                state.overall_accuracy
            ))

            print()

        # Max iterations reached
        final_state = self._get_current_state(max_iter)
        return self._build_report(final_state, 'MAX_ITERATIONS')

    def _get_current_state(self, iteration: int) -> QualityState:
        """Get current quality state."""
        state = QualityState(iteration=iteration)

        # Count total symbols
        cursor = self.conn.execute("SELECT COUNT(*) FROM symbols")
        state.total_symbols = cursor.fetchone()[0]

        # Sample-based accuracy for each category
        state.services_accuracy = self._check_category_accuracy('services')
        state.database_accuracy = self._check_category_accuracy('database')
        state.ui_accuracy = self._check_category_accuracy('ui')
        state.objects_accuracy = self._check_category_accuracy('objects')

        # Overall is average of non-zero categories
        accuracies = [a for a in [state.services_accuracy, state.database_accuracy,
                                   state.ui_accuracy, state.objects_accuracy] if a > 0]
        state.overall_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0

        return state

    def _check_category_accuracy(self, category: str) -> float:
        """Check accuracy for a category using sampling."""
        # Get sample of indexed symbols for this category
        type_map = {
            'services': ['service', 'controller', 'endpoint', 'handler', 'route_func', 'view_class'],
            'database': ['entity', 'model', 'field', 'repository'],
            'ui': ['component', 'hook'],
            'objects': ['class', 'interface', 'function', 'method', 'type'],
        }

        types = type_map.get(category, [])
        if not types:
            return 1.0

        placeholders = ','.join('?' * len(types))
        cursor = self.conn.execute(f"""
            SELECT name, file_path, line_start FROM symbols
            WHERE type IN ({placeholders})
            ORDER BY RANDOM() LIMIT 50
        """, types)

        rows = cursor.fetchall()
        if not rows:
            return 0.0  # No symbols of this type indexed

        valid = 0
        for row in rows:
            if self._verify_symbol(row['name'], row['file_path'], row['line_start']):
                valid += 1

        return valid / len(rows)

    def _verify_symbol(self, name: str, file_path: str, line_start: int) -> bool:
        """Verify a symbol exists at stated location."""
        try:
            path = Path(file_path)
            if not path.exists():
                return False

            content = path.read_text(errors='ignore')
            lines = content.split('\n')
            line_num = line_start or 1

            # Check if name appears near stated line
            search_range = range(max(0, line_num - 3), min(len(lines), line_num + 3))
            return any(name in lines[i] for i in search_range)
        except Exception:
            return False

    def _build_report(self, state: QualityState, status: str) -> Dict[str, Any]:
        """Build final report."""
        return {
            'status': status,
            'iterations': state.iteration,
            'overall_accuracy': state.overall_accuracy,
            'total_symbols': state.total_symbols,
            'categories': {
                'services': state.services_accuracy,
                'database': state.database_accuracy,
                'ui': state.ui_accuracy,
                'objects': state.objects_accuracy,
            },
            'scripts_generated': list(self.scripts_dir.glob('*.py')),
            'passed': state.overall_accuracy >= self.QUALITY_THRESHOLD
        }

    def close(self):
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="Index quality crew")
    parser.add_argument("--db", required=True, help="Path to symbol graph database")
    parser.add_argument("--project", required=True, help="Project root directory")
    parser.add_argument("--max-iterations", type=int, default=10)

    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Error: Database not found: {args.db}")
        return 1

    crew = IndexQualityCrew(args.db, args.project)

    try:
        report = crew.run(args.max_iterations)

        print("\n=== Final Report ===")
        print(f"Status: {report['status']}")
        print(f"Iterations: {report['iterations']}")
        print(f"Overall accuracy: {report['overall_accuracy']:.1%}")
        print(f"Total symbols: {report['total_symbols']}")
        print("\nCategory accuracies:")
        for cat, acc in report['categories'].items():
            print(f"  {cat}: {acc:.1%}")

        return 0 if report['passed'] else 1
    finally:
        crew.close()


if __name__ == "__main__":
    sys.exit(main())

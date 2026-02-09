# Changelog

## [1.1.1] - 2026-02-08

### Features
- feat(wicked-qe): integrate with wicked-scenarios for E2E scenario discovery and execution (6538a71)
- feat(wicked-mem): add PostToolUse nudge for MEMORY.md direct edits (a15db3f)
- feat: add wicked-scenarios plugin for E2E testing via markdown scenarios (c7d4422)

### Documentation
- docs: rewrite all 17 plugin READMEs with sell-first structure (c30ebec)

### Chores
- chore: add wicked-scenarios to marketplace catalog (74de311)
- chore: remove old release notes replaced by new versions (39955d9)
- release: bump 8 plugins - dynamic flow, friction fixes, batch release (49dfd00)

## [1.1.0] - 2026-02-07

### Features
- feat: dynamic crew flow, usage friction fixes, batch release tooling (311401b)
- feat(wicked-mem): add TaskCompleted hook for memory capture prompt (531713c)
- feat(wicked-kanban): add TaskCompleted hook for reliable task sync (25057d3)
- feat(wicked-crew): replace hardcoded phases with flexible phases.json config (f8e7baa)

### Chores
- release: wicked-mem v0.3.2 (f46577e)
- release: wicked-kanban v0.4.0 (4824f18)
- release: wicked-crew v0.8.0 (7f48928)
- release: bump 12 plugins - onboarding fixes, mem hooks, crew features (d819228)

## [1.0.3] - 2026-02-06

### Features
- feat(wicked-crew): enforce sign-off verification in approve gate (ade44e2)
- feat(wicked-crew): add phase sign-off priority chain (cec0e13)
- feat(wicked-crew): add task lifecycle tracking to all crew agents (6254613)
- feat(wicked-patch): v1.0.0 - language-agnostic code generation (5e24b0b)
- feat(wicked-search): v1.0.0 - reasoning capabilities and index quality (4a1e6b3)
- feat: update existing plugins with enhanced capabilities (6ae5cfc)
- feat: add specialist plugins for domain expertise (4682037)
- feat(wicked-startah): add runtime-exec skill for Python/Node execution (55b1393)
- feat(wicked-search): add extensible parser/linker system with form binding support (ab18b36)
- feat(wicked-kanban): enhance TodoWrite hook for rich traceability (85d55c5)

### Bug Fixes
- fix(wicked-crew): enforce phase documentation and non-skippable review (d64a673)
- fix(wicked-mem): enforce memory storage with directive hook prompts (8703418)
- fix: resolve onboarding issues - ghost plugins, code defects, structure (d16c293)
- fix(wicked-mem,wicked-crew): memory filtering and task lifecycle improvements (c014f92)
- fix(hooks): update Stop hooks to use required JSON response format (6e1c236)
- fix(wicked-kanban): fix UI bugs and add security hardening (9ccbcd4)

### Documentation
- docs: standardize command prefixes and improve plugin READMEs (5129e89)

### Refactoring
- refactor: remove deprecated plugins consolidated into specialist plugins (a32a81f)

### Chores
- release: wicked-mem v0.3.0, wicked-kanban v0.3.10, wicked-crew v0.6.1 (044f1d2)
- chore: fix stale plugin names in scaffold and update hook standards (e6bfe62)
- chore: clean up repo garbage and auto-prune old release notes (eea12a8)
- release: bump all plugins, automate release pipeline, extract QE (769c540)
- chore: add wicked-patch to marketplace (62befa4)
- version updates (36c7444)
- chore: update plugin .gitignore files and crew hook script (7f263a2)
- chore: update dev tools and scaffolding templates (df55616)
- lots of stuff (278d71f)

## [1.0.2] - 2026-02-06

### Features
- feat(wicked-patch): v1.0.0 - language-agnostic code generation (5e24b0b)
- feat(wicked-search): v1.0.0 - reasoning capabilities and index quality (4a1e6b3)
- feat: update existing plugins with enhanced capabilities (6ae5cfc)
- feat: add specialist plugins for domain expertise (4682037)
- feat(wicked-startah): add runtime-exec skill for Python/Node execution (55b1393)
- feat(wicked-search): add extensible parser/linker system with form binding support (ab18b36)
- feat(wicked-kanban): enhance TodoWrite hook for rich traceability (85d55c5)

### Bug Fixes
- fix(wicked-mem,wicked-crew): memory filtering and task lifecycle improvements (c014f92)
- fix(hooks): update Stop hooks to use required JSON response format (6e1c236)
- fix(wicked-kanban): fix UI bugs and add security hardening (9ccbcd4)

### Documentation
- docs: standardize command prefixes and improve plugin READMEs (5129e89)

### Refactoring
- refactor: remove deprecated plugins consolidated into specialist plugins (a32a81f)

### Chores
- chore: add wicked-patch to marketplace (62befa4)
- version updates (36c7444)
- chore: update plugin .gitignore files and crew hook script (7f263a2)
- chore: update dev tools and scaffolding templates (df55616)
- lots of stuff (278d71f)

## [0.8.1] - 2026-02-01

### Fixed
- **SessionStart hook**: Fixed index detection using wrong hash algorithm
  - Hook used SHA256[:16] but unified_search.py uses MD5[:12]
  - Index now correctly detected on session start
- **Console formatting**: Replaced markdown `**bold**` with `[Tag]` prefix format
  - Output now displays cleanly in terminal without raw asterisks

## [0.8.0] - 2026-02-01

### Added
- **Adapter Pattern Architecture**: Extensible language parsing with `LanguageAdapter` ABC
  - `AdapterRegistry` with thread-safe caching and auto-discovery via `@register` decorator
  - 10 language adapters: Java, Python, TypeScript, Ruby, C#, Go, JSP, HTML, Vue
  - Shared utilities in `adapters/utils.py`: `NamingUtils`, `safe_text`, `safe_line`
- **Multi-ORM Data Lineage**: Entity-to-column mapping across 7 ORMs
  - Python: SQLAlchemy (`Column`, `mapped_column`), Django ORM (`models.CharField`, etc.)
  - TypeScript: TypeORM (`@Entity`, `@Column`), Prisma (`model`, `@id`)
  - Ruby: ActiveRecord (`belongs_to`, `has_many`, associations)
  - C#: Entity Framework (`[Table]`, `[Key]`, `[Column]`, navigation properties)
  - Go: GORM (struct tags with `gorm:"column:..."`)
- **Frontend Binding Extraction**: Vue SFC support with v-model, v-bind, v-on patterns

### Changed
- Unified file processing loop uses `AdapterRegistry` exclusively
- Removed 530+ lines of inline parsing from `unified_search.py`
- All regex patterns moved to class-level constants for performance
- Standardized metadata field names across all adapters (`base_class`, `table_name`)

### Fixed
- **Thread safety**: `AdapterRegistry` uses `threading.Lock` to prevent race conditions
- **Bounds checking**: C# brace counting now detects unbalanced braces
- **Code duplication**: `NamingUtils` consolidates `to_snake_case`, `pluralize`, `tableize`

## [0.7.1] - 2026-02-01

### Added
- **SessionStart hook**: Shows index status on session start
  - Displays symbol count, doc count, and last update time
  - Prompts to run `/wicked-search:index .` when no index exists

## [0.7.0] - 2026-02-01

### Added
- **Graph Export API**: Cross-plugin graph data sharing via wicked-cache
  - `GraphExporter` class: Exports SymbolGraph to cache with versioned schema
  - `GraphClient` class: Typed consumer API for reading cached graph data
  - Four query types: `symbol_dependencies`, `file_references`, `definition_lookup`, `call_chain`
  - Freshness metadata (timestamp + workspace hash) for staleness detection
  - Version compatibility checks between producer and consumer
- **graph-export skill**: Consumer skill documentation with examples
  - Cache schema reference
  - Usage patterns for common integration scenarios
  - Error handling guidance (CacheStaleError, VersionMismatchError)
- **--export-cache flag**: New index command option exports graph to wicked-cache
  - Integrates with existing `--export-graph` workflow
  - Auto-invalidates old cache entries before export
- **Incremental export support**: `export_incremental()` for changed-file updates
- **BFS call chain traversal**: Proper depth/path tracking for upstream and downstream analysis

### Fixed
- **Call chain depth/path**: Now uses BFS traversal with actual depth tracking (was stubbed)
- **Upstream transitive refs**: Call chain now includes transitive upstream dependencies (was direct only)
- **Filter hash ordering**: Canonicalized list values before hashing for consistent cache keys
- **Version mismatch errors**: Fixed potential KeyError when cache version missing
- **Filtered cache invalidation**: `invalidate_all()` now clears filtered variants too

## [0.6.0] - 2026-01-31

### Added
- **Missing version bump**: Internal version alignment

## [0.5.1] - 2026-01-31

### Fixed
- **Java parsing in Symbol Graph**: Fixed issue where Java files were not being parsed during `build_symbol_graph()`, resulting in 0 references from EL resolver
- **Cross-layer linking**: EL expressions now correctly resolve to Java entities (4,000+ binds_to references in test codebase)
- **Print statement consistency**: Symbol Graph build output now correctly shows Java file count

## [0.5.0] - 2026-01-31

### Added
- **Symbol Graph Model**: Unified representation across backend, view, frontend, and database layers
  - 20+ SymbolTypes: entity, controller, jsp_page, el_expression, component, data_binding, etc.
  - ReferenceTypes: binds_to, maps_to, returns_view, renders, extends, implements, etc.
  - Confidence scoring for inferred relationships (HIGH, MEDIUM, LOW, INFERRED)
- **Java Annotation Parsing**: Tree-sitter based extraction with enhanced java.scm query
  - `@Entity` classes → SymbolType.ENTITY with child ENTITY_FIELD symbols
  - `@Controller/@RestController` → SymbolType.CONTROLLER
  - `@Service` → SymbolType.SERVICE
  - `@Repository` → SymbolType.DAO
  - `@RequestMapping/@GetMapping/etc` → SymbolType.CONTROLLER_METHOD
  - Field annotations captured: `@Column`, `@Id`, `@JoinColumn`
- **Enhanced JSP Parser**: EL path decomposition and Spring form support
  - `${person.address.city}` → segments [person, address, city] with root_bean tracking
  - Spring form:input path bindings with segment decomposition
  - JSTL variable tracking (c:forEach, c:set)
  - Taglib and include relationship tracking
- **HTML/Frontend Parser**: React, Vue, Angular pattern detection
  - Framework auto-detection from content and extension
  - Component usage extraction (PascalCase, kebab-case)
  - Data binding patterns (v-model, [(ngModel)], {state.value})
  - Event handler extraction (@click, onClick, (click))
- **Plugin Pattern for Linkers**: Extensible linker architecture
  - `@register_linker` decorator for auto-discovery
  - `LinkerRegistry` for prioritized execution
  - Built-in linkers: el_resolver (priority 20), controller (30), frontend (40)
- **Cross-Layer Relationship Resolution**
  - EL expressions linked to Java entities via bean naming conventions
  - Controller methods linked to JSP views via naming conventions
  - Form bindings linked to entity fields
- **New CLI Commands**:
  - `graph` command: Build and query Symbol Graph with stats
  - `--export-graph` flag: Export Symbol Graph to JSON
  - `--export-db` flag: Export Symbol Graph to SQLite
  - `--list-linkers` flag: Show available linkers
  - `--no-resolve` flag: Skip linker resolution for faster indexing

### Changed
- Enhanced `queries/java.scm` to capture class/method/field annotations
- Symbol Graph exports include layer classification (backend, view, frontend, database)
- Linkers now implement `link_all()` abstract method with `resolve_all()` alias for compatibility

## [0.4.2] - 2026-01-31

### Added
- **SQL support**: Index and search SQL files (CREATE TABLE, CREATE VIEW, CTEs)
- **XML support**: Index and search XML files (elements, attributes)
- **HTML support**: Index and search HTML files (tags, attributes, scripts)
- **JSP support**: Custom parser extracts directives, taglibs, beans, JSTL tags, declarations, form fields

### Fixed
- **Build config**: Added `ignore_handler.py` to pyproject.toml for proper installation
- **CLI UX**: Show full help on invalid commands/options instead of just error message
- **SQL not ignored**: Removed `*.sql` from default ignore patterns

## [0.4.0] - 2026-01-31

### Added
- **JSONL reference graph**: New Pydantic-based graph model with streaming JSONL storage
- **Parallel indexing**: Multi-threaded file parsing with ThreadPoolExecutor
- **Hybrid lookup**: Exact ID → exact name → case-insensitive → fuzzy suggestions
- **Blast radius analysis**: Compute dependencies and dependents with BFS traversal
- **Incremental updates**: Fast path (~0.5s) when no files have changed
- **Quality suggestions**: Fuzzy matching with score filtering (≥70%) and length filtering
- **Gitignore support**: Respects `.gitignore` patterns via hierarchical `ignore_handler.py`
- **Document indexing**: Parse markdown, text, and binary docs (PDF/Office via kreuzberg)

### Removed
- **Legacy NetworkX code**: Removed `UnifiedGraph`, `UnifiedSearcher`, legacy dataclasses
- **Legacy index format**: JSON graph format replaced by JSONL
- **CrossRefDetector class**: Cross-references now computed in two-pass linking

### Changed
- JSONL is now the only index format (no `--legacy` flag)
- `find_references()` and `blast_radius()` use hybrid lookup with suggestions
- `_find_files()` uses single directory traversal (faster than per-extension glob)
- Staleness detection uses JSONL metadata file instead of in-memory dict

### Performance
- Index check (no changes): 0.5s (was 53s)
- Full index (12K files, 151K symbols): ~2 min
- Search/refs/blast-radius: ~3.4s (includes index load)

## [0.3.0] - 2026-01-30

### Added
- **Cross-file call detection**: Function/method calls now properly link across files
- **Tree-sitter query files**: Added 71 language-specific .scm query files for precise code parsing
- **Enhanced refs output**: Shows detailed relationship types (Called by, Calls, Inherited by, Inherits from, Defines, Defined by, Documented in)
- **Deduplication**: Removed duplicate entries in refs and call detection

### Fixed
- Call relationships now work across files (was limited to same-file only)
- Fixed tree-sitter capture name matching for call.function, call.method patterns
- Fixed pyproject.toml hatch build configuration

### Changed
- Commands now support multiple Python package managers (uv, poetry, venv, python3)
- Improved refs command grouping with semantic relationship names

## [0.2.11] - 2025-01-27

### Fixed
- Removed invalid PreToolUse hook with unsupported "condition" field
- Empty hooks.json - routing handled elsewhere

## [0.2.8] - 2026-01-26

### Fixed
- **BREAKING**: Removed hanging Python hooks that caused Claude Code to crash
- Replaced UserPromptSubmit/PostToolUse Python hooks with prompt-based PreToolUse hooks

### Added
- Auto-indexing: Search commands now automatically build/rebuild index when stale
- PreToolUse hook routes Grep calls to wicked-search for better results
- `ensure_fresh()` method checks file mtimes and rebuilds index as needed

### Changed
- No more manual `/wicked-search:index` required - index auto-maintains
- Glob allowed for file pattern matching, Grep redirected to wicked-search

## [0.2.5] - 2026-01-23

### Chores
- chore: marketplace validation and cleanup (3e350f1)
- initial check-in (98cb674)


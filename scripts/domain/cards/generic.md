# Language card: generic (every language without its own card; certified here for TS/JS only)

## comment syntax (by extension)
- C family, TS/JS, Java, Go, Rust, C#, Kotlin, PHP: `//` line comments; `/* ... */` and `/** ... */` blocks.
- Python, shell, Ruby, YAML, TOML: `#`.
- SQL: `--` and `/* ... */`.
- floor (unknown extension): no comment syntax; non-blank lines are code lines.

## declaration patterns (a range made only of these lines is dropped from the unidentified list)
- `^\s*import\b` (including `import type`), `^\s*export\s+(type\s+)?(\*|\{[^}]*\}?)\s*(from\b.*)?;?\s*$`, `^\s*\}?\s*from\s+['"].*['"];?\s*$`
- `^\s*export\s+default\s+\w+;?\s*$`, `^\s*(const|let|var)\s+\w+\s*=\s*require\(`, `^\s*["']use strict["'];?\s*$`
- `^\s*(package|use|using|namespace)\b`, `^\s*#\s*include\b`, `^\s*from\s+\S+\s+import\b`
- punctuation-only lines: `^\s*[\]\)\}]+[;,]?\s*$`
- type-only lines inside an interface or type literal: `^\s*(readonly\s+)?[\w$]+\??\s*:\s*[^=]+;?\s*$` when the enclosing block opener is `interface` or `type`.

## definition-looking regexes (a line matching one with no node starting there becomes a range start)
- `^\s*(export\s+)?(default\s+)?(async\s+)?function\*?\s+[\w$]+`
- `^\s*(export\s+)?(const|let|var)\s+[\w$]+\s*(:[^=]+)?=\s*(async\s*)?(\([^)]*\)|[\w$]+)\s*(:[^=]+)?=>`
- `^\s*(export\s+)?(const|let|var)\s+[A-Z][A-Z0-9_]+\s*(:[^=]+)?=` (top-level constant: a rule value)
- `^\s*(export\s+)?(abstract\s+)?class\s+[\w$]+`, `^\s*(export\s+)?(interface|type|enum)\s+[\w$]+`
- `^\s*(public|private|protected|static|async|\s)*[\w$]+\s*\([^)]*\)\s*(:[^{]+)?\{\s*$` (method)
- Python `^\s*(async\s+)?def\s+\w+`, `^\s*class\s+\w+`; Go `^func\s`; Rust `^\s*(pub\s+)?(async\s+)?fn\s`.

## structural splitter
- brace languages: brace-match from the definition line to its closing brace; a top-level statement otherwise ends at the `;` or the line before the next top-level definition.
- indent languages: the indented block under the definition line.
- data files (json, yaml, toml, ini): top-level key to the next top-level key.

## decision tokens (M7: a not_rule whose lines contain one goes to the validator)
`if`, `else`, `switch`, `case`, `default:`, `? :` (ternary), `&&`, `||`, `??`, `?.`, `throw`, `catch`, `return` inside a
condition, `filter(`, `find(`, `some(`, `every(`, `includes(`, `has(`, `startsWith(`, `endsWith(`, `test(`, `match(`,
comparison operators `===`, `!==`, `==`, `!=`, `<=`, `>=`, `<`, `>`, `Math.min(`, `Math.max(`, zod `.min(` `.max(` `.refine(` `.default(`.

## call-site greps (trigger fetch)
`\bX\(`, `\.X\(`, `new X\(`, `X\.call\(`, `await X\(`; for a constant or type: `\bX\b`.

## scan patterns (entry points and config, §3.1 A)
- HTTP routes: estate `serves` edges (endpoint nodes), plus text `\b(app|server|fastify|router|r)\.(get|post|put|delete|patch|route|all)\(\s*['"\`]` (registration line; the path literal follows).
- WebSocket / SSE: `\.(get|register)\(.*websocket`, `\bnew\s+WebSocketServer\(`.
- CLI: `bin` entries in every `package.json`; `\.command\(\s*['"\`]`; `process\.argv`; files under `bin/`, `cli/`, `cmd/`, `commands/`.
- Jobs, schedulers, consumers: `setInterval\(`, `cron`, `schedule`, `\.subscribe\(`, `\.on\(\s*['"\`][\w.:-]+['"\`]`, workflow YAML under `.github/workflows/` (CI only, listed, not product).
- Config: `process\.env\.([A-Z][A-Z0-9_]*)`, `process\.env\[\s*['"\`]([A-Z][A-Z0-9_]*)`, `getenv\(`, `os\.environ`, `System\.getenv\(`; settings schemas (`z\.object\(` in files whose name contains `setting` or `config`); JSON/YAML/TOML defaults files outside test dirs; feature flags (`flag`, `enabled` keys in settings schemas).

## semantics the model must get right
1. Early `return`/`throw` is a guard for every statement after it in the same block.
2. `a ?? b` uses b only when a is null or undefined; `a || b` also when a is falsy (0, '', false).
3. Optional chaining `a?.b` yields undefined, not an error, when a is nullish.
4. `Array.prototype.find` returns the first match or undefined; `some`/`every` short-circuit; `filter` keeps order.
5. A `Set`/`Map` membership test is exact string equality (case-sensitive).
6. zod: `.default(v)` applies only when the key is undefined; `.min`/`.max` are inclusive; `.catch(v)` replaces any invalid value.
7. A top-level `const` array or object can still be mutated (`push`, property set) unless frozen.

## platform facts (shown to the checker with every statement; DES-j6-v2 §1)
CARD FACTS (TypeScript / Node): `throw` leaves the function and skips every later line unless an enclosing try/catch catches it. `return` inside a callback (forEach, map, filter, find, some) returns from the callback only. Awaiting a rejected promise throws at the await. `process.env.X` is a string or undefined. `a ?? b` uses b only when a is null or undefined; `a || b` also when a is falsy. zod `.default(v)` applies only when the key is undefined; `.min`/`.max` are inclusive. A `Set`/`Map` lookup is exact, case-sensitive equality.

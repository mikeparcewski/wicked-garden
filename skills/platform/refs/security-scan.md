# Security Scan: Detect + Run + Triage

Run the real security scanners, then triage their actual output. Use for ad
hoc vulnerability scans on code, PRs, or full repos. NOT for compliance
evidence collection (use the `audit` sub-skill) or IaC posture (use the
`infra` action).

This rubric does NOT grep-guess. It detects which scanners are installed, runs
the ones that exist, and feeds their findings to triage. A missing scanner is
reported and skipped — the scan never fails because a tool is absent.

## 1. Detect + run scanners

Set `TARGET` to the requested path (default `.` if empty, or the PR's changed
files when given a PR number). Then run, gracefully skipping any absent tool:

```bash
SC=$(command -v semgrep || true); GL=$(command -v gitleaks || true); NPM=$(command -v npm || true)
TMP="${TMPDIR:-/tmp}"
# Secrets — gitleaks. NOTE: exit 1 means "leaks found", NOT a tool error; ignore exit code, read the JSON.
[ -n "$GL" ] && gitleaks detect --no-banner --redact -f json --report-path "$TMP/gitleaks.json" >/dev/null 2>&1; echo "gitleaks: ${GL:-ABSENT}"
# SAST — semgrep auto ruleset (carries CWE/OWASP/severity per finding).
[ -n "$SC" ] && semgrep --config auto --json "$TARGET" > "$TMP/semgrep.json" 2>/dev/null; echo "semgrep: ${SC:-ABSENT}"
# Dependencies — npm audit, only where a package.json exists.
[ -n "$NPM" ] && [ -f "$TARGET/package.json" ] && (cd "$TARGET" && npm audit --json > "$TMP/npm-audit.json" 2>/dev/null); echo "npm: ${NPM:-ABSENT}"
```

Read whichever report files exist (paths printed `ABSENT` were skipped — say
so in the report, don't treat it as a failure):

- `$TMP/gitleaks.json` — JSON array; each: `RuleID`, `Description`, `File`, `StartLine`, `Match`/`Secret` (redacted), `Entropy`, `Commit`. Scans full git **history** by default, so many hits are old/example secrets in docs — triage accordingly.
- `$TMP/semgrep.json` — `{results:[{check_id, path, start.line, extra:{severity (ERROR|WARNING|INFO), message, metadata:{cwe, owasp}}}], errors[]}`.
- `$TMP/npm-audit.json` — `{vulnerabilities:{<pkg>:{severity, via, range}}, metadata.vulnerabilities:{critical,high,...}}`.

## 2. Triage the real findings

Read `${CLAUDE_PLUGIN_ROOT}/skills/platform-security-engineer/SKILL.md` for
the triage rubric (your reference, NOT a thing to re-derive): the CWE table,
severity bands, OWASP matrix, output format, `--scenarios` behaviour, and bus
emit.

Your job is to triage actual scanner output, not guess: dedupe, drop false
positives (e.g. example secrets in `*.md`/scenarios, test fixtures), keep
semgrep's own `cwe`/`owasp`/`severity` (don't reinvent them), and rank true
findings CRITICAL→LOW with `file:line`. If `--scenarios` is set, emit a
wicked-scenarios block per surviving CRITICAL/HIGH. Report risk level, the
severity-ranked findings table, the OWASP matrix, prioritized fixes, and
which scanners were ABSENT/skipped.

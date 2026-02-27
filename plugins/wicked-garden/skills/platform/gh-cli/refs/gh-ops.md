# gh_ops.py Reference

Unified GitHub operations CLI with intelligent features.

## Commands

### diagnose

Analyze failed workflow runs with categorized errors.

```bash
python3 gh_ops.py diagnose
python3 gh_ops.py diagnose --repo owner/name
python3 gh_ops.py diagnose --suggest-fixes
```

**Error categories detected:**
- npm/node dependency issues
- Python import errors
- Rust compilation errors
- Resource limits (OOM)
- Rate limiting
- Permission issues
- Timeouts

### pr-review-queue

List PRs requesting your review across all repos.

```bash
python3 gh_ops.py pr-review-queue
```

### pr-merge-ready

Find PRs that are approved, passing CI, and mergeable.

```bash
python3 gh_ops.py pr-merge-ready --dry-run
```

### pr-status

Comprehensive PR status with checks, reviews, and stats.

```bash
python3 gh_ops.py pr-status 123
python3 gh_ops.py pr-status 123 --repo owner/name
```

### release

Auto-generate release with changelog from commits.

```bash
# Preview
python3 gh_ops.py release --dry-run

# Create patch release
python3 gh_ops.py release --bump patch

# Minor release with notes
python3 gh_ops.py release --bump minor --notes "Breaking: new API"
```

**Changelog categories:**
- Features: commits starting with "feat" or containing "add"
- Bug Fixes: commits starting with "fix" or containing "bug"
- Changes: everything else (excludes merge commits)

### health

Repository health check.

```bash
python3 gh_ops.py health
python3 gh_ops.py health --repo owner/name
```

**Checks:**
- Branch protection enabled
- Security advisories count
- Open Dependabot alerts
- Recent CI failure rate

## Output Format

All commands output JSON for easy parsing:

```bash
# Pretty print
python3 gh_ops.py diagnose | jq '.'

# Extract just errors
python3 gh_ops.py diagnose | jq '.errors[].message'

# Get PR URLs needing review
python3 gh_ops.py pr-review-queue | jq '.[].url'
```

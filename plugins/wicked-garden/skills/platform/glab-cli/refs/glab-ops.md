# glab_ops.py Reference

GitLab operations CLI with intelligent features.

## Commands

### diagnose

Analyze failed pipelines with categorized errors.

```bash
python3 glab_ops.py diagnose
python3 glab_ops.py diagnose --project group/project
python3 glab_ops.py diagnose --suggest-fixes
```

**Error categories:**
- npm/node dependency issues
- Python import errors
- Rust compilation errors
- Resource limits
- Network issues

### mr-review-queue

List MRs requesting your review.

```bash
python3 glab_ops.py mr-review-queue
```

### mr-merge-ready

Find MRs approved and passing CI.

```bash
python3 glab_ops.py mr-merge-ready --dry-run
```

### mr-status

Get MR details.

```bash
python3 glab_ops.py mr-status 123
python3 glab_ops.py mr-status 123 --project group/name
```

### release

Create release with changelog.

```bash
# Preview
python3 glab_ops.py release --dry-run

# Create
python3 glab_ops.py release --bump minor

# With notes
python3 glab_ops.py release --notes "Breaking change"
```

## Output Format

All commands output JSON:

```bash
# Pretty print
python3 glab_ops.py diagnose | jq '.'

# Extract errors
python3 glab_ops.py diagnose | jq '.errors[].message'
```

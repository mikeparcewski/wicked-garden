# Release {{component}} v{{version}}

**Date**: {{date}}
**Component**: {{component}}

## Summary

{{summary}}

## Changes

### Breaking Changes

{{#breaking_changes}}
- {{message}} ({{hash}})
{{/breaking_changes}}
{{^breaking_changes}}
No breaking changes in this release.
{{/breaking_changes}}

### Features

{{#features}}
- {{message}} ({{hash}})
{{/features}}
{{^features}}
No new features in this release.
{{/features}}

### Bug Fixes

{{#fixes}}
- {{message}} ({{hash}})
{{/fixes}}
{{^fixes}}
No bug fixes in this release.
{{/fixes}}

### Documentation

{{#docs}}
- {{message}} ({{hash}})
{{/docs}}

### Other Changes

{{#chores}}
- {{message}} ({{hash}})
{{/chores}}

## Upgrade Guide

{{#has_breaking_changes}}
This release contains breaking changes. Please review the breaking changes above and update your code accordingly.

### Migration Steps

1. Review breaking changes listed above
2. Update your code to match new API
3. Test thoroughly before deploying
4. Consult documentation for detailed migration guides

{{/has_breaking_changes}}
{{^has_breaking_changes}}
This release is fully backwards compatible. No migration steps required.
{{/has_breaking_changes}}

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install {{component}}@wicked-garden
```

## Full Changelog

See [CHANGELOG.md](./CHANGELOG.md) for complete history.

---

**Note**: This is an automated release. For questions or issues, please file a GitHub issue or consult the documentation.

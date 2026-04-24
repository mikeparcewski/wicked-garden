# Deprecation Coverage — v8-PR-6

Maps each old surface to its new-mode equivalent and documents test coverage.

## Surface mapping table

| Old surface | File | New mode | Shim type | Test coverage |
|-------------|------|----------|-----------|---------------|
| `crew:auto-approve` | `commands/crew/auto-approve.md` | `full` | Markdown command shim with deprecation notice + autonomy layer call | `test_autonomy_deprecation.py::TestDeprecationMappings::test_auto_approve_command_maps_to_full` |
| `--yolo` (on `just-finish`) | `commands/crew/just-finish.md` | `full` | Markdown command shim with deprecation notice + autonomy layer call | `test_autonomy_deprecation.py::TestDeprecationMappings::test_yolo_flag_maps_to_full` |
| `--just-finish` (engagement level) | `commands/crew/just-finish.md` | `full` | Argument shim: `--just-finish` → `AutonomyMode.FULL` | `test_autonomy_deprecation.py::TestDeprecationMappings::test_just_finish_flag_maps_to_full` |
| `engagementLevel: just-finish` | `scripts/crew/autonomy.py` (DEPRECATION_MAP) | `full` | Python constant in deprecation map | `test_autonomy_deprecation.py::TestDeprecationMappings::test_engagement_level_camel_maps_to_full` |
| `engagement_level: just-finish` | `scripts/crew/autonomy.py` (DEPRECATION_MAP) | `full` | Python constant (snake_case variant) | `test_autonomy_deprecation.py::TestDeprecationMappings::test_engagement_level_snake_maps_to_full` |

## Warning emission coverage

| Test | Verifies |
|------|---------|
| `test_first_call_emits_warning_returns_true` | Warning fires on call-1 |
| `test_second_call_suppressed_returns_false` | Warning suppressed on call-2 |
| `test_warning_emitted_once_across_sequential_calls` | Two sequential calls → [True, False] |
| `test_auto_approve_warning_mentions_surface` | Surface name in message |
| `test_yolo_warning_mentions_autonomy_full` | New flag in message |

## Notes

- Old commands are NOT deleted — they remain as shims per the hard rule.
- The Python DEPRECATION_MAP in `autonomy.py` is the authoritative surface→mode lookup.
- `WG_AUTONOMY_DEPRECATION_WARNED` env var gates the one-shot emission at process level.
- All 5 surfaces map to `full`; no old surface maps to `ask` or `balanced` (all old surfaces expressed "more autonomous").

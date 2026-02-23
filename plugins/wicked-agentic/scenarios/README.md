# wicked-agentic Scenarios

Acceptance test scenarios for the wicked-agentic plugin.

## Scenarios

| Scenario | Command | Difficulty | Time |
|----------|---------|------------|------|
| [Architecture Review](01-architecture-review.md) | `/wicked-agentic:review` | Intermediate | 15 min |
| [Trust and Safety Audit](02-trust-safety-audit.md) | `/wicked-agentic:audit` | Advanced | 12 min |
| [Framework Comparison](03-framework-comparison.md) | `/wicked-agentic:frameworks` | Basic | 8 min |
| [Five-Layer Design](04-five-layer-design.md) | `/wicked-agentic:design` | Advanced | 15 min |

## Running Scenarios

```bash
/wg-test wicked-agentic                          # select interactively
/wg-test wicked-agentic/architecture-review      # specific scenario
/wg-test wicked-agentic --all                    # all scenarios
```

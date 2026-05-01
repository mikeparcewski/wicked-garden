# Concrete Dispatch Example

Fully-substituted Task() dispatch example for the `crew:start` Step 5 call. The abstract template (with `{token}` placeholders) lives in SKILL.md; this is the concrete illustration with real values.

```
Task(
  subagent_type="wicked-garden:crew:process-facilitator",
  prompt="""
    Run the propose-process rubric. Documented inputs (one field per line):

    description: Add MFA to the existing login flow.
    priors: none
    constraints: none
    mode: propose
    current_chain: none
    auto_proceed: none
    project_dir: /Users/alex/.something-wicked/wicked-garden/projects/2026-04-26-1430/wicked-crew/projects/auth_rewrite
    project_slug: auth_rewrite
    bookend: none
    phase: none

    For any field whose value is `none`, treat it as absent (use the input's
    documented default).

    Write the resulting JSON to {project_dir}/process-plan.draft.json before
    returning. Do NOT issue TaskCreate calls — the caller emits the chain.
  """
)
```

Notes for adaptation:
- Substitute `description`, `project_dir`, and `project_slug` with the caller's actual values.
- Pass `none` (not empty string, not omitted) for any documented input the caller did not provide — the agent treats `none` as the input's documented default.
- Do not forward `output` to the agent — the shim decides whether to render `process-plan.md` after reading the draft back from disk.

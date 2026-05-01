# Concrete Dispatch Example

Concrete Task() dispatch example for the `crew:start` Step 5 call. The abstract template (with all `{token}` placeholders) lives in SKILL.md; this version has the *top-level documented inputs* substituted with realistic values so callers can see the expected shape.

Note: `{project_dir}` inside the prompt body **stays as a literal placeholder** — that's the path the agent itself writes the draft JSON to, and it should match the value passed in the `project_dir:` field above. The shim reads from that same path after the agent returns.

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
    project_dir: ~/.something-wicked/wicked-garden/projects/2026-04-26-1430/wicked-crew/projects/auth_rewrite
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
- Substitute `description`, `project_dir`, and `project_slug` with the caller's actual values. The `~/.something-wicked/...` path above is illustrative; the shim resolves the real absolute path via `resolve_path.py`.
- Pass `none` (not empty string, not omitted) for any documented input the caller did not provide — the agent treats `none` as the input's documented default.
- Do not forward `output` to the agent — the shim decides whether to render `process-plan.md` after reading the draft back from disk.

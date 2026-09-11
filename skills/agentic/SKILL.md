---
name: wicked-garden-agentic
user-invocable: true
description: |
  Agentic-systems domain skill: review, design, audit, and framework selection
  for AI agent systems. Routes to one of four actions (review | design | audit |
  frameworks) backed by the rubrics in refs/.

  Use when: "agentic review", "review this agent system", "full agentic codebase
  review", "trust and safety audit", "audit my agents for GDPR/HIPAA/SOC2/NIST
  compliance", "design an agentic system", "design a multi-agent architecture",
  "which agentic framework should I use", "compare LangChain vs CrewAI vs
  AutoGen", or any former /wicked-garden:agentic:{review|design|audit|frameworks}
  invocation.

  Disambiguation: this domain reviews and designs **AI agent systems**. For
  ordinary source code use the engineering review; for a binding go/no-go
  verdict use the archetype review (see docs/domains.md → "review appears in
  three domains").
phase_relevance: ["design", "review"]
archetype_relevance: ["*"]
---

# Agentic Domain

One entry point for the agentic domain. Pick the action from the request,
parse its args, load its ref, and apply it inline.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Action router

| Action | Use for | Args | Ref |
|--------|---------|------|-----|
| `review` | Full agentic-codebase review: framework detection, topology, architecture + safety + performance, remediation roadmap | `[path] [--quick] [--framework NAME] [--output FILE]` | `refs/review.md` |
| `design` | Greenfield agentic system design: requirements → pattern + five-layer architecture → safety validation → design doc | `[problem description] [--output FILE]` | `refs/design.md` |
| `audit` | Compliance-grade trust+safety audit: tool risk classification, HITL gates, PII handling, evidence | `[path] [--standard GDPR\|HIPAA\|SOC2\|NIST] [--output FILE] [--scenarios]` | `refs/audit.md` |
| `frameworks` | Framework selection / comparison / wizard | `[--compare fw1,fw2,...] [--language python\|typescript\|java\|go] [--use-case TYPE]` | `refs/frameworks.md` |

Routing hints:
- Assessing **existing** agentic code → `review`. Compliance-grade safety
  evidence → `audit`. **Greenfield** design → `design`. Picking or comparing
  frameworks → `frameworks`.
- Ordinary (non-agent) source code → engineering review, not this skill.
- Binding go/no-go verdict → archetype review, not this skill.

## Action: review

Full agentic-codebase review: framework detection → topology → architecture +
safety + performance assessments → pattern scoring → unified remediation roadmap.

1. Parse `[path]`, `--quick`, `--framework`, `--output`.
2. Read `refs/review.md` (relative to this skill's base directory) — the full
   5-step review rubric: framework+topology detection, architecture assessment,
   safety 8-layer, performance assessment, pattern scoring + issue taxonomy,
   and output format.
3. Run the detection scripts from the ref (Step 1). If `--quick`, stop and return
   the structural summary. Otherwise apply all rubric steps directly.
4. Write to `--output` file when set; otherwise return inline.

### Heavyweight full review (optional dispatch)

For large codebases, or when independent parallel assessments are wanted,
dispatch the three fork skills as parallel workers instead of applying rubric
steps 2–4 inline, then merge their findings into the ref's unified roadmap:

- `wicked-garden-agentic-architect` — five-layer architecture + agent topology
- `wicked-garden-agentic-safety-reviewer` — guardrails, prompt injection, PII, HITL
- `wicked-garden-agentic-performance-analyst` — tokens, latency, cost, parallelization

## Action: design

Interactive design session for a new agentic system: requirements → pattern +
five-layer architecture → safety validation → design doc. Greenfield only —
use `review` to assess existing code, `audit` for compliance evidence.

1. Parse `[problem description]` and `--output`.
2. Read `refs/design.md` — the design
   rubric: requirements gathering, pattern selection, five-layer architecture,
   safety section, framework recommendation, and output format.
3. Work through the rubric phases directly. If no problem statement is supplied,
   ask the 3–5 clarifying questions from the ref before proceeding.
4. Write to `--output` file when set; otherwise return inline.

## Action: audit

Deep trust+safety audit: classifies tool risks, verifies HITL gates, checks PII
handling, optionally emits compliance evidence + wicked-scenarios. Use `review`
for the broader architecture+perf+safety sweep.

1. Parse `[path]`, `--standard`, `--output`, `--scenarios`.
2. Read `refs/audit.md` — the 8-layer rubric,
   checklist, compliance extensions, and output format.
3. Apply the rubric directly to the target path. For each layer, assess findings,
   classify severity, and build the risk matrix.
4. If `--standard` is given, append the matching compliance checklist from the ref.
5. If `--scenarios`, emit a `wicked-scenarios` block per CRITICAL/HIGH finding.
6. Write to `--output` file when set; otherwise return inline.

## Action: frameworks

Framework selection / comparison / wizard. NOT for reviewing existing agentic
code (use `review`) or architecture design (use `design`).

1. Derive mode from args: `--compare` → side-by-side comparison; filters only
   (`--language`, `--use-case`) → filtered selection; no args → interactive
   5-question wizard.
2. Read `refs/frameworks.md` — the
   mode detection table, wizard questions, decision tree, comparison table,
   scoring template, and output format.
3. Use WebSearch for latest 2026 ecosystem state (versions, features, community)
   before rendering the comparison or recommendation. The curated framework
   profiles live in the `skills/agentic/frameworks/` knowledge module.
4. End output with a pointer to the `design` action of this skill as the next step.

## Knowledge modules

The domain's reference knowledge lives beside this skill and is loaded on demand:

- `skills/agentic/agentic-patterns/` — pattern catalog + five-layer model
- `skills/agentic/context-engineering/` — context/token optimization techniques
- `skills/agentic/frameworks/` — curated framework profiles + decision tree
- `skills/agentic/review-methodology/` — systematic review approach
- `skills/agentic/trust-and-safety/` — guardrail + HITL patterns

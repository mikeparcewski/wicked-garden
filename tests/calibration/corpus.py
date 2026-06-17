"""tests/calibration/corpus.py — Calibration corpus for the v11 archetype
detector.

A representative set of prompts spanning the work-shape archetypes plus
paraphrase / multi-archetype / ambiguous edge cases. Each entry declares
the expected primary archetype (the one the detector MUST find) and an
optional set of acceptable secondary archetypes.

Used by tests/calibration/test_corpus_recall.py to compute per-archetype
recall and overall precision. Phrase calibration in
.claude-plugin/archetypes.json is tuned to keep recall ≥ 0.85 across
this corpus.

Each entry shape:
    {
      "prompt": "...",
      "primary": "build",        # MUST be in detector output
      "may_also": ["migrate"],   # acceptable additional archetypes
      "signals": {...},          # optional boolean flags to pass to detector
    }
"""

from __future__ import annotations


CORPUS = [
    # ===== build =====
    {"prompt": "implement caching for the dashboard",
     "primary": "build", "may_also": []},
    {"prompt": "add a /healthz endpoint to the API",
     "primary": "build", "may_also": []},
    {"prompt": "fix the off-by-one in the pagination logic",
     "primary": "build", "may_also": []},
    {"prompt": "create a webhook handler for stripe charge events",
     "primary": "build", "may_also": []},
    {"prompt": "build the email export feature",
     "primary": "build", "may_also": []},
    {"prompt": "refactor the auth module to support OIDC",
     "primary": "build", "may_also": []},
    {"prompt": "patch the rate limiter to skip allow-listed IPs",
     "primary": "build", "may_also": []},
    {"prompt": "wire up the new logging library",
     "primary": "build", "may_also": []},

    # ===== migrate =====
    {"prompt": "drop the legacy_id column from orders and backfill",
     "primary": "migrate", "may_also": ["build"],
     "signals": {"reversibility_low": True, "state_complexity_high": True}},
    {"prompt": "rename the user_email column to email_address",
     "primary": "migrate", "may_also": [],
     "signals": {"state_complexity_high": True}},
    {"prompt": "expand the orders table to support multi-currency",
     "primary": "migrate", "may_also": ["build"]},
    {"prompt": "schema change: split address into street/city/postal",
     "primary": "migrate", "may_also": []},
    {"prompt": "we need to migrate the session store from redis to postgres",
     "primary": "migrate", "may_also": []},
    {"prompt": "breaking change: rename the v1 webhooks endpoint to v2",
     "primary": "migrate", "may_also": []},
    {"prompt": "cutover the new pricing service after backfill",
     "primary": "migrate", "may_also": []},

    # ===== modernize (legacy codebase -> new stack) =====
    {"prompt": "modernize this COBOL batch system to Java",
     "primary": "modernize", "may_also": [],
     "signals": {"novelty_high": True, "state_complexity_high": True,
                 "reversibility_low": True}},
    {"prompt": "port this AngularJS app to a modern Angular stack",
     "primary": "modernize", "may_also": [],
     "signals": {"novelty_high": True}},
    {"prompt": "rewrite the legacy .NET Framework service on .NET Core",
     "primary": "modernize", "may_also": [],
     "signals": {"novelty_high": True}},
    {"prompt": "lift and shift the legacy codebase onto a new stack",
     "primary": "modernize", "may_also": [],
     "signals": {"novelty_high": True, "reversibility_low": True}},

    # ===== incident =====
    {"prompt": "checkout is down — 5xx error rate spiking",
     "primary": "incident", "may_also": [],
     "signals": {"production_impact": True}},
    {"prompt": "outage on the api — oncall paged",
     "primary": "incident", "may_also": []},
    {"prompt": "we have an incident: stripe webhooks failing",
     "primary": "incident", "may_also": []},
    {"prompt": "production is broken: 500s on the user profile page",
     "primary": "incident", "may_also": []},
    {"prompt": "post-mortem for INC-4829 (checkout 500 on coupon reuse)",
     "primary": "incident", "may_also": []},
    {"prompt": "error rate climbed to 12% in the last 5 minutes",
     "primary": "incident", "may_also": []},

    # ===== ship =====
    {"prompt": "kick off the canary rollout for the new pricing logic",
     "primary": "ship", "may_also": [],
     "signals": {"blast_radius_high": True, "post_build": True}},
    {"prompt": "deploy v2.4.0 to production",
     "primary": "ship", "may_also": []},
    {"prompt": "ramp the feature flag to 25% traffic",
     "primary": "ship", "may_also": []},
    {"prompt": "release the new dashboard to all users",
     "primary": "ship", "may_also": []},
    {"prompt": "cutover the new payment processor at 2am UTC",
     "primary": "migrate", "may_also": ["ship"]},

    # ===== review =====
    {"prompt": "review the new auth middleware",
     "primary": "review", "may_also": [],
     "signals": {"independent_assessment_needed": True}},
    {"prompt": "code review the PR that adds OIDC support",
     "primary": "review", "may_also": []},
    {"prompt": "audit the data export endpoint for GDPR compliance",
     "primary": "review", "may_also": []},
    {"prompt": "evaluate the proposed redis architecture",
     "primary": "review", "may_also": []},
    {"prompt": "design review on the new event sourcing approach",
     "primary": "review", "may_also": []},
    {"prompt": "give me a verdict on this implementation",
     "primary": "review", "may_also": []},

    # ===== specify =====
    {"prompt": "write acceptance criteria for the export feature",
     "primary": "specify", "may_also": []},
    {"prompt": "let's flesh out the requirements for saved searches",
     "primary": "specify", "may_also": []},
    {"prompt": "draft a user story for the multi-tenant feature",
     "primary": "specify", "may_also": []},
    {"prompt": "we need a spec for the new billing flow",
     "primary": "specify", "may_also": []},

    # ===== decide =====
    {"prompt": "should we use redis or memcached for the session store?",
     "primary": "decide", "may_also": [],
     "signals": {"multiple_viable_options": True,
                 "reversibility_medium_or_low": True}},
    {"prompt": "I want an ADR on the queue migration",
     "primary": "decide", "may_also": []},
    {"prompt": "let's write a decision record on the auth provider choice",
     "primary": "decide", "may_also": []},
    {"prompt": "trade-off analysis: postgres vs cockroachdb",
     "primary": "decide", "may_also": []},

    # ===== explore =====
    {"prompt": "what should we do about the rate-limit story?",
     "primary": "explore", "may_also": [],
     "signals": {"novelty_high": True, "ambiguity_high": True}},
    {"prompt": "how might we improve dashboard load time",
     "primary": "explore", "may_also": []},
    {"prompt": "explore options for adding offline support to the mobile app",
     "primary": "explore", "may_also": []},
    {"prompt": "let's brainstorm approaches to the multi-region replication problem",
     "primary": "explore", "may_also": []},

    # ===== triage (only when nothing else fits) =====
    {"prompt": "hi there", "primary": "triage", "may_also": []},
    {"prompt": "thanks", "primary": "triage", "may_also": []},
    {"prompt": "ok cool", "primary": "triage", "may_also": []},
    {"prompt": "what's up", "primary": "triage", "may_also": []},

    # ===== multi-archetype =====
    {"prompt": "implement schema change to add tenant_id with backfill",
     "primary": "build", "may_also": ["migrate"],
     "signals": {"state_complexity_high": True, "code_change": True,
                 "reversibility_low": True}},
    {"prompt": "ship the auth middleware after security review",
     "primary": "ship", "may_also": ["review"],
     "signals": {"post_build": True, "independent_assessment_needed": True}},
    {"prompt": "review the migration plan for the tenant_id rollout",
     "primary": "review", "may_also": ["migrate"],
     "signals": {"independent_assessment_needed": True}},

    # ===== paraphrase / harder cases =====
    {"prompt": "we need to retire the old payment provider",
     "primary": "migrate", "may_also": [],
     "signals": {"reversibility_low": True}},
    {"prompt": "take the legacy_id column out of orders",
     "primary": "migrate", "may_also": [],
     "signals": {"state_complexity_high": True}},
    {"prompt": "I want to ship a fix for the off-by-one bug",
     "primary": "build", "may_also": ["ship"]},
    {"prompt": "can you take a look at this PR?",
     "primary": "review", "may_also": []},
    {"prompt": "memory leak in the worker process is paging us nightly",
     "primary": "incident", "may_also": []},
    {"prompt": "let's pick a database for the analytics service",
     "primary": "decide", "may_also": []},
    {"prompt": "I'm not sure how to model the permissions table",
     "primary": "explore", "may_also": []},
]

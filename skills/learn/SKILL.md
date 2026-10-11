---
name: wicked-garden-learn
description: |
  Learn a topic or an event from outside sources and save it to the
  repository as KNOWLEDGE: research with cited sources, synthesize a claims
  ledger, walk the operator through it in chat, then author
  .wicked/knowledge/<slug>/ (topic.json, claims.jsonl, README.md) plus
  text-only skills that cite the claims. Every claim carries its source URL
  and observed_at. A refresh re-researches and proposes only changes:
  confirm, supersede, contradict, retire. Nothing is deleted silently.

  Use when: "learn about X", "research X and save what we learn", "what
  happened with <event>", "teach me X", "make a skill from what we learned",
  "refresh the knowledge on X", "is our knowledge on X stale", "check the
  learned knowledge", "index the learned knowledge", or a phase of the
  `learn` workflow (scope, research, synthesize, walkthrough, author,
  review). NOT for learning this repository's own code (that is
  wicked-garden-repo-learn) or for storing what the operator told you
  (that is a memory: wicked-garden-mem).
metadata:
  role: router
  phases: "*"
  archetypes: "*"
---

# Learn: outside knowledge, cited, into the repository

Learn ACQUIRES knowledge: it reads sources outside the repository and records what they say,
each claim with the URL it came from and when it was seen. What the operator says during the
walkthrough is not acquired knowledge; it is a memory (witnessed or told), so it goes in the
README's "Operator notes", never into the claims ledger. The repository is the record: a pull
request delivers the files, a human merges them, and only then is the topic indexed into the
estate knowledge store.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Actions (one per `learn` workflow phase)

| Action | Role | Writes | Does |
|---|---|---|---|
| `scope` | neutral | nothing | Name the slug (kebab-case, at most 64 characters), the kind (`topic` or `event`), 3 to 7 questions to answer, what is out of scope, and the source policy: primary sources first (specs, official docs, release notes, the project's own site), dated reporting for events. Read `.wicked/knowledge/<slug>/` if it exists: then this run is a **refresh** (see refs/refresh.md). |
| `research` | neutral | nothing | Fetch sources with your web tools (or `curl -sL`). For each source, record the URL, title, published date when the page states one, and `observed_at` = now in UTC. Draft candidate claims, each tied to the sources that support it. No network: write `research: no web access` and stop; never answer from memory as if it were sourced. |
| `synthesize` | neutral | nothing | Turn the candidates into the claims ledger (refs/claims.md): one atomic, checkable statement per claim, deduplicated. Leave new claim ids to the author (a neutral seat may not run scripts); on a refresh keep each existing id. Keep only claims that would help a fresh session in 3 months. On a refresh, output the diff against the existing ledger. |
| `walkthrough` | neutral | nothing | Teach it in the run thread: a 5-line summary, a worked example, what changed (on a refresh), the open questions, and 3 to 5 check questions. The operator answers, asks or corrects by sending the step back; answer each point, re-teach what was unclear, and mark which corrections you verified against a source. |
| `author` | creator | `.wicked/knowledge/<slug>/`, skills | Compute each new claim's id (`wicked-garden run scripts/learn/check.py --claim-id "<text>"`), write the files (refs/claims.md), then run the check below and paste its JSON and exit code. |
| `review` | evaluator | nothing | Re-run the check yourself; re-fetch and spot-check at least 3 claims (every retirement, too); judge the durability test; last line `VERDICT: PASS` or `VERDICT: FAIL`. |
| `check` | any | nothing | `wicked-garden run scripts/learn/check.py --repo . [--slug <slug>]` |
| `index` | human or daemon only | estate knowledge | `wicked-garden run scripts/learn/index.py --repo <default-branch checkout>` after the PR merged. It refuses inside a governed run. |

In a wicked-crew run, each phase is one unit: do only that row, and hand the next unit what it
needs in your output. Follow the `wicked-garden-governed-worker` skill for your role. The
neutral rows write nothing to the repository; their output is the record the next phase reads.

## What the author writes

```
.wicked/knowledge/<slug>/topic.json     {"schema":1,"slug","title","kind","questions":[],"created_at","refreshed_at","run_ids":[]}
.wicked/knowledge/<slug>/claims.jsonl   one claim per line (refs/claims.md)
.wicked/knowledge/<slug>/README.md      the synthesis; every factual sentence cites [c-xxxxxxxx]; ## Sources; ## Operator notes
<skill dir>/<skill-name>/SKILL.md       0..n text-only skills (below)
```

The skill dir is the repository's own, if it has one: `wicked-garden run scripts/learn/check.py --skill-dir --repo .`
prints it. That is the first existing dir in the check's order, else `.agents/skills/`, which you create.

**Skills.** Author a skill only for a procedure a future agent should follow. Facts stay in the
claims ledger. A learn skill:
- uses only the frontmatter keys `name`, `description` and `metadata`;
- carries `metadata.learn-topic: <slug>`, and its `name` equals its directory;
- keeps its description to 1024 characters and its body to 500 lines;
- is plain markdown, with no scripts and no other files;
- names no agent-specific tool and no harness;
- ends with `## Sources`, which lists the claim ids it rests on.

The check enforces each of these rules.

## Durability test

Ask of every claim and every skill line: would this help a fresh session in 3 months? Drop the
following:
- claims about this run;
- restated page titles;
- an event fact without its date (write "as of 2026-10-11").

The check flags the mechanical half: thin claims, and undated event claims. The judgement is the
reviewer's.

## Honest output

- **Report counts.** State sources fetched, claims derived, claims kept, and skills authored.
- **On a refresh**, also state confirmed, superseded, contradicted and retired.
- **Never assert a fact without a source.** Never present memory as research.
- **Leave a removal reviewable.** A claim leaves only through a status change in the pull
  request, with its reason and evidence. It is never deleted from claims.jsonl.

## Depth

- [refs/claims.md](refs/claims.md): the claim record, the id, statuses, the README citation rule,
  and a worked example.
- [refs/refresh.md](refs/refresh.md): how a refresh diffs against the existing ledger, the staleness
  rule, and how removals are proposed.

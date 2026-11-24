---
name: wicked-garden-learn
description: |
  Learn from outside sources, every claim cited. Learn mode: research a topic
  or event, synthesize a claims ledger (each claim with its source URL and
  observed_at), walk the operator through it, then author
  .wicked/knowledge/<slug>/ plus text-only skills that cite the claims; a
  refresh proposes only changes (confirm, supersede, contradict, retire),
  never a silent delete. Report mode (the `sourced-report` workflow): the
  same research and synthesis, without the write-up, from staged documents,
  the job's picked sources and the web, then a fidelity check by a seat that
  did not gather. It changes nothing.

  Use when: "learn about X", "research X and save what we learn", "what
  happened with <event>", "refresh the knowledge on X", "check the learned
  knowledge", a brief with a `Lens:` line, or a phase of the `learn` or
  `sourced-report` workflow. NOT for this repository's own code
  (wicked-garden-repo-learn) or for what the operator told you (a memory:
  wicked-garden-mem).
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

## Actions (one per phase of the `learn` and `sourced-report` workflows)

| Action | Role | Writes | Does |
|---|---|---|---|
| `scope` | neutral | nothing | Name the slug (kebab-case, at most 64 characters), the kind (`topic` or `event`), 3 to 7 questions to answer, what is out of scope, and the source policy: primary sources first (specs, official docs, release notes, the project's own site), dated reporting for events. Read `.wicked/knowledge/<slug>/` if it exists: then this run is a **refresh** (see refs/refresh.md). |
| `research` | neutral | nothing | In report mode, see Report mode below. Otherwise: fetch sources with your web tools (or `curl -sL`). For each source, record the URL, title, published date when the page states one, and `observed_at` = now in UTC. Draft candidate claims, each tied to the sources that support it. No network: write `research: no web access` and stop; never answer from memory as if it were sourced. |
| `synthesize` | neutral | nothing | In report mode, see Report mode below. Otherwise: turn the candidates into the claims ledger (refs/claims.md): one atomic, checkable statement per claim, deduplicated. Leave new claim ids to the author (a neutral seat may not run scripts); on a refresh keep each existing id. Keep only claims that would help a fresh session in 3 months. On a refresh, output the diff against the existing ledger. |
| `walkthrough` | neutral | nothing | Teach it in the run thread: a 5-line summary, a worked example, what changed (on a refresh), the open questions, and 3 to 5 check questions. The operator answers, asks or corrects by sending the step back; answer each point, re-teach what was unclear, and mark which corrections you verified against a source. |
| `author` | creator | `.wicked/knowledge/<slug>/`, skills | Compute each new claim's id (`wicked-garden run scripts/learn/check.py --claim-id "<text>"`), write the files (refs/claims.md), then run the check below and paste its JSON and exit code. |
| `review` | evaluator | nothing | Re-run the check yourself; re-fetch and spot-check at least 3 claims (every retirement, too); judge the durability test; last line `VERDICT: PASS` or `VERDICT: FAIL`. |
| `fidelity` | evaluator | nothing | Report mode's check: refs/report-check.md. Re-check every claim at its source yourself, remove what does not hold, last line `VERDICT: PASS` or `VERDICT: FAIL`. |
| `check` | any | nothing | `wicked-garden run scripts/learn/check.py --repo . [--slug <slug>]` |
| `index` | human or daemon only | estate knowledge | `wicked-garden run scripts/learn/index.py --repo <default-branch checkout>` after the PR merged. It refuses inside a governed run. |

In a wicked-crew `learn` run, each phase is one unit: do only that row, and hand the next unit
what it needs in your output. Follow the `wicked-garden-governed-worker` skill for your role. The
neutral rows write nothing to the repository; their output is the record the next phase reads.

## Report mode (the `sourced-report` workflow)

Six job cards run report mode: Research, Competitive, Due diligence, Analyze documents, Critique, and
Estimate. It is learn without the walkthrough and the author steps: nothing is written to any repository,
and the run delivers the checked report itself. Its record is the report packet (refs/report-claims.md),
not the claims ledger. The brief's `Lens:` line picks the report's shape; no line means `research`.

| Brief line | Read | Documents |
|---|---|---|
| `Lens: research.` | refs/report-research.md | not taken |
| `Lens: competitive.` | refs/report-competitive.md | not taken |
| `Lens: due-diligence.` | refs/report-due-diligence.md | required |
| `Lens: analyze.` | refs/report-analyze.md | required |
| `Lens: critique.` | refs/report-critique.md | optional |
| `Lens: estimate.` | refs/report-estimate.md | optional |

**`research` in report mode** (the `gather` step; often a team, each member covering part of the question):
1. **Preflight.** Run `wicked-garden run scripts/learn/report_check.py preflight --lens <lens> --records <documents folder>`
   (the documents folder is `records/` in a crew run). Exit 3 means the lens needs documents and none
   were staged: stop with its reason. Otherwise put the absolute documents path it prints (`records`) in
   your output; the later steps use it. Without the launcher, count the staged files yourself:
   `due-diligence` and `analyze` need at least one.
2. **Read only this job's sources:** the staged documents, the repository in scope, the project sources
   your tools list, the web, and the text the brief itself carries (a claim to critique, a scope to
   estimate: refs/report-claims.md's `brief`).
3. **The web.** In a crew run, reach it only through the job's `web` source, with its `search` and `fetch`
   tools. Never use curl or another fetcher: the fetch time in each record comes from that source. Paste
   each fetch result's receipt (its URL and `fetched_at`) verbatim in your output. If those tools are not in
   your list, the web is `not-picked`. If a call is refused or the source is not installed, it is
   `unavailable`. Record which, with the reason, and go on with the rest. Outside a crew run, use your own
   web tools and record each fetch time yourself.
4. **Record as you read.** Put each source in the source log as you read it, and draft candidate claims,
   each tied to the ids of the sources that support it.
5. **Stop only when nothing is readable:** no document, no repository, no picked source, no web and no text
   in the brief to work from. Then `stopped` says what was missing. Never answer from memory.

**`synthesize` in report mode:** merge the logs (one record per page, per quote and per call, renumbered
S1..Sn), number the claims C1..Cn, and write the report in the lens's shape. Save the packet in your notes
folder and run the floor on it, `wicked-garden run scripts/learn/report_check.py check --packet <file> --records <documents folder> [--repo <repository>]`,
with absolute paths. Fix every finding, except the one exception refs/report-claims.md names. Put the
packet, and the receipts `gather` pasted, in your output.

**`fidelity`:** refs/report-check.md.

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
- [refs/report-claims.md](refs/report-claims.md): report mode's packet: the source log, the claims and
  the floor.
- [refs/report-check.md](refs/report-check.md): report mode's fidelity check.
- The six lens refs, in the Report mode table above.

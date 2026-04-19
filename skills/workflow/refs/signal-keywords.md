# Signal Keywords

All 16 signal categories with keyword lists and specialist routing.
Keywords ending with `*` match as stems (e.g., `auth*` matches authentication,
authorization). Detection threshold: confidence >= 0.1 (matched / total).

---

## Signal-to-Keyword Reference

### security — triggers: platform, qe

`auth*`, `encrypt*`, `pii`, `credential*`, `token*`, `password`, `oauth`, `jwt`,
`secret*`, `vault`, `certific*`, `login`, `session`, `csrf`, `xss`, `inject*`,
`security`, `permiss*`, `rbac`

---

### performance — triggers: engineering, qe

`scal*`, `load`, `optimi*`, `latency`, `throughput`, `cache`, `caching`,
`performance`, `slow`, `fast`, `bottleneck`, `memory`, `cpu`, `concurren*`,
`benchmark*`

---

### product — triggers: product

`requirement`, `feature`, `story`, `customer`, `stakeholder`, `acceptance`,
`roadmap`, `backlog`, `priority`, `user story`

---

### compliance — triggers: platform

`soc2`, `hipaa`, `gdpr`, `pci`, `audit`, `policy`, `regulation`, `privacy`,
`data-protection`, `compliance`, `regulatory`

---

### ambiguity — triggers: jam

`maybe`, `either`, `could`, `should we`, `not sure`, `alternative`, `options`,
`tradeoff`, `versus`, `vs`, `compare`, `brainstorm`

---

### complexity — triggers: delivery, engineering

`multiple`, `system`, `integration`, `migrate`, `migration`, `refactor`,
`distributed`, `microservice`, `legacy`, `cross-team`, `downstream`,
`cascading`, `cross-cutting`, `foundational`, `core module`, `affects all`

---

### data — triggers: data

`data`, `analytics`, `metrics`, `report*`, `dashboard`, `visuali*`, `query`,
`database`, `sql`, `csv`, `etl`, `pipeline`, `ml`, `model`, `training`,
`dataset`, `warehouse`, `schema`, `ontology`

---

### infrastructure — triggers: platform

`deploy`, `deployment`, `ci/cd`, `pipeline`, `docker`, `kubernetes`, `k8s`,
`cloud`, `aws`, `gcp`, `azure`, `terraform`, `helm`, `hook binding`,
`event handler`, `event listener`, `middleware config`, `build system`,
`makefile`, `configuration-as-code`

---

### architecture — triggers: agentic, engineering

`architecture`, `design pattern`, `component`, `api contract`, `schema`,
`system design`, `adr`, `decision record`, `monolith`, `microservice`,
`event-driven`, `cqrs`, `hexagonal`, `algorithm`, `orchestrat*`, `dispatcher`,
`resolver`, `parser`, `engine`, `scoring`, `routing logic`, `decision logic`,
`phase selection`, `signal detection`

---

### ux — triggers: product

`user`, `experience`, `ux`, `ui`, `flow`, `usability`, `accessibility`,
`a11y`, `wcag`, `persona`, `journey`, `wireframe`, `prototype`,
`design system`, `interaction`

---

### strategy — triggers: product

`roi`, `business value`, `investment`, `competitive`, `market`, `strategic`,
`value proposition`, `differentiation`, `business case`

---

### content — triggers: jam, product

`readme`, `documentation`, `docs`, `rewrite`, `messaging`, `copy`, `content`,
`landing page`, `blog post`, `user guide`, `editorial`, `tone`, `voice`,
`narrative`, `announcement`, `release note*`

---

### text-as-code — triggers: qe, engineering

`command`, `skill`, `agent`, `prompt`, `instruction`, `SKILL.md`, `frontmatter`,
`slash command`, `hook script`, `persona`, `specialist`, `phase gate`,
`crew routing`, `signal detection`, `phase selection`, `plugin instruction*`,
`behavior-defining`

---

### reversibility — triggers: platform, delivery

`migrat*`, `schema`, `breaking change`, `deprecat*`, `backward incompatible`,
`drop table`, `drop column`, `remove api`, `rename api`, `data transform*`,
`restructur*`, `irreversible`, `feature flag`, `toggle`, `rollback`, `canary`,
`blue-green`

---

### novelty — triggers: jam, engineering

`first time`, `new pattern`, `prototype`, `proof of concept`, `poc`,
`greenfield`, `from scratch`, `never done`, `unfamiliar`, `research`,
`spike`, `experiment*`, `evaluat*`

---

### quality — triggers: qe

`quality`, `testing`, `coverage`, `reliability`, `qe`, `test strategy`,
`acceptance criteria`, `testability`, `tdd`, `regression`, `lint`,
`static analysis`, `slo`, `error rate`, `error budget`, `canary`, `rollback`,
`performance regression`, `quality gate`, `shift-left`

---

### imagery — triggers: design (not in default specialist set)

`image`, `visual`, `illustration`, `graphic`, `photo`, `screenshot`, `mockup`,
`render`, `generate image`, `create image`, `edit image`, `modify image`,
`inpaint`, `logo`, `icon`, `banner`, `hero image`, `thumbnail`, `dall-e`,
`imagen`, `stable diffusion`, `flux`, `asset`, `creative`, `artwork`

---

## Detection Algorithm

1. Lowercase the input text
2. For each signal category: count matching keywords (stem match for `*`, whole-word for plain)
3. confidence = matched / total_in_category
4. Signal detected when confidence >= 0.1 (default threshold, configurable)
5. Detected signals → specialist routing (see specialist-routing-rules.md)

## Ambiguity Detection (separate from signal keywords)

Fires `jam` specialist regardless of signal confidence when input matches:
- Multiple question marks in input (`?.*?`)
- Phrases: `should we`, `should i`, `could be`, `might be`, `may be`
- Words: `not sure`, `options`, `alternative`, `tradeoff`, `versus`, `vs.`,
  `compare`, `comparison`

## Semantic Signal Entries

**Deprecated in v6**: the v5 `signal_library.py` semantic-matching entry point was
removed in the v6 rebuild (see issue #428) along with the rule-engine stack. The
facilitator rubric reads project context directly via factor scoring rather than
looking up cached signal entries. This document is retained as a historical reference
for the keyword categories; no runtime consumer reads it in v6.

# codemod-first eval cases

`triggers.json` holds the 4 + 2 trigger cases from garden#1334; `responses/` holds the
decision-block cases (a plan with the block, a plan that hand-edits without it, a written
rejection).

| Half | What it proves | When it runs |
|---|---|---|
| `tests/codemod_first/test_codemod_first.py` | each positive prompt matches the skill's trigger list and its description, each negative matches neither; `mechanical_first.py check` passes the block and the rejection and fails the hand edit | every `pytest` run |
| an agent run per case | an agent with garden installed loads `wicked-garden-codemod-first` before its first edit on a positive prompt and does not on a negative one | user-triggered only (model calls) |

To run one by hand: give the case's `prompt` to an agent with garden installed, in a scratch
repo, and note whether it loads the skill before it edits a file. Grade its plan with
`python3 scripts/engineering/mechanical_first.py check <plan file>`.

# Product demo skills

Three portable [Agent Skills](https://agentskills.io) for turning a working web product into a rehearsed demo and a
captioned, chaptered demo video. They follow the open `SKILL.md` format, so the same folders work in Claude Code,
OpenAI Codex, Cursor, GitHub Copilot / VS Code, Gemini CLI and any other agent that reads Agent Skills. Nothing in
them depends on a particular agent, CLI or IDE: the instructions say "run" and "open", and the scripts are plain
Node.js and Python that run on macOS, Linux and Windows.

| Skill | Use it to | Ships |
|---|---|---|
| [`demo-planning`](demo-planning/SKILL.md) | Turn a product into a demo: pitch, one chapter per capability, a case bank with fresh alternates, resettable state, a live rehearsal with measured timings, and a presenter script. | Presenter-script and segment templates; rehearsal and storytelling guides. |
| [`demo-video-recording`](demo-video-recording/SKILL.md) | Record the demo as a 1080p video: the app in a browser-window frame with a lower-third caption band, a visible cursor, labelled callouts, chapter slides, honest time-lapse of waits, a closing card with measured timings, and MP4 chapters. Each chapter records as its own segment and can be redone alone. | A generic Playwright + ffmpeg recording engine (`scripts/record.mjs`), a read-only selector probe (`scripts/probe.mjs`), the storyline API, an example storyline, stage design and gotchas. |
| [`demo-video-review`](demo-video-review/SKILL.md) | QA the video before sharing: labelled contact sheets (per chapter, around joins, at the end), caption sync, callouts, dead air, state leaks, numbers; then decide re-encode vs re-record one segment vs fix the app. | `contact_sheet.py` and a symptom → fix checklist. |

They chain: **plan** (chapters, cases, reset, rehearsal, script) → **record** (one segment per chapter, stitched) →
**review** (contact sheets, verdicts) → re-record only what failed → review the joins and the end again.

## Install

```sh
python3 install.py                           # user level: ~/.agents/skills and ~/.claude/skills (the default)
python3 install.py --tools all               # every location below
python3 install.py --project /path/to/repo   # project level: <repo>/.agents/skills and <repo>/.claude/skills
python3 install.py --tools agents,cursor --link   # symlink instead of copy, to pick up edits here (POSIX)
python3 install.py --dry-run                 # show what would happen
python3 install.py --uninstall               # remove these three skills again
```

Use `python` instead of `python3` on Windows if needed. `--link` falls back to copying on Windows. Only these three
skill folders are added or replaced; nothing else in a skills directory is touched. Or copy the folders by hand.

### Where each tool looks for skills

As documented in September 2026. Paths move, so check your tool's docs if a skill doesn't show up.

| Tool | User level | Project level | Also reads |
|---|---|---|---|
| Vendor-neutral (`--tools agents`) | `~/.agents/skills` | `.agents/skills` | Primary path for Codex |
| Claude Code (`claude`) | `~/.claude/skills` | `.claude/skills` | |
| OpenAI Codex | `~/.agents/skills` | `.agents/skills` | |
| Cursor (`cursor`) | `~/.cursor/skills` | `.cursor/skills` | `.agents/skills` |
| GitHub Copilot / VS Code (`copilot`) | `~/.copilot/skills` | `.github/skills` | `.agents/skills`, `.claude/skills`; more via `chat.agentSkillsLocations` |
| Gemini CLI (`gemini`) | `~/.gemini/skills` | `.gemini/skills` | Falls back to `.agents/skills` |

The default install (`agents` + `claude`) covers all five tools above.

## Prerequisites

| For | Needs |
|---|---|
| Planning | Nothing beyond your agent and the product. |
| Recording | Node.js 20+, `ffmpeg` and `ffprobe` on PATH (or `FFMPEG=/path/to/ffmpeg`), and the app running locally. Run `npm install && npx playwright install chromium` once in `demo-video-recording/scripts`. |
| Review | Python 3.9+ and `ffmpeg`/`ffprobe`. Pillow is optional: it labels the tiles when your ffmpeg build has no `drawtext`. |

## Validate

```sh
python3 install.py --check        # spec rules: name = folder, lengths, SKILL.md present, size, broken links
skills-ref validate ./demo-video-recording   # the official validator, if installed
```

The official validator can be run without installing it:
`uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" skills-ref validate ./demo-planning`.

## Layout

```
agent-skills/
├── README.md, LICENSE, install.py
├── demo-planning/          SKILL.md · references/ · assets/
├── demo-video-recording/   SKILL.md · scripts/ (engine) · references/ · assets/ (example storyline)
└── demo-video-review/      SKILL.md · scripts/contact_sheet.py · references/checklist.md
```

Each `SKILL.md` stays short (the agent loads it only when the task matches); details live in `references/` and are
read on demand. Output such as `node_modules/`, recorded frames and videos is never installed.

MIT licensed; see [LICENSE](LICENSE).

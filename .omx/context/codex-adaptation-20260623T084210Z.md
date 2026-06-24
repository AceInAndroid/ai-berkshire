# Context Snapshot: Codex adaptation for ai-berkshire

## Task Statement
Plan how to adapt `xbtlin/ai-berkshire`, currently framed as a Claude Code project, so its research mechanisms and workflows are usable inside Codex.

## Desired Outcome
A migration plan that preserves the investment-research discipline while mapping Claude-specific slash commands, team/task primitives, and project memory into Codex-native surfaces.

## Known Facts / Evidence
- `README.md:7` describes AI Berkshire as a Claude Code based investment-research skill collection.
- `README.md:216-236` installs Claude Code and copies `skills/*.md` into `~/.claude/commands/`, then invokes commands such as `/investment-research`.
- `CLAUDE.md:1-111` contains durable project instructions: report structure, naming, objective analysis rules, Chinese output style, Git workflow, and financial verification requirements.
- There are 18 Markdown skill files under `skills/`.
- Several skill files use Claude-specific mechanics: `$ARGUMENTS`, `Task`, `TeamCreate`, `TaskCreate`, `TaskUpdate`, `SendMessage`, `WebSearch`, and hardcoded `~/ai-berkshire` paths.
- `tools/financial_rigor.py` and `tools/report_audit.py` are Python validation tools that should remain shared tooling.
- CodeGraph indexes 7 Python files under `tools/`; most project value is Markdown workflow content and report artifacts.
- Current Codex manual states Codex skills live in `.agents/skills` at repo/user/admin/system scope and require a folder with `SKILL.md`; plugins are the distribution unit for reusable skills; `AGENTS.md` is the repo instruction surface; Codex subagents exist but only spawn when explicitly asked.
- This user's installed OMX/Codex profile states that project-local skills load from `./.codex/skills` and user skills from `~/.codex/skills`. This conflicts with the current public Codex manual path and must be treated as an environment compatibility decision.

## Constraints
- Do not break Claude Code compatibility unless intentionally making a Codex-only fork.
- Do not move or rewrite all research reports.
- Investment claims remain high-risk; workflows must preserve data-source citation, two-source financial validation, and "facts vs opinion" separation.
- Codex does not automatically treat Claude `~/.claude/commands/*.md` as Codex skills.

## Unknowns / Open Questions
- Whether the desired end state is repo-local private use only, personal global install, or shareable Codex plugin.
- Whether to preserve Claude and Codex workflows side by side or replace Claude docs entirely.
- Whether to implement custom Codex agents for four-master roles, or rely on explicit subagent prompting inside skills.
- Whether this repo should target this user's OMX-enhanced Codex path (`.codex/skills`) first, or public Codex repo skill path (`.agents/skills`) first.

## Likely Touchpoints
- `AGENTS.md` new repo guidance, likely derived from `CLAUDE.md`.
- `.codex/skills/<skill-name>/SKILL.md` for this user's current environment; `.agents/skills/<skill-name>/SKILL.md` or plugin packaging for public Codex distribution after verification.
- Optional `.agents/plugins/marketplace.json` and `plugins/ai-berkshire/.codex-plugin/plugin.json`.
- `README.md` quickstart and usage table.
- Skill templates replacing `$ARGUMENTS`, `WebSearch`, `Task*`, `TeamCreate`, and `~/ai-berkshire`.

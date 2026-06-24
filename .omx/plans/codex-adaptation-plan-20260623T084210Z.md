# Ralplan: Adapt AI Berkshire from Claude Code to Codex

## Requirements Summary
Adapt the current Claude Code oriented AI Berkshire project so Codex can use its mechanisms and workflows natively while preserving the investment-research discipline: structured skills, multi-perspective review, factual sourcing, Python-based financial validation, Chinese report style, and report naming conventions.

## RALPLAN-DR Summary

### Principles
- Preserve research rigor before changing invocation syntax.
- Separate durable repo rules from task-specific workflows.
- Keep Claude compatibility unless the user explicitly chooses a Codex-only fork.
- Prefer Codex-native surfaces over emulating Claude internals.
- Make migration mechanical and testable across a small pilot set before converting all skills.

### Decision Drivers
- Codex/OMX skill discovery must be explicit: this user's current profile says project-local skills load from `.codex/skills`, while the current public Codex manual documents `.agents/skills`. The migration should target `.codex/skills` first for this machine and document `.agents/skills` or plugin packaging as the public/upstream-compatible distribution path.
- Current workflows contain Claude-specific primitives (`$ARGUMENTS`, `Task`, `TeamCreate`, `SendMessage`, `WebSearch`) that need Codex equivalents or neutral instructions.
- The project has durable project behavior in `CLAUDE.md` that belongs in Codex `AGENTS.md`, not inside every skill.

### Viable Options

#### Option A: Minimal Repo-Local Codex Compatibility
Create `AGENTS.md`, convert the most-used 3-5 skills into this environment's Codex skill path (`.codex/skills/<name>/SKILL.md`), and update README with Codex usage plus a compatibility note for public Codex `.agents/skills`.

Pros:
- Fastest usable path.
- Low risk to the existing repository.
- Lets one pilot validate Codex skill activation and report output quality.

Cons:
- Leaves some skills Claude-only until converted.
- Users must know which skills are available in Codex.

#### Option B: Full Dual-Mode Migration
Keep `skills/*.md` as Claude command sources, add `.codex/skills` as this environment's Codex-native generated or maintained copies, and document both routes. If distributing to stock/public Codex, mirror or package the Codex skills through `.agents/skills` or a plugin after verifying discovery.

Pros:
- Preserves Claude users and supports Codex users.
- Makes the repo broadly usable without forcing a tool choice.
- Can be implemented incrementally with a converter script later.

Cons:
- Duplicated skill content can drift unless tooling or clear source-of-truth rules are added.
- More documentation and QA work.

#### Option C: Codex Plugin Distribution
Package AI Berkshire as a Codex plugin with skills, optional metadata, optional MCP/tool dependencies, and marketplace entry.

Pros:
- Best installation experience for Codex app/CLI users.
- Can bundle many skills and metadata cleanly.
- Shareable across personal/workspace contexts.

Cons:
- Higher upfront packaging work.
- Still requires skill content cleanup first.
- Plugin is a distribution layer, not a substitute for adapting Claude-specific workflow language.

## Recommended Decision
Use Option B as the target architecture, executed through Option A first. Convert a pilot set into Codex repo-local skills under `.codex/skills` for this environment, create `AGENTS.md` from the durable parts of `CLAUDE.md`, validate one real research run, then batch-convert remaining skills. Add `.agents/skills` mirroring or Option C plugin packaging only after the Codex skill set is stable and discovery is verified.

## Evidence
- `README.md:7` frames the project as Claude Code based.
- `README.md:216-236` tells users to install Claude Code, copy `skills/*.md` to `~/.claude/commands/`, and invoke `/investment-research`.
- `README.md:129-145` and `README.md:162-165` define the core three-layer model: skills, multi-agent perspectives, and validation tools.
- `CLAUDE.md:68-76` contains tool-independent objective research principles that should become Codex repo instructions.
- `CLAUDE.md:78-85` defines Chinese report style and source requirements.
- `CLAUDE.md:106-111` defines financial verification expectations.
- `skills/investment-research.md:35-92` requires two-source financial data and `tools/financial_rigor.py` validation.
- `skills/investment-team.md:34-138` depends on Claude-specific team/task/message primitives.
- `tools/financial_rigor.py:1-16` is a Python CLI toolkit for validation and can remain callable from Codex.
- `/Users/bingzhang/.codex/config.toml:3` says this installed profile loads skills from `.codex/skills`, while the current Codex manual says repo skills live under `.agents/skills`.

## Implementation Plan

### 1. Create Codex Repo Guidance
Add `AGENTS.md` at the repository root.

Include:
- Project purpose and directory map from `CLAUDE.md:3-15`.
- Report layout and naming rules from `CLAUDE.md:17-66`.
- Objective-analysis rules from `CLAUDE.md:68-76`.
- Chinese style and source requirements from `CLAUDE.md:78-85`.
- Git and report hygiene rules from `CLAUDE.md:87-111`, adjusted for this checkout path instead of hardcoded `~/ai-berkshire`.

Acceptance criteria:
- Starting Codex in repo root loads the project rules.
- No Claude-only tool names are required to understand the repository behavior.

### 2. Lock the Codex Skill Discovery Contract
Before converting content, make the target path explicit:

- Local OMX/Codex target for this machine: `.codex/skills/<skill-name>/SKILL.md`.
- Public Codex/manual-compatible target: `.agents/skills/<skill-name>/SKILL.md`.
- Plugin target: `plugins/ai-berkshire/skills/<skill-name>/SKILL.md`.

Initial implementation should use `.codex/skills` because the active profile says that is the loaded project-local skill path. Add a README compatibility note that stock Codex users may need `.agents/skills` or plugin installation, and verify before publishing.

Acceptance criteria:
- `AGENTS.md` or docs state which path is canonical for this checkout.
- Verification includes the active profile check and a skill discovery smoke test.

### 3. Establish Source-of-Truth and Drift Control
Do not manually maintain two diverging prompt products.

Phase-1 source of truth:
- Keep `skills/*.md` as the Claude command source.
- Create Codex skills as adapted derivatives under `.codex/skills`.
- Add a migration note that any change to a Claude skill must either update the paired Codex skill or explicitly mark the Codex skill stale.

Recommended phase-2 hardening:
- Add `tools/convert_skill_to_codex.py` or a checklist-driven converter that:
  - wraps each skill in `SKILL.md` frontmatter,
  - replaces `$ARGUMENTS`,
  - rewrites hardcoded `~/ai-berkshire` paths,
  - flags Claude-only primitives for manual handling.
- Add a drift check script or documented command:

```bash
rg -n "TeamCreate|TaskCreate|TaskUpdate|SendMessage|WebSearch|\\$ARGUMENTS|~/ai-berkshire|~/.claude" .codex/skills AGENTS.md README.md
```

Acceptance criteria:
- The pilot migration includes an explicit source-of-truth note.
- The drift grep is part of verification, not a deferred nice-to-have.

### 4. Convert Pilot Skills to Codex Skill Format
Create these first:
- `.codex/skills/investment-research/SKILL.md`
- `.codex/skills/investment-team/SKILL.md`
- `.codex/skills/financial-data/SKILL.md`
- `.codex/skills/news-pulse/SKILL.md`

Skill frontmatter should use concise Codex trigger descriptions. Example:

```md
---
name: investment-research
description: Produce a rigorous Chinese value-investing research report for a public company using four-master analysis, two-source financial validation, and Python tool checks.
---
```

Adaptation rules:
- Replace `$ARGUMENTS` with "the company/topic supplied by the user".
- Replace `~/ai-berkshire` with "repo root" or relative paths like `tools/financial_rigor.py`.
- Replace `WebSearch` with "use current web research when market/company facts are time-sensitive; cite sources".
- Replace Claude `Task` with Codex subagent language: "When the user explicitly asks for parallel research or the skill requires team mode, spawn bounded subagents for independent lanes."
- Replace `TeamCreate`, `TaskCreate`, `TaskUpdate`, `SendMessage` with Codex app/CLI subagent orchestration instructions and final synthesis requirements.
- Keep mandatory Python validation commands, but use `python3 tools/...` from repo root.

Acceptance criteria:
- Each pilot skill has valid `name` and `description`.
- Codex can explicitly invoke each via `$investment-research`, `$investment-team`, etc. in this local profile.
- Pilot skill text no longer requires Claude-only APIs to be actionable.

### 5. Define the Codex Team-Skill Execution Contract
For team-heavy skills such as `investment-team`, do not merely replace words. Define the actual Codex workflow:

- Main Codex agent is Team Lead.
- Four optional subagent lanes:
  - `business-analyst`: business model, moat, user/customer value, Duan Yongping lens.
  - `financial-analyst`: financial statements, valuation, capital allocation, Buffett lens, plus mandatory Python validation.
  - `industry-researcher`: industry structure, competitors, failure modes, Munger lens.
  - `risk-assessor`: management, governance, regulation, long-term uncertainty, Li Lu lens.
- Each lane must return a Markdown section with sources, confidence markers, unresolved data gaps, and a clear pass/conditional/fail view.
- If subagents are unavailable or the user did not explicitly authorize parallel work, the main agent must run the same four lanes sequentially and say so in the report metadata.
- Shutdown/message primitives are removed; synthesis happens by collecting subagent final responses or sequential lane outputs.
- Team Lead output must include disagreement analysis, not just averaged scores.

Acceptance criteria:
- `investment-team` no longer mentions `TeamCreate`, `TaskCreate`, `TaskUpdate`, or `SendMessage` except in a Claude-compatibility note outside Codex skill text.
- The final report structure still matches `CLAUDE.md:56-66`.

### 6. Preserve Tooling and Add Verification Commands
Do not rewrite `tools/financial_rigor.py` initially. Add a short `docs/codex-usage.md` or README section showing:

```bash
python3 tools/financial_rigor.py verify-market-cap ...
python3 tools/report_audit.py extract ...
python3 tools/report_audit.py verdict ...
```

Acceptance criteria:
- Tool examples run from repository root.
- Skill instructions point to the same commands.

### 7. Validate One End-to-End Pilot
Run one representative prompt in Codex, preferably:

```text
$investment-research 腾讯
```

Expected evidence:
- Report is Chinese.
- It includes information richness rating.
- Key financial data has two sources or explicit gap markers.
- Market cap or valuation math is checked with `tools/financial_rigor.py`.
- Facts and opinions are separated.
- Output path follows `CLAUDE.md` naming rules.

### 8. Batch-Convert Remaining Skills
After the pilot passes, convert the remaining Markdown commands:
- `earnings-review`, `earnings-team`, `industry-research`, `industry-funnel`, `quality-screen`, `investment-checklist`, `portfolio-review`, `thesis-tracker`, `management-deep-dive`, `private-company-research`, `deep-company-series`, `bottleneck-hunter`, `wechat-article`, `dyp-ask`.

Use the same migration rules as step 2. For team-heavy skills, explicitly state whether Codex should stay single-agent unless the user asks for subagents, or whether the skill itself asks the user to explicitly authorize parallel subagents.

### 9. Optional Plugin Packaging
Once repo-local skills are stable, create a plugin:
- `plugins/ai-berkshire/.codex-plugin/plugin.json`
- `plugins/ai-berkshire/skills/...`
- `.agents/plugins/marketplace.json`
- Optional `agents/openai.yaml` metadata per high-value skill.

Acceptance criteria:
- Plugin appears in Codex plugin directory after restart.
- Skills are discoverable from plugin install.
- Repo-local and plugin copies have a documented source-of-truth strategy.

## Risks and Mitigations

- Risk: Skill drift between Claude and Codex copies.
  Mitigation: Make source-of-truth and drift grep mandatory in phase 1. Prefer generated or checklist-converted Codex skills over freehand copies.

- Risk: Codex subagents are spawned only when explicitly requested, while current Claude skills assume automatic parallel agents.
  Mitigation: Rewrite team skills with an explicit Codex team-skill execution contract and sequential fallback.

- Risk: Web-researched financial facts become stale.
  Mitigation: Codex skill descriptions should say market/company facts are time-sensitive and require live source lookup plus citations.

- Risk: Hardcoded paths fail on this checkout.
  Mitigation: Replace `~/ai-berkshire` with repo-relative commands everywhere in Codex skills.

- Risk: Investment reports become persuasive without evidence.
  Mitigation: Keep `AGENTS.md` objective-analysis constraints and tool validation as non-optional.

## Verification Steps
- Run `find .codex/skills -name SKILL.md -maxdepth 3` and confirm expected skills exist for this local profile.
- If targeting stock Codex/public distribution, also run `find .agents/skills -name SKILL.md -maxdepth 3` or verify plugin installation.
- Run `rg -n "TeamCreate|TaskCreate|TaskUpdate|SendMessage|WebSearch|\\$ARGUMENTS|~/ai-berkshire|~/.claude" .codex/skills AGENTS.md README.md` and confirm remaining mentions are either removed or explicitly documented as Claude-only.
- Run `rg -n "reports/.+|最终报告|report_audit|financial_rigor" .codex/skills AGENTS.md` and confirm report path, audit, and financial validation requirements survived migration.
- Run `python3 tools/financial_rigor.py --help` and `python3 tools/report_audit.py --help`.
- Start a fresh Codex session in repo root and ask it to summarize loaded instructions.
- Invoke one pilot skill and inspect the generated report against the acceptance criteria above.

## ADR

### Decision
Adopt dual-mode migration: first create Codex-native repo skills under the active local `.codex/skills` path plus `AGENTS.md`, then optionally mirror to public Codex `.agents/skills` or package a Codex plugin after the workflow content is stable.

### Drivers
- Codex and Claude use different discovery and orchestration surfaces.
- This user's active Codex/OMX profile and public Codex documentation disagree on repo skill path, so the local implementation target must be explicit.
- The project has high-value reusable workflows that map naturally to Codex skills.
- Durable project behavior belongs in `AGENTS.md`, while task workflows belong in skills.

### Alternatives Considered
- Copy `skills/*.md` directly into `.codex/skills` or `.agents/skills` without edits: rejected because Codex skills require `SKILL.md` folders and Claude-specific primitives would remain unusable.
- Replace all Claude docs with Codex docs immediately: rejected because it would break existing Claude users and create a larger, riskier diff.
- Build plugin first: rejected because plugin packaging does not solve the Claude-specific instruction adaptation.

### Why Chosen
The phased dual-mode path creates immediate Codex usability with limited blast radius and keeps the existing Claude workflow intact until Codex parity is validated.

### Consequences
- Some duplication exists during migration, controlled by explicit source-of-truth and drift checks.
- Team-heavy skills require careful rewriting around Codex subagent semantics.
- Documentation must clearly distinguish Claude slash commands from Codex `$skill` invocation.

### Follow-ups
- Decide whether to maintain dual sources manually or add a converter script.
- Decide whether to publish/share a plugin after pilot validation.
- Add a small regression checklist for generated reports.

## Available-Agent-Types Roster
- `explore`: repo lookup and migration inventory.
- `planner`: migration sequencing.
- `architect`: design review of Codex surface mapping.
- `critic`: plan quality and risk review.
- `executor`: implement skill/doc/file changes.
- `test-engineer`: validate pilot report and command checks.
- `writer`: README and usage documentation.
- `researcher`: official Codex docs lookup when behavior changes.

## Follow-up Staffing Guidance
- Default `$ultragoal`: one durable goal with sequential checkpoints for `AGENTS.md`, pilot skills, docs, validation, then batch conversion.
- `$team`: useful for batch conversion after pilot, with disjoint lanes by skill category.
- Suggested team lanes:
  - `executor` for `AGENTS.md` and pilot skills.
  - `writer` for README and `docs/codex-usage.md`.
  - `test-engineer` for command validation and pilot report QA.
  - `critic` for final migration review.
- `$ralph` fallback: use only if a single persistent owner is desired for the whole migration and parallel conversion is not worth the coordination cost.

## Launch Hints
```text
$ultragoal "Implement .omx/plans/codex-adaptation-plan-20260623T084210Z.md"
```

For parallel conversion after pilot:

```text
$team "Convert the remaining ai-berkshire Claude skills to Codex .codex/skills using .omx/plans/codex-adaptation-plan-20260623T084210Z.md"
```

## Team Verification Path
Team must prove:
- All converted skills have valid `SKILL.md` frontmatter.
- Claude-only terms have been removed or explicitly marked as Claude-only docs.
- Tool commands run from repo root.
- One pilot report satisfies factuality and validation gates.

Ultragoal checkpoints:
- `AGENTS.md` created.
- Pilot Codex skills created.
- Pilot verification passed.
- Remaining skills converted.
- Optional plugin packaged.

## Goal-Mode Follow-up Suggestions
- `$ultragoal`: recommended default for implementing this migration with durable checkpoints.
- `$team`: recommended after the pilot when converting many skills in parallel.
- `$autoresearch-goal`: not recommended as the main follow-up; this is migration work, not a research deliverable.
- `$performance-goal`: not applicable unless later optimizing tool runtime or report generation latency.

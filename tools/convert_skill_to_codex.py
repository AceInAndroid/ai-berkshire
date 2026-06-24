#!/usr/bin/env python3
"""Convert Claude Code command markdown into Codex skill wrappers."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


DESCRIPTIONS = {
    "bottleneck-hunter": "Find AI-era supply-chain bottleneck investment opportunities with Chinese research discipline, current sources, and validation gates.",
    "deep-company-series": "Create an eight-part Chinese deep company series with strict fact checking, revision handling, and publication-quality structure.",
    "dyp-ask": "Answer business, investing, and life questions through a Duan Yongping-style reasoning lens in Chinese.",
    "earnings-review": "Review original earnings materials in Chinese with primary-source discipline, financial validation, and thesis impact analysis.",
    "earnings-team": "Run a Codex-native multi-lane earnings review team and synthesize Chinese earnings analysis plus publishable output.",
    "industry-funnel": "Screen an industry from broad universe to top candidates using Chinese value-investing funnel discipline and data validation.",
    "industry-research": "Produce a Chinese industry-wide investment research report with value-chain mapping, company screening, and validation.",
    "investment-checklist": "Apply a Buffett-style Chinese buy-before checklist to one or more companies with hard rejection rules and data checks.",
    "management-deep-dive": "Research management quality, incentives, culture, and capital allocation in Chinese using value-investing standards.",
    "portfolio-review": "Review and improve a portfolio in Chinese across concentration, thesis, valuation, risk, and rebalancing discipline.",
    "private-company-research": "Research a private company in Chinese using limited-information discipline, source confidence labels, and first-principles analysis.",
    "quality-screen": "Screen companies or themes for quality using hard exclusion criteria, financial evidence, and concise Chinese output.",
    "thesis-tracker": "Maintain or review an investment thesis tracker in Chinese with falsification signals, valuation anchors, and monitoring rules.",
    "wechat-article": "Turn investment research into a Chinese WeChat-style article while preserving factual rigor and source discipline.",
}

TEAM_HEAVY = {
    "investment-team",
    "earnings-team",
    "news-pulse",
    "private-company-research",
}


def title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :].lstrip()
    return text


def transform_body(text: str) -> str:
    replacements = {
        "$ARGUMENTS": "the user-supplied company, ticker, industry, or topic",
        "~/ai-berkshire/": "",
        "~/ai-berkshire": "the repository root",
        "WebSearch": "current web research",
        "Bash": "shell",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\bTask 工具\b", "Codex subagent or sequential research lane", text)
    text = re.sub(r"\bTask\b", "Codex subagent or sequential research lane", text)
    return text


def codex_preamble(slug: str) -> str:
    team_note = ""
    if slug in TEAM_HEAVY:
        team_note = """
For team-heavy steps, run Codex subagents only when the user explicitly asks for parallel research or the active Codex surface authorizes subagents. Otherwise execute the same lanes sequentially and note that fallback in the output metadata. Do not use Claude-specific team creation, task creation, task update, or inter-agent message primitives.
"""

    return f"""# {title_from_slug(slug)}

This is the Codex-adapted derivative of `skills/{slug}.md`. Treat the original file as the Claude command source and this file as the executable Codex skill for this local OMX/Codex profile.

Follow repository rules in `AGENTS.md` before applying this workflow.

Codex adaptation rules:
- Use the user-supplied company, ticker, industry, portfolio, or topic as the task input.
- Run commands from the repository root.
- Use `python3 tools/financial_rigor.py ...` and `python3 tools/report_audit.py ...` for financial validation and report audits.
- Use current web research with citations for time-sensitive market, company, financial, or news facts.
- Keep facts, opinions, estimates, and uncertainty explicitly separated.
- Write reports in Chinese unless the user asks otherwise.
{team_note}
## Original Methodology Adapted For Codex
"""


def convert(src: Path, dest_root: Path) -> Path:
    slug = src.stem
    body = transform_body(strip_frontmatter(src.read_text(encoding="utf-8")))
    description = DESCRIPTIONS.get(
        slug,
        f"Run the AI Berkshire {slug} workflow in Codex with Chinese investment research rigor and validation.",
    )
    out_dir = dest_root / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "SKILL.md"
    out_path.write_text(
        f"---\nname: {slug}\ndescription: {description}\n---\n\n"
        + codex_preamble(slug)
        + "\n"
        + body,
        encoding="utf-8",
    )
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src-dir", default="skills")
    parser.add_argument("--dest-dir", default=".codex/skills")
    parser.add_argument("--skip", action="append", default=[])
    args = parser.parse_args()

    src_dir = Path(args.src_dir)
    dest_root = Path(args.dest_dir)
    skip = set(args.skip)

    for src in sorted(src_dir.glob("*.md")):
        if src.stem in skip:
            continue
        out = convert(src, dest_root)
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

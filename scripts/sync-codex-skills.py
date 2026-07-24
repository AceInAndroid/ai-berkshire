#!/usr/bin/env python3
"""Generate Codex skills from AI Berkshire Claude command files."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILLS = ROOT / "skills"
CODEX_SKILLS = ROOT / "codex-skills"


# Human-facing metadata for the most common Codex App entry points. Other
# generated skills receive a deterministic fallback so every canonical AI
# Berkshire skill is discoverable from the Skills UI.
SKILL_UI = {
    "research": (
        "AI Berkshire 投研路由",
        "输入公司或投资问题，自动选择研究、财报、估值和跟踪流程",
        "使用 $research 研究这家公司或投资问题，并自动选择正确的 AI Berkshire 工作流。",
    ),
    "investment-research": (
        "公司深度研究",
        "用巴菲特、芒格、段永平和李录框架研究上市公司",
        "使用 $investment-research 对这家公司执行完整的价值投资研究。",
    ),
    "earnings-review": (
        "财报精读",
        "从一手披露核验业绩、预期差、现金流和论文变化",
        "使用 $earnings-review 精读这家公司最新或指定期间的财报。",
    ),
    "investment-checklist": (
        "买入前检查",
        "检查公司质量、估值安全边际、风险和关键反证",
        "使用 $investment-checklist 判断这些候选公司是否通过买入前检查。",
    ),
    "tradingagents-astock": (
        "A股融合研究",
        "融合多角色辩论、市场资金证据和长期价值判断",
        "使用 $tradingagents-astock 对这家 A 股公司做只读融合研究。",
    ),
    "news-pulse": (
        "公司异动归因",
        "建立事件时间线，解释大涨大跌并判断是否重审论文",
        "使用 $news-pulse 调查这家公司近期异动的主要原因和论文影响。",
    ),
    "industry-funnel": (
        "行业选股漏斗",
        "从行业或主题逐层筛选到少数高质量候选公司",
        "使用 $industry-funnel 从这个行业或主题筛选值得深入研究的公司。",
    ),
    "management-deep-dive": (
        "管理层研究",
        "研究创始人、管理层、治理、激励和资本配置记录",
        "使用 $management-deep-dive 深入研究这家公司及其管理层。",
    ),
    "portfolio-review": (
        "投资组合复盘",
        "检查持仓结构、集中度、相关风险和下一步研究动作",
        "使用 $portfolio-review 复盘这个投资组合并给出风险与研究建议。",
    ),
    "thesis-tracker": (
        "投资论文跟踪",
        "把催化剂、观察指标和失效条件转成持续跟踪清单",
        "使用 $thesis-tracker 更新这家公司的投资论文与观察清单。",
    ),
}


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 5 :].lstrip("\n")


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def yaml_quote(value: str) -> str:
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def metadata_for(name: str, source_name: str, source_text: str) -> str:
    existing, body = split_frontmatter(source_text)
    if existing:
        has_name = re.search(r"(?m)^name:\s*", existing) is not None
        has_description = re.search(r"(?m)^description:\s*", existing) is not None
        lines = []
        if not has_name:
            lines.append(f"name: {name}")
        if not has_description:
            title = first_heading(body, name)
            lines.append(
                "description: "
                + yaml_quote(f"AI Berkshire skill: {title}. Source: skills/{source_name}.")
            )
        lines.append(existing.rstrip())
        return "---\n" + "\n".join(lines) + "\n---\n\n"

    title = first_heading(source_text, name)
    description = f"AI Berkshire skill: {title}. Source: skills/{source_name}."
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {yaml_quote(description)}\n"
        "---\n\n"
    )


def codex_body(name: str, source_name: str, source_text: str) -> str:
    _, body = split_frontmatter(source_text)
    note = (
        "## Codex adapter note\n\n"
        f"This skill is generated from `skills/{source_name}` so Claude Code "
        "and Codex users share one canonical workflow.\n\n"
        "- Treat `$ARGUMENTS` as the user's request in the current Codex thread.\n"
        "- When the source mentions Claude-only surfaces such as Task, Agent, "
        "WebSearch, Bash, Read, or Write, use the closest Codex capability "
        "available in this session: subagents when available, web search when "
        "needed, shell commands for local tools, and normal file edits for "
        "workspace files.\n"
        "- Use shared project tools from `tools/` in this repository. Commands "
        "that reference `~/ai-berkshire/tools/...` assume the repo is checked "
        "out at `~/ai-berkshire`; if needed, prefer the current workspace path.\n"
        "- Preserve the research quality rules from `AGENTS.md`: cross-check "
        "financial data, use exact arithmetic tools for valuation/math, and "
        "clearly label uncertainty and source gaps.\n\n"
    )
    return note + body.rstrip() + "\n"


def ui_metadata(name: str, title: str) -> str:
    display_name, short_description, default_prompt = SKILL_UI.get(
        name,
        (
            title,
            f"AI Berkshire 工作流：{title}",
            f"使用 ${name} 按 AI Berkshire 方法完成这项请求。",
        ),
    )
    return (
        "interface:\n"
        f"  display_name: {yaml_quote(display_name)}\n"
        f"  short_description: {yaml_quote(short_description)}\n"
        f"  default_prompt: {yaml_quote(default_prompt)}\n"
    )


def main() -> None:
    check = "--check" in sys.argv[1:]
    unknown_args = [arg for arg in sys.argv[1:] if arg != "--check"]
    if unknown_args:
        joined = ", ".join(unknown_args)
        raise SystemExit(f"Unknown argument(s): {joined}")

    if not check:
        CODEX_SKILLS.mkdir(exist_ok=True)

    count = 0
    stale: list[str] = []
    for source in sorted(CLAUDE_SKILLS.glob("*.md")):
        name = source.stem
        source_text = source.read_text(encoding="utf-8")
        target_dir = CODEX_SKILLS / name
        target = target_dir / "SKILL.md"
        agents_dir = target_dir / "agents"
        ui_target = agents_dir / "openai.yaml"
        content = metadata_for(name, source.name, source_text) + codex_body(
            name, source.name, source_text
        )
        _, body = split_frontmatter(source_text)
        ui_content = ui_metadata(name, first_heading(body, name))
        if check:
            if not target.exists() or target.read_text(encoding="utf-8") != content:
                stale.append(str(target.relative_to(ROOT)))
            if (
                not ui_target.exists()
                or ui_target.read_text(encoding="utf-8") != ui_content
            ):
                stale.append(str(ui_target.relative_to(ROOT)))
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            agents_dir.mkdir(parents=True, exist_ok=True)
            ui_target.write_text(ui_content, encoding="utf-8")
        count += 1

    if check:
        if stale:
            print("Codex skills are out of date:")
            for path in stale:
                print(f"  {path}")
            raise SystemExit(1)
        print(f"Checked {count} Codex skills in {CODEX_SKILLS.relative_to(ROOT)}")
        return

    print(f"Generated {count} Codex skills in {CODEX_SKILLS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

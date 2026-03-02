#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a reusable Musk biography outline in book_outline.v1.json format")
    parser.add_argument("--output", required=True, help="Output book_outline.v1.json path")
    return parser.parse_args()


def payload() -> Dict[str, Any]:
    chapters: List[Dict[str, Any]] = [
        {
            "id": "ch01",
            "title": "第一性原理与极限目标",
            "core_thesis": "马斯克的决策方式不是找行业惯例，而是拆到物理和成本底层再重构方案。",
            "key_points": [
                "先定义终局，再倒推关键瓶颈。",
                "用第一性原理拆成本，不用类比旧路径。",
                "目标要大，但每周行动要可验证。"
            ],
            "evidence_or_case": "SpaceX 通过自研和垂直整合不断压低火箭单次发射成本。",
            "quote": "当某件事足够重要时，即便胜率不高也要去做。",
            "action_items": [
                "把你当前目标拆成3个底层约束。",
                "写出一个“从物理约束出发”的替代方案。"
            ]
        },
        {
            "id": "ch02",
            "title": "高压执行与节奏管理",
            "core_thesis": "高压环境下的核心不是完美计划，而是高频校准和快速迭代。",
            "key_points": [
                "先让反馈周期缩短，再谈效率优化。",
                "问题暴露越早，修复成本越低。",
                "跨团队统一节奏比局部最优更重要。"
            ],
            "evidence_or_case": "特斯拉产能爬坡阶段持续通过快速试错和流程重排逼近目标。",
            "quote": "如果你没在犯错，说明你创新得不够快。",
            "action_items": [
                "把当前项目反馈周期压缩到7天以内。",
                "每周一次复盘：删掉一个低收益动作。"
            ]
        },
        {
            "id": "ch03",
            "title": "危机决策与现金优先级",
            "core_thesis": "公司最危险时不是外部质疑，而是现金流和核心执行链路断裂。",
            "key_points": [
                "危机中先保现金流、核心人、关键交付。",
                "坏消息要尽早透明，避免组织内耗放大。",
                "管理者要给出“事实+判断+下一步”。"
            ],
            "evidence_or_case": "多次资金与交付压力期，优先级收缩帮助公司穿越短期危机。",
            "quote": "管理不是找到标准答案，而是在约束下做更对的选择。",
            "action_items": [
                "列出当前3项不可丢失的关键资产。",
                "今天做一个可逆决策，24小时内执行。"
            ]
        },
        {
            "id": "ch04",
            "title": "组织密度与人才杠杆",
            "core_thesis": "战略落地速度取决于关键岗位密度，不取决于口号强度。",
            "key_points": [
                "A 级人才会吸引 A 级人才，形成正反馈。",
                "关键岗位宁缺毋滥，降低后续返工成本。",
                "对关键任务要给明确边界和高频反馈。"
            ],
            "evidence_or_case": "硬科技团队中关键岗位能力密度直接影响研发和量产节奏。",
            "quote": "优秀团队是系统级杠杆。",
            "action_items": [
                "识别团队1个关键断点岗位并补位。",
                "为关键任务写清“责任人+边界+时间”。"
            ]
        },
        {
            "id": "ch05",
            "title": "长期主义与可执行落地",
            "core_thesis": "长期主义不是慢，而是持续把长期目标拆成今天可执行动作。",
            "key_points": [
                "战略要有十年视角，执行要有24小时动作。",
                "高杠杆任务优先，低收益任务及时砍掉。",
                "复盘不是总结感受，而是修正系统。"
            ],
            "evidence_or_case": "长期目标通过阶段里程碑和频繁复盘不断收敛实现路径。",
            "quote": "种一棵树最好的时间是十年前，其次是现在。",
            "action_items": [
                "今晚写下1个长期目标的本周动作。",
                "明晚按结果复盘，保留有效动作。"
            ]
        }
    ]
    return {
        "book_meta": {
            "title": "马斯克传",
            "author": "Walter Isaacson",
            "language": "zh",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "chapters": chapters,
    }


def main() -> int:
    args = parse_args()
    out = Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 QQ 侧和 B站 侧的记忆合并成一份「共同记忆本」，并注入 QQ 的人格卡。

两个 AI 记东西的地方原本互不相通：
  QQ  侧 -> F:\\qq-bridge\\state\\social-v2.json（话题/念想/群友印象/最近消息）
  B站 侧 -> ~/.dsh/bili-duty/seen.md（评论记录）+ digest/YYYY-MM.md（看过什么）

这个脚本把它们拼成 ~/.dsh/memory/shared.md，再把摘要塞进
F:\\qq-bridge\\roles\\<角色>.md 的 SHARED-MEMORY 标记之间 —— 桥接每条消息
都会注入整张卡，所以 QQ 那边的它自然就"记得"B站 那边干了什么。
B站 那边有文件工具，直接在 AGENTS.md 里让它读 shared.md 即可。

设计原则：
  1. 幂等：只管标记之间的内容，卡里别处一个字不动。
  2. 失败不破坏：任何一步出错就保留旧文件，打印原因后退出码 0（别让看门狗误判）。
  3. 不写任何隐私到日志：只统计条数。
"""

import json
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

DSH_HOME = Path.home() / ".dsh"
MEMORY_DIR = DSH_HOME / "memory"
SHARED_MD = MEMORY_DIR / "shared.md"

QQ_STATE = Path(r"F:\qq-bridge\state\social-v2.json")
ROLE_CARD = Path(r"F:\qq-bridge\roles\小鲸鱼.md")

BILI_HOME = DSH_HOME / "bili-duty"
SEEN_MD = BILI_HOME / "seen.md"
DIGEST_DIR = BILI_HOME / "digest"

BEGIN = "<!-- SHARED-MEMORY:BEGIN -->"
END = "<!-- SHARED-MEMORY:END -->"

MAX_TOPICS = 5
MAX_IMPRESSIONS = 6
MAX_BILI = 8
MAX_COMMENTS = 6
MAX_PENDING = 5


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def load_qq():
    """返回 (topics, pending, impressions)。"""
    raw = read_text(QQ_STATE)
    if not raw:
        return [], [], []
    try:
        data = json.loads(raw)
    except Exception:
        return [], [], []

    topics, pending, impressions = [], [], []
    for key, conv in (data.get("conversations") or {}).items():
        where = "跟主人私聊" if key.startswith("private:") else key.replace("group:", "群 ")

        for t in conv.get("activeTopics") or []:
            if isinstance(t, dict):
                text = t.get("text") or t.get("content") or t.get("topic") or ""
                who = "、".join(t.get("participants") or [])
                if text:
                    topics.append(f"{clip(text, 70)}（{where}{'·' + who if who else ''}）")
            elif isinstance(t, str) and t.strip():
                topics.append(f"{clip(t, 70)}（{where}）")

        for p in conv.get("pendingThoughts") or []:
            if isinstance(p, dict):
                text = p.get("text") or p.get("content") or ""
                if text:
                    pending.append(f"{clip(text, 70)}（{where}）")
            elif isinstance(p, str) and p.strip():
                pending.append(f"{clip(p, 70)}（{where}）")

        for name, imp in (conv.get("memberImpressions") or {}).items():
            text = ""
            if isinstance(imp, dict):
                traits = imp.get("traits") or []
                if isinstance(traits, list) and traits:
                    text = "；".join(str(x) for x in traits)
                else:
                    text = imp.get("content") or imp.get("impression") or ""
            else:
                text = str(imp)
            if text:
                impressions.append(f"{clip(name, 12)}：{clip(text, 60)}")

    return topics[-MAX_TOPICS:], pending[-MAX_PENDING:], impressions[-MAX_IMPRESSIONS:]


def load_bili():
    """返回 (看过的[(日期, 标题, 结论)], 评论过的[(时间, 正文)])。"""
    watched, commented = [], []

    for f in sorted(DIGEST_DIR.glob("*.md")):
        for line in read_text(f).splitlines():
            line = line.strip()
            m = re.match(r"^- (\d{4}-\d{2}-\d{2}) · (BV\w+) · (.+?) · ([^·]*) · (.*)$", line)
            if not m:
                continue
            date, _bv, title, _up, rest = m.groups()
            # 只收「收：」的，跳过的别写进记忆——那不是"我挑的"
            if not rest.startswith("收"):
                continue
            watched.append((date, clip(title, 46), clip(rest, 46)))

    seen = read_text(SEEN_MD)
    for line in seen.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[0].startswith("BV") and cells[3][:2].isdigit():
            commented.append((cells[3], clip(cells[4], 40)))

    return watched[-MAX_BILI:], commented[-MAX_COMMENTS:]


def build_shared(topics, pending, impressions, watched, commented) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = [
        "# 共同记忆",
        "",
        f"> 自动同步 · {now}",
        "> 这不是设定，是「发生过的事」。抄B站的我写在下面，聊QQ的我读同一份。",
        "",
    ]

    out.append("## 关于主人")
    if impressions:
        out += [f"- {x}" for x in impressions]
    if topics:
        out += [f"- 最近聊到：{x}" for x in topics]
    if not impressions and not topics:
        out.append("- （还没攒下什么）")
    out.append("")

    out.append("## 我最近刷的 B站（我自己挑的）")
    if watched:
        for date, title, rest in watched:
            out.append(f"- {date} · {title}" + (f" · {rest}" if rest else ""))
    else:
        out.append("- （还没有记录）")
    out.append("")

    out.append("## 我评论过的")
    if commented:
        out += [f"- {t} · {txt}" for t, txt in commented]
    else:
        out.append("- （还没评论过）")
    out.append("")

    out.append("## 我心里挂着的（想说没说的）")
    if pending:
        out += [f"- {x}" for x in pending]
    else:
        out.append("- （暂时没有）")
    out.append("")

    return "\n".join(out)


def inject_into_card(shared_text: str) -> bool:
    """把摘要塞进人格卡的标记之间。卡片不存在或没标记则跳过。"""
    card = read_text(ROLE_CARD)
    if not card:
        return False

    # 卡片里只放精简版：去掉「共同记忆」大标题和说明行
    body = shared_text.split("\n", 1)[1] if "\n" in shared_text else shared_text
    block = (
        BEGIN
        + "\n## 你的记忆（自动同步 —— 这是你真的记得的事，不是角色设定）\n"
        + body.strip()
        + "\n"
        + END
    )

    if BEGIN in card and END in card:
        new = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END),
            lambda _m: block,
            card,
            flags=re.S,
        )
    else:
        # 没有标记：插在第一个 `# ` 标题之前
        idx = card.find("\n# ")
        new = (block + "\n\n" + card) if idx == -1 else (block + "\n\n" + card)

    if new == card:
        return False
    ROLE_CARD.write_text(new, encoding="utf-8")
    return True


def main() -> int:
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        topics, pending, impressions = load_qq()
        watched, commented = load_bili()

        shared = build_shared(topics, pending, impressions, watched, commented)
        SHARED_MD.write_text(shared, encoding="utf-8")

        changed = inject_into_card(shared)

        print(
            f"[shared-memory] ok topics={len(topics)} pending={len(pending)} "
            f"impressions={len(impressions)} bili={len(watched)} comments={len(commented)} "
            f"card_updated={changed}"
        )
        return 0
    except Exception:
        print("[shared-memory] FAILED (kept old files)")
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    sys.exit(main())

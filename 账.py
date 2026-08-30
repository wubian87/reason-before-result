"""只增不改的账本：按天一个 JSONL 文件，只追加、永不改写、永不删除。

给交易流程当「黑匣子」用：每一次判断、每一道闸、每一笔下单和回执，
都原样落盘；出事的时候，用 渲染中文() 把当天的事讲给不懂技术的人听。
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 全部时间一律按北京时间记，不用本机时区
北京时区 = ZoneInfo("Asia/Shanghai")

# 「类」的合法取值就这八种，传别的直接抛错
合法的类 = ("判断", "闸", "下单", "回执", "MCP请求", "MCP回执", "复盘", "错")

# 记() 不传编号时按「类」取默认前缀自动发号（见 漏列候选.md 第 2 条）
类到前缀 = {
    "判断": "J",
    "闸": "Z",
    "下单": "D",
    "回执": "H",
    "MCP请求": "M",
    "MCP回执": "M",
    "复盘": "F",
    "错": "E",
}


def 今日() -> str:
    """北京时间今天的日期，YYYY-MM-DD。"""
    return datetime.now(北京时区).strftime("%Y-%m-%d")


def 现在时刻() -> str:
    """北京时间此刻的 ISO 8601，精确到秒，带 +08:00。"""
    return datetime.now(北京时区).isoformat(timespec="seconds")


def 取正文(记录: dict) -> dict:
    """安全地取出「正文」：不是字典就当空字典，绝不崩。"""
    正文 = 记录.get("正文")
    return 正文 if isinstance(正文, dict) else {}


class 账本:
    """一天一个文件（<目录>/YYYY-MM-DD.jsonl），一行一条 JSON，只追加。"""

    def __init__(self, 目录: str | Path):
        self.目录 = Path(目录)
        self.目录.mkdir(parents=True, exist_ok=True)
        self._锁 = threading.Lock()
        # 记住每个（日期， 前缀）今天已经发到几号。
        # 纯靠「数文件里同前缀的条数」的话，连发三次会三次都拿到同一个号，
        # 和自检要求的 -001/-002/-003 矛盾，所以实例内记账（见 漏列候选.md 第 1 条）。
        self._已发到: dict[tuple[str, str], int] = {}

    def 发号(self, 前缀: str) -> str:
        """发一个当天的序号，形如 J-2026-08-31-001。"""
        日期 = 今日()
        with self._锁:
            return self._发号于(日期, 前缀)

    def 记(self, 类: str, 正文: dict, 编号: str | None = None) -> dict:
        """追加一条记录，返回写下去的那条完整记录。"""
        if 类 not in 合法的类:
            raise ValueError(f"「类」只能是：{'、'.join(合法的类)}；这次传的是「{类}」。")
        if not isinstance(正文, dict):
            raise ValueError("「正文」必须是字典。")
        时刻 = 现在时刻()
        日期 = 时刻[:10]
        with self._锁:
            if 编号 is None:
                编号 = self._发号于(日期, 类到前缀[类])
            记录 = {"时刻": 时刻, "类": 类, "编号": 编号, "正文": 正文}
            行 = json.dumps(记录, ensure_ascii=False)
            # 追加模式打开、一次写完一整行，多进程也不会互相截断
            with open(self.目录 / f"{日期}.jsonl", "a", encoding="utf-8") as 文件:
                文件.write(行 + "\n")
        return 记录

    def 读(self, 日期: str | None = None) -> list[dict]:
        """读出某天全部记录；文件不存在给空表；坏行跳过并把原文收进一条「错」里。"""
        路径 = self.目录 / f"{日期 or 今日()}.jsonl"
        if not 路径.exists():
            return []
        记录们: list[dict] = []
        with open(路径, "r", encoding="utf-8") as 文件:
            for 原行 in 文件:
                行 = 原行.strip()
                if not 行:
                    continue
                try:
                    记录 = json.loads(行)
                except json.JSONDecodeError:
                    记录 = None
                if not isinstance(记录, dict) or "类" not in 记录:
                    记录们.append({
                        "时刻": 现在时刻(),
                        "类": "错",
                        "编号": None,
                        "正文": {"坏行原文": 行},
                    })
                    continue
                记录们.append(记录)
        return 记录们

    def 渲染中文(self, 日期: str | None = None) -> str:
        """把某天的流水渲染成给「不懂技术、不懂英文的人」看的中文说明。"""
        日 = 日期 or 今日()
        记录们 = self.读(日)

        def 数(类: str) -> int:
            return sum(1 for 条 in 记录们 if 条.get("类") == 类)

        放行数 = sum(1 for 条 in 记录们 if 条.get("类") == "闸" and 取正文(条).get("放行"))
        行们 = [
            f"# 当日流水 · {日}（北京时间）",
            "",
            f"共 {len(记录们)} 条：判断 {数('判断')} 笔 ｜ 闸放行 {放行数} 笔 ｜ "
            f"闸拦下 {数('闸') - 放行数} 笔 ｜ 下单 {数('下单')} 笔 ｜ 出错 {数('错')} 次",
            "",
        ]
        for 条 in 记录们:
            行们.extend(self._渲染一条(条))
        return "\n".join(行们)

    # ---- 内部工具 ----

    def _发号于(self, 日期: str, 前缀: str) -> str:
        """在指定日期上给指定前缀发下一个号（调用方需已持锁）。"""
        键 = (日期, 前缀)
        if 键 not in self._已发到:
            self._已发到[键] = self._当天最大序号(日期, 前缀)
        self._已发到[键] += 1
        return f"{前缀}-{日期}-{self._已发到[键]:03d}"

    def _当天最大序号(self, 日期: str, 前缀: str) -> int:
        """扫一遍当天文件，取该前缀已用过的最大序号（没有就 0）。"""
        样子 = re.compile(re.escape(前缀) + r"-(\d{4}-\d{2}-\d{2})-(\d+)$")
        最大 = 0
        for 记录 in self.读(日期):
            编号 = 记录.get("编号")
            if not isinstance(编号, str):
                continue
            匹配 = 样子.fullmatch(编号)
            if 匹配 and 匹配.group(1) == 日期:
                最大 = max(最大, int(匹配.group(2)))
        return 最大

    def _渲染一条(self, 记录: dict) -> list[str]:
        """把一条记录渲染成两三行中文；渲染失败也不许整个渲染崩掉。"""
        类 = str(记录.get("类", "错"))
        时刻 = str(记录.get("时刻", ""))
        时间 = 时刻[11:19] if len(时刻) >= 19 else 时刻
        编号 = 记录.get("编号") or "无编号"
        正文 = 取正文(记录)
        try:
            if 类 == "闸":
                判词 = "✅ 放行" if 正文.get("放行") else "⛔ 拦下"
                一句话 = 正文.get("一句话", "")
                return [f"- {时间} 【闸】{判词}——{一句话}", f"  - 编号：{编号}"]
            if 类 == "MCP请求":
                工具 = 正文.get("工具", "未知工具")
                return [f"- {时间} 【调用】→ 通过 MCP 调用工具：{工具}", f"  - 编号：{编号}"]
            if 类 == "MCP回执":
                工具 = 正文.get("工具", "未知工具")
                耗时 = 正文.get("耗时秒", "？")
                结果 = "成功" if 正文.get("成功") else "失败"
                return [f"- {时间} 【返回】工具 {工具} 已返回（{结果}，耗时 {耗时} 秒）",
                        f"  - 编号：{编号}"]
            if 类 == "错":
                return [f"- {时间} ⛔ 【出错】{self._短文本(正文)}", f"  - 编号：{编号}"]
            标签 = {"判断": "判断", "下单": "下单", "回执": "回执", "复盘": "复盘"}.get(类, "记录")
            return [f"- {时间} 【{标签}】{self._短文本(正文)}", f"  - 编号：{编号}"]
        except Exception:
            return [f"- {时间} 【{类}】（这条渲染失败，原文见账本文件）", f"  - 编号：{编号}"]

    def _短文本(self, 正文: dict, 上限: int = 160) -> str:
        """把正文压成一小段「键：值；键：值」的中文摘要。"""
        片段 = []
        for 键, 值 in 正文.items():
            值文本 = json.dumps(值, ensure_ascii=False) if isinstance(值, (dict, list)) else str(值)
            片段.append(f"{键}：{值文本}")
        拼接 = "；".join(片段) if 片段 else "（无正文）"
        return 拼接 if len(拼接) <= 上限 else 拼接[:上限] + "…"

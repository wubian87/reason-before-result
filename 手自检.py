"""自检：直接 python3 手自检.py [项目根]（默认项目根 = 当前目录）。

本机没有密钥（ALPACA_API_KEY / ALPACA_SECRET_KEY 任一为空）时只做静态检查，
打印「跳过：本机没有密钥，只做静态检查」，退出码 0。自检绝不下一张单。
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # 别在当前目录留 __pycache__ 这种子目录

import 账
import 手

项目根 = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

# 渲染里不许出现的英文整词（合约代码、工具名这类专有串里的字母不算）
禁用英文词 = re.compile(r"\b(order|account|error)\b", re.IGNORECASE)


def 密钥齐() -> bool:
    """只看两个环境变量空不空，绝不读值、绝不打印值。"""
    return (os.environ.get("ALPACA_API_KEY", "").strip() != ""
            and os.environ.get("ALPACA_SECRET_KEY", "").strip() != "")


def 显(值) -> str:
    """打印用的占位：没取到就给中文提示，不打印英文的 None。"""
    return "（没取到）" if 值 is None else str(值)


def 挑键(结果, 键):
    """在嵌套的返回里找一个键的值，只用来挑几项关键数字打印。"""
    if isinstance(结果, dict):
        if 键 in 结果:
            return 结果[键]
        for 值 in 结果.values():
            找到 = 挑键(值, 键)
            if 找到 is not None:
                return 找到
    return None


def 静态检查() -> bool:
    print("== 第一步：静态检查（不需要密钥）==")
    过 = True
    print("✅ 账.py、手.py 都能正常导入")

    # mcp SDK 按需导入，这里单独提一句装没装，不影响静态检查的结果
    try:
        手.引入mcp()
        print("提示：本机装了 mcp SDK，联机检查可以直接用。")
    except ImportError:
        print("提示：本机没装 mcp SDK；静态检查不受影响，联机检查用得上它。")

    with tempfile.TemporaryDirectory(prefix="账本自检-") as 临时目录:
        本账 = 账.账本(临时目录)
        今天 = 账.今日()

        # 六条不同类的记录（内容是自检用的假数据，只进临时账本）
        六条 = [
            ("判断", {"一句话": "自检用：波动在预算内，继续观察。", "标的": "SPY"}),
            ("闸", {"放行": True, "一句话": "自检用：是模拟盘，放行。"}),
            ("下单", {"一句话": "自检用：记一笔两条腿的意图。", "腿数": 2}),
            ("MCP请求", {"工具": "get_account_info", "参数": {}}),
            ("MCP回执", {"工具": "get_account_info", "耗时秒": 0.01, "成功": True,
                        "结果": {"自检用": True}}),
            ("错", {"一句话": "自检用：模拟一条出错记录。"}),
        ]
        for 第几, (类, 正文) in enumerate(六条, start=1):
            写下 = 本账.记(类, 正文, 编号=f"自检-{第几:03d}")
            if 写下.get("编号") != f"自检-{第几:03d}":
                过 = False
                print(f"⛔ 记() 返回的记录没带上编号：{写下.get('编号')}")
        print("✅ 六条不同类的记录都写下去了")

        读回 = 本账.读()
        if len(读回) == 6:
            print("✅ 写 6 条、读回 6 条，条数对得上")
        else:
            过 = False
            print(f"⛔ 写了 6 条，读回 {len(读回)} 条，对不上")

        渲染 = 本账.渲染中文()
        表头 = f"# 当日流水 · {今天}（北京时间）"
        if not 渲染.startswith(表头):
            过 = False
            print(f"⛔ 渲染中文() 开头不是约定的表头：{表头}")
        撞词 = 禁用英文词.findall(渲染)
        if 撞词:
            过 = False
            print(f"⛔ 渲染中文() 里出现了英文整词：{撞词}")
        else:
            print("✅ 渲染中文() 表头正确，且没有 order/account/error 这类英文整词")

        连发 = [本账.发号("J") for _ in range(3)]
        期望 = [f"J-{今天}-001", f"J-{今天}-002", f"J-{今天}-003"]
        if 连发 == 期望:
            print("✅ 发号连发三次：-001 / -002 / -003")
        else:
            过 = False
            print(f"⛔ 发号连发三次得到 {连发}，期望 {期望}")

        # 乱传「类」必须被拦下
        try:
            本账.记("不存在的类", {})
            过 = False
            print("⛔ 传乱七八糟的「类」居然没抛 ValueError")
        except ValueError:
            print("✅ 传乱七八糟的「类」会被 ValueError 拦下")

        # 坏行不能把整个 读() 弄崩
        当天文件 = Path(临时目录) / f"{今天}.jsonl"
        with open(当天文件, "a", encoding="utf-8") as 文件:
            文件.write("这一行是自检故意写坏的，不是 JSON\n")
        再读 = 本账.读()
        if (len(再读) == 7 and 再读[-1].get("类") == "错"
                and "坏行原文" in 再读[-1].get("正文", {})):
            print("✅ 坏行被跳过、原文收进一条「错」里，整本没崩")
        else:
            过 = False
            print("⛔ 坏行处理不符合预期")

    return 过


def 联机检查() -> bool:
    print("== 第二步：联机检查（只取数，不下一张单）==")
    过 = True
    with tempfile.TemporaryDirectory(prefix="联机账本-") as 临时目录:
        本账 = 账.账本(临时目录)
        try:
            with 手.手(本账, 项目根) as 手柄:
                钟 = 手柄.时钟()
                print(f"✅ 时钟：{'已开市' if 挑键(钟, 'is_open') else '未开市'}；"
                      f"最新时间戳：{显(挑键(钟, 'timestamp'))}")

                户 = 手柄.账户()
                print(f"✅ 账户：账号 {显(挑键(户, 'account_number'))}；"
                      f"权益 {显(挑键(户, 'equity'))}；"
                      f"购买力 {显(挑键(户, 'buying_power'))}；"
                      f"现金 {显(挑键(户, 'cash'))}")

                仓表 = 手柄.持仓()
                print(f"✅ 持仓：共 {len(仓表)} 条")
                for 一条 in 仓表[:5]:
                    合约 = 挑键(一条, "symbol") or 挑键(一条, "asset_id")
                    print(f"     - {显(合约)}：数量 {显(挑键(一条, 'qty'))}，"
                          f"市值 {显(挑键(一条, 'market_value'))}")
        except Exception as 意外:
            过 = False
            print(f"⛔ 联机检查失败：{意外}")
    return 过


def 主() -> int:
    过 = 静态检查()
    if 密钥齐():
        过 = 联机检查() and 过
    else:
        print("跳过：本机没有密钥，只做静态检查")
    return 0 if 过 else 1


if __name__ == "__main__":
    sys.exit(主())

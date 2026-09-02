"""strategy.py —— 期权组合的挑选与落纸判断模块。

对外只有两样东西：
    默认判据: dict
    挑一个(链, 标的, 标的现价, 今天, 判据=None) -> dict

「挑一个」是纯函数：不联网、不写文件、不打印。
输入是 手.期权链(...) 的原始返回（snapshots 那种形状），输出三样：
    有没有得开 / 提案（不含编号，编号由调用方填）/ 判断书（全中文，给不懂技术的人看）。
"""

import math
from datetime import date

默认判据 = {
    # 最短 3 天：2 天期的合约上，delta≈0.16 的行权价离现价天然只有 0.7～0.9%，
    # gamma 也最凶——一根 1% 的日内波动就打穿。3 天起，行权价能站到 1.1% 以外。
    "最短到期天": 3,
    "最长到期天": 9,
    "目标卖腿delta": 0.16,
    "宽度": 5.0,
    "张数": 1,
    "最低收权占宽度": 0.15,
    # 这一条只是防脏数据的地板，⛔ 不是策略旋钮——真正决定行权价的是 delta。
    # 原来写 1.0%，等于把 delta 已经判过的事又判一遍，短期合约会被整段错杀。
    "最小距离占现价": 0.006,
}

# 三种结构给人看的全名
结构中文名 = {
    "铁鹰": "Iron condor — a put spread and a call spread sold together, each with a protective long leg",
    "看跌信用价差": "Put credit spread — sell a put, buy a lower-strike put as protection, take in a net credit",
    "看涨信用价差": "Call credit spread — sell a call, buy a higher-strike call as protection, take in a net credit",
}

# 「不开」时钱那一栏全部留空，不编数
空的钱 = {"净收权美元": None, "最大亏损美元": None, "最大盈利美元": None,
          "盈亏平衡下沿": None, "盈亏平衡上沿": None, "宽度": None, "张数": None}


# ---------- 基础工具 ----------

def 取值(字典, *键名们):
    """从一组容错键名里取第一个不是 None 的值；取不到就返回 None。"""
    if not isinstance(字典, dict):
        return None
    for 键 in 键名们:
        if 键 in 字典 and 字典[键] is not None:
            return 字典[键]
    return None


def 转浮点(值):
    """能转成数就转，转不了返回 None（不许拿 0 或猜的值顶上）。"""
    try:
        return float(值)
    except (TypeError, ValueError):
        return None


def 简洁数(值):
    """给人看的数：是整数就不带小数点，否则保留两位。"""
    if 值 is None:
        return "?"
    if abs(值 - round(值)) < 1e-9:
        return str(int(round(值)))
    return f"{值:.2f}"


_月名 = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def 中文日期(日期串):
    """'2026-09-04' → 'Sep 4'。名字是历史遗留，出的是给评委看的英文。"""
    try:
        日 = date.fromisoformat(str(日期串))
    except (TypeError, ValueError):
        return str(日期串)
    return f"{_月名[日.month - 1]} {日.day}"


def 向下取整到分(值):
    """保留两位小数、向下取整：收权宁可报低一点，不报高。"""
    return math.floor(round(值 * 100.0, 6)) / 100.0


# ---------- 链的解析 ----------

def 解析合约代码(代码):
    """从 OCC 合约代码里取出 到期 / 类型 / 行权价。

    代码形状：根符号（1~6 位）+ 6 位到期（YYMMDD）+ C/P + 8 位行权价（行权价×1000 左补零）。
    例如 SPY260904P00755000 → 2026-09-04 / P / 755.0。
    解析不出来返回 None；跟链里给的其它信息对不上时，以这里的解析结果为准。
    """
    if not isinstance(代码, str) or len(代码) < 15:
        return None
    到期六位 = 代码[-15:-9]
    类型 = 代码[-9]
    行权价八位 = 代码[-8:]
    if 类型 not in ("C", "P") or not 到期六位.isdigit() or not 行权价八位.isdigit():
        return None
    try:
        到期 = date(2000 + int(到期六位[:2]), int(到期六位[2:4]), int(到期六位[4:6]))
        行权价 = int(行权价八位) / 1000.0
    except ValueError:
        return None
    return {"到期": 到期.isoformat(), "类型": 类型, "行权价": 行权价}


def 解析全链(链):
    """把链里每个合约整理成统一形状。

    报价、delta、隐波任一取不到（键缺失、值为空、不是数），或买卖价有小于等于 0 的，
    就把这个合约整个丢掉——不许拿 0 或猜的值顶上。
    键名两种写法都试：latestQuote/latest_quote、impliedVolatility/implied_volatility。
    """
    合约表 = []
    快照表 = 取值(链, "snapshots")
    if not isinstance(快照表, dict):
        return 合约表
    for 代码, 快照 in 快照表.items():
        头 = 解析合约代码(代码)
        if 头 is None or not isinstance(快照, dict):
            continue
        报价 = 取值(快照, "latestQuote", "latest_quote")
        买价 = 转浮点(取值(报价, "bp", "bid_price", "bidPrice"))
        卖价 = 转浮点(取值(报价, "ap", "ask_price", "askPrice"))
        delta = 转浮点(取值(取值(快照, "greeks"), "delta"))
        隐波 = 转浮点(取值(快照, "impliedVolatility", "implied_volatility"))
        if 买价 is None or 卖价 is None or delta is None or 隐波 is None:
            continue
        if 买价 <= 0 or 卖价 <= 0:
            continue
        合约表.append({
            "合约": 代码,
            "到期": 头["到期"],
            "类型": 头["类型"],
            "行权价": 头["行权价"],
            "买价": 买价,
            "卖价": 卖价,
            "中价": (买价 + 卖价) / 2.0,
            "delta": delta,
            "隐波": 隐波,
        })
    return 合约表


# ---------- 挑选的各个小步 ----------

def 选到期日(合约表, 今天, 判据):
    """只留距今天 [最短到期天, 最长到期天] 的到期日，取距今天最近的一个。

    返回 (天数, 到期日字符串)；一个都没有返回 None。
    """
    try:
        今天日 = date.fromisoformat(str(今天))
    except (TypeError, ValueError):
        return None
    候选 = []
    for 合约 in 合约表:
        try:
            天 = (date.fromisoformat(合约["到期"]) - 今天日).days
        except (TypeError, ValueError):
            continue
        if 判据["最短到期天"] <= 天 <= 判据["最长到期天"]:
            候选.append((天, 合约["到期"]))
    if not 候选:
        return None
    候选.sort()
    return 候选[0]


def 选最接近delta(合约们, 目标):
    """挑 abs(delta) 最接近目标的合约；并列时取链里先出现的（可复现）。"""
    最佳 = None
    for 合约 in 合约们:
        差 = abs(abs(合约["delta"]) - 目标)
        if 最佳 is None or 差 < 最佳[0]:
            最佳 = (差, 合约)
    return 最佳[1] if 最佳 else None


def 选保护腿(同类合约们, 卖腿, 目标行权价, 必须更低):
    """在同到期、同类型的合约里挑保护腿。

    认沽保护腿必须行权价严格低于卖腿；认购保护腿必须严格高于卖腿；
    在满足方向的前提下取行权价最接近「目标行权价」的那个。找不到返回 None。
    """
    最佳 = None
    for 合约 in 同类合约们:
        if 必须更低:
            if not 合约["行权价"] < 卖腿["行权价"]:
                continue
        else:
            if not 合约["行权价"] > 卖腿["行权价"]:
                continue
        差 = abs(合约["行权价"] - 目标行权价)
        if 最佳 is None or 差 < 最佳[0]:
            最佳 = (差, 合约)
    return 最佳[1] if 最佳 else None


# ---------- 主入口 ----------

def 挑一个(链, 标的, 标的现价, 今天, 判据=None):
    """挑一个今天就开的期权组合，并写好判断书。纯函数。"""
    判据 = dict(默认判据) if not 判据 else dict(判据)
    底 = {"标的": 标的, "标的现价": 标的现价, "今天": 今天}

    def 不开(理由):
        书 = dict(底)
        书.update({
            "结论": "不开",
            "结构中文": None,
            "为什么开": [],
            "腿明细": [],
            "钱": dict(空的钱),
            "什么会证明我错": None,
            "打算怎么退出": None,
            "不开的理由": 理由,
        })
        return {"有": False, "提案": None, "判断书": 书}

    # 1. 先解析全链（不合格的合约在这一步就被丢掉）
    合约表 = 解析全链(链)

    # 2. 选到期日：距今天 [最短, 最长] 天里最近的一个，后面只用这一个到期日
    选中 = 选到期日(合约表, 今天, 判据)
    if 选中 is None:
        return 不开(f"今天不开：没有合适到期日的合约（要距今天 {判据['最短到期天']} 到 "
                    f"{判据['最长到期天']} 天的到期日，这条链里一个都没有）。")
    天数, 到期 = 选中
    本日 = [c for c in 合约表 if c["到期"] == 到期]
    认沽全体 = [c for c in 本日 if c["类型"] == "P"]
    认购全体 = [c for c in 本日 if c["类型"] == "C"]

    # 3. 选卖腿：delta 符号要对，abs(delta) 最接近目标
    卖认沽 = 选最接近delta([c for c in 认沽全体 if c["delta"] < 0], 判据["目标卖腿delta"])
    卖认购 = 选最接近delta([c for c in 认购全体 if c["delta"] > 0], 判据["目标卖腿delta"])

    # 9.（提前并入选腿阶段）卖腿离现价太近的那一边作废，这样「降级成单边」才自然
    距离比 = 判据["最小距离占现价"]
    下限 = 标的现价 * (1 - 距离比)
    上限 = 标的现价 * (1 + 距离比)
    认沽边行 = True
    认沽边理由 = None
    认购边行 = True
    认购边理由 = None
    if 卖认沽 is None:
        认沽边行 = False
        认沽边理由 = f"链里找不到 delta 合适的卖出认沽（要 delta 为负、绝对值最接近 {判据['目标卖腿delta']}）"
    elif 卖认沽["行权价"] > 下限:
        认沽边行 = False
        认沽边理由 = (f"卖出认沽行权价 {简洁数(卖认沽['行权价'])} 离现价 {简洁数(标的现价)} 太近"
                    f"（要求不高于 {简洁数(round(下限, 2))}），这一边作废")
    if 卖认购 is None:
        认购边行 = False
        认购边理由 = f"链里找不到 delta 合适的卖出认购（要 delta 为正、绝对值最接近 {判据['目标卖腿delta']}）"
    elif 卖认购["行权价"] < 上限:
        认购边行 = False
        认购边理由 = (f"卖出认购行权价 {简洁数(卖认购['行权价'])} 离现价 {简洁数(标的现价)} 太近"
                    f"（要求不低于 {简洁数(round(上限, 2))}），这一边作废")

    # 4. 选买腿（保护腿）：认沽往低处找，认购往高处找
    买认沽 = None
    买认购 = None
    if 认沽边行:
        买认沽 = 选保护腿(认沽全体, 卖认沽, 卖认沽["行权价"] - 判据["宽度"], 必须更低=True)
        if 买认沽 is None:
            认沽边行 = False
            认沽边理由 = (f"卖出认沽 {简洁数(卖认沽['行权价'])} 下面找不到保护腿"
                        f"（想要行权价 {简洁数(round(卖认沽['行权价'] - 判据['宽度'], 2))} 附近、更低的认沽）")
    if 认购边行:
        买认购 = 选保护腿(认购全体, 卖认购, 卖认购["行权价"] + 判据["宽度"], 必须更低=False)
        if 买认购 is None:
            认购边行 = False
            认购边理由 = (f"卖出认购 {简洁数(卖认购['行权价'])} 上面找不到保护腿"
                        f"（想要行权价 {简洁数(round(卖认购['行权价'] + 判据['宽度'], 2))} 附近、更高的认购）")

    # 5. 结构定型
    if not 认沽边行 and not 认购边行:
        return 不开(f"今天不开：认沽、认购两边都作废——{认沽边理由}；{认购边理由}")
    if 认沽边行 and 认购边行:
        结构 = "铁鹰"
    elif 认沽边行:
        结构 = "看跌信用价差"
    else:
        结构 = "看涨信用价差"

    # 6. 算净价：每条腿用中价，卖腿收钱、买腿付钱；保留两位小数、向下取整
    腿序 = []
    宽度们 = []
    if 认沽边行:
        腿序 += [(卖认沽, "sell"), (买认沽, "buy")]
        宽度们.append(abs(卖认沽["行权价"] - 买认沽["行权价"]))
    if 认购边行:
        腿序 += [(卖认购, "sell"), (买认购, "buy")]
        宽度们.append(abs(卖认购["行权价"] - 买认购["行权价"]))
    卖腿中价和 = sum(腿["中价"] for 腿, 方向 in 腿序 if 方向 == "sell")
    买腿中价和 = sum(腿["中价"] for 腿, 方向 in 腿序 if 方向 == "buy")
    每份 = 向下取整到分(卖腿中价和 - 买腿中价和)

    # 8. 收权太薄就不开：真实宽度取各边宽度的最大值
    真实宽度 = max(宽度们)
    门槛 = 真实宽度 * 判据["最低收权占宽度"]
    if 每份 < 门槛:
        return 不开(f"收权 {每份:.2f} 美元，不到宽度 {真实宽度:.2f} 美元的 "
                    f"{判据['最低收权占宽度']:.0%}（{门槛:.2f} 美元），今天不开")

    # 7. 张数直接用判据里的
    张数 = int(判据["张数"])

    # —— 钱的账 ——
    净收权美元 = round(每份 * 100 * 张数, 2)
    最大亏损美元 = round(max(0.0, 真实宽度 - 每份) * 100 * 张数, 2)
    盈亏平衡下沿 = round(卖认沽["行权价"] - 每份, 2) if 认沽边行 else None
    盈亏平衡上沿 = round(卖认购["行权价"] + 每份, 2) if 认购边行 else None

    # —— 判断书的人话 ——
    到期中文 = 中文日期(到期)
    为什么开 = []
    if 结构 == "铁鹰":
        为什么开.append(f"No directional bet. This position wins on time: it only needs {标的} to "
                        f"stay above {简洁数(卖认沽['行权价'])} and below {简洁数(卖认购['行权价'])} "
                        f"through {到期中文}.")
        最大d = max(abs(卖认沽["delta"]), abs(卖认购["delta"]))
        为什么开.append(f"The short legs carry at most about {简洁数(round(最大d, 2))} delta, so by the "
                        f"market's own pricing the worse side finishes in the money roughly "
                        f"{简洁数(round(最大d * 100))}% of the time.")
    elif 结构 == "看跌信用价差":
        d = abs(卖认沽["delta"])
        为什么开.append(f"No directional bet. This position wins on time: it only needs {标的} to stay "
                        f"above {简洁数(卖认沽['行权价'])} through {到期中文}. If it does break down, the "
                        f"lower-strike long put caps how far the loss can go.")
        为什么开.append(f"The short leg carries about {简洁数(round(d, 2))} delta, so by the market's own "
                        f"pricing it finishes in the money roughly {简洁数(round(d * 100))}% of the time.")
    else:
        d = abs(卖认购["delta"])
        为什么开.append(f"No directional bet. This position wins on time: it only needs {标的} to stay "
                        f"below {简洁数(卖认购['行权价'])} through {到期中文}. If it does break out, the "
                        f"higher-strike long call caps how far the loss can go.")
        为什么开.append(f"The short leg carries about {简洁数(round(d, 2))} delta, so by the market's own "
                        f"pricing it finishes in the money roughly {简洁数(round(d * 100))}% of the time.")
    为什么开.append(f"{天数} days to expiry: every day that passes moves time value my way.")

    if 结构 == "铁鹰":
        什么会证明我错 = (f"{标的} closing below {盈亏平衡下沿:.2f} or above {盈亏平衡上沿:.2f} before "
                        f"expiry is what proves me wrong. If it really breaks through, the most this "
                        f"loses is ${最大亏损美元:,.2f} — and that number is fixed before the order exists.")
    elif 结构 == "看跌信用价差":
        什么会证明我错 = (f"{标的} closing below {盈亏平衡下沿:.2f} before expiry is what proves me wrong. "
                        f"If it really breaks down, the most this loses is ${最大亏损美元:,.2f} — and that "
                        f"number is fixed before the order exists.")
    else:
        什么会证明我错 = (f"{标的} closing above {盈亏平衡上沿:.2f} before expiry is what proves me wrong. "
                        f"If it really breaks out, the most this loses is ${最大亏损美元:,.2f} — and that "
                        f"number is fixed before the order exists.")
    一半 = round(净收权美元 / 2, 2)
    打算怎么退出 = (f"Close once half the credit is earned (${简洁数(一半)}). If the target has not been "
                  f"hit by expiry day, close anyway — nothing is carried into the close.")

    类型中文表 = {"P": "put (loses if price falls through)", "C": "call (loses if price rises through)"}
    腿明细 = [{"合约": 腿["合约"],
               "做什么": "sell" if 方向 == "sell" else "buy",
               "行权价": 腿["行权价"],
               "类型中文": 类型中文表[腿["类型"]],
               "买价": 腿["买价"], "卖价": 腿["卖价"], "中价": 腿["中价"]}
              for 腿, 方向 in 腿序]

    # —— 提案（不含编号，编号由调用方填） ——
    提案 = {
        "标的": 标的,
        "结构": 结构,
        "张数": 张数,
        "净价": -每份,  # 负数 = 净收入，符合 Alpaca 口径
        "标的现价": 标的现价,
        "腿": [{"合约": 腿["合约"], "方向": 方向, "比例": 1,
                "行权价": 腿["行权价"], "类型": 腿["类型"], "到期": 腿["到期"],
                "买价": 腿["买价"], "卖价": 腿["卖价"]}
               for 腿, 方向 in 腿序],
    }

    判断书 = dict(底)
    判断书.update({
        "结论": "开",
        "结构中文": 结构中文名[结构],
        "为什么开": 为什么开,
        "腿明细": 腿明细,
        "钱": {"净收权美元": 净收权美元, "最大亏损美元": 最大亏损美元, "最大盈利美元": 净收权美元,
               "盈亏平衡下沿": 盈亏平衡下沿, "盈亏平衡上沿": 盈亏平衡上沿,
               "宽度": 真实宽度, "张数": 张数},
        "什么会证明我错": 什么会证明我错,
        "打算怎么退出": 打算怎么退出,
        "不开的理由": None,
    })
    return {"有": True, "提案": 提案, "判断书": 判断书}

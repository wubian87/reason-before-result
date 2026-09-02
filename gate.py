"""gate.py —— 期权下单风控闸（纯函数、零网络、零第三方依赖）。

对外只提供两样东西：
    默认配置 : dict
    过闸(提案, 账户, 时钟, 配置=None) -> dict

约定：
    · 纯函数：不读文件、不读环境变量、不打印、不抛异常；
      任何内部异常都接住，变成一条「拦」（默认拒绝，fail-closed）。
    · 七条规则 G1–G7 逐条都跑、逐条留账，不许短路提前返回。
    · 某条规则因为前置数据算不出来时，那条记「过: False」，说明以「算不出：」开头。
    · 只用 Python 3.11+ 标准库。
"""

from datetime import datetime as _日期时间

__all__ = ["默认配置", "过闸"]  # 对外只有这两样东西

默认配置 = {
    "单笔最大亏损占权益": 0.02,
    "当日止损占权益": 0.03,
    "最大点差占中价": 0.35,
    "最大点差绝对值": 0.60,
    "最短到期天": 1,
    "最长到期天": 14,
    "最多未平仓组数": 4,
}

_合约乘数 = 100  # 一组期权合约对应 100 股
_两腿价差白名单 = ("看跌信用价差", "看涨信用价差", "看跌借记价差", "看涨借记价差")
# 结构的内部名是中文（账本里的历史值，⛔ 不动）；对外一律用下面这张表。
_结构英文 = {"看跌信用价差": "put credit spread", "看涨信用价差": "call credit spread",
            "看跌借记价差": "put debit spread", "看涨借记价差": "call debit spread",
            "铁鹰": "iron condor"}


def _英(结构):
    return _结构英文.get(结构, str(结构))
_铁鹰名 = "铁鹰"
_七条规则名 = ("Paper account only", "Loss must be capped by the structure",
              "Per-order ceiling", "Daily stop", "Every leg needs a live quote",
              "Expiry window", "Open-position cap")


class _算不出错(ValueError):
    """数据缺漏或类型不对，导致判不了。统一按 fail-closed 处理。"""


# ---------------- 通用小工具 ----------------

def _通俗数字(值):
    """把数字写成给人看的样子：整数不带小数点，其余最多两位小数。"""
    数 = float(值)
    if 数 == int(数):
        return str(int(数))
    return f"{数:.2f}".rstrip("0").rstrip(".")


def _钱(值):
    """把金额写成 $12.30 / -$12.30，负号在美元符号外面。"""
    数 = float(值)
    return ("-$" if 数 < 0 else "$") + _通俗数字(abs(数))


def _百分比(比例):
    """0.02 -> "2%"，0.35 -> "35%"。"""
    return _通俗数字(round(float(比例) * 100, 6)) + "%"


def _取数(值, 名):
    if isinstance(值, bool) or not isinstance(值, (int, float)):
        raise _算不出错(f"{名} must be a number; got {值!r}")
    return float(值)


def _取正整数(值, 名):
    if isinstance(值, bool) or not isinstance(值, int) or 值 <= 0:
        raise _算不出错(f"{名} must be a positive integer; got {值!r}")
    return 值


def _解析日期(文本, 名):
    if not isinstance(文本, str):
        raise _算不出错(f"{名} must be a YYYY-MM-DD string; got {文本!r}")
    try:
        return _日期时间.strptime(文本, "%Y-%m-%d").date()
    except ValueError:
        raise _算不出错(f"{名} {文本!r} is not a YYYY-MM-DD date") from None


def _合并配置(传入):
    """默认配置打底，传进来的键值覆盖；传进来的东西不可用则返回 None（各规则会算不出）。"""
    合并 = dict(默认配置)
    if 传入 is None:
        return 合并
    try:
        for 键, 值 in 传入.items():
            合并[键] = 值
    except Exception:
        return None
    return 合并


# ---------------- G2 的结构核验 ----------------

def _裸卖补语(腿表):
    """找出没有同到期同类型买入腿保护的卖出腿，拼进拦的说明里。"""
    买入对 = []
    for 腿 in 腿表:
        if isinstance(腿, dict) and 腿.get("方向") == "buy":
            买入对.append((腿.get("到期"), 腿.get("类型")))
    无保护卖出 = []
    for 腿 in 腿表:
        if isinstance(腿, dict) and 腿.get("方向") == "sell":
            if (腿.get("到期"), 腿.get("类型")) not in 买入对:
                无保护卖出.append(str(腿.get("合约")))
    if not 无保护卖出:
        return ""
    return (" - sold " + ", ".join(无保护卖出)
            + " with no bought leg of the same type and expiry behind it (naked short)")


def _单方向腿(同类型腿表, 方向, 名):
    匹配 = [腿 for 腿 in 同类型腿表 if 腿.get("方向") == 方向]
    if len(匹配) != 1:
        raise ValueError(f"{名} needs exactly one bought and one sold leg; this order has {len(匹配)} on the {方向} side")
    return 匹配[0]


def _验两腿价差(结构, 腿表):
    """四种两腿价差共用的结构核验，通过就返回宽度（行权价之差）。"""
    if len(腿表) != 2:
        raise ValueError(f"a {_英(结构)} needs exactly 2 legs; this order has {len(腿表)}")
    for 腿 in 腿表:
        if 腿.get("比例") != 1:
            raise ValueError(f"every leg of a {_英(结构)} must have ratio 1; this order has a leg with ratio {腿.get('比例')!r}")
    两方向 = sorted(str(腿.get("方向")) for 腿 in 腿表)
    if 两方向 != ["buy", "sell"]:
        raise ValueError(f"a {_英(结构)} must be one bought and one sold leg; this order has {两方向[0]!r} and {两方向[1]!r}")
    到期一, 到期二 = 腿表[0].get("到期"), 腿表[1].get("到期")
    if 到期一 != 到期二:
        raise ValueError(f"the two legs of this {_英(结构)} expire on different days ({到期一} vs {到期二})")
    类型一, 类型二 = 腿表[0].get("类型"), 腿表[1].get("类型")
    if 类型一 not in ("C", "P") or 类型一 != 类型二:
        raise ValueError(f"both legs of a {_英(结构)} must be the same type (both C or both P); this order has {类型一!r} and {类型二!r}")
    行权一 = _取数(腿表[0].get("行权价"), "第一条腿的行权价")
    行权二 = _取数(腿表[1].get("行权价"), "第二条腿的行权价")
    if 行权一 == 行权二:
        raise ValueError(f"both legs of this {_英(结构)} share strike {_通俗数字(行权一)}, so the width is undefined")
    return abs(行权一 - 行权二)


def _验铁鹰(腿表):
    """铁鹰的结构核验，通过就返回宽度（两对宽度里的最大值）。"""
    if len(腿表) != 4:
        raise ValueError(f"an iron condor needs exactly 4 legs; this order has {len(腿表)}")
    for 腿 in 腿表:
        if 腿.get("比例") != 1:
            raise ValueError(f"every leg of an iron condor must have ratio 1; this order has a leg with ratio {腿.get('比例')!r}")
    到期集合 = {腿.get("到期") for 腿 in 腿表}
    if len(到期集合) != 1:
        raise ValueError("all 4 legs of an iron condor must expire on the same day; this order expires "
                         + "、".join(sorted(str(某) for 某 in 到期集合)))
    认沽腿 = [腿 for 腿 in 腿表 if 腿.get("类型") == "P"]
    认购腿 = [腿 for 腿 in 腿表 if 腿.get("类型") == "C"]
    if len(认沽腿) != 2 or len(认购腿) != 2:
        raise ValueError(f"an iron condor needs 2 puts and 2 calls; this order has {len(认沽腿)} P and {len(认购腿)} C")
    认沽买 = _单方向腿(认沽腿, "buy", "铁鹰的认沽一对")
    认沽卖 = _单方向腿(认沽腿, "sell", "铁鹰的认沽一对")
    认购买 = _单方向腿(认购腿, "buy", "铁鹰的认购一对")
    认购卖 = _单方向腿(认购腿, "sell", "铁鹰的认购一对")
    认沽买价 = _取数(认沽买.get("行权价"), "铁鹰认沽买腿的行权价")
    认沽卖价 = _取数(认沽卖.get("行权价"), "铁鹰认沽卖腿的行权价")
    认购买价 = _取数(认购买.get("行权价"), "铁鹰认购买腿的行权价")
    认购卖价 = _取数(认购卖.get("行权价"), "铁鹰认购卖腿的行权价")
    if not 认沽买价 < 认沽卖价:
        raise ValueError(f"iron condor put side: the bought strike must sit below the sold one (bought {_通俗数字(认沽买价)} vs sold {_通俗数字(认沽卖价)})")
    if not 认购买价 > 认购卖价:
        raise ValueError(f"iron condor call side: the bought strike must sit above the sold one (bought {_通俗数字(认购买价)} vs sold {_通俗数字(认购卖价)})")
    return max(abs(认沽买价 - 认沽卖价), abs(认购买价 - 认购卖价))


def _试算风险量(提案):
    """把提案的 宽度/净收权/最大亏损/最大盈利 尽量算出来；绝不抛异常。

    返回的字典里：
        净收权 —— 只要 净价 和 张数 是有效数字就照算（不依赖腿结构）；
        宽度/最大亏损/最大盈利 —— 要结构核验通过才算得出；
        G2拦 —— 不是 None 就表示 G2 要拦，内容是拦的说明；
        算不出 —— True 表示是数据缺漏（说明要加「算不出：」前缀），False 表示是实打实的违规。
    """
    试算 = {"净收权": None, "宽度": None, "最大亏损": None, "最大盈利": None,
            "张数": None, "G2拦": None, "算不出": False}
    try:
        张数 = _取正整数(提案.get("张数"), "提案里的张数")
        净价 = _取数(提案.get("净价"), "提案里的净价")
    except _算不出错 as 错:
        试算["算不出"] = True
        试算["G2拦"] = f"{错}; the credit and the maximum loss cannot be worked out"
        return 试算
    净收权 = -净价 * _合约乘数 * 张数
    试算["张数"] = 张数
    试算["净收权"] = 净收权

    腿表 = 提案.get("腿")
    if not isinstance(腿表, list) or not 腿表:
        试算["G2拦"] = "the proposal has no usable list of legs, so the structure is undefined"
        return 试算
    结构 = 提案.get("结构")
    try:
        if 结构 in _两腿价差白名单:
            宽度 = _验两腿价差(结构, 腿表)
        elif 结构 == _铁鹰名:
            宽度 = _验铁鹰(腿表)
        else:
            raise ValueError(f"structure {结构!r} is not on the allow-list (put/call credit spread, put/call debit spread, iron condor)")
    except _算不出错 as 错:
        试算["算不出"] = True
        试算["G2拦"] = str(错)
        return 试算
    except ValueError as 错:
        试算["G2拦"] = f"{错}{_裸卖补语(腿表)}."
        return 试算
    except Exception as 错:
        试算["算不出"] = True
        试算["G2拦"] = f"the structure check itself failed: {错}"
        return 试算

    宽度总额 = 宽度 * _合约乘数 * 张数
    if 净收权 > 0:
        最大亏损 = 宽度总额 - 净收权
        最大盈利 = 净收权
    else:
        最大亏损 = -净收权
        最大盈利 = 宽度总额 + 净收权
    if not (最大亏损 > 0 and 净收权 < 宽度总额):
        试算["G2拦"] = (f"the quotes do not add up: credit ${_通俗数字(净收权)}, "
                        f"width ${_通俗数字(宽度)} x {张数} contract(s) = ${_通俗数字(宽度总额)}, "
                        f"which puts the maximum loss at ${_通俗数字(最大亏损)}. It must be above 0, "
                        f"and the credit must stay below the total width.")
        return 试算
    试算["宽度"] = 宽度
    试算["最大亏损"] = 最大亏损
    试算["最大盈利"] = 最大盈利
    return 试算


# ---------------- 七条规则，每条一个独立函数 ----------------

def _判G1(账户):
    """G1 只许模拟盘。"""
    if 账户.get("是模拟盘") is True:
        return True, "The account is flagged as paper."
    return False, "This is not a paper account. The gate only releases orders on paper."


def _判G2(提案, 试算):
    """G2 风险必须定义得出来。"""
    if 试算["G2拦"] is not None:
        if 试算["算不出"]:
            raise _算不出错(试算["G2拦"])
        return False, 试算["G2拦"]
    return True, (f"{_英(提案.get('结构')).capitalize()} verified: width ${_通俗数字(试算['宽度'])}, "
                  f"credit ${_通俗数字(试算['净收权'])}, "
                  f"maximum loss ${_通俗数字(试算['最大亏损'])}, "
                  f"maximum gain ${_通俗数字(试算['最大盈利'])}.")


def _判G3(账户, 试算, 配置):
    """G3 单笔上限。"""
    if 试算["最大亏损"] is None:
        raise _算不出错("the maximum loss is undefined - see why G2 failed first")
    权益 = _取数(账户.get("权益"), "账户里的权益")
    比例 = _取数(配置.get("单笔最大亏损占权益"), "配置里的单笔最大亏损占权益")
    上限 = 权益 * 比例
    亏损 = 试算["最大亏损"]
    if 亏损 <= 上限:
        return True, (f"Worst case ${_通俗数字(亏损)}, inside the "
                      f"${_通俗数字(上限)} ceiling ({_百分比(比例)} of equity).")
    return False, (f"Worst case ${_通俗数字(亏损)} is over the "
                   f"${_通俗数字(上限)} ceiling ({_百分比(比例)} of equity).")


def _判G4(账户, 配置):
    """G4 当日止损。"""
    权益 = _取数(账户.get("权益"), "账户里的权益")
    当日盈亏 = _取数(账户.get("当日盈亏"), "账户里的当日盈亏")
    比例 = _取数(配置.get("当日止损占权益"), "配置里的当日止损占权益")
    止损线 = -权益 * 比例
    if 当日盈亏 > 止损线:
        return True, (f"Today's P&L is {_钱(当日盈亏)}, nowhere near the "
                      f"{_钱(-止损线)} daily stop.")
    return False, (f"Down ${_通俗数字(-当日盈亏)} today, past the ${_通俗数字(-止损线)} "
                   f"daily stop. From here it may only close, never open.")


def _判G5(提案, 配置):
    """G5 报价必须是活的（fail-closed）。"""
    腿表 = 提案.get("腿")
    if not isinstance(腿表, list) or not 腿表:
        raise _算不出错("the proposal has no usable list of legs")
    绝对上限 = _取数(配置.get("最大点差绝对值"), "配置里的最大点差绝对值")
    比例上限 = _取数(配置.get("最大点差占中价"), "配置里的最大点差占中价")
    问题 = []
    最宽点差, 最宽合约 = None, None
    for 腿 in 腿表:
        合约 = 腿.get("合约")
        买价, 卖价 = 腿.get("买价"), 腿.get("卖价")
        if 买价 is None or 卖价 is None:
            缺哪个 = "bid and ask are" if (买价 is None and 卖价 is None) else ("bid is" if 买价 is None else "ask is")
            问题.append(f"{合约}: the {缺哪个} empty, so the quote is not live")
            continue
        买 = _取数(买价, f"{合约} 的买价")
        卖 = _取数(卖价, f"{合约} 的卖价")
        if 买 <= 0 or 卖 <= 0:
            问题.append(f"{合约}: bid {_通俗数字(买)} / ask {_通俗数字(卖)}; both must be above 0")
            continue
        if 卖 < 买:
            问题.append(f"{合约}: ask {_通俗数字(卖)} is below bid {_通俗数字(买)}; the quote is crossed")
            continue
        点差 = 卖 - 买
        if 最宽点差 is None or 点差 > 最宽点差:
            最宽点差, 最宽合约 = 点差, 合约
        中价 = (买 + 卖) / 2
        比例限额 = 中价 * 比例上限
        if 点差 > 绝对上限 and 点差 > 比例限额:
            问题.append(f"{合约}: spread ${_通俗数字(点差)} is over both limits - the flat "
                        f"${_通俗数字(绝对上限)} cap (by ${_通俗数字(点差 - 绝对上限)}) and "
                        f"{_百分比(比例上限)} of the ${_通俗数字(中价)} mid, i.e. "
                        f"${_通俗数字(比例限额)} (by ${_通俗数字(点差 - 比例限额)})")
    if 问题:
        return False, "; ".join(问题) + "."
    return True, (f"All {len(腿表)} leg{' quotes' if len(腿表) == 1 else 's quote'} two-sided. Widest spread ${_通俗数字(最宽点差)} "
                  f"({最宽合约}), inside both the ${_通俗数字(绝对上限)} flat cap and the "
                  f"{_百分比(比例上限)}-of-mid cap.")


def _判G6(提案, 时钟, 配置):
    """G6 到期日窗口。"""
    腿表 = 提案.get("腿")
    if not isinstance(腿表, list) or not 腿表:
        raise _算不出错("the proposal has no usable list of legs")
    最短 = _取数(配置.get("最短到期天"), "配置里的最短到期天")
    最长 = _取数(配置.get("最长到期天"), "配置里的最长到期天")
    今天 = _解析日期(时钟.get("今天"), "时钟里的今天")
    问题 = []
    概览 = []
    for 腿 in 腿表:
        到期 = 腿.get("到期")
        try:
            到期日 = _解析日期(到期, "腿上的到期")
        except _算不出错 as 错:
            问题.append(str(错))
            continue
        天数 = (到期日 - 今天).days
        概览.append(f"{到期} is {天数} day(s) out")
        if not (最短 <= 天数 <= 最长):
            问题.append(f"{到期} is {天数} day(s) out, outside the {_通俗数字(最短)}-{_通俗数字(最长)} day window")
    if 问题:
        return False, "; ".join(dict.fromkeys(问题)) + "."  # 同样的毛病只说一遍
    return True, ("Legs: " + ", ".join(dict.fromkeys(概览))
                  + f" - all inside the {_通俗数字(最短)}-{_通俗数字(最长)} day window.")


def _判G7(提案, 账户, 配置):
    """G7 仓位数上限。"""
    张数 = _取正整数(提案.get("张数"), "提案里的张数")
    已有 = _取数(账户.get("未平仓组数"), "账户里的未平仓组数")
    上限 = _取数(配置.get("最多未平仓组数"), "配置里的最多未平仓组数")
    合计 = 已有 + 张数
    if 合计 <= 上限:
        return True, (f"{_通俗数字(已有)} open plus {张数} new = {_通俗数字(合计)} group(s), "
                      f"within the cap of {_通俗数字(上限)}.")
    return False, (f"{_通俗数字(已有)} open plus {张数} new = {_通俗数字(合计)} group(s), "
                   f"over the cap of {_通俗数字(上限)}.")


# ---------------- 汇总 ----------------

def _跑一条(编号, 名字, 判定函数):
    """跑一条规则并接住它的一切异常（异常=算不出=拦）。"""
    try:
        通过, 说明 = 判定函数()
    except Exception as 错:
        return {"规则": 编号, "名": 名字, "过": False, "说明": f"Cannot be determined: {错}"}
    return {"规则": 编号, "名": 名字, "过": bool(通过), "说明": 说明}


def _兜底拦():
    """连正文都没跑完时的最后防线：整单拦下，七条账目照样给全。"""
    逐条 = [{"规则": f"G{序}", "名": 名, "过": False,
             "说明": "Cannot be determined: the gate itself errored, so the default is refuse."}
            for 序, 名 in enumerate(_七条规则名, start=1)]
    return {"过": False, "一句话": "STOP: the gate itself errored, so the default is refuse.",
            "最大亏损": None, "最大盈利": None, "宽度": None, "净收权": None, "逐条": 逐条}


def _过闸正文(提案, 账户, 时钟, 配置参数):
    if not isinstance(提案, dict):
        提案 = {}
    if not isinstance(账户, dict):
        账户 = {}
    if not isinstance(时钟, dict):
        时钟 = {}
    配置 = _合并配置(配置参数)
    试算 = _试算风险量(提案)

    逐条 = [
        _跑一条("G1", _七条规则名[0], lambda: _判G1(账户)),
        _跑一条("G2", _七条规则名[1], lambda: _判G2(提案, 试算)),
        _跑一条("G3", _七条规则名[2], lambda: _判G3(账户, 试算, 配置)),
        _跑一条("G4", _七条规则名[3], lambda: _判G4(账户, 配置)),
        _跑一条("G5", _七条规则名[4], lambda: _判G5(提案, 配置)),
        _跑一条("G6", _七条规则名[5], lambda: _判G6(提案, 时钟, 配置)),
        _跑一条("G7", _七条规则名[6], lambda: _判G7(提案, 账户, 配置)),
    ]

    通过 = all(条目["过"] for 条目 in 逐条)
    if 通过:
        一句话 = (f"RELEASED: {_英(提案.get('结构'))} verified - maximum loss "
                  f"${_通俗数字(试算['最大亏损'])}, maximum gain ${_通俗数字(试算['最大盈利'])}, "
                  f"credit ${_通俗数字(试算['净收权'])}. All seven rules pass.")
    else:
        首条未过 = next(条目 for 条目 in 逐条 if not 条目["过"])
        一句话 = "STOP: " + 首条未过["说明"]

    return {
        "过": 通过,
        "一句话": 一句话,
        "最大亏损": 试算["最大亏损"],
        "最大盈利": 试算["最大盈利"],
        "宽度": 试算["宽度"],
        "净收权": 试算["净收权"],
        "逐条": 逐条,
    }


def 过闸(提案: dict, 账户: dict, 时钟: dict, 配置: dict | None = None) -> dict:
    """七条规则全部跑一遍再汇总。纯函数：任何内部异常都接住并变成一条「拦」。"""
    try:
        return _过闸正文(提案, 账户, 时钟, 配置)
    except Exception:
        return _兜底拦()

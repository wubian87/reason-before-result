"""跑.py —— 中文命令行主入口。

子命令：
    体检   检查四个模块能不能加载、密钥文件在不在，再连一次账户和时钟
    看     给不懂的人看 15 秒的那一屏：权益、持仓、止损线
    演闸   三笔写死的假提案过闸，留账面证据（休市也能做）
    开     一轮完整动作：时钟→账户→现价→链→挑组合→落纸→过闸→（可选）下单
    close  close positions that expired or already earned half the credit
    复盘   把当天账本渲染成 Markdown 日志，写进 <根>/日志/

全局可选参数（放在子命令前面）：
    --根 <路径>   项目根目录，默认当前目录
    --账 <路径>   账本目录，默认 <根>/账

gate.py / broker.py / ledger.py 由别人同时在写，这里全部延迟到子命令真正用到时才 import，
保证 python3 跑.py --help 不依赖它们也能打出中文帮助。
"""

import argparse
import math
import os
import sys
from datetime import date, timedelta


# ---------- 基础工具 ----------

def 引入(模块名):
    """延迟 import：把模块名当字符串引进来，缺不缺由调用方处理。"""
    import importlib
    return importlib.import_module(模块名)


def 取键(字典, *键名们):
    """从一组容错键名里取第一个不是 None 的值；取不到返回 None。"""
    if not isinstance(字典, dict):
        return None
    for 键 in 键名们:
        if 键 in 字典 and 字典[键] is not None:
            return 字典[键]
    return None


def 浮(值):
    """能转成数就转，转不了返回 None（不许拿 0 顶上）。"""
    try:
        return float(值)
    except (TypeError, ValueError):
        return None


def 钱样(值):
    """钱的排版：千分位、两位小数；拿不到就打一个占位符。"""
    if 值 is None:
        return "—"
    return f"{值:,.2f}"


def 带号(值):
    """盈亏的排版：带正负号、两位小数。"""
    if 值 is None:
        return "-"
    return ("+" if 值 >= 0 else "-") + f"{abs(值):,.2f}"


def 带号钱(值):
    """盈亏的排版，带美元符号：+$54.00 / -$4.00。"""
    if 值 is None:
        return "-"
    return ("+$" if 值 >= 0 else "-$") + f"{abs(值):,.2f}"


def 简洁数(值):
    """给人看的数：是整数就不带小数点，否则保留两位。"""
    if 值 is None:
        return "?"
    if abs(值 - round(值)) < 1e-9:
        return str(int(round(值)))
    return f"{值:.2f}"


def 线(符="=", 数=64):
    """打印一条分隔线。"""
    print(符 * 数)


# 过闸摘要里那几个键，对外用英文
_钱名 = {"最大亏损": "Maximum loss", "最大盈利": "Maximum gain",
        "宽度": "Width", "净收权": "Credit"}

# 结构的内部名是中文（账本历史值，⛔ 不动）；打印一律走这张表
_结构英文 = {"看跌信用价差": "put credit spread", "看涨信用价差": "call credit spread",
            "看跌借记价差": "put debit spread", "看涨借记价差": "call debit spread",
            "铁鹰": "iron condor"}


def 账号打码(账号):
    """账户号打码显示：前两位 + … + 后两位（模拟盘账号也不大意）。"""
    账号 = str(账号 or "")
    if len(账号) <= 4:
        return 账号 or "？"
    return 账号[:2] + "..." + 账号[-2:]


def 记错(账本, 位置, 错):
    """把异常记进账本（尽力而为，账本本身坏了也不许再炸）。"""
    try:
        账本.记("错", {"位置": 位置, "说明": f"{type(错).__name__}: {错}"}, None)
    except Exception:
        pass


def 取正文(条):
    """从账本条目里把正文抠出来：键名没给死，几种写法都试，再兜底找平铺。"""
    正文 = 取键(条, "正文", "body", "内容", "数据")
    if 正文 is None and any(k in 条 for k in ("提案", "结果", "结论")):
        正文 = 条
    return 正文 if isinstance(正文, dict) else {}


def 从账本数闸(账本, 日期):
    """数当天闸拦下几笔、放行几笔（演习的不算，单列）。认不出的条目不数、不猜。"""
    拦 = 放 = 演习 = 0
    try:
        条目们 = 账本.读(日期) or []
    except Exception:
        return (拦, 放, 演习)
    for 条 in 条目们:
        if not isinstance(条, dict) or 取键(条, "类", "type", "类别") != "闸":
            continue
        正文 = 取正文(条)
        结果 = 取键(正文, "结果") or 取键(条, "结果")
        过 = 取键(结果, "过") if isinstance(结果, dict) else None
        if 过 is not True and 过 is not False:
            continue
        if 取键(正文, "演习"):
            演习 += 1
            continue
        if 过:
            放 += 1
        else:
            拦 += 1
    return (拦, 放, 演习)


# ---------- 通用打印 ----------

def 打印闸表(标题, 闸判, 提案=None):
    """把 过闸 返回的逐条明细打成中文表格。"""
    print()
    print(f"  {标题}")
    if isinstance(提案, dict):
        print(f"  Proposal: {_结构英文.get(提案.get('结构'), 提案.get('结构'))}, "
              f"{提案.get('张数')} contract(s), net {提案.get('净价')}, "
              f"{len(提案.get('腿') or [])} legs, underlying last {提案.get('标的现价')}")
    过 = 取键(闸判, "过")
    print(f"  Gate: {取键(闸判, '一句话') or ('RELEASED' if 过 is True else 'STOPPED')}")
    逐条 = 取键(闸判, "逐条") or []
    if 逐条:
        print(f"    {'RULE':<6}{'NAME':<38}{'VERDICT':<9}WHY")
        print("    " + "-" * 56)
        for 条 in 逐条:
            if not isinstance(条, dict):
                continue
            这过 = 取键(条, "过")
            标记 = "PASS" if 这过 is True else "STOP"
            print(f"    {str(取键(条, '规则') or ''):<6}{str(取键(条, '名') or ''):<38}"
                  f"{标记:<9}{取键(条, '说明') or ''}")
    for 键 in ("最大亏损", "最大盈利", "宽度", "净收权"):
        值 = 取键(闸判, 键)
        if 值 is not None:
            print(f"    {_钱名.get(键, 键)}: {简洁数(值)}")


def 打印判断书(书, 编号=None):
    """把判断书整屏打出来，给录屏用。"""
    线()
    print("  W R I T T E N   J U D G M E N T" + (f"   ({编号})" if 编号 else ""))
    线()
    print(f"  Underlying {书.get('标的')}    last {书.get('标的现价')}    date {书.get('今天')}")
    print(f"  Decision: {'OPEN' if 书.get('结论') == '开' else 书.get('结论')}")
    if 书.get("结构中文"):
        print(f"  Structure: {书['结构中文']}")
    为什么 = 书.get("为什么开") or []
    if 为什么:
        print()
        print("  Why:")
        for 句 in 为什么:
            print(f"    · {句}")
    腿明细 = 书.get("腿明细") or []
    if 腿明细:
        print()
        print("  Legs:")
        print(f"    {'CONTRACT':<20}{'SIDE':<6}{'STRIKE':>7}  {'TYPE':<36}{'BID':>7}{'ASK':>7}{'MID':>7}")
        for 腿 in 腿明细:
            print(f"    {str(腿.get('合约', '')):<20}{str(腿.get('做什么', '')):<5}"
                  f"{简洁数(腿.get('行权价')):>7}  {str(腿.get('类型中文', '')):<14}"
                  f"{简洁数(腿.get('买价')):>7}{简洁数(腿.get('卖价')):>7}{简洁数(腿.get('中价')):>7}")
    钱 = 书.get("钱") or {}
    print()
    print("  Money:")
    print(f"    Credit taken in   ${钱样(钱.get('净收权美元'))}")
    print(f"    Maximum gain      ${钱样(钱.get('最大盈利美元'))}")
    print(f"    Maximum loss      ${钱样(钱.get('最大亏损美元'))}  (fixed before the order exists)")
    print(f"    Break-evens       {钱样(钱.get('盈亏平衡下沿'))} / {钱样(钱.get('盈亏平衡上沿'))}")
    print(f"    Width ${钱样(钱.get('宽度'))}    contracts {简洁数(钱.get('张数'))}")
    if 书.get("什么会证明我错"):
        print()
        print(f"  What would prove it wrong: {书['什么会证明我错']}")
    if 书.get("打算怎么退出"):
        print(f"  Planned exit: {书['打算怎么退出']}")
    if 书.get("不开的理由"):
        print()
        print(f"  Why it is not opening: {书['不开的理由']}")
    线()


# ---------- 子命令：体检 ----------

def 跑体检(参):
    红 = []
    线()
    print("  P R E F L I G H T   -   local checks first, then one live round-trip")
    线()
    print("  [1 - offline]")
    模块们在 = {}
    for 名 in ("gate", "broker", "ledger", "strategy"):
        try:
            引入(名)
            模块们在[名] = True
            print(f"  OK   module {名}.py imports")
        except Exception as 错:
            模块们在[名] = False
            print(f"  FAIL module {名}.py: {错}")
            红.append(f"{名}.py 加载失败")
    密钥文件 = os.path.join(参.根, ".env")
    # 只查在不在，不打开、不读内容、不打印内容
    if os.path.isfile(密钥文件):
        print("  OK   .env is present (existence only - it is never opened here)")
    else:
        print("  FAIL .env is missing (it belongs in the project root, named exactly .env)")
        红.append(".env 不存在")
    print("  [2 - live]")
    if not (模块们在.get("broker") and 模块们在.get("ledger")):
        print("  FAIL broker.py / ledger.py did not import; skipping the live half")
        红.append("联机部分没做成")
    else:
        try:
            账 = 引入("ledger")
            手模块 = 引入("broker")
            账本 = 账.账本(参.账)
            with 手模块.手(账本, 参.根) as 手柄:
                时钟原始 = 手柄.时钟()
                账户原始 = 手柄.账户()
            开市 = 取键(时钟原始, "is_open", "isOpen")
            print(f"  {'·' if not 开市 else 'OK  '} the market is {'open' if 开市 else 'closed'}")
            print(f"    next open      {取键(时钟原始, 'next_open', 'nextOpen') or '-'}")
            print(f"    account status {取键(账户原始, 'status') or '-'}")
            print(f"    equity         ${钱样(浮(取键(账户原始, 'equity')))}")
            账号 = 取键(账户原始, "account_number", "accountNumber")
            模拟 = isinstance(账号, str) and 账号.startswith("PA")
            print(f"    paper account  {'YES - the account number starts with PA' if 模拟 else 'NO! this account number does not start with PA - real money may be at risk'}")
        except Exception as 错:
            print(f"  FAIL the live half: {type(错).__name__}: {错}")
            红.append("联机部分失败")
    线()
    if 红:
        print(f"PREFLIGHT FAILED: {'; '.join(红)}")
        return 1
    print("PREFLIGHT GREEN")
    return 0


# ---------- 子命令：看 ----------

def 跑看(参):
    账 = 引入("ledger")
    手模块 = 引入("broker")
    账本 = 账.账本(参.账)
    今天 = date.today().isoformat()
    with 手模块.手(账本, 参.根) as 手柄:
        账户原始 = 手柄.账户()
        持仓们 = 手柄.持仓()
    账号 = 取键(账户原始, "account_number", "accountNumber") or "？"
    模拟 = isinstance(账号, str) and 账号.startswith("PA")
    权益 = 浮(取键(账户原始, "equity"))
    昨权益 = 浮(取键(账户原始, "last_equity", "lastEquity"))
    当日 = (权益 - 昨权益) if (权益 is not None and 昨权益 is not None) else None

    线()
    if 模拟:
        print("  P A P E R   A C C O U N T   -   no real money, not one cent of it")
    else:
        print("  !! L I V E   A C C O U N T   -   this is real money !!")
    线()
    print(f"  Account         {账号打码(账号)}")
    print(f"  Equity          ${钱样(权益)}")
    print(f"  P&L today       {带号钱(当日)}")
    线("-")
    print("  O P T I O N S   P O S I T I O N S")
    期权持仓们 = [p for p in (持仓们 or []) if 取键(p, "asset_class", "assetClass") == "us_option"]
    if not 期权持仓们:
        print("    nothing open")
    for 持仓 in 期权持仓们:
        合约 = str(取键(持仓, "symbol") or "?")
        方向 = 取键(持仓, "side")
        张 = 浮(取键(持仓, "qty"))
        if 方向 == "short" or (方向 is None and 张 is not None and 张 < 0):
            做什么 = "short"
        else:
            做什么 = "long "
        现价 = 浮(取键(持仓, "current_price", "currentPrice"))
        浮盈 = 浮(取键(持仓, "unrealized_pl", "unrealizedPl"))
        print(f"    {合约:<20} {做什么} {简洁数(abs(张)) if 张 is not None else '?'}   "
              f"last {钱样(现价)}   unrealised {带号钱(浮盈)}")
    线("-")
    print("  I T   S T O P S   W H E N   I T   L O S E S")
    上限 = 权益 * 0.02 if 权益 is not None else None
    止损 = -权益 * 0.03 if 权益 is not None else None
    print(f"    Per-order ceiling  ${钱样(上限)}   (2% of equity)")
    print(f"    Daily stop         -${钱样(abs(止损))}   (3% of equity) - past it, closes only")
    拦, 放, 演习 = 从账本数闸(账本, 今天)
    print(f"    Stopped today      {拦}")
    print(f"    Released today     {放}")
    if 演习:
        print(f"    ({演习} rehearsal run(s), not counted above)")
    线()
    return 0


# ---------- 子命令：演闸 ----------

def 组合约代码(标的, 到期日, 类型, 行权价):
    """拼 OCC 合约代码：标的 + YYMMDD + C/P + 8 位行权价（×1000 左补零）。"""
    return f"{标的}{到期日:%y%m%d}{类型}{int(round(行权价 * 1000)):08d}"


def 造腿(标的, 到期日, 类型, 行权价, 方向, 买价, 卖价):
    """造一条演习用的腿。"""
    return {"合约": 组合约代码(标的, 到期日, 类型, 行权价), "方向": 方向, "比例": 1,
            "行权价": 行权价, "类型": 类型, "到期": 到期日.isoformat(),
            "买价": 买价, "卖价": 卖价}


def 造裸卖认沽提案(账本, 到期日):
    """演习一：裸卖一条认沽，只有卖出腿、没有保护腿——应当被拦。"""
    编号 = 账本.发号("演")
    return {"编号": 编号, "标的": "SPY", "结构": "看跌信用价差", "张数": 1,
            "净价": -1.16, "标的现价": 769.28,
            "腿": [造腿("SPY", 到期日, "P", 755.0, "sell", 1.10, 1.22)]}


def 造太宽价差提案(账本, 到期日):
    """演习二：宽度 50 美元、最大亏损约占假账户权益 12% 的价差——应当被拦。"""
    编号 = 账本.发号("演")
    return {"编号": 编号, "标的": "SPY", "结构": "看跌信用价差", "张数": 5,
            "净价": -1.50, "标的现价": 769.28,
            "腿": [造腿("SPY", 到期日, "P", 750.0, "sell", 2.00, 2.10),
                   造腿("SPY", 到期日, "P", 700.0, "buy", 0.50, 0.60)]}


def 造缺报价提案(账本, 到期日):
    """演习三：有一条腿的买价是空的——应当被拦。"""
    编号 = 账本.发号("演")
    return {"编号": 编号, "标的": "SPY", "结构": "看跌信用价差", "张数": 1,
            "净价": -0.81, "标的现价": 769.28,
            "腿": [造腿("SPY", 到期日, "P", 755.0, "sell", 1.10, 1.22),
                   造腿("SPY", 到期日, "P", 750.0, "buy", None, 0.65)]}


def 跑演闸(参):
    闸 = 引入("gate")
    账 = 引入("ledger")
    账本 = 账.账本(参.账)
    今天 = date.today().isoformat()
    到期日 = date.today() + timedelta(days=5)
    # 演习用的假账户与假时钟：闸只拿它们做算术，不联网。
    # 假时钟写「开市中」是为了让三笔分别栽在各自该栽的规则上，不被「休市」一条挡住视线。
    # ⛔ 演习的假账户权益要跟真账户对得上（100000），否则「看」那一屏写 2,000 上限、
    #    这里写 4,000 上限，录屏里两个数打架，看的人会以为闸是随口编的。
    假账户 = {"是模拟盘": True, "权益": 100000.0, "现金": 100000.0, "当日盈亏": 0.0,
              "未平仓组数": 0, "期权购买力": 100000.0}
    假时钟 = {"今天": 今天, "开市中": True}
    演习们 = [
        ("a naked short put - one sold leg, nothing bought behind it", 造裸卖认沽提案(账本, 到期日)),
        ("a $50-wide spread whose worst case is about 12% of equity", 造太宽价差提案(账本, 到期日)),
        ("a leg with no bid at all", 造缺报价提案(账本, 到期日)),
    ]
    线()
    print("  R E H E A R S A L   -   three deliberately bad proposals (works when shut)")
    线()
    栽在哪 = []
    全部拦下 = True
    for 序, (说明, 提案) in enumerate(演习们, 1):
        闸判 = 闸.过闸(提案, 假账户, 假时钟)
        账本.记("闸", {"演习": True, "提案": 提案, "结果": 闸判}, 提案["编号"])
        打印闸表(f"Rehearsal {序}/3: {说明}   ({提案['编号']})", 闸判, 提案)
        逐条 = 取键(闸判, "逐条") or []
        首拦 = next((条 for 条 in 逐条 if isinstance(条, dict) and 取键(条, "过") is False), None)
        if 首拦 is not None:
            栽在哪.append(f"#{序} stopped at {取键(首拦, '规则')} {取键(首拦, '名')}")
        elif 取键(闸判, "过") is True:
            全部拦下 = False
            栽在哪.append(f"#{序} WAS RELEASED - this must not happen; check the gate")
        else:
            全部拦下 = False
            栽在哪.append(f"#{序} returned no per-rule receipts, so where it stopped is unknown")
    线()
    print("  R E H E A R S A L   S U M M A R Y")
    print("  All three were stopped - which is the point." if 全部拦下
          else "  NOT all three were stopped. Check the gate.")
    for 句 in 栽在哪:
        print(f"    {句}")
    线()
    return 0


# ---------- 子命令：开 ----------

def 组装账户(账户原始, 持仓们):
    """把 Alpaca 原始账户 JSON 拼成 闸.过闸 要的「账户」形状。"""
    账号 = 取键(账户原始, "account_number", "accountNumber")
    权益 = 浮(取键(账户原始, "equity"))
    昨权益 = 浮(取键(账户原始, "last_equity", "lastEquity"))
    期权条数 = len([p for p in (持仓们 or []) if 取键(p, "asset_class", "assetClass") == "us_option"])
    # 未平仓组数用简化口径：期权持仓条数 ÷ 2 向上取整（默认一组价差正好一卖一买两条腿）
    return {
        "是模拟盘": isinstance(账号, str) and 账号.startswith("PA"),
        "权益": 权益 if 权益 is not None else 0.0,
        "现金": 浮(取键(账户原始, "cash")) or 0.0,
        "当日盈亏": (权益 - 昨权益) if (权益 is not None and 昨权益 is not None) else 0.0,
        "未平仓组数": math.ceil(期权条数 / 2) if 期权条数 else 0,
        "期权购买力": 浮(取键(账户原始, "buying_power", "buyingPower")) or 0.0,
    }


def 跑开(参):
    账 = 引入("ledger")
    手模块 = 引入("broker")
    闸 = 引入("gate")
    判 = 引入("strategy")
    账本 = 账.账本(参.账)
    编号 = None
    try:
        with 手模块.手(账本, 参.根) as 手柄:
            # 1. 先看时钟：休市就到此为止，一笔单都不下
            时钟原始 = 手柄.时钟()
            # ⛔ 踩过：这里原来取 date.today()，那是本机的北京日期。
            #    美股时段是北京 21:30 到次日 04:00，跨午夜之后北京日期比美东多一天
            #    ⟹ 到期天数整体错一位，挑到的到期日跟着错，而且不会报错。
            #    ⟹ 交易日一律以服务端时钟的美东时间戳为准。
            今天 = str(取键(时钟原始, "timestamp") or "")[:10] or date.today().isoformat()
            开市中 = bool(取键(时钟原始, "is_open", "isOpen"))
            print(f"US trading day {今天} - market {'open' if 开市中 else 'closed'}")
            if not 开市中:
                if not getattr(参, "空转", False):
                    print("Market is shut, so nothing opens today. To watch the gate refuse "
                          "an order right now, run: python3 agent.py rehearse")
                    return 0
                # 空转本来就永远不下单，所以休市照走完整条链——这是休市期间唯一能验挑腿的路。
                print("(market shut + dry run: the whole chain runs, the final send is withheld)")

            # 2. 组装账户（是模拟盘：账户号以 PA 开头；当日盈亏 = equity - last_equity）
            账户原始 = 手柄.账户()
            持仓们 = 手柄.持仓()
            账户 = 组装账户(账户原始, 持仓们)

            # 3. 标的现价
            现价 = 手柄.标的现价("SPY")

            # 4. 拉期权链：到期窗口从今天到今天 + 最长到期天
            判据 = dict(判.默认判据)
            截止 = (date.fromisoformat(今天) + timedelta(days=int(判据["最长到期天"]))).isoformat()
            # 只要现价上下 8% 这一段：delta≈0.16 的档全在里面，
            # 而全链有 2500+ 个合约，整批拖回来又慢又没用。
            链 = 手柄.期权链("SPY", 今天, 截止, 数据源="indicative", 条数=1000,
                             行权价下限=round(现价 * 0.92, 2), 行权价上限=round(现价 * 1.08, 2))

            # 5. 挑组合
            结果 = 判.挑一个(链, "SPY", 现价, 今天, 判据)
            书 = 结果["判断书"]

            # 6. 先落纸再过闸：判断书必须在下单之前、过闸之前进账本
            编号 = 账本.发号("J")
            账本.记("判断", 书, 编号)
            打印判断书(书, 编号)

            # 7. 结论不开就收工（这不是错误）
            if 书.get("结论") != "开" or 结果["提案"] is None:
                理由 = str(书.get("不开的理由") or "判断书没给理由")
                print(理由 if 理由.startswith("今天不开") else f"Not opening today: {理由}")
                return 0
            提案 = 结果["提案"]
            提案["编号"] = 编号

            # 8. 过闸，并把提案全文和结果记进账本
            闸判 = 闸.过闸(提案, 账户, {"今天": 今天, "开市中": True})
            账本.记("闸", {"放行": bool(闸判.get("过")), "一句话": 闸判.get("一句话", ""),
                           "提案": 提案, "结果": 闸判}, 编号)
            打印闸表("T H E   G A T E", 闸判, 提案)

            # 9. 闸拦下不是错误，正常收工
            if 取键(闸判, "过") is not True:
                print(f"STOPPED by the gate: {取键(闸判, '一句话') or 'no reason given'}")
                print("(a stop means the proposal had something wrong with it - that is the gate working)")
                return 0

            # 10. 空转：闸已放行，但本次不下单
            if getattr(参, "空转", False):
                print("(dry run: the gate released it, but nothing was sent)")
                return 0

            # 11. 真下单：先记「下单」，再发单，回执入账
            下单腿 = []
            for 腿 in 提案["腿"]:
                开平 = "sell_to_open" if 腿["方向"] == "sell" else "buy_to_open"
                下单腿.append({"合约": 腿["合约"], "方向": 腿["方向"],
                               "比例": 腿.get("比例", 1), "开平": 开平})
            账本.记("下单", {"用途": "开仓", "提案": 提案, "幂等键": 编号}, 编号)
            回执 = 手柄.下多腿期权单(提案["张数"], 下单腿, 提案["净价"], 幂等键=编号)
            账本.记("回执", 回执, 编号)
            单号 = 取键(回执, "id", "order_id", "orderId") or "？"
            状态 = 取键(回执, "status") or "？"
            print()
            print(f"ORDER SENT: id {单号}, status {状态}")
            return 0
    except Exception as 错:
        # 12. 任何异常：先记进账本，再报中文错，退出码 1
        记错(账本, "开", 错)
        print(f"ERROR - this pass is aborted: {type(错).__name__}: {错}")
        print("(the detail is already in the ledger; run `recap` to see the full day)")
        return 1


# ---------- 子命令：平 ----------

def 跑平(参):
    账 = 引入("ledger")
    手模块 = 引入("broker")
    判 = 引入("strategy")
    账本 = 账.账本(参.账)
    今天 = date.today().isoformat()
    try:
        with 手模块.手(账本, 参.根) as 手柄:
            持仓们 = 手柄.持仓() or []
            期权持仓们 = [p for p in 持仓们 if 取键(p, "asset_class", "assetClass") == "us_option"]
            线()
            print("  C L O S E   C H E C K")
            线()
            if not 期权持仓们:
                print("  Nothing open, nothing to close.")
                线()
                return 0
            for 持仓 in 期权持仓们:
                合约 = str(取键(持仓, "symbol") or "?")
                头 = 判.解析合约代码(合约)
                浮盈 = 浮(取键(持仓, "unrealized_pl", "unrealizedPl"))
                成本 = 浮(取键(持仓, "cost_basis", "costBasis"))
                理由 = None
                if 头 is not None and 头["到期"] == 今天:
                    # 到期日就是今天：不留到收盘，直接平
                    理由 = "expiry day - nothing is carried into the close"
                elif 浮盈 is None or 成本 is None or 成本 == 0:
                    # 找不到判断依据的持仓不许乱平
                    print(f"  {合约:<20} skipped: cannot work out whether to close")
                    continue
                elif 浮盈 >= 0.5 * abs(成本):
                    理由 = (f"unrealised {带号钱(浮盈)}, which is half the ${钱样(abs(成本))} "
                            f"cost basis (${钱样(0.5 * abs(成本))})")
                else:
                    print(f"  {合约:<20} holding: unrealised {带号钱(浮盈)}, short of the "
                          f"${钱样(0.5 * abs(成本))} half-credit target")
                    continue
                编号 = 账本.发号("P")
                账本.记("下单", {"用途": "平仓", "合约": 合约, "理由": 理由, "幂等键": 编号}, 编号)
                回执 = 手柄.平仓(合约)
                账本.记("回执", 回执, 编号)
                print(f"  {合约:<20} CLOSED - {理由}")
            线()
            return 0
    except Exception as 错:
        记错(账本, "平", 错)
        print(f"ERROR: {type(错).__name__}: {错}")
        return 1


# ---------- 子命令：复盘 ----------

def 一句话来路(类, 正文):
    """给账本里一条记录配一句中文来路；认不出的返回 None。"""
    if 类 == "判断":
        结论 = 取键(正文, "结论") or "?"
        if 结论 == "不开":
            return f"判断：不开——{取键(正文, '不开的理由') or '没写理由'}"
        return f"判断：开（{取键(正文, '结构中文') or '没写结构'}）"
    if 类 == "闸":
        结果 = 取键(正文, "结果")
        过 = 取键(结果, "过") if isinstance(结果, dict) else None
        一句话 = 取键(结果, "一句话") if isinstance(结果, dict) else None
        前 = "演习·" if 取键(正文, "演习") else ""
        return f"{前}闸：{'放行' if 过 is True else '拦下'}——{一句话 or '没给一句话'}"
    if 类 == "下单":
        用途 = 取键(正文, "用途") or "开仓"
        合约 = 取键(正文, "合约")
        return f"下单：{用途}" + (f"（{合约}）" if 合约 else "")
    if 类 == "回执":
        return "回执：券商已答复，已入账"
    if 类 == "错":
        return f"出错：{取键(正文, '说明') or '（没写细节）'}"
    if 类 == "复盘":
        return "复盘：写了当天日志"
    if 类 in ("MCP请求", "MCP回执"):
        return f"{类}：接口往来记录"
    return None


def 跑复盘(参):
    账 = 引入("ledger")
    账本 = 账.账本(参.账)
    今天 = date.today().isoformat()
    try:
        条目们 = 账本.读(今天) or []
    except Exception as 错:
        print(f"ERROR: today's ledger could not be read: {type(错).__name__}: {错}")
        return 1
    try:
        渲染 = 账本.渲染中文(今天) or ""
    except Exception:
        渲染 = "（账本「渲染中文」这一栏暂时拿不到）"

    开单数 = 平单数 = 接口次数 = 0
    来路们 = []
    for 条 in 条目们:
        if not isinstance(条, dict):
            continue
        类 = 取键(条, "类", "type", "类别")
        正文 = 取正文(条)
        if 类 == "下单":
            if 取键(正文, "用途") == "平仓":
                平单数 += 1
            else:
                开单数 += 1
        # MCP 的一来一回是接口流水，逐条列出来会把「每一笔的来路」淹掉。
        # 它们在下面的完整流水里一条不少，这里只数个数。
        if 类 in ("MCP请求", "MCP回执"):
            接口次数 += 1
            continue
        句 = 一句话来路(类, 正文)
        if 句:
            编号 = 取键(条, "编号", "id")
            来路们.append(f"{编号}：{句}" if 编号 else 句)

    拦, 放, 演习 = 从账本数闸(账本, 今天)

    # 当前权益、当日盈亏：尽力连一次账户，拿不到就在小结里写明
    权益 = 当日 = None
    try:
        手模块 = 引入("broker")
        with 手模块.手(账本, 参.根) as 手柄:
            账户原始 = 手柄.账户()
        权益 = 浮(取键(账户原始, "equity"))
        昨权益 = 浮(取键(账户原始, "last_equity", "lastEquity"))
        if 权益 is not None and 昨权益 is not None:
            当日 = 权益 - 昨权益
    except Exception:
        权益 = 当日 = None

    小结行 = [
        "## 当天小结",
        f"- 今天开了 {开单数} 笔（另有平仓 {平单数} 笔）",
        f"- 闸拦下 {拦} 笔、放行 {放} 笔" + (f"（另有演习 {演习} 笔，不计入）" if 演习 else ""),
        f"- 当前权益 {钱样(权益)} 美元，当日盈亏 {钱样(当日)} 美元"
        + ("" if 权益 is not None else "（账户暂时连不上，这两个数没拿到）"),
    ]
    小结行.append(f"- 全程走 MCP，今天一共调了 {接口次数 // 2} 次接口（一来一回逐条落在下面的流水里）")
    if 来路们:
        小结行.append("- 每一笔的来路：")
        for 句 in 来路们:
            小结行.append(f"  - {句}")

    日志目录 = os.path.join(参.根, "日志")
    os.makedirs(日志目录, exist_ok=True)
    文件 = os.path.join(日志目录, f"{今天}.md")
    with open(文件, "w", encoding="utf-8") as 笔:
        笔.write(f"# {今天} 复盘\n\n" + "\n".join(小结行) + "\n\n---\n\n" + 渲染 + "\n")
    账本.记("复盘", {"文件": 文件, "小结": "\n".join(小结行)}, None)
    print(f"Recap written to: {文件}")
    return 0


# ---------- 命令行组装 ----------

def 中文化argparse():
    """把 argparse 自带的几个英文标签换成中文（不然帮助里会夹英文）。"""
    词条 = {
        "usage: ": "用法：",
        "options": "可选项",
        "positional arguments": "子命令",
        "show this help message and exit": "显示这份帮助然后退出",
        "the following arguments are required: %s": "缺了这些参数：%s",
        "unrecognized arguments: %s": "多出不认识的参数：%s",
        "invalid choice: %(value)r (choose from %(choices)s)": "没有这个子命令：%(value)r（可以选：%(choices)s）",
        "%(prog)s: error: %(message)s": "%(prog)s：出错：%(message)s\n",
    }
    原翻译 = argparse._

    def 翻译(提示):
        return 词条.get(提示, 原翻译(提示))

    argparse._ = 翻译


class 中文解析器(argparse.ArgumentParser):
    """argparse 报错时也不让英文提示漏出去：整句换成中文再退出。"""

    def error(self, 消息):
        import re
        # argparse 自己拼的「argument xxx: 」前缀不走翻译，直接剪掉
        消息 = re.sub(r"^argument\s+[^:]*:\s*", "", str(消息))
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}：出错：{消息}\n")
        sys.exit(2)


# 英文动词是对外那一层；中文动词留着当别名，⛔ 免得已排好的定时任务断掉。
命令别名 = {"preflight": "体检", "status": "看", "rehearse": "演闸",
            "open": "开", "close": "平", "recap": "复盘"}


def 建解析器():
    中文化argparse()
    解析器 = 中文解析器(
        prog="agent.py",
        description="Paper-options agent CLI: preflight, status, rehearse, open, close, recap.",
        epilog="e.g. python3 agent.py open --dry-run   (gate may release; no order is sent)")
    解析器.add_argument("--根", "--root", dest="根", default=".",
                        help="project root (default: current directory)")
    解析器.add_argument("--账", "--ledger", dest="账", default=None,
                        help="ledger directory (default: <root>/账)")
    子 = 解析器.add_subparsers(dest="命令", required=True,
                                metavar="{preflight,status,rehearse,open,close,recap}")
    子.add_parser("preflight", aliases=["体检"],
                  help="load all four modules, check the key file, then reach the account and clock")
    子.add_parser("status", aliases=["看"],
                  help="the 15-second screen: paper flag, equity, open positions, daily stop")
    子.add_parser("rehearse", aliases=["演闸"],
                  help="run three deliberately bad proposals through the gate (works when the market is shut)")
    开 = 子.add_parser("open", aliases=["开"],
                       help="one full pass: chain -> pick -> write the judgment -> gate -> (optionally) order")
    开.add_argument("--dry-run", "--空转", dest="空转", action="store_true",
                    help="stop before sending, even if the gate releases")
    子.add_parser("close", aliases=["平"],
                  help="close positions that expired or already earned half the credit")
    子.add_parser("recap", aliases=["复盘"],
                  help="render today's ledger into a Markdown log and write the summary")
    return 解析器


def 主():
    解析器 = 建解析器()
    参 = 解析器.parse_args()
    参.根 = os.path.abspath(参.根)
    if not 参.账:
        参.账 = os.path.join(参.根, "账")
    分发 = {"体检": 跑体检, "看": 跑看, "演闸": 跑演闸, "开": 跑开, "平": 跑平, "复盘": 跑复盘}
    参.命令 = 命令别名.get(参.命令, 参.命令)
    try:
        码 = 分发[参.命令](参)
    except SystemExit:
        raise
    except Exception as 错:
        # 兜底：不许让使用者看见一屏英文堆栈
        print(f"ERROR - aborted: {type(错).__name__}: {错}")
        码 = 1
    sys.exit(int(码 or 0))


if __name__ == "__main__":
    主()

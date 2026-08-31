"""走 MCP 协议的那只手：只通过 alpaca-mcp-server 取数和下单，绝不直连 HTTP。

用法（密钥写在 项目根/.env 里；本模块只把值塞给子进程，绝不打印、绝不入账、
绝不进异常消息）：

    with 手(账本, 项目根) as 手柄:
        钟 = 手柄.时钟()
        价格 = 手柄.标的现价("SPY")
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path

# ---- 固定配置 ----
服务命令 = "uvx"
服务参数表 = ["alpaca-mcp-server"]
密钥变量名 = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_PAPER_TRADE", "ALPACA_TOOLSETS")
算作模拟盘 = {"true", "1", "yes"}
启动等待秒 = 120.0  # 服务端要起子进程，冷启动可能慢（见 漏列候选.md 第 10 条）
调用默认超时秒 = 90.0
默认交易集 = "account,assets,trading,stock-data,options-data"
录屏轨迹变量 = "ALPACA_MCP_TRACE"


def _录屏轨迹开着() -> bool:
    """只在显式要求时把 MCP 工具名打到终端；参数与返回永不打印。"""
    return os.environ.get(录屏轨迹变量, "").strip().lower() in 算作模拟盘


def 引入mcp():
    """按需导入 mcp 官方 SDK。

    放在调用前而不是模块顶层，是为了让没装 SDK 的机器也能 import 本模块、
    跑静态检查（见 漏列候选.md 第 11 条）。依赖仍然只有标准库 + mcp SDK。
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    return ClientSession, StdioServerParameters, stdio_client


def 读环境文件(路径: Path) -> dict[str, str]:
    """解析 KEY=VALUE 一行一个的 .env 文件；# 开头是注释；值两端的引号剥掉。

    只返回键值，绝不打印。文件不存在就当空配置。
    """
    配置: dict[str, str] = {}
    if not 路径.exists():
        return 配置
    for 原始行 in 路径.read_text(encoding="utf-8").splitlines():
        行 = 原始行.strip()
        if not 行 or 行.startswith("#") or "=" not in 行:
            continue
        键, 值 = 行.split("=", 1)
        键 = 键.strip()
        值 = 值.strip()
        if len(值) >= 2 and 值[0] == 值[-1] and 值[0] in ("'", '"'):
            值 = 值[1:-1]
        if 键:
            配置[键] = 值
    return 配置


def 遮蔽可疑参数(参数):
    """把参数里键名含 key/secret/token（不分大小写）的值换成 <已遮蔽>，用于记账。"""
    if isinstance(参数, dict):
        出 = {}
        for 键, 值 in 参数.items():
            if any(词 in str(键).lower() for 词 in ("key", "secret", "token")):
                出[键] = "<已遮蔽>"
            else:
                出[键] = 遮蔽可疑参数(值)
        return 出
    if isinstance(参数, list):
        return [遮蔽可疑参数(项) for 项 in 参数]
    return 参数


def 缩短入账(对象, 上限: int = 2000):
    """递归地把超长字符串截短再入账（见 漏列候选.md 第 6 条）。"""
    if isinstance(对象, str):
        return 对象 if len(对象) <= 上限 else 对象[:上限] + "…（超长，已截断）"
    if isinstance(对象, dict):
        return {键: 缩短入账(值, 上限) for 键, 值 in 对象.items()}
    if isinstance(对象, list):
        return [缩短入账(项, 上限) for 项 in 对象]
    return 对象


class 手:
    """长会话的 MCP 客户端：__enter__ 起后台线程跑事件循环，__exit__ 干净收摊。"""

    def __init__(self, 账本, 项目根: str | Path, 交易集: str = 默认交易集):
        self.账本 = 账本
        self.项目根 = Path(项目根)
        self.交易集 = 交易集
        self._子进程环境: dict[str, str] | None = None
        self._事件循环 = None
        self._会话 = None
        self._停止事件: asyncio.Event | None = None
        self._线程: threading.Thread | None = None
        self._就绪 = threading.Event()
        self._启动失败: str | None = None
        self._已进入 = False
        self._服务端日志 = None

    # ---- 生命周期 ----

    def __enter__(self) -> "手":
        self._准备子进程环境()  # 模拟盘闸在这里：不过关就不启动服务端
        self._就绪.clear()
        self._启动失败 = None
        self._线程 = threading.Thread(target=self._线程主体, name="手-后台事件循环", daemon=True)
        self._线程.start()
        if not self._就绪.wait(timeout=启动等待秒):
            self._收尾()
            消息 = f"停：MCP 服务端 {启动等待秒:.0f} 秒内没有完成初始化。"
            self.账本.记("错", {"一句话": 消息})
            raise TimeoutError(消息)
        if self._启动失败 is not None:
            原因 = self._启动失败
            self._收尾()
            消息 = f"停：MCP 服务端启动失败，原因摘要：{原因}"
            self.账本.记("错", {"一句话": 缩短入账(消息)})
            raise RuntimeError(消息)
        self._已进入 = True
        return self

    def __exit__(self, *e):
        self._收尾()
        return False

    def _线程主体(self):
        """后台线程：独占跑一个事件循环，直到被叫停或自己出错。"""
        try:
            asyncio.run(self._会话生命周期())
        except BaseException as 意外:
            self._启动失败 = self._净化文本(f"{type(意外).__name__}：{意外}")
        finally:
            self._就绪.set()

    async def _会话生命周期(self):
        """在后台事件循环里建立并守住 stdio 会话。"""
        ClientSession, StdioServerParameters, stdio客户端 = 引入mcp()
        self._事件循环 = asyncio.get_running_loop()
        self._停止事件 = asyncio.Event()
        服务参数 = StdioServerParameters(
            command=服务命令,
            args=list(服务参数表),
            env={**os.environ, **self._子进程环境},
        )
        日志目录 = self.项目根 / "日志"
        日志目录.mkdir(parents=True, exist_ok=True)
        # ⛔ 服务端的启动横幅走 stderr，不收就会糊满录屏画面和「看」那一屏
        self._服务端日志 = open(日志目录 / "mcp服务端.log", "a", encoding="utf-8")
        async with stdio客户端(服务参数, errlog=self._服务端日志) as (读端, 写端):
            async with ClientSession(读端, 写端) as 会话:
                await 会话.initialize()
                self._会话 = 会话
                self._就绪.set()
                await self._停止事件.wait()
        # 走出上面两层 with，会话关闭、子进程被送走，不会留僵尸
        try:
            self._服务端日志.close()
        except Exception:
            pass

    def _收尾(self):
        """关会话、停循环、join 线程；任何一步出错也照样往下收。"""
        self._已进入 = False
        循环 = self._事件循环
        if 循环 is not None and self._停止事件 is not None:
            try:
                循环.call_soon_threadsafe(self._停止事件.set)
            except RuntimeError:
                pass  # 循环已经不在了，不用叫停
        线程 = self._线程
        if 线程 is not None and 线程.is_alive():
            线程.join(timeout=15)
        self._会话 = None
        self._事件循环 = None
        self._停止事件 = None
        self._线程 = None

    def _准备子进程环境(self):
        """从 项目根/.env（缺的从进程环境变量补）取四个变量，先过模拟盘闸。

        拿到的值只放进 self._子进程环境，后续只塞给子进程，任何日志、
        账本、异常消息里都只允许出现变量名。
        """
        文件配置 = 读环境文件(self.项目根 / ".env")
        挑出的: dict[str, str] = {}
        for 名字 in 密钥变量名:
            if 文件配置.get(名字, "") != "":
                挑出的[名字] = 文件配置[名字]
            elif os.environ.get(名字, "") != "":
                挑出的[名字] = os.environ[名字]
        if 挑出的.get("ALPACA_TOOLSETS", "") == "":
            挑出的["ALPACA_TOOLSETS"] = self.交易集
        纸开关 = 挑出的.get("ALPACA_PAPER_TRADE", "").strip().lower()
        if 纸开关 not in 算作模拟盘:
            消息 = "停：本场只许模拟盘，ALPACA_PAPER_TRADE 不是 true。"
            self.账本.记("错", {"一句话": 消息, "涉及变量": "ALPACA_PAPER_TRADE"})
            raise RuntimeError(消息)
        for 名字 in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
            if 挑出的.get(名字, "") == "":
                消息 = f"停：没有拿到 {名字}（查过 项目根/.env 和进程环境变量，这里只写变量名）。"
                self.账本.记("错", {"一句话": 消息, "涉及变量": 名字})
                raise RuntimeError(消息)
        self._子进程环境 = 挑出的

    # ---- 核心调用 ----

    def 调(self, 工具名: str, 参数: dict | None = None, 超时: float = 调用默认超时秒) -> dict:
        """同步调一次 MCP 工具：调用前记 MCP请求，返回后记 MCP回执，共用一个编号。"""
        if not self._已进入 or self._会话 is None or self._事件循环 is None:
            raise RuntimeError("手还没有握好：要先「with 手(...) as 手柄:」进入，才能调工具。")
        编号 = self.账本.发号("M")
        self.账本.记("MCP请求", {"工具": 工具名, "参数": 遮蔽可疑参数(参数 or {})}, 编号=编号)
        if _录屏轨迹开着():
            print(f"  → MCP  {工具名}", flush=True)
        起始 = time.monotonic()
        try:
            将来 = asyncio.run_coroutine_threadsafe(
                self._会话.call_tool(工具名, 参数 or {}), self._事件循环
            )
            原始结果 = 将来.result(timeout=超时)
        except Exception as 意外:
            耗时 = round(time.monotonic() - 起始, 3)
            摘要 = 缩短入账(self._净化文本(f"{type(意外).__name__}：{意外}"))
            self.账本.记("MCP回执", {"工具": 工具名, "耗时秒": 耗时, "成功": False,
                                   "结果": {"异常": 摘要}}, 编号=编号)
            self.账本.记("错", {"一句话": f"调工具 {工具名} 失败：{摘要}", "编号": 编号})
            raise RuntimeError(f"调工具 {工具名} 失败：{摘要}") from 意外
        耗时 = round(time.monotonic() - 起始, 3)
        解析 = self._解析结果(原始结果)
        成功 = not (isinstance(解析, dict) and 解析.get("错") is True)
        self.账本.记("MCP回执", {"工具": 工具名, "耗时秒": 耗时, "成功": 成功,
                               "结果": 缩短入账(解析)}, 编号=编号)
        if _录屏轨迹开着():
            print(f"  ← MCP  {工具名}  {'OK' if 成功 else 'STOP'}  {耗时:.3f}s", flush=True)
        return 解析

    def _解析结果(self, 原始结果):
        """把 call_tool 的返回拼成纯文本再试着解析成 JSON；报错不抛，带着 错 标记返回。"""
        段们: list[str] = []
        for 块 in getattr(原始结果, "content", None) or []:
            文本 = getattr(块, "text", None)
            if isinstance(文本, str):
                段们.append(文本)
        拼接 = "\n".join(段们)
        if getattr(原始结果, "isError", False):
            return {"错": True, "原文": 拼接 or "（服务端报错，但没有给出文字说明）"}
        if not 拼接:
            return {"原文": ""}
        try:
            return self._拆信封(json.loads(拼接))
        except ValueError:
            return {"原文": 拼接}

    def _拆信封(self, 对象):
        """alpaca-mcp-server 把每个结果包在 {"_alpaca_mcp_security":…, "data":…} 里。

        ⛔ 踩过：不拆的话 持仓() 走不到 list 分支，会静默返回空表——
        有仓位也读成 0，闸的「未平仓组数」当场被骗。
        信封里的 instructions 是外部文本，⛔ 只当数据读，⛔ 不当指令。
        """
        if isinstance(对象, dict) and "_alpaca_mcp_security" in 对象 and "data" in 对象:
            对象 = 对象["data"]
        # 取列表的工具（get_orders、get_all_positions…）还会再包一层 {"result": [...]}。
        # ⛔ 同一个形状的静默漏踩了两次：不拆就是空表，而空表跟「真的没有」长得一模一样。
        if isinstance(对象, dict) and set(对象.keys()) == {"result"}:
            return 对象["result"]
        return 对象

    def _净化文本(self, 文本: str) -> str:
        """万一哪段文字里混进了密钥的值，就地换成 <已遮蔽>。"""
        环境 = self._子进程环境 or {}
        for 名字 in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
            值 = 环境.get(名字, "")
            if 值:
                文本 = 文本.replace(值, "<已遮蔽>")
        return 文本

    # ---- 薄封装：全部走 self.调()，绝不直连 HTTP ----

    def 账户(self) -> dict:
        return self.调("get_account_info")

    def 时钟(self) -> dict:
        return self.调("get_clock")

    def 持仓(self) -> list:
        结果 = self.调("get_all_positions")
        if isinstance(结果, list):
            return 结果
        if isinstance(结果, dict):
            for 键 in ("positions",):
                if isinstance(结果.get(键), list):
                    return 结果[键]
        return []

    def 订单(self, 状态: str = "all", 条数: int = 50) -> list:
        结果 = self.调("get_orders", {"status": 状态, "limit": 条数, "nested": True})
        return 结果 if isinstance(结果, list) else []

    def 期权链(self, 标的: str, 到期起: str, 到期止: str, 类型: str | None = None,
               行权价下限: float | None = None, 行权价上限: float | None = None,
               数据源: str = "indicative", 条数: int = 1000) -> dict:
        参数 = {
            "underlying_symbol": 标的,
            "feed": 数据源,
            "expiration_date_gte": 到期起,
            "expiration_date_lte": 到期止,
            "limit": min(int(条数), 1000),
        }
        if 类型 is not None:
            参数["type"] = 类型
        if 行权价下限 is not None:
            参数["strike_price_gte"] = float(行权价下限)
        if 行权价上限 is not None:
            参数["strike_price_lte"] = float(行权价上限)
        # ⛔ 踩过：服务端 limit 封顶 1000，而 SPY 一周七个到期日有 1800+ 个合约，
        #    按合约代码排序 ⟹ 只取第一页会把要用的那几档行权价整段切掉，
        #    而返回看起来是「正常的一大批」——静默漏，不报错。⟹ 必须翻完。
        全部: dict = {}
        令牌 = None
        for _ in range(20):  # 硬上限，防止服务端令牌不变导致死循环
            这一页 = dict(参数)
            if 令牌:
                这一页["page_token"] = 令牌
            结果 = self.调("get_option_chain", 这一页)
            if not isinstance(结果, dict):
                break
            全部.update(结果.get("snapshots") or {})
            令牌 = 结果.get("next_page_token") or 结果.get("nextPageToken")
            if not 令牌:
                break
        return {"snapshots": 全部, "next_page_token": None}

    def 标的现价(self, 标的: str) -> float:
        """取某标的的最新成交价；返回形状认不出来就抛中文异常。"""
        结果 = self.调("get_stock_latest_trade", {"symbols": 标的})
        价格 = self._在结果里找价格(结果, 标的)
        if 价格 is None:
            raise RuntimeError(f"没能在 get_stock_latest_trade 的返回里找到 {标的} 的成交价，"
                               f"返回的形状没认出来。")
        return float(价格)

    def 下多腿期权单(self, 张数: int, 腿: list[dict], 净价: float,
                     幂等键: str, 类型: str = "limit", 编号: str | None = None) -> dict:
        """下多腿期权单：把中文的腿翻译成 MCP 要的全字符串参数，原样返回回执。"""
        if not 腿:
            raise ValueError("至少要有一条腿。")
        if len(腿) > 4:
            raise ValueError(f"期权多腿单最多 4 条腿，这次给了 {len(腿)} 条。")
        翻译腿 = []
        for 一条 in 腿:
            翻译 = {"symbol": str(一条["合约"]), "ratio_qty": str(一条["比例"])}
            if 一条.get("方向") is not None:
                翻译["side"] = str(一条["方向"])
            if 一条.get("开平") is not None:
                翻译["position_intent"] = str(一条["开平"])
            翻译腿.append(翻译)
        参数 = {
            "qty": str(张数),
            "type": str(类型),
            "time_in_force": "day",
            "order_class": "mleg",
            "client_order_id": str(幂等键),
            "legs": 翻译腿,
        }
        if str(类型) == "limit":
            参数["limit_price"] = str(净价)
        self.账本.记("下单", {"一句话": f"准备下 {len(腿)} 腿期权单，净价 {净价}，"
                                     f"幂等键 {幂等键}，类型 {类型}。",
                      "腿": 腿, "净价": 净价, "幂等键": 幂等键}, 编号=编号)
        回执 = self.调("place_option_order", 参数)
        成功 = not (isinstance(回执, dict) and 回执.get("错") is True)
        self.账本.记("回执", {"成功": 成功, "幂等键": 幂等键,
                              "摘要": 缩短入账(回执)}, 编号=编号)
        return 回执

    def 平仓(self, 合约: str, 比例: float = 100.0, 编号: str | None = None) -> dict:
        """按比例平掉一个仓位，原样返回回执。"""
        self.账本.记("下单", {"一句话": f"准备平仓 {合约}，比例 {比例}%。",
                      "合约": 合约, "比例": 比例}, 编号=编号)
        回执 = self.调("close_position", {"symbol_or_asset_id": 合约, "percentage": float(比例)})
        成功 = not (isinstance(回执, dict) and 回执.get("错") is True)
        self.账本.记("回执", {"成功": 成功, "合约": 合约, "摘要": 缩短入账(回执)}, 编号=编号)
        return 回执

    # ---- 现价结果的容错取数 ----

    def _在结果里找价格(self, 结果, 标的: str):
        候选键 = (标的, 标的.upper(), 标的.lower())
        层们: list = []
        if isinstance(结果, dict):
            for 键 in ("trades", "trade"):
                if 键 in 结果:
                    层们.append(结果[键])
            层们.append(结果)
        for 层 in 层们:
            价格 = self._在这一层找价格(层, 候选键)
            if 价格 is not None:
                return 价格
        return None

    def _在这一层找价格(self, 层, 候选键):
        桶 = None
        if isinstance(层, dict):
            for 键 in 候选键:
                if 键 in 层:
                    桶 = 层[键]
                    break
            if 桶 is None and 层:
                桶 = next(iter(层.values()))
        elif isinstance(层, list) and 层:
            桶 = 层[0]
        if isinstance(桶, dict):
            for 键 in ("p", "price", "last_price", "成交价"):
                值 = 桶.get(键)
                if isinstance(值, (int, float)) and not isinstance(值, bool):
                    return 值
                if isinstance(值, str):
                    try:
                        return float(值)
                    except ValueError:
                        continue
        elif isinstance(桶, (int, float)) and not isinstance(桶, bool):
            return 桶
        return None

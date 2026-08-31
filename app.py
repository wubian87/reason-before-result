"""Read-only Streamlit demo for the public hackathon submission.

This app never reads Alpaca credentials and never places an order. It runs the
same pure fail-closed gate used by the paper-trading CLI against transparent
sample proposals.
"""

from datetime import date, timedelta

import streamlit as st

from 闸 import 过闸


st.set_page_config(page_title="Reason Before Result", page_icon="🧾", layout="wide")


def 合约代码(到期: date, 类型: str, 行权价: float) -> str:
    return f"SPY{到期:%y%m%d}{类型}{int(round(行权价 * 1000)):08d}"


def 腿(到期: date, 类型: str, 行权价: float, 方向: str, 买价, 卖价) -> dict:
    return {
        "合约": 合约代码(到期, 类型, 行权价),
        "方向": 方向,
        "比例": 1,
        "行权价": 行权价,
        "类型": 类型,
        "到期": 到期.isoformat(),
        "买价": 买价,
        "卖价": 卖价,
    }


def 样例们() -> dict[str, dict]:
    今天 = date.today()
    到期 = 今天 + timedelta(days=5)
    return {
        "Defined-risk spread — should pass": {
            "编号": "DEMO-001",
            "标的": "SPY",
            "结构": "看跌信用价差",
            "张数": 1,
            "净价": -0.62,
            "标的现价": 769.28,
            "腿": [
                腿(到期, "P", 755.0, "sell", 1.10, 1.22),
                腿(到期, "P", 750.0, "buy", 0.54, 0.62),
            ],
        },
        "Naked short put — must stop": {
            "编号": "DEMO-002",
            "标的": "SPY",
            "结构": "看跌信用价差",
            "张数": 1,
            "净价": -1.16,
            "标的现价": 769.28,
            "腿": [腿(到期, "P", 755.0, "sell", 1.10, 1.22)],
        },
        "Missing quote — must stop": {
            "编号": "DEMO-003",
            "标的": "SPY",
            "结构": "看跌信用价差",
            "张数": 1,
            "净价": -0.81,
            "标的现价": 769.28,
            "腿": [
                腿(到期, "P", 755.0, "sell", 1.10, 1.22),
                腿(到期, "P", 750.0, "buy", None, 0.65),
            ],
        },
    }


st.title("The reason is written before the order exists.")
st.write(
    "A paper-options agent that leaves a readable decision first, then lets "
    "deterministic code decide whether an MCP order may exist."
)

左, 中, 右 = st.columns(3)
左.metric("Capital at risk", "$0 real money", "PAPER only")
中.metric("Instrument", "OPTIONS", "defined-risk structures")
右.metric("Per-trade loss ceiling", "2% equity", "unknown risk → stop")

st.caption(
    "This public demo is intentionally read-only: it contains no Alpaca keys, "
    "account identifier, live positions, or order capability."
)

st.subheader("Put a proposal through the same gate")
样例 = 样例们()
选择 = st.selectbox("Transparent sample", list(样例))
提案 = 样例[选择]
账户 = {"是模拟盘": True, "权益": 100_000.0, "当日盈亏": 0.0, "未平仓组数": 0}
时钟 = {"今天": date.today().isoformat(), "开市中": True}
结果 = 过闸(提案, 账户, 时钟)

if 结果.get("过") is True:
    st.success("RELEASED — every rule returned a structured pass.")
else:
    st.error("HELD — no order would be sent.")

英文结论 = {
    "Defined-risk spread — should pass": (
        "The protected spread defines a USD 438 maximum loss on a USD 100,000 paper account."
    ),
    "Naked short put — must stop": (
        "The short put has no protective buy leg, so maximum loss is not defined by the structure."
    ),
    "Missing quote — must stop": (
        "One protective leg has no usable bid, so the proposal cannot prove an executable price."
    ),
}
st.write(英文结论[选择])

规则英文 = {
    "G1": ("Paper account only", "The account is explicitly marked as paper."),
    "G2": ("Risk must be defined", "The option structure must bound maximum loss."),
    "G3": ("Per-trade ceiling", "Maximum loss must remain within 2% of equity."),
    "G4": ("Daily stop", "No new position after the 3% daily-loss boundary."),
    "G5": ("Usable quotes", "Every leg needs a valid, sufficiently tight quote."),
    "G6": ("Expiration window", "Every leg must expire inside the allowed window."),
    "G7": ("Position cap", "The new group must fit inside the open-position cap."),
}

with st.expander("Seven rule receipts", expanded=True):
    for 条 in 结果.get("逐条", []):
        标记 = "PASS" if 条.get("过") is True else "STOP"
        代码 = 条.get("规则")
        名, 说明 = 规则英文.get(代码, (str(条.get("名", "Rule")), "See engine receipt."))
        st.markdown(f"**{代码} · {标记} · {名}**")
        st.write(说明)

with st.expander("Original engine receipt (Chinese, exactly as logged)"):
    st.write(结果.get("一句话", ""))
    for 条 in 结果.get("逐条", []):
        st.markdown(f"**{条.get('规则')} · {条.get('名')}**")
        st.write(条.get("说明", ""))

with st.expander("Proposal data used by the gate"):
    st.json(提案)

st.divider()
st.markdown(
    "**Real paper-trading path:** written judgment → seven-rule receipt → "
    "Alpaca MCP `place_option_order` → append-only ledger.  "
    "The official submission supplies the dedicated paper account ID privately "
    "so judges can verify activity themselves."
)

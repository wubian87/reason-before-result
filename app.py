"""Read-only Streamlit demo for the public hackathon submission.

This app never reads Alpaca credentials and never places an order. It runs the
same pure fail-closed gate used by the paper-trading CLI against transparent
sample proposals.
"""

from datetime import date, timedelta

import streamlit as st

from 闸 import 过闸


st.set_page_config(page_title="Reason Before Result", page_icon="🧾", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #07111f; color: #e8eef8; }
    .block-container { max-width: 1180px; padding-top: 3.2rem; padding-bottom: 4rem; }
    h1, h2, h3 { letter-spacing: -0.035em; }
    .eyebrow { color: #7dd3fc; font-size: .78rem; font-weight: 700; letter-spacing: .16em; }
    .hero { padding: 1.7rem 0 1.2rem; }
    .hero h1 { font-size: clamp(2.8rem, 7vw, 5.4rem); line-height: .94; margin: .5rem 0 1rem; }
    .hero p { color: #b8c7dc; font-size: 1.16rem; max-width: 720px; line-height: 1.6; }
    .pill { display: inline-block; border: 1px solid #29425f; border-radius: 999px; padding: .35rem .7rem;
            margin: .25rem .35rem .25rem 0; color: #c9dbf5; font-size: .8rem; }
    .step { border-top: 1px solid #29425f; padding: 1rem 0 1.25rem; min-height: 138px; }
    .step-no { color: #7dd3fc; font-weight: 700; font-size: .78rem; letter-spacing: .12em; }
    .step h3 { margin: .45rem 0; font-size: 1.25rem; }
    .step p { color: #aabbd1; margin: 0; }
    .signal { border: 1px solid #29425f; border-radius: 16px; padding: 1.3rem 1.4rem; margin: 1.5rem 0 1rem;
              background: linear-gradient(135deg, #0d2036, #091827); }
    .signal-pass { border-color: #2bbf88; background: linear-gradient(135deg, #083529, #091827); }
    .signal-stop { border-color: #fb7185; background: linear-gradient(135deg, #3a1824, #091827); }
    .signal-label { font-size: .76rem; letter-spacing: .14em; font-weight: 700; color: #9fb5d2; }
    .signal-value { font-size: 2rem; font-weight: 750; margin: .25rem 0 .35rem; }
    .signal-copy { color: #c6d5e8; line-height: 1.55; }
    .rule { border-bottom: 1px solid #20364f; padding: .85rem 0; }
    .rule strong { color: #f4f8ff; }
    .rule-pass { color: #4ade80; font-weight: 700; }
    .rule-stop { color: #fb7185; font-weight: 700; }
    .footer-note { color: #89a0bc; font-size: .88rem; line-height: 1.6; }
    </style>
    """,
    unsafe_allow_html=True,
)


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


st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">ALPACA MCP · PAPER OPTIONS</div>
      <h1>Reason<br>Before Result.</h1>
      <p>An options agent that writes down why a trade exists <em>before</em>
      deterministic code decides whether an order is even allowed to exist.</p>
      <span class="pill">PAPER ONLY</span><span class="pill">DEFINED RISK</span>
      <span class="pill">FAIL CLOSED</span><span class="pill">READ-ONLY DEMO</span>
    </section>
    """,
    unsafe_allow_html=True,
)

第一, 第二, 第三 = st.columns(3)
with 第一:
    st.markdown("<div class='step'><div class='step-no'>01 · EXPLAIN</div><h3>Write the reason</h3><p>Thesis, invalidation, loss bound, and exit plan are appended before execution.</p></div>", unsafe_allow_html=True)
with 第二:
    st.markdown("<div class='step'><div class='step-no'>02 · PROVE</div><h3>Run seven receipts</h3><p>Every rule returns a readable pass or stop. Missing information always stops.</p></div>", unsafe_allow_html=True)
with 第三:
    st.markdown("<div class='step'><div class='step-no'>03 · EXECUTE</div><h3>Only then, MCP</h3><p>Only a released paper proposal may reach Alpaca through its MCP order tool.</p></div>", unsafe_allow_html=True)

st.markdown("### Try the execution boundary")
st.caption("This is the real, credential-free gate. It never reads an account, sends an order, or stores your inputs.")
样例 = 样例们()
选择 = st.selectbox("Choose a transparent scenario", list(样例), label_visibility="collapsed")
提案 = 样例[选择]
账户 = {"是模拟盘": True, "权益": 100_000.0, "当日盈亏": 0.0, "未平仓组数": 0}
时钟 = {"今天": date.today().isoformat(), "开市中": True}
结果 = 过闸(提案, 账户, 时钟)

if 结果.get("过") is True:
    状态, 样式 = "RELEASED", "signal-pass"
else:
    状态, 样式 = "STOPPED", "signal-stop"

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
最大亏损 = 结果.get("最大亏损")
风险文字 = f"${最大亏损:,.0f} maximum loss" if isinstance(最大亏损, (int, float)) else "risk is not provable"
st.markdown(
    f"<div class='signal {样式}'><div class='signal-label'>GATE DECISION</div>"
    f"<div class='signal-value'>{状态}</div><div class='signal-copy'>{英文结论[选择]}</div></div>",
    unsafe_allow_html=True,
)

甲, 乙, 丙 = st.columns(3)
甲.metric("Real money", "$0", "paper account only")
乙.metric("Structure", 提案["结构"], f"{len(提案['腿'])} option legs")
丙.metric("Bound", 风险文字, "2% maximum per trade")

规则英文 = {
    "G1": ("Paper account only", "The account is explicitly marked as paper."),
    "G2": ("Risk must be defined", "The option structure must bound maximum loss."),
    "G3": ("Per-trade ceiling", "Maximum loss must remain within 2% of equity."),
    "G4": ("Daily stop", "No new position after the 3% daily-loss boundary."),
    "G5": ("Usable quotes", "Every leg needs a valid, sufficiently tight quote."),
    "G6": ("Expiration window", "Every leg must expire inside the allowed window."),
    "G7": ("Position cap", "The new group must fit inside the open-position cap."),
}

st.markdown("### Seven receipts, no hidden bypass")
with st.container():
    for 条 in 结果.get("逐条", []):
        标记 = "PASS" if 条.get("过") is True else "STOP"
        代码 = 条.get("规则")
        名, 说明 = 规则英文.get(代码, (str(条.get("名", "Rule")), "See engine receipt."))
        颜色 = "rule-pass" if 标记 == "PASS" else "rule-stop"
        st.markdown(
            f"<div class='rule'><span class='{颜色}'>{标记}</span> &nbsp; <strong>{代码} · {名}</strong><br>"
            f"<span class='footer-note'>{说明}</span></div>",
            unsafe_allow_html=True,
        )

with st.expander("Audit trail: original engine receipt (Chinese)"):
    st.write(结果.get("一句话", ""))
    for 条 in 结果.get("逐条", []):
        st.markdown(f"**{条.get('规则')} · {条.get('名')}**")
        st.write(条.get("说明", ""))

with st.expander("Inspect the proposal data used by the gate"):
    st.dataframe(提案["腿"], use_container_width=True, hide_index=True)

st.divider()
st.markdown(
    "<p class='footer-note'><strong>Real paper path:</strong> written judgment → seven receipts → "
    "Alpaca MCP <code>place_option_order</code> → append-only ledger. This public demo contains "
    "no key, account identifier, live position, or order capability. Judges receive the dedicated "
    "paper account identifier only through the private submission form.</p>",
    unsafe_allow_html=True,
)

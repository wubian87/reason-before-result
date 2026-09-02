"""Public, credential-free demo page for the hackathon submission.

Two things a visitor can actually do here:

  1. read the receipt of a real paper order this agent already placed, and the
     sentence it wrote down *before* that order existed;
  2. take that same real trade, break it by hand, and watch the production
     gate refuse it.

The gate is imported from 闸.py — the exact module the paper-trading CLI uses.
This page reads no credentials, holds no account, and cannot place an order.
The frozen evidence in 递送/证据.json is a redacted snapshot of the local
append-only ledger; it carries no account identifier and no key.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from 闸 import 过闸

证据路径 = Path(__file__).parent / "递送" / "证据.json"

st.set_page_config(page_title="Reason Before Result", page_icon="🧾", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #07111f; color: #e8eef8; }
    .block-container { max-width: 1120px; padding-top: 2.6rem; padding-bottom: 4rem; }
    h1, h2, h3 { letter-spacing: -0.03em; }
    .lede { padding: .4rem 0 1.4rem; }
    .lede h1 { font-size: clamp(2.1rem, 4.4vw, 3.2rem); line-height: 1.12; margin: 0 0 1rem;
               max-width: 21ch; }
    .lede p { color: #b8c7dc; font-size: 1.12rem; line-height: 1.62; max-width: 62ch; margin: 0; }
    .lede em { color: #e8eef8; font-style: normal; font-weight: 650; }
    .kicker { color: #8fa6c2; font-size: .82rem; letter-spacing: .1em; font-weight: 700;
              text-transform: uppercase; margin: 2.6rem 0 .2rem; }
    .receipt { border: 1px solid #29425f; border-radius: 14px; padding: 1.25rem 1.4rem;
               background: #0b1a2b; margin: .6rem 0 0; }
    .receipt-row { display: flex; flex-wrap: wrap; gap: 1.8rem; margin-bottom: .9rem; }
    .receipt-cell { min-width: 130px; }
    .receipt-k { color: #7f97b5; font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; }
    .receipt-v { font-size: 1.02rem; font-weight: 640; margin-top: .15rem; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9rem;
            color: #cfe0f5; word-break: break-all; }
    .said { border-left: 3px solid #7dd3fc; padding: .1rem 0 .1rem 1rem; margin: .2rem 0 .3rem;
            color: #dbe7f6; font-size: 1.04rem; line-height: 1.6; }
    .said-when { color: #7f97b5; font-size: .8rem; margin-top: .45rem; }
    .verdict { border: 1px solid #29425f; border-radius: 14px; padding: 1.15rem 1.4rem;
               margin: .2rem 0 1rem; }
    .v-ok { border-color: #2bbf88; background: linear-gradient(135deg, #083529, #091827); }
    .v-no { border-color: #fb7185; background: linear-gradient(135deg, #3a1824, #091827); }
    .v-label { font-size: .74rem; letter-spacing: .13em; font-weight: 700; color: #9fb5d2; }
    .v-value { font-size: 1.75rem; font-weight: 750; margin: .2rem 0 .3rem; }
    .v-copy { color: #cfdcec; line-height: 1.55; }
    .rule { border-bottom: 1px solid #1d3149; padding: .7rem 0; }
    .rule-ok { color: #4ade80; font-weight: 700; }
    .rule-no { color: #fb7185; font-weight: 700; }
    .rule-why { color: #a9bcd3; font-size: .9rem; line-height: 1.5; }
    p.note { color: #89a0bc !important; font-size: .88rem !important; line-height: 1.62; }
    .stCheckbox label p, .stSlider label p { font-size: .92rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

证据 = json.loads(证据路径.read_text(encoding="utf-8"))
这一笔 = 证据["这一笔"]
判断书 = 这一笔["判断书"]
钱 = 判断书["钱"]
券商回执 = 这一笔["券商回执"]
原提案 = 这一笔["闸"]["提案"]
基准腿 = 原提案["腿"]
基准今天 = date.fromisoformat(判断书["今天"])
基准到期 = date.fromisoformat(基准腿[0]["到期"])
基准天数 = (基准到期 - 基准今天).days


# ---------------------------------------------------------------- 第一屏

st.markdown(
    """
    <section class="lede">
      <h1>It writes the reason before the order can exist.</h1>
      <p>This agent trades options on an Alpaca <em>paper</em> account. Before it sends
      anything, it writes down what it is doing, what would prove it wrong, and the most
      it can lose. If it cannot prove the loss is capped, it does not order.</p>
    </section>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- 一、真回执

st.markdown("<div class='kicker'>What it actually did</div>", unsafe_allow_html=True)
st.markdown("### One real order, straight off the ledger")

腿英文 = {("sell", "P"): "sell put", ("buy", "P"): "buy put",
        ("sell", "C"): "sell call", ("buy", "C"): "buy call"}
腿摘要 = " · ".join(
    f"{腿英文[(腿['方向'], 腿['类型'])]} {腿['行权价']:g}" for 腿 in 基准腿
)

st.markdown(
    f"""
    <div class="receipt">
      <div class="receipt-row">
        <div class="receipt-cell"><div class="receipt-k">Placed</div>
          <div class="receipt-v">{券商回执['submitted_at'][:10]}</div></div>
        <div class="receipt-cell"><div class="receipt-k">Structure</div>
          <div class="receipt-v">Iron condor · 4 legs</div></div>
        <div class="receipt-cell"><div class="receipt-k">Most it could lose</div>
          <div class="receipt-v">${钱['最大亏损美元']:,.0f}</div></div>
        <div class="receipt-cell"><div class="receipt-k">Credit taken in</div>
          <div class="receipt-v">${钱['净收权美元']:,.0f}</div></div>
        <div class="receipt-cell"><div class="receipt-k">Real money at risk</div>
          <div class="receipt-v">$0 · paper</div></div>
      </div>
      <div class="receipt-k">Alpaca order id</div>
      <div class="mono">{券商回执['order_id']}</div>
      <div class="receipt-k" style="margin-top:.7rem">Legs</div>
      <div class="mono">{腿摘要} &nbsp;·&nbsp; expiring {基准到期:%b %-d}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("**And this is what it wrote down before that order was sent:**")
st.markdown(
    f"""
    <div class="said">“SPY closing below {钱['盈亏平衡下沿']} or above {钱['盈亏平衡上沿']} before expiry
    is what proves me wrong. If it really breaks through, the most this loses is
    ${钱['最大亏损美元']:,.2f} — and that number was fixed before the order existed.”</div>
    <div class="said-when">Appended to the ledger at {这一笔['落纸判断时刻'][11:16]} on
    {这一笔['落纸判断时刻'][:10]}. The gate ran after it. The broker receipt came after that.</div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    "<p class='note'>Paper trading only — no real capital, and not investment advice. "
    "The dedicated paper account ID goes to the judges through the official form, not onto "
    "this page: pull the options activity and P&amp;L from Alpaca yourself rather than "
    "taking any of this on our word.</p>",
    unsafe_allow_html=True,
)

with st.expander("The full written judgment, verbatim from the ledger (Chinese original)"):
    st.caption(
        "The agent is operated in Chinese by a non-programmer, so its judgments are written "
        "in Chinese. This is the untouched record — the numbers above are read out of it."
    )
    st.json(判断书)


# ---------------------------------------------------------------- 二、你来改

st.markdown("<div class='kicker'>Now try to break it</div>", unsafe_allow_html=True)
st.markdown("### Take that same order and make it a bad one")
st.caption(
    "Everything below starts as the real trade above, with its real quotes. Change it and "
    "the production gate — the same 闸.py the live CLI imports — re-decides on every move. "
    "No credentials are read and nothing is sent anywhere."
)

甲, 乙 = st.columns(2, gap="large")
with 甲:
    st.markdown("**The order**")
    留保护腿 = st.checkbox(
        "Keep the two protective long legs", value=True,
        help="Uncheck to sell the two short legs naked, with nothing capping the downside.")
    张数 = st.slider("Contracts", 1, 8, 1)
    天数 = st.slider("Days to expiry", 0, 40, 基准天数)
    死报价 = st.checkbox(
        "Blank out one leg's bid", value=False,
        help="Simulates an illiquid or stale quote the agent cannot price.")
with 乙:
    st.markdown("**The account it would trade in**")
    是模拟盘 = st.checkbox("Paper account", value=True)
    今日已亏 = st.slider("Lost on the account so far today ($)", 0, 5000, 0, step=100)
    已有组数 = st.slider("Positions already open", 0, 5, 0)

权益 = 100_000.0


def 合约代码(到期: date, 类型: str, 行权价: float) -> str:
    return f"SPY{到期:%y%m%d}{类型}{int(round(行权价 * 1000)):08d}"


def 造提案() -> dict:
    """按屏上的旋钮，从真实那笔单改出一个提案。报价用的是账上原样。"""
    到期 = 基准今天 + timedelta(days=天数)
    腿表 = []
    for 序, 原 in enumerate(基准腿):
        if not 留保护腿 and 原["方向"] == "buy":
            continue
        腿 = dict(原)
        腿["到期"] = 到期.isoformat()
        腿["合约"] = 合约代码(到期, 原["类型"], 原["行权价"])
        if 死报价 and 序 == 1:          # 认沽保护腿
            腿["买价"] = None
        腿表.append(腿)
    净价 = round(
        sum((腿["买价"] or 0) + 腿["卖价"] for 腿 in 腿表 if 腿["方向"] == "buy") / 2
        - sum((腿["买价"] or 0) + 腿["卖价"] for 腿 in 腿表 if 腿["方向"] == "sell") / 2,
        2,
    )
    return {"编号": "WHAT-IF", "标的": "SPY", "结构": "铁鹰", "张数": 张数,
            "净价": 净价, "标的现价": 原提案["标的现价"], "腿": 腿表}


提案 = 造提案()
当日盈亏 = -float(今日已亏)
账户 = {"是模拟盘": 是模拟盘, "权益": 权益,
       "当日盈亏": 当日盈亏, "未平仓组数": float(已有组数)}
时钟 = {"今天": 基准今天.isoformat(), "开市中": True}
结果 = 过闸(提案, 账户, 时钟)

放行 = 结果.get("过") is True
最大亏损 = 结果.get("最大亏损")

规则名 = {
    "G1": "Paper account only",
    "G2": "Loss must be capped by the structure",
    "G3": "Per-order ceiling: 2% of equity",
    "G4": "Daily stop: 3% of equity",
    "G5": "Every leg needs a live, tradable quote",
    "G6": "Expiry inside the 1–14 day window",
    "G7": "At most 4 open groups",
}


def 为什么(代码: str, 过: bool) -> str:
    """给这一条规则一句英文。只覆盖屏上旋钮够得着的那几种，其余交回中文原文。"""
    if 代码 == "G1":
        return ("The account is flagged as paper." if 过 else
                "This is not a paper account. The gate only releases orders on paper.")
    if 代码 == "G2":
        if 过:
            return (f"Iron condor verified: the two spreads are 5 wide, so the worst case is "
                    f"${最大亏损:,.0f} and it is known before the order goes out.")
        if not 留保护腿:
            return ("Two short legs with nothing bought against them. Nothing caps the loss, "
                    "so there is no maximum to check the next rules against.")
        return "The structure no longer prices out to a bounded loss."
    if 代码 == "G3":
        if 过:
            return (f"Worst case ${最大亏损:,.0f} on ${权益:,.0f} of equity, inside the "
                    f"${权益 * 0.02:,.0f} per-order ceiling.")
        if 最大亏损 is None:
            return "Cannot be checked: the maximum loss is unknown while G2 is failing."
        return (f"Worst case ${最大亏损:,.0f} is over the ${权益 * 0.02:,.0f} ceiling "
                f"({张数} contracts × ${最大亏损 / max(张数, 1):,.0f}).")
    if 代码 == "G4":
        return ("Nothing near the daily stop." if 过 else
                f"Down ${-当日盈亏:,.0f} today, past the ${权益 * 0.03:,.0f} daily stop. "
                "From here it may only close positions, never open one.")
    if 代码 == "G5":
        return ("Every leg has a two-sided quote tight enough to trade on." if 过 else
                "A leg has no usable bid, so no honest price exists for it. Unknown is "
                "treated as a stop, never as an approval.")
    if 代码 == "G6":
        return (f"Expires in {天数} days, inside the 1–14 day window." if 过 else
                f"Expires in {天数} days, outside the 1–14 day window this agent is allowed "
                "to hold.")
    if 代码 == "G7":
        合计 = 已有组数 + 张数
        组 = "group" if 合计 == 1 else "groups"
        return (f"{已有组数} open plus {张数} new = {合计} {组}, within the cap of 4."
                if 过 else
                f"{已有组数} open plus {张数} new = {合计} {组}, over the cap of 4.")
    return "See the verbatim receipt below."


if 放行:
    st.markdown(
        f"<div class='verdict v-ok'><div class='v-label'>THE GATE'S ANSWER</div>"
        f"<div class='v-value'>This order may be placed</div>"
        f"<div class='v-copy'>All seven checks pass. The worst case is "
        f"${最大亏损:,.0f}, known before anything is sent.</div></div>",
        unsafe_allow_html=True,
    )
else:
    首个 = next((条 for 条 in 结果.get("逐条", []) if not 条.get("过")), None)
    理由 = 为什么(首个.get("规则"), False) if 首个 else "The gate refused."
    st.markdown(
        f"<div class='verdict v-no'><div class='v-label'>THE GATE'S ANSWER</div>"
        f"<div class='v-value'>This order will not be placed</div>"
        f"<div class='v-copy'>{理由}</div></div>",
        unsafe_allow_html=True,
    )

for 条 in 结果.get("逐条", []):
    代码 = 条.get("规则")
    过 = 条.get("过") is True
    st.markdown(
        f"<div class='rule'><span class='{'rule-ok' if 过 else 'rule-no'}'>"
        f"{'PASS' if 过 else 'STOP'}</span> &nbsp; <strong>{代码} · {规则名.get(代码, '')}</strong>"
        f"<br><span class='rule-why'>{为什么(代码, 过)}</span></div>",
        unsafe_allow_html=True,
    )

st.markdown(
    "<p class='note' style='margin-top:1rem'>All seven run every time — there is no "
    "short-circuit that hides a later failure, and every one of them fails closed. "
    "Missing data, a malformed number, an unknown structure, a crash inside the gate: "
    "all of those come out as <strong>stop</strong>, never as approval.</p>",
    unsafe_allow_html=True,
)

with st.expander("The gate's own receipt for what you just built (Chinese, verbatim)"):
    st.caption("This is the untouched engine output the English above is written from.")
    st.write(结果.get("一句话", ""))
    for 条 in 结果.get("逐条", []):
        st.markdown(f"**{条.get('规则')} · {条.get('名')}** — {条.get('说明', '')}")

with st.expander("The proposal the gate is reading"):
    st.dataframe(提案["腿"], use_container_width=True, hide_index=True)

拦过的 = 证据.get("账上留过的拦") or []
if 拦过的:
    with st.expander(f"{len(拦过的)} refusals already written into the real ledger"):
        st.caption(
            "Rehearsed against deliberately bad proposals on the live system. A stop is a "
            "normal outcome with an exit code of zero, and its reason is appended like any "
            "other event."
        )
        for 条 in 拦过的:
            st.markdown(f"`{条['编号']}` — {条['一句话']}")


# ---------------------------------------------------------------- 三、自己跑

st.markdown("<div class='kicker'>Run it against your own paper account</div>",
            unsafe_allow_html=True)
st.markdown("### Three commands")
st.code(
    "python 跑.py 体检        # preflight: MCP server up, paper flag on, account reachable\n"
    "python 闸自检.py         # ten deterministic gate cases, no network\n"
    "python 跑.py 开 --空转    # full path with the order call withheld",
    language="bash",
)
st.markdown(
    "<p class='note'>The order path is MCP-only: <code>手.py</code> keeps a long-lived "
    "session against <code>alpaca-mcp-server</code> over stdio and the sole multi-leg "
    "method delegates to <code>place_option_order</code>. There is no direct-HTTP bypass, "
    "and every MCP request and receipt is appended to the ledger with sensitive parameters "
    "redacted.</p>",
    unsafe_allow_html=True,
)

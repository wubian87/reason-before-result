# Devpost / lablab submission copy

## Project name

Reason Before Result

## Tagline

An Alpaca paper-options agent whose explanation must exist before its order can.

## Long description

Reason Before Result is an autonomous paper-options agent built around a simple
constraint: the reason must be written before the result exists. The agent
reads the market clock, dedicated paper account, SPY price, positions, and
option chain through Alpaca MCP. It selects a small defined-risk structure and
first appends a plain-language judgment containing every leg, maximum gain and
loss, break-evens, invalidation, and intended exit. Only then does a pure
seven-rule gate inspect the proposal. Missing data, malformed values, unknown
structures, stale or unusable quotes, excessive loss, daily drawdown, and
position-cap violations all stop the order by default. A released proposal is
sent through the MCP `place_option_order` tool, and the Alpaca receipt is
appended to the same ledger. There is no direct-HTTP execution bypass.

The public repository includes deterministic tests, a Chinese CLI designed for
an operator who does not write code, a recording-safe MCP trace, and a
credential-free Streamlit demo of the production gate. The official form
supplies the dedicated paper account ID privately, allowing Alpaca to verify
options activity and P&L independently. The goal is not to make a backtest
sound convincing; it is to leave a paper trail in which every order and every
stop has a readable cause.

Paper trading only. No real capital. Not investment advice.

## Technologies

Python · Alpaca Trading API · Alpaca MCP Server · Model Context Protocol ·
Streamlit · ffmpeg

## Required private form field

- Alpaca paper account ID: **take from `.env` / the frozen evidence row at submission time; never paste into this public file**

## Links to fill

- Public GitHub: `[PENDING]`
- Hosted application: `[PENDING]`
- Demo video: `[PENDING]`

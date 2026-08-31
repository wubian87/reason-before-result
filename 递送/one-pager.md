# Reason Before Result — One-Page Technical Brief

## The AI logic

The agent does not begin with an order payload. It reads the Alpaca paper
account, market clock, SPY price, and the relevant option-chain window through
Alpaca MCP. A pure selector looks for a small, defined-risk premium-selling
structure whose quotes and distance satisfy explicit criteria. It then emits a
plain-language judgment: what it proposes, why, all legs, maximum gain and
loss, break-evens, what would prove the judgment wrong, and how the position is
meant to exit. That judgment is appended before any gate or order action.

## The risk gate

The proposal must pass seven independent rules: paper account, defined risk,
2% per-trade maximum loss, 3% daily stop, usable quotes, bounded expiration,
and position-count cap. All rules run and produce receipts; there is no
short-circuit that hides later failures. Unknown structures, missing quotes,
bad types, parser failures, and internal exceptions fail closed. A stopped
proposal is a normal outcome and its reason remains in the ledger.

## How Alpaca is connected

The execution hand is an MCP client, not a direct HTTP wrapper. It launches the
official `alpaca-mcp-server` over stdio and uses MCP tools for account state,
market clock, positions, stock trades, option chains, orders, and multi-leg
option execution. Every MCP request and receipt is written to the append-only
ledger with suspicious parameters redacted. The multi-leg execution method
delegates to `place_option_order`; there is no alternate order path.

## What makes the result independently verifiable

The official submission gives judges the dedicated Alpaca paper account ID so
they can pull options activity and P&L themselves. The public repository shows
the full MCP path, the pure gate, deterministic tests, and a credential-free
hosted demo. The demo video shows the written judgment appearing first, every
gate receipt, the recording-safe MCP tool trace, and the Alpaca paper receipt.

**Boundary:** paper trading only; no real capital; not investment advice.

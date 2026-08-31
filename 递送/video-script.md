# Demo video script — target 3:30–4:15, hard limit 5:00

## 0:00–0:15 · Cold open: the receipt, not the pitch

**Picture:** the redacted paper-account screen from `python 跑.py 看`, then a
fast cut to an order line and its prior judgment number.

**Narration:** “This is a paper account. These are options. Every order has a
maximum loss before it exists—and when the agent cannot prove that number, it
stops.”

On-screen words: `PAPER · OPTIONS · LOSS IS CAPPED BEFORE ORDER`

## 0:15–0:40 · What it is

**Picture:** one flat sequence: market data → written judgment → seven receipts
→ Alpaca MCP → append-only receipt.

**Narration:** “Reason Before Result is an autonomous Alpaca paper-options
agent. The unusual part is not the strategy. The explanation is written before
the gate and before the order, so a later outcome cannot invent its reason.”

## 0:40–2:35 · One uncut run

**Picture:** recording-safe terminal command:

```bash
ALPACA_MCP_TRACE=true .venv/bin/python 跑.py 开
```

The terminal must visibly show only tool names/timing, the written judgment,
all rule receipts, and the paper order receipt. Crop or redact the full account
ID if any external tool ever emits it.

**Sparse narration:**

- “Clock, account, positions, price, and option chain all arrive through MCP.”
- “The judgment is appended here—before the gate runs.”
- “Every rule leaves a receipt. Unknown is a stop, never an approval.”
- “Only after release does the MCP tool `place_option_order` appear.”

If the selector decides not to open, keep that run as truthful evidence and
record another trading window; never force parameters merely to manufacture a
video.

## 2:35–3:10 · Break it on purpose

**Picture:** public Streamlit demo. Select “Naked short put” and “Missing
quote”; show that both resolve to HELD with different rule receipts.

**Narration:** “A stop is not an exception. Here is a naked option, and here is
a protected spread with one missing quote. The code runs all seven rules and
records why neither may become an order.”

## 3:10–3:40 · Independent verification

**Picture:** repository map, then redacted account/activity screen.

**Narration:** “The repository contains the full MCP path, the deterministic
gate tests, and the read-only demo. The dedicated paper account ID is supplied
privately in the official form, so Alpaca can pull the activity and P&L without
trusting our screenshots.”

## 3:40–4:00 · Close

**Picture:** final card with repository, hosted demo, and the sequence.

**Narration:** “A winning trade can still have a bad reason. A stopped trade can
prove that the agent worked. Reason Before Result makes both visible.”

Footer: `Paper trading only · No real capital · Not investment advice`

## Recording gates

1. Total duration ≤ 5:00.
2. First 15 seconds visibly communicate paper, options, and loss-stop.
3. At least one uncut run visibly names MCP tools.
4. No keys, full account ID, participant profile, or raw server stderr.
5. No claim of a fill unless the Alpaca account shows it.
6. Owner performs the 15-second non-expert test; AI does not substitute for it.

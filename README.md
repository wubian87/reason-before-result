# Reason Before Result

An autonomous Alpaca paper-options agent that writes its reason **before** an
order can exist. A deterministic, fail-closed gate then decides whether the
proposal may reach Alpaca through MCP. Every decision, stop, MCP call, and
receipt is appended to a local ledger.

> Paper trading only. No real capital. This project is not investment advice.

## What judges can verify

- A dedicated Alpaca paper account, supplied privately in the official form.
- Options activity and P&L pulled by Alpaca from that account.
- A real MCP path: the program launches `alpaca-mcp-server` over stdio and uses
  its account, market-data, options-data, and trading tools.
- An append-only sequence: written judgment → gate receipt → order request →
  Alpaca receipt.
- A public, credential-free demo of the same pure gate in `app.py`.

## The complete path

```text
Alpaca clock/account/quotes/option chain (MCP)
                      ↓
              pick one proposal
                      ↓
        append the human-readable judgment
                      ↓
       run all seven rules without short-circuiting
              ↙ stop          release ↘
      append the reason      place_option_order (MCP)
                                      ↓
                              append Alpaca receipt
```

The order path never calls Alpaca HTTP directly. `手.py` owns a long-lived MCP
session; its `调()` method records a redacted request and receipt around every
tool call. The only method that places a multi-leg options order delegates to
the MCP tool `place_option_order`.

## Why the gate stops by default

All seven rules run and leave individual receipts:

1. paper account only;
2. risk must be structurally defined;
3. maximum loss ≤ 2% of equity;
4. stop opening after a 3% daily loss;
5. every leg must have a live, usable quote;
6. expiration must be inside the allowed window;
7. open-position count must remain within the cap.

Missing data, malformed types, unknown structures, parser errors, and internal
exceptions resolve to **STOP**, not approval.

## Run it

Requires Python 3.11+, `uvx`, and Alpaca paper credentials.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill only ALPACA_API_KEY and ALPACA_SECRET_KEY. Keep PAPER=true.

python 跑.py 体检
python 闸自检.py
python 跑.py 演闸
python 跑.py 开 --空转
```

When the market is open, `python 跑.py 开` may send a **paper** order only after
the written judgment and all seven rule receipts have already been appended.

For a recording-safe proof that MCP is in the loop, enable the optional trace.
It prints only MCP tool names, success state, and elapsed time—never parameters,
keys, account IDs, or response bodies.

```bash
ALPACA_MCP_TRACE=true python 跑.py 体检
```

## Read-only hosted demo

```bash
streamlit run app.py
```

The public app needs no secrets and cannot trade. It applies the production
pure gate to visible sample proposals so every pass or stop can be inspected.

## Repository map

| File | Role |
|---|---|
| `跑.py` | Chinese CLI: preflight, status, gate rehearsal, open, close, recap |
| `判.py` | Pure option-chain selection and written judgment |
| `闸.py` | Pure seven-rule fail-closed gate |
| `手.py` | MCP-only Alpaca client and redacted MCP ledger |
| `账.py` | Append-only JSONL ledger and Chinese human rendering |
| `闸自检.py` | Ten deterministic gate cases |
| `手自检.py` | Ledger/client static and persistence checks |
| `app.py` | Credential-free, read-only Streamlit demonstration |

Runtime ledgers, logs, account identifiers, participant data, credentials, and
the local virtual environment are excluded from Git.

## Safety boundary

`手.py` refuses to start unless `ALPACA_PAPER_TRADE` is explicitly true. Secrets
are passed only to the MCP child process, suspicious parameter names are
redacted before ledger writes, and raw MCP server stderr goes to a gitignored
local log rather than the terminal or recording.

## License

MIT. See `LICENSE`.

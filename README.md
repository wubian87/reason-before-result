# Reason Before Result

An autonomous Alpaca paper-options agent that writes its reason **before** an
order can exist. A deterministic, fail-closed gate then decides whether the
proposal may reach Alpaca through MCP. Every decision, stop, MCP call, and
receipt is appended to a local ledger.

> Paper trading only. No real capital. This project is not investment advice.

**[Two-minute demo video](https://youtu.be/6-u2ReXTkh4)** · **[Live demo](https://reason-before-result-llurb8m9jg7ryfpv598vhr.streamlit.app/)** · **[One-page technical brief](delivery/one-pager.pdf)**

## What judges can verify

- A dedicated Alpaca paper account, supplied privately in the official form.
- Options activity and P&L pulled by Alpaca from that account.
- A real MCP path: the program launches `alpaca-mcp-server` over stdio and uses
  its account, market-data, options-data, and trading tools.
- An append-only sequence: written judgment → gate receipt → order request →
  Alpaca receipt.
- A public, credential-free page (`app.py`) that shows one of those orders off
  the ledger — the written judgment, the gate receipt, and the Alpaca order id —
  and lets anyone bend that same trade until the production gate refuses it.

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

The order path never calls Alpaca HTTP directly. `broker.py` owns a long-lived MCP
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

python agent.py preflight
python gate_selftest.py
python agent.py rehearse
python agent.py open --dry-run
```

When the market is open, `python agent.py open` may send a **paper** order only after
the written judgment and all seven rule receipts have already been appended.

### Running it unattended

`一轮.sh` is one round — close, open at most once a day, recap — and it is what a
`systemd` user timer fires every 30 minutes:

```ini
# ~/.config/systemd/user/alpaca-agent.timer
[Timer]
OnCalendar=*-*-* *:00,30:00
```

The script gates itself twice, and both gates come from something that actually went
wrong. It does nothing outside 09:35-15:55 US Eastern on a weekday, because closing a
position while the market is shut returns `422 options market orders are only allowed
during market hours` — noise, not signal. And it opens at most one round per US trading
day, marked by a dated file, so a restarted timer cannot stack positions; the count
itself is still the gate's job, not the script's.

For a recording-safe proof that MCP is in the loop, enable the optional trace.
It prints only MCP tool names, success state, and elapsed time—never parameters,
keys, account IDs, or response bodies.

```bash
ALPACA_MCP_TRACE=true python agent.py preflight
```

## Read-only hosted demo

Open the live demo: <https://reason-before-result-llurb8m9jg7ryfpv598vhr.streamlit.app/>

```bash
streamlit run app.py
```

The public app needs no secrets and cannot trade. It opens on a real order this
agent placed — order id, capped loss, and the sentence it wrote down *before*
sending — read out of `delivery/evidence.json`, a redacted snapshot of the append-only
ledger that carries no account identifier and no key. Below it, the same trade
is wired to the production gate: drop the protective legs, raise the size, push
the expiry out, blank a quote, and `gate.py` re-decides live. At its default
settings the page reproduces the ledger's own receipt word for word.

Refreeze the snapshot from the local ledger with:

```bash
python delivery/freeze_evidence.py
```

## Repository map

| File | Role |
|---|---|
| `agent.py` | CLI: `preflight` · `status` · `rehearse` · `open` · `close` · `recap` |
| `strategy.py` | Pure option-chain selection and the written judgment |
| `gate.py` | Pure seven-rule fail-closed gate |
| `broker.py` | MCP-only Alpaca client, with every call redacted into the ledger |
| `ledger.py` | Append-only JSONL ledger and its human-readable rendering |
| `gate_selftest.py` | Ten deterministic gate cases |
| `broker_selftest.py` | Ledger and client static / persistence checks |
| `app.py` | Credential-free public page: one real receipt, plus a live gate to push on |
| `一轮.sh` | One scheduled round: close, open once a day, recap — self-gated to US market hours |
| `delivery/freeze_evidence.py` | Freezes a redacted evidence snapshot out of the ledger into `delivery/evidence.json` |

Runtime ledgers, logs, account identifiers, participant data, credentials, and
the local virtual environment are excluded from Git.

## Safety boundary

`broker.py` refuses to start unless `ALPACA_PAPER_TRADE` is explicitly true. Secrets
are passed only to the MCP child process, suspicious parameter names are
redacted before ledger writes, and raw MCP server stderr goes to a gitignored
local log rather than the terminal or recording.

## License

MIT. See `LICENSE`.

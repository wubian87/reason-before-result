#!/usr/bin/env python3
"""读 paper 账户。没有密钥或不是 paper 就停，不下单。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

key = os.environ.get("ALPACA_API_KEY", "").strip()
secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
paper = os.environ.get("ALPACA_PAPER_TRADE", "true").strip().lower()

if not key or not secret:
    print("停：把 Paper API Key / Secret 放进 .env（抄 .env.example）。不下单。")
    sys.exit(2)
if paper not in ("true", "1", "yes"):
    print("停：本场只许 paper。ALPACA_PAPER_TRADE 必须是 true。")
    sys.exit(2)

try:
    from alpaca.trading.client import TradingClient
except ImportError:
    print("停：先 pip install alpaca-py")
    sys.exit(2)

client = TradingClient(key, secret, paper=True)
acct = client.get_account()
equity = float(acct.equity)
print(f"status={acct.status}")
print(f"account_number={acct.account_number}")
print(f"equity={equity}")
print(f"cash={acct.cash}")
print(f"pattern_day_trader={acct.pattern_day_trader}")
if abs(equity - 100_000) > 500 and abs(equity - 100_000) / 100_000 > 0.02:
    print("注意：权益不在 100000 附近。官方要求本场起始 100000。核后台是否新开了专用 paper 户。")
else:
    print("冒烟绿：paper 账户读到了。")

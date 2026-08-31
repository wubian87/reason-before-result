# Social drafts — owner posts, AI does not publish

Every post must retain both tags: **@lablabai @AlpacaHQ**.

## 1 · First accepted / filled paper order

The first artifact from our trading agent is not a chart. It is a sequence:
written judgment → seven rule receipts → Alpaca MCP order → paper-account
receipt. If the data is incomplete, there is no order to explain away later.
[Add one redacted screenshot after the first accepted/filled order.]
@lablabai @AlpacaHQ

## 2 · The failure that looked normal

Our MCP response arrived inside two nested envelopes. Before we handled both,
an existing position could look exactly like an empty position list—no crash,
just a believable zero. That is more dangerous than a loud failure. We fixed
the parser and added a regression test before letting the agent trade again.
@lablabai @AlpacaHQ

## 3 · Why the reason comes first

An order receipt can prove that code ran, but not why the trade existed. Our
agent writes the legs, maximum loss, break-evens, invalidation, and exit plan to
an append-only ledger before the gate or Alpaca order call. The later result
cannot rewrite its own origin story. @lablabai @AlpacaHQ

## 4 · What the public demo can and cannot do

We shipped a credential-free Streamlit demo that runs the same pure gate as the
paper-trading CLI. It can expose every pass and stop, but it cannot read an
account or place a trade. Judges get the real paper account ID privately and
can verify activity with Alpaca directly. @lablabai @AlpacaHQ

## 5 · Submission close

Reason Before Result is submitted: a paper-options agent using Alpaca MCP,
defined-risk structures, a fail-closed execution boundary, and an append-only
ledger. The most useful output is not the P&L number—it is being able to point
to every order and every stopped proposal and explain its cause. [Add GitHub,
demo, and video links.] @lablabai @AlpacaHQ

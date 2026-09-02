#!/bin/bash
# 交易日的一轮：平 → 开（每天只开一次）→ 复盘。
# ⛔ 只在美东盘中动手：休市时 close 会被 Alpaca 顶回 422，那是噪声不是信号。
# ⛔ 全程模拟盘。闸拦下也算跑完。
# ⚠️ 变量名一律 ASCII —— bash 不认非 ASCII 变量名（2026-09-03 踩过）。
set -uo pipefail
cd /home/xin/AI项目/种子园/黑客松-alpaca
PY=.venv/bin/python
LOG=日志/定时.log
mkdir -p 日志 .tmp
say() { printf '[%s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

et() { TZ=America/New_York date "+$1"; }
DOW=$(et %u); HHMM=$(et %H%M); TODAY=$(et %F)

# —— 闸一：美东周一至周五 09:35–15:55 之外，⛔ 什么都不做 ——
if [ "$DOW" -gt 5 ] || [ "$HHMM" -lt 935 ] || [ "$HHMM" -gt 1555 ]; then
  say "休市（美东 周$DOW $HHMM），跳过"
  exit 0
fi

say "=== 一轮开始（美东 $TODAY 周$DOW $HHMM）==="

say "— 平仓检查 —"
timeout 600 "$PY" agent.py close >> "$LOG" 2>&1 || say "close 非零，继续"

# —— 闸二：一天只开一次。仓位上限归 G7 管，这里只防同一天反复开 ——
MARK=".tmp/opened-$TODAY"
if [ -e "$MARK" ]; then
  say "— 今天（美东 $TODAY）已开过一轮，⛔ 不再开 —"
else
  say "— 开仓 —"
  timeout 900 "$PY" agent.py open >> "$LOG" 2>&1
  RC=$?
  say "open 退出码 $RC"
  [ "$RC" -eq 0 ] && touch "$MARK"
fi

say "— 复盘 —"
timeout 600 "$PY" agent.py recap >> "$LOG" 2>&1 || say "recap 非零"

say "=== 一轮结束 ==="

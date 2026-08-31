#!/bin/bash
# 无人值守录制：虚拟屏 + 真终端 + ffmpeg。参数与回执由被录命令自己控制。
set -euo pipefail
OUT="${1:?输出名}"; shift
CMD="$*"
D=:78; W=1920; H=1080
HERE="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  [ -n "${FF:-}" ] && kill -INT "$FF" 2>/dev/null || true
  [ -n "${XVFB:-}" ] && kill "$XVFB" 2>/dev/null || true
  [ -n "${STATUS:-}" ] && [ -e "$STATUS" ] && unlink "$STATUS" 2>/dev/null || true
}
trap cleanup EXIT

pkill -f "Xvfb $D" 2>/dev/null || true
Xvfb "$D" -screen 0 ${W}x${H}x24 -nolisten tcp >/dev/null 2>&1 &
XVFB=$!
sleep 2

# 先起录像，再让终端出现。否则快命令可能在 ffmpeg 开始前已经打完第一屏，
# 而「一镜未剪的 MCP 真跑」会从证据开头少一截。
ffmpeg -hide_banner -loglevel error -f x11grab -draw_mouse 0 \
  -framerate 15 -video_size ${W}x${H} -i "$D" \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -y "$HERE/$OUT.mp4" &
FF=$!
sleep 1

STATUS=$(mktemp "$HERE/.recorder-status.XXXXXX")
DISPLAY=$D xterm -geometry 176x44+0+0 \
  -fa 'DejaVu Sans Mono' -fs 15 \
  -bg '#0d1117' -fg '#d6dde6' -cr '#58a6ff' \
  +sb -bc \
  -xrm 'XTerm*colorBDMode: true' \
  -e bash -lc 'printf "PAPER ONLY | ONE UNCUT MCP RUN | SAFE TRACE\n\n"; sleep 1; bash -lc "$1"; rc=$?; printf "\n── run complete (rc=%s) ──\n" "$rc"; printf "%s\n" "$rc" > "$2"; sleep 5' \
  recorder "$CMD" "$STATUS" >/dev/null 2>&1 &
XT=$!

# 被录命令写下退出码后，xterm 还会在完成画面停 5 秒。
# 在它消失前关录像，否则末帧会变黑，合成时 tpad 就会把黑屏冻住。
while [ ! -s "$STATUS" ] && kill -0 "$XT" 2>/dev/null; do
  sleep 0.1
done
RUN_RC=$(tr -cd '0-9' < "$STATUS")
[ -n "$RUN_RC" ] || RUN_RC=125
sleep 3
kill -INT "$FF" 2>/dev/null || true
wait "$FF" 2>/dev/null || true
FF=""
wait "$XT" 2>/dev/null || true
unlink "$STATUS"
STATUS=""
kill "$XVFB" 2>/dev/null || true
XVFB=""

dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$HERE/$OUT.mp4")
if [ "$RUN_RC" -eq 0 ]; then
  echo "✅ $OUT.mp4  ${dur}s  $(du -h "$HERE/$OUT.mp4" | cut -f1)"
else
  echo "⛔ $OUT.mp4 已保留，但被录命令退出码是 $RUN_RC"
  exit "$RUN_RC"
fi

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

DISPLAY=$D xterm -geometry 176x52+0+0 \
  -fa 'DejaVu Sans Mono' -fs 15 \
  -bg '#0d1117' -fg '#d6dde6' -cr '#58a6ff' \
  +sb -bc \
  -xrm 'XTerm*colorBDMode: true' \
  -e bash -lc "$CMD; echo; echo '── run complete ──'; sleep 5" >/dev/null 2>&1 &
XT=$!

wait "$XT" 2>/dev/null || true
sleep 1
kill -INT "$FF" 2>/dev/null || true
wait "$FF" 2>/dev/null || true
FF=""
kill "$XVFB" 2>/dev/null || true
XVFB=""

dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$HERE/$OUT.mp4")
echo "✅ $OUT.mp4  ${dur}s  $(du -h "$HERE/$OUT.mp4" | cut -f1)"

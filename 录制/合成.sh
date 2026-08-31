#!/bin/bash
# 以八段旁白为时间源合成。默认用休市空转做试片；正式成交后把第二参数换成成交录像。
set -euo pipefail
cd "$(dirname "$0")"

OUT="${1:-试片.mp4}"
TERMINAL="${2:-素材-空转.mp4}"
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
mkdir -p 片段

duration() {
  ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"
}

caption_filter() {
  local caption="$1"
  printf "drawtext=fontfile=%s:textfile=%s:fontcolor=white:fontsize=42:box=1:boxcolor=black@0.78:boxborderw=18:x=(w-text_w)/2:y=h-108" "$FONT" "$caption"
}

still_segment() {
  local image="$1" audio="$2" caption="$3" out="$4"
  local dur
  dur=$(python3 -c "print(float('$({ duration "$audio"; })') + 0.8)")
  ffmpeg -hide_banner -loglevel error -y \
    -loop 1 -framerate 15 -i "$image" -i "$audio" -t "$dur" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0d1117,$(caption_filter "$caption")" \
    -map 0:v -map 1:a -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -r 15 \
    -c:a aac -b:a 192k -shortest "$out"
}

terminal_segment() {
  local start="$1" audio="$2" caption="$3" out="$4"
  local dur
  dur=$(python3 -c "print(float('$({ duration "$audio"; })') + 0.8)")
  ffmpeg -hide_banner -loglevel error -y \
    -ss "$start" -i "$TERMINAL" -i "$audio" -t "$dur" \
    -vf "scale=1920:1080,tpad=stop_mode=clone:stop_duration=60,$(caption_filter "$caption")" \
    -map 0:v -map 1:a -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -r 15 \
    -c:a aac -b:a 192k -shortest "$out"
}

still_segment 卡-第一屏.png 旁白-01-open.wav 字幕-01.txt 片段/01.mp4
still_segment 卡-流程.png 旁白-02-what.wav 字幕-02.txt 片段/02.mp4
terminal_segment 0 旁白-03-mcp.wav 字幕-03.txt 片段/03.mp4
terminal_segment 7 旁白-04-judgment.wav 字幕-04.txt 片段/04.mp4
still_segment demo-held.png 旁白-05-gate.wav 字幕-05.txt 片段/05.mp4
terminal_segment 10 旁白-06-order.wav 字幕-06.txt 片段/06.mp4
still_segment 卡-MCP.png 旁白-07-verify.wav 字幕-07.txt 片段/07.mp4
still_segment 卡-收口.png 旁白-08-close.wav 字幕-08.txt 片段/08.mp4

: > 片段/concat.txt
for n in 01 02 03 04 05 06 07 08; do
  printf "file '%s.mp4'\n" "$n" >> 片段/concat.txt
done

ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i 片段/concat.txt -c copy "$OUT"
echo "✅ $OUT  $(duration "$OUT")s  $(du -h "$OUT" | cut -f1)"

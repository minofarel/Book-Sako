#!/bin/bash
# Usage: bash scripts_build.sh <fmt> <out.mp4>
# Renders sequence-aligned chunks (crf18 master), then concats + re-encodes to a
# shareable crf23 deliverable muxed with the synthesized soundtrack.
set -e
FMT=$1
OUT=$2
CH="$PWD/build/chunks"
mkdir -p "$CH" out
echo "=== Rendering $FMT chunks ==="
python3 src/render.py $FMT 0   270 "$CH/${FMT}_c0.mp4"
python3 src/render.py $FMT 270 570 "$CH/${FMT}_c1.mp4"
python3 src/render.py $FMT 570 870 "$CH/${FMT}_c2.mp4"
printf "file '%s'\n" "$CH/${FMT}_c0.mp4" "$CH/${FMT}_c1.mp4" "$CH/${FMT}_c2.mp4" > "$CH/${FMT}_list.txt"
echo "=== Concat + encode + mux ==="
ffmpeg -y -f concat -safe 0 -i "$CH/${FMT}_list.txt" -i out/sako_music.wav \
  -c:v libx264 -preset medium -crf 25 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest "$OUT" 2>/dev/null
echo "=== Done: $OUT ($(du -h "$OUT" | cut -f1)) ==="
ffprobe -v error -show_entries format=duration -show_entries stream=codec_type,codec_name,width,height -of default=noprint_wrappers=1 "$OUT"

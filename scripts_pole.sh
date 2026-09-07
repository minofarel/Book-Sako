#!/bin/bash
set -e
CH="$PWD/build/chunks"
mkdir -p "$CH" out
python3 src/pole.py 0   330 "$CH/pole_c0.mp4"
python3 src/pole.py 330 660 "$CH/pole_c1.mp4"
printf "file '%s'\n" "$CH/pole_c0.mp4" "$CH/pole_c1.mp4" > "$CH/pole_list.txt"
ffmpeg -y -f concat -safe 0 -i "$CH/pole_list.txt" -i out/sako_pole_music.wav \
  -c:v libx264 -preset medium -crf 25 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest out/sako_teaser_pole_1x1.mp4 2>/dev/null
echo "DONE $(du -h out/sako_teaser_pole_1x1.mp4|cut -f1)"

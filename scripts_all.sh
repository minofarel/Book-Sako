#!/bin/bash
set -e
bash scripts_build.sh 9x16 out/sako_teaser_9x16.mp4
bash scripts_build.sh 16x9 out/sako_teaser_16x9.mp4
bash scripts_pole.sh
echo "ALL DONE"

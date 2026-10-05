#!/bin/bash
# Prints the images to index as "IMAGE|COMMAND", without comments: images.txt,
# then the generated lists in lists/ (the most pulled images, the official
# images), each image once, the first mention winning. With SHARD and SHARDS,
# prints only every SHARDS-th image, starting at SHARD, so the workflow can
# split the list across runners.
set -euo pipefail
shard=${1:-0}; shards=${2:-1}
here=$(dirname "$0")
shopt -s nullglob
cat "$here/images.txt" "$here"/lists/*.txt | sed 's/#.*//' | awk -F'|' -v k="$shard" -v n="$shards" '
  { gsub(/^[ \t]+|[ \t]+$/, "", $1); gsub(/^[ \t]+|[ \t]+$/, "", $2) }
  $1 != "" && !seen[$1]++ { if (i++ % n == k) print $1 "|" $2 }'

#!/bin/bash
# Prints the lines of images.txt as "IMAGE|COMMAND", without comments. With
# SHARD and SHARDS, prints only every SHARDS-th image, starting at SHARD, so
# the workflow can split the list across runners.
set -euo pipefail
shard=${1:-0}; shards=${2:-1}
sed 's/#.*//' "$(dirname "$0")/images.txt" | awk -F'|' -v k="$shard" -v n="$shards" '
  { gsub(/^[ \t]+|[ \t]+$/, "", $1); gsub(/^[ \t]+|[ \t]+$/, "", $2) }
  $1 != "" { if (i++ % n == k) print $1 "|" $2 }'

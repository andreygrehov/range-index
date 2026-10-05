#!/bin/bash
# Uploads every index under DIR to the release named by its shard: the first
# two hex digits of the layer digest. A release holds at most 1000 assets,
# and 256 shards keep each one far below that.
set -euo pipefail
dir=${1:?usage: publish.sh DIR}
shopt -s nullglob
count=0
for shard_dir in "$dir"/*/; do
  shard=$(basename "$shard_dir")
  files=("$shard_dir"*.idx)
  [ ${#files[@]} -gt 0 ] || continue
  if ! gh release view "$shard" >/dev/null 2>&1; then
    gh release create "$shard" --title "sha256:$shard" \
      --notes "Range layer indexes for layer digests starting with sha256:$shard."
  fi
  gh release upload "$shard" "${files[@]}" --clobber
  count=$((count + ${#files[@]}))
done
echo "published $count index(es)"

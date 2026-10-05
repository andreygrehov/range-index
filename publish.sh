#!/bin/bash
# Uploads every index and profile under DIR to the release named by its shard:
# the first two hex digits of the digest it is named by. A release holds at
# most 1000 assets, and 256 shards keep each one far below that. Runners
# publish at the same time, so a failed upload is retried, then left for the
# next day's run.
set -uo pipefail
dir=${1:?usage: publish.sh DIR}
shopt -s nullglob
count=0; failed=0
for shard_dir in "$dir"/*/; do
  shard=$(basename "$shard_dir")
  files=("$shard_dir"*.idx "$shard_dir"*.profile.json)
  [ ${#files[@]} -gt 0 ] || continue
  if ! gh release view "$shard" >/dev/null 2>&1; then
    gh release create "$shard" --title "sha256:$shard" \
      --notes "Range layer indexes and startup profiles for digests starting with sha256:$shard." 2>/dev/null ||
      gh release view "$shard" >/dev/null
  fi
  for attempt in 1 2 3 4 5; do
    if gh release upload "$shard" "${files[@]}" --clobber; then
      count=$((count + ${#files[@]})); break
    fi
    if [ $attempt = 5 ]; then
      failed=$((failed + ${#files[@]})); echo "::warning::could not publish shard $shard"
    else
      sleep $((attempt * 30))
    fi
  done
done
echo "published $count file(s), $failed left for the next run"

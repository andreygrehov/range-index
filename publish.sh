#!/bin/bash
# Uploads every index and profile under DIR that the catalog does not hold yet
# to the release named by its shard: the first two hex digits of the digest it
# is named by. A release holds at most 1000 assets, and 256 shards keep each
# one far below that.
#
# The workflow's token may make 1000 API requests an hour, so this checks
# for a file through its download URL, which is not an API request, and
# stops before the job's time runs out. It also stops from 9:00 to 18:00 New
# York time on weekdays. What it leaves, the next run publishes.
set -uo pipefail
dir=${1:?usage: publish.sh DIR [MINUTES]}
deadline=$(( $(date +%s) + ${2:-300} * 60 ))
catalog=https://github.com/andreygrehov/range-index/releases/download
shopt -s nullglob
missing() {
  local f=$1 shard; shard=$(basename "$(dirname "$f")")
  curl -sfIL -o /dev/null "$catalog/$shard/$(basename "$f")" || echo "$f"
}
export -f missing; export catalog
mapfile -t todo < <(find "$dir" -name '*.idx' -o -name '*.profile.json' | sort | xargs -P 16 -I{} bash -c 'missing "$@"' _ {} | sort)
echo "${#todo[@]} file(s) not in the catalog yet"
releases=$(gh release list --limit 1000 --json tagName --jq '.[].tagName')
# Weekdays, 9:00 to 17:59 in New York.
office_hours() {
  local day hour
  read -r day hour < <(TZ=America/New_York date '+%u %H')
  [ "$day" -le 5 ] && [ "$((10#$hour))" -ge 9 ] && [ "$((10#$hour))" -lt 18 ]
}
count=0; left=0
upload() {
  local shard=$1; shift
  [ $# -gt 0 ] || return 0
  if [ "$(date +%s)" -ge "$deadline" ] || office_hours; then left=$((left + $#)); return; fi
  if ! grep -qx "$shard" <<<"$releases"; then
    gh release create "$shard" --title "sha256:$shard" \
      --notes "Range layer indexes and startup profiles for digests starting with sha256:$shard." >/dev/null
  fi
  for attempt in 1 2 3; do
    if gh release upload "$shard" "$@" --clobber; then
      count=$((count + $#)); return
    fi
    # A rate limit lifts within the hour.
    if [ $attempt = 3 ]; then left=$((left + $#)); echo "::warning::could not publish shard $shard"; else sleep 600; fi
  done
}
# todo is sorted, so each shard's files are next to each other.
current=""; files=()
for f in "${todo[@]}"; do
  shard=${f%/*}; shard=${shard##*/}
  if [ "$shard" != "$current" ]; then upload "$current" "${files[@]}"; current=$shard; files=(); fi
  files+=("$f")
done
upload "$current" "${files[@]}"
echo "published $count file(s), $left left for the next run"

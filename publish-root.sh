#!/bin/bash
# Publishes the command map's root, DIR/commands/commands.json, as the asset
# commands.json of the release "commands". The root names every shard of one
# version of the map, so it goes last, and only once each shard it names is
# in the catalog: a client never sees a root whose shards are missing. Like
# publish.sh, it does nothing from 9:00 to 18:00 New York time on weekdays.
set -euo pipefail
dir=${1:?usage: publish-root.sh DIR}
root=$dir/commands/commands.json
catalog=https://github.com/andreygrehov/range-index/releases/download
read -r day hour < <(TZ=America/New_York date '+%u %H')
if [ "$day" -le 5 ] && [ "$((10#$hour))" -ge 9 ] && [ "$((10#$hour))" -lt 18 ]; then
  echo "office hours in New York: the root waits for the next run"
  exit 0
fi
missing=0
while read -r digest; do
  hex=${digest#sha256:}
  if ! curl -sfIL -o /dev/null "$catalog/${hex:0:2}/sha256-$hex.commands.json.gz"; then
    echo "not in the catalog yet: $digest"
    missing=$((missing + 1))
  fi
done < <(jq -r '.shards[]' "$root")
if [ "$missing" -gt 0 ]; then
  echo "::warning::$missing shard(s) are not published: the root waits for the next run"
  exit 0
fi
if ! gh release view commands >/dev/null 2>&1; then
  gh release create commands --title "Command map" \
    --notes "The root of Range's command map: which image holds each command. Its shards are in the sha256 releases." >/dev/null
fi
gh release upload commands "$root" --clobber
echo "published the root: $(jq -r '.shards | length' "$root") shards, built $(jq -r .built "$root")"

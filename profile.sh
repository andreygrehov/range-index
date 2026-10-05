#!/bin/bash
# Runs each image of one shard of images.txt once with Range, records which
# blocks its startup needs, and writes that profile into DIR for the catalog.
# An image whose profile the catalog already holds is skipped, and so is one
# that does not start (no shell, no linux build for this runner).
set -uo pipefail
dir=${1:?usage: profile.sh DIR [SHARD SHARDS]}
shard=${2:-0}; shards=${3:-1}
export RANGE_CACHE_DIR=${RANGE_CACHE_DIR:-$HOME/range-cache}
catalog=https://github.com/andreygrehov/range-index/releases/download
shell_start='command -v bash >/dev/null && exec bash -c true; true'
err=${RUNNER_TEMP:-/tmp}/profile-err.txt
ok=0; have=0; failed=0
while IFS='|' read -r image cmd; do
  [ -n "$cmd" ] || cmd=$shell_start
  # The profile is named by the platform manifest's digest, which inspect
  # prints as the image's ETag.
  etag=$(./range inspect "$image" </dev/null 2>"$err" | awk '/^ETag:/ {print $2}')
  hex=${etag#range-oci-1:sha256:}
  if [ ${#hex} -ne 64 ]; then
    failed=$((failed + 1)); echo "skipped $image: $(tail -1 "$err")"; continue
  fi
  if curl -sfIL -o /dev/null </dev/null "$catalog/${hex:0:2}/range-oci-1-sha256-$hex.profile.json"; then
    have=$((have + 1)); continue
  fi
  if timeout 300 sudo -E ./range run --profile record "$image" -- sh -c "$cmd" </dev/null >/dev/null 2>"$err" &&
     sudo -E ./range profile export "$image" --catalog "$dir" >/dev/null 2>>"$err"; then
    ok=$((ok + 1)); echo "profiled $image"
  else
    failed=$((failed + 1)); echo "skipped $image: $(tail -1 "$err")"
  fi
  # Keep the runner's disk for the images still to come.
  sudo rm -rf "$RANGE_CACHE_DIR"
done < <(./images.sh "$shard" "$shards")
sudo chown -R "$(id -u)" "$dir" 2>/dev/null || true
echo "profiled $ok image(s), $have already in the catalog, skipped $failed"

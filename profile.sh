#!/bin/bash
# Runs each image in images.txt once with Range, records which blocks its
# startup needs, and writes that profile into DIR for the catalog. An image
# that does not start (no shell, no linux build for this runner) is skipped.
set -uo pipefail
dir=${1:?usage: profile.sh DIR}
export RANGE_CACHE_DIR=${RANGE_CACHE_DIR:-$HOME/range-cache}
shell_start='command -v bash >/dev/null && exec bash -c true; true'
ok=0; failed=0
while IFS= read -r line; do
  line=${line%%#*}
  [ -n "${line// }" ] || continue
  image=$(echo "${line%%|*}" | xargs)
  cmd=$(echo "${line#*|}" | xargs); [ "$line" = "${line#*|}" ] && cmd=""
  [ -n "$cmd" ] || cmd=$shell_start
  if timeout 600 sudo -E ./range run --profile record "$image" -- sh -c "$cmd" </dev/null >/dev/null 2>"$RUNNER_TEMP/err.txt" &&
     sudo -E ./range profile export "$image" --catalog "$dir" >/dev/null 2>>"$RUNNER_TEMP/err.txt"; then
    ok=$((ok + 1)); echo "profiled $image"
  else
    failed=$((failed + 1)); echo "skipped $image: $(tail -1 "$RUNNER_TEMP/err.txt")"
  fi
done < images.txt
sudo chown -R "$(id -u)" "$dir" 2>/dev/null || true
echo "profiled $ok image(s), skipped $failed"

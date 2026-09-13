#!/usr/bin/env bash
# Run stages 03-08 for every segment of one class: calibrate + hovers per segment,
# then read (VLM), rank anticipation and export once for the class.
#
#   pipeline/scripts/run_class.sh paladin            # everything
#   pipeline/scripts/run_class.sh paladin --skip-video   # only 05 -> 08 (hovers already exist)
#   pipeline/scripts/run_class.sh paladin --skip-read    # only 06 -> 08 (candidates already exist)
#   pipeline/scripts/run_class.sh paladin --second-opinion  # also run scripts/second_opinion.py (codex CLI) after 05
#
# Needs llama-server up (scripts/llama-server.sh) for stage 05. Fragment fetches
# are sequential (one request at a time) by construction. Stops on the first error.
set -euo pipefail
cd "$(dirname "$0")/.."
cls="${1:?usage: run_class.sh <class> [--skip-video] [--skip-read] [--second-opinion] [--no-encoding]}"
shift
skip_video=0; skip_read=0; second=0; encoding="--update-encoding"
for a in "$@"; do
  case "$a" in
    --skip-video) skip_video=1 ;;
    --skip-read) skip_read=1 ;;
    --second-opinion) second=1 ;;
    --no-encoding) encoding="" ;;
    *) echo "unknown option $a" >&2; exit 2 ;;
  esac
done

if [ "$skip_video" = 0 ] && [ "$skip_read" = 0 ]; then
  if [ "$(grep -c 'Skipping fragment' work/video/download.log 2>/dev/null || echo 0)" != "0" ]; then
    echo "download.log shows skipped fragments; not touching the stream" >&2; exit 1
  fi
  mapfile -t segs < <(uv run python -c "
import json
for i, s in enumerate(json.load(open('../data/extracted/segments.json')), 1):
    if s['class'] == '$cls': print(i)")
  [ "${#segs[@]}" -gt 0 ] || { echo "no segments for $cls in data/extracted/segments.json" >&2; exit 1; }
  echo "$cls: segments ${segs[*]}"
  for seg in "${segs[@]}"; do
    echo "== stage 03 segment $seg"
    uv run stages/03_calibrate.py run "$seg" | grep -v 'frame ok'
    echo "== stage 04 segment $seg"
    uv run stages/04_hovers.py run "$seg" | grep -v '^sq='
  done
fi

if [ "$skip_read" = 0 ]; then
  echo "== stage 05 $cls"
  uv run stages/05_read.py run "$cls"
fi
if [ "$second" = 1 ]; then
  echo "== second opinion (codex) $cls"
  uv run scripts/second_opinion.py "$cls"
fi
echo "== stage 06 $cls"
uv run stages/06_rankfill.py "$cls" --force
echo "== stage 08 $cls"
uv run stages/08_export.py extract "$cls" $encoding
echo "== validate"
uv run validate.py "../data/extracted/$cls.json" --report

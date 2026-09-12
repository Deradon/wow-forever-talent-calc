#!/usr/bin/env bash
# Start llama-server with a Qwen3-VL Instruct GGUF model (flags per docs/briefs/pipeline.md §2).
# Usage: pipeline/scripts/llama-server.sh <4b|8b> [extra llama-server args...]
#
# Model files (verified on Hugging Face 2026-09-13 via /api/models/<repo> siblings):
#   Qwen/Qwen3-VL-4B-Instruct-GGUF: Qwen3VL-4B-Instruct-Q4_K_M.gguf  mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf
#   Qwen/Qwen3-VL-8B-Instruct-GGUF: Qwen3VL-8B-Instruct-Q4_K_M.gguf  mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf
#   (both repos also ship F16 / Q8_0 weights and an F16 mmproj; not used here)
set -euo pipefail

SIZE="${1:-}"
case "$SIZE" in
  4b) TAG=4B ;;
  8b) TAG=8B ;;
  *) echo "usage: $0 <4b|8b> [extra llama-server args]" >&2; exit 2 ;;
esac
shift

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_DIR="$ROOT/pipeline/work/models"
MODEL="$MODEL_DIR/Qwen3VL-${TAG}-Instruct-Q4_K_M.gguf"
MMPROJ="$MODEL_DIR/mmproj-Qwen3VL-${TAG}-Instruct-Q8_0.gguf"
SERVER="${LLAMA_SERVER:-$HOME/Dev/llama.cpp/build/bin/llama-server}"

for f in "$SERVER" "$MODEL" "$MMPROJ"; do
  [[ -e "$f" ]] || { echo "missing: $f (run pipeline/scripts/download-model.sh $SIZE?)" >&2; exit 1; }
done

exec "$SERVER" -m "$MODEL" --mmproj "$MMPROJ" \
  -ngl 99 -c 4096 \
  --image-min-tokens 512 --image-max-tokens 1536 \
  --host 127.0.0.1 --port "${LLAMA_PORT:-8080}" -np 1 \
  "$@"

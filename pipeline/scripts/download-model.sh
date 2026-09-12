#!/usr/bin/env bash
# Download Qwen3-VL Instruct Q4_K_M weights + Q8_0 mmproj into pipeline/work/models/.
# Usage: pipeline/scripts/download-model.sh <4b|8b>
# File names verified on Hugging Face 2026-09-13 (see llama-server.sh header).
set -euo pipefail

SIZE="${1:-}"
case "$SIZE" in
  4b) TAG=4B ;;
  8b) TAG=8B ;;
  *) echo "usage: $0 <4b|8b>" >&2; exit 2 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_DIR="$ROOT/pipeline/work/models"
mkdir -p "$MODEL_DIR"

exec uvx --from huggingface_hub hf download "Qwen/Qwen3-VL-${TAG}-Instruct-GGUF" \
  "Qwen3VL-${TAG}-Instruct-Q4_K_M.gguf" "mmproj-Qwen3VL-${TAG}-Instruct-Q8_0.gguf" \
  --local-dir "$MODEL_DIR"

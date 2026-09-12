# 2026-09-13 – llama.cpp CUDA build

## What was done

- Cloned `https://github.com/ggml-org/llama.cpp` to `~/Dev/llama.cpp`, checked out
  release tag **b10931** (commit `3057bb66c`, ggml 0.23.0). Not on master.
- Configured and built (cmake 3.22.1 is fine; repo minimum is 3.14):
  ```bash
  export PATH=/usr/local/cuda-13.3/bin:$PATH
  cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=86   # 8 GB Ampere GPU = sm_86, flag name per docs/build.md
  cmake --build build --config Release -j 12 --target llama-server llama-mtmd-cli
  ```
  Build time: ~7.5 min (448 s) total. CUDA host compiler GNU 11.4.0. NCCL not found
  (irrelevant, single GPU). Note: `-j 12` was used; on this 15 GB box prefer `-j 6`
  for rebuilds — `free -m` showed ~13.8 GB available afterwards, so it was not a problem this time.
- Verified: `llama-server --version` -> `0.4.0-dev (build 10931, commit 3057bb66c)`;
  `ldd build/bin/llama-server` links `libggml-cuda.so.0`, `libcudart.so.13`, `libcublas.so.13`,
  `libcuda.so.1` (WSL driver stub). Binaries: `~/Dev/llama.cpp/build/bin/{llama-server,llama-mtmd-cli}`.
- VRAM: `nvidia-smi --query-gpu=memory.free` measured about 6 GB free with other
  things running (idle baseline not confirmed). Below the 7 GB threshold from the
  brief -> **4B model** unless an idle measurement says otherwise.
- Wrote `pipeline/scripts/llama-server.sh <4b|8b>` (starts server with the brief's flags,
  env `LLAMA_SERVER`, `LLAMA_PORT` overridable, extra args pass through) and
  `pipeline/scripts/download-model.sh <4b|8b>`. Model dir `pipeline/work/models/` (not created yet).
- HF file names verified via the HF API for both repos:
  `Qwen3VL-{4B,8B}-Instruct-Q4_K_M.gguf`, `mmproj-Qwen3VL-{4B,8B}-Instruct-Q8_0.gguf`.

## State

No model weights downloaded (bandwidth reserved for the video download). No server running.

## Next, in order

```bash
cd <repo root>
nvidia-smi --query-gpu=memory.free --format=csv,noheader   # re-measure idle; >= 7000 MiB -> use 8b below
pipeline/scripts/download-model.sh 4b                       # ~3 GB, wait for the video download to finish
pipeline/scripts/llama-server.sh 4b                         # foreground; 127.0.0.1:8080
# smoke test (other terminal): crop a text box from the 11000-s probe frame, then
curl -s http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' -d @- <<'JSON'
{"model":"qwen3vl","temperature":0,"max_tokens":300,
 "response_format":{"type":"json_schema","json_schema":{"name":"t","schema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}},
 "messages":[{"role":"user","content":[
   {"type":"image_url","image_url":{"url":"data:image/png;base64,<BASE64>"}},
   {"type":"text","text":"Transcribe the tooltip text as JSON."}]}]}
JSON
nvidia-smi --query-gpu=memory.used --format=csv,noheader     # expect < 5 GB
```
Then swap the schema for the one in `docs/briefs/pipeline.md` §4 and expect valid JSON in < 3 s.

## Surprises / decisions

- cmake 3.22.1 satisfied the repo minimum; no uv-installed cmake needed.
- Server starts via `exec`, so `Ctrl-C` kills llama-server directly.

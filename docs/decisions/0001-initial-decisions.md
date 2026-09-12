# ADR 0001: Initial project decisions (2026-09-13)

Status: accepted. Decided by the project owner after a research round
(see `docs/research/`).

| # | Decision | Choice | Alternatives considered | Why |
|---|----------|--------|-------------------------|-----|
| 1 | Strategy | Ship as fast as possible; video extraction is essential | Wait for beta datamining; Classic placeholder | Beta opens 2026-09-17 and datamined data follows; a working calculator with real Forever data before that is the whole point. Schema must allow datamined data to replace video data. |
| 2 | Footage | Direct game capture, 1080p60 | Camera-at-demo-station | Owner watched the stream. Fixed UI position, sharp text. |
| 3 | Segment location | Only known: after ~3 h into the stream | Per-class timestamps | Automatic segmentation over the last ~4 h. |
| 4 | Ranks | Rank-0 hovers only; anticipate higher ranks from Classic Era scaling | Capture per-rank text | Not shown on stream. Every talent records how its ranks were derived. |
| 5 | Text reader | Local Qwen3-VL on the local GPU via llama.cpp | Claude vision API; both | Owner's choice: free, offline. Deterministic OpenCV for all positions. |
| 6 | Web stack | Vite + React + TypeScript, Tailwind, Vitest | SvelteKit; plain TS | Reliable with AI-assisted maintenance; static output. |
| 7 | Hosting | GitHub Pages via Actions | Cloudflare Pages | Owner's choice. Needs base path and hash/query routing. |
| 8 | License | MIT for code; game data stays Blizzard's | AGPL; none | Permissive reuse. |
| 9 | Source video | Full from-start download started 2026-09-13 00:16 local (stream still live) | Wait for VOD | yt-dlp cannot partially download a live stream from its start; the VOD could be removed. |

Open questions carried in `docs/PLAN.md`.

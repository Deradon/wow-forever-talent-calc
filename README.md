# WoW Forever Talent Calculator

A community talent calculator for **World of Warcraft: Forever** (Classic+),
announced at BlizzCon 2026. Built to exist *before* official data is
available: talent data is extracted from gameplay footage in which every
talent tooltip is hovered, then reviewed by hand.

Repository: https://github.com/Deradon/wow-forever-talent-calc
Site (once Pages is enabled): https://deradon.github.io/wow-forever-talent-calc/

Status: **bootstrapping** – see `docs/PLAN.md`, briefs in `docs/briefs/`.

## How it works

1. `pipeline/` downloads the source video, finds the segments per class,
   extracts one clean frame per hovered talent, reads the tooltip (OCR /
   vision model) and writes candidate JSON with provenance.
2. `data/` holds reviewed talent data, one file per class.
3. `web/` is a static talent calculator (Classic-style trees, point rules,
   shareable build links) deployed as plain files.

## Source

- Xaryu, BlizzCon 2026 day 1 stream: https://www.youtube.com/watch?v=DxtVEhjyROU

## Development

Tooling is documented per subfolder once it exists. Requirements so far:
`git`, `ffmpeg`, `yt-dlp`, `uv` (Python), `node` ≥ 22.

## License

Code: MIT (see `LICENSE`). Talent names, descriptions and icons are
© Blizzard Entertainment and not covered by the license. Not affiliated with
Blizzard Entertainment.

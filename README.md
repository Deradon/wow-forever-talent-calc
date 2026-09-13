# WoW Forever Talent Calculator

A community talent calculator for **World of Warcraft: Forever** (Classic+),
announced at BlizzCon 2026. Built to exist *before* official data is
available: talent data is extracted from gameplay footage in which every
talent tooltip is hovered, then reviewed by hand.

Repository: https://github.com/Deradon/wow-forever-talent-calc
Site: https://deradon.github.io/wow-forever-talent-calc/

Status: **live, unreviewed.** All nine classes and 469 of 470 talents are
published (one mage Fire talent was never hovered on stream). No record has
passed human review yet, so every tooltip carries its provenance and a
caveat. Plan and history: `docs/PLAN.md`; open findings:
`docs/reviews/2026-09-13-consolidated.md`.

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

Requirements: `uv` (Python 3.12) and `node` >= 22; `ffmpeg` and `yt-dlp` only
to re-run the extraction from video.

```bash
# web app
cd web && npm install && npm run dev      # http://localhost:5173
npm test                                  # vitest

# pipeline
cd pipeline
uv run pytest                                              # 171 tests
uv run python validate.py --check ../data/talents/*.json   # 0 errors
```

Commands stage by stage: `pipeline/README.md`. Web app details:
`web/README.md`. Data contract: `docs/DATA-SCHEMA.md`. Conventions for
working in this repo: `CLAUDE.md`.

## License

Code: MIT (see `LICENSE`). Talent names, descriptions and icons are
© Blizzard Entertainment and not covered by the license. Not affiliated with
Blizzard Entertainment.

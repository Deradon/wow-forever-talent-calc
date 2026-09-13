# Class icons (`classicon_<class>.jpg`)

The nine `classicon_*.jpg` files in this directory are **not** produced by the
pipeline. Every other file here is written by `pipeline/stages/09_icons.py`
(talent icons, matched against the video crops); these nine were fetched by
hand for the UI, because they belong to the chrome - the class switcher chips
in the class header and the class cards on the landing page - and not to any
talent record.

| | |
|---|---|
| Files | `classicon_warrior`, `_paladin`, `_hunter`, `_rogue`, `_priest`, `_shaman`, `_mage`, `_warlock`, `_druid` (`.jpg`) |
| Source | `https://wow.zamimg.com/images/wow/icons/large/classicon_<class>.jpg` |
| Size | 56 x 56 JPEG, ~1.7-2.3 kB each, ~17 kB for all nine |
| Retrieved | 2026-09-13, one request at a time with a 1 s pause and a descriptive User-Agent, verified to return image data |
| Consumed by | `web/src/ui/ClassSwitcher.tsx`, `web/src/ui/ClassPicker.tsx` (`classIconUrl` in `web/src/ui/classIcon.ts`) |

Do not add these to `data/icons/matches.json` or to the stage 9 fetch list: a
`match`/`fetch` run must be free to rewrite every talent icon in this
directory without ever touching or removing these nine. They have no talent,
no crop and no match score.

## Licensing

Same position as every other icon here: the artwork is copyrighted by Blizzard
Entertainment and is used under the fan-site tolerance for non-commercial
community tools. The full statement, including what to do if Blizzard or
Wowhead object, is the "Licensing" section of `data/icons/SOURCES.md` - read
that; this file only records where these nine came from. The MIT licence on
this repository covers the code, not the icons.

The UI degrades on its own if the files are removed: both the chips and the
cards fall back to the class-coloured two-letter initials they used before
(`onError` on the `<img>`), so dropping `web/public/icons/` never breaks a
page.

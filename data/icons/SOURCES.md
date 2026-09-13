# Icons: sources, matching, licensing

Stage 9 (`pipeline/stages/09_icons.py`) replaces the 36 px screengrab icons
of talents whose icon is already known by the icon's canonical name, so the
web app can show a clean `web/public/icons/<name>.jpg` instead of the video
crop. Talents whose crop matches nothing keep `iconSource: "crop"`.

## Files

| File | Content | Origin |
|---|---|---|
| `matches.json` | Per class and `<tree>/<talent-id>`: chosen `icon`, NCC `score`, `margin` to the runner-up, pHash distance, `method` (`classic-prior` / `visual`), `confidence`, reference `tier`, `verified`, the top-3 candidates, the cell of the source candidate record. `icon: null` means keep the crop. | `09_icons.py match all` |
| `verified.json` (optional) | `{class: {"tree/talent": true \| false \| "<icon name>"}}` hand verdicts, merged on the next `match` run: `false` retracts, `true` confirms (or accepts the best candidate of a rejected talent), an icon name forces that icon (`method: "manual"`). | by hand |
| `../../web/public/icons/<name>.jpg` | 56 px (`large`) icon per accepted match; only referenced icons are stored. | `09_icons.py fetch` from Wowhead's CDN |

## Reference set (git-ignored, `pipeline/work/icons/`)

Built by `09_icons.py refs [--fetch-lists]`, 6,631 icon names in three tiers
(names with spaces, apostrophes or a stray extension are dropped; 6,628 exist
on the CDN, retrieved 2026-09-13), each fetched once as the 36 px `medium` JPG from
`https://wow.zamimg.com/images/wow/icons/medium/<name>.jpg` (one request at a
time, 0.3 s pause, descriptive User-Agent, run stops on 403/429):

| Tier | Names | Source |
|---|---|---|
| `prior` | 306 | icons of the 432 Classic Era talents in `data/prior/classic-era/talents.json` (Wowhead Classic talent data, see `../prior/classic-era/SOURCES.md`) |
| `later-talents` | 1,320 (1,017 new) | `"icon"` fields of Wowhead's talent data files for TBC, Wrath, Cataclysm and MoP Classic (`https://nether.wowhead.com/<game>/data/talents-classic`, `<game>` = `tbc`, `wotlk`, `cata`, `mop-classic`; retrieved 2026-09-13). Forever talents that were lifted from later expansions (e.g. Infusion of Light) reuse those icons. |
| `classic-era-client` | 6,364 (5,308 new) | every `Interface\ICONS\*.blp` in `ManifestInterfaceData` of the Classic Era client build 1.15.9.69722, CSV export from `https://wago.tools/db2/ManifestInterfaceData/csv?build=1.15.9.69722` (retrieved 2026-09-13). |

The Forever client (build 1.60.x) is not listed on wago.tools yet; when it is,
its `ManifestInterfaceData` (or `Talent.db2` + `SpellIcon`) should replace the
matching altogether (`iconSource: "datamined"`, DATA-SCHEMA.md section 9).

## Matching method

`pipeline/src/wowtalents/icons.py`, thresholds in `Thresholds`:

- The review crop is the whole 36 px talent cell: icon inset by about 4 px
  inside the cell border, plus, for available (learnable) talents, a green
  border and a rank digit in the bottom-right corner. Locked talents are
  drawn darkened and desaturated. Colour is therefore unusable for most
  cells; the comparison uses luminance structure only.
- Crop and reference are cut to the icon area (crop inset 4 or 5 px,
  reference trimmed 0 or 1 px), resized to 24 x 24, normalised to zero mean
  and unit variance with the digit corner masked, and compared by normalised
  cross-correlation (NCC) against every reference; the best inset pair wins.
- The top 10 are re-ranked with a 64-bit pHash distance (imagehash).
- Classic-prior hint: when the Forever talent has the same name as a Classic
  talent of the same class, that talent's icon is accepted if it sits within
  the top 3 with NCC >= 0.45 (`method: "classic-prior"`). Otherwise a match
  needs NCC >= 0.60 and a 0.04 margin over the runner-up (or NCC >= 0.80),
  and a pHash distance <= 26 unless NCC >= 0.80 (`method: "visual"`).
- A visual winner that contradicts the Classic prior needs NCC >= 0.85 and a
  0.10 margin. Two references with NCC >= 0.90 to each other count as
  variants of one picture and do not veto each other through the margin.
- `confidence: "high"` = NCC >= 0.80 with margin, or the prior icon ranked
  first; `medium` otherwise. `apply` and `fetch` take `high` (and hand
  verified) matches only unless `--min-confidence medium` is given.
- Everything else keeps the crop.

## Licensing

Icon artwork is copyrighted by Blizzard Entertainment. Wowhead's CDN is the de
facto public source for these files; fan sites and talent calculators have
self-hosted them for two decades under Blizzard's fan-site tolerance for
non-commercial community tools. This project is a non-commercial fan tool
(MIT-licensed code; the icons and the talent text are not covered by the MIT
licence). Only icons actually referenced by the data are stored, at 56 px.
Wowhead's and wago.tools' data files are used as name lists only and are not
redistributed (they live under the git-ignored `pipeline/work/`). If Blizzard
or Wowhead object, `web/public/icons/` can be dropped and the app falls back
to crops or initials.

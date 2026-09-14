# Handover: the priest spell search (2026-09-14)

Answers one open question from `docs/handover/2026-09-13-spells-data.md`
section 7.3 and `CLAUDE.md` §State: *were priest spells shown anywhere in the
stream?* No code and no data changed; `data/spells/` still has eight files and
no priest one, which is now a measured result rather than an assumption.

## 1. What was done

**Verdict: the priest spellbook was never opened, no priest spell was ever
hovered, and no priest spell name is legible anywhere in the 8.5 h VOD.**
`data/spells/priest.json` stays absent; the web app's "never shown on stream"
copy is correct.

Scratch tool: `pipeline/work/priest-search/sweep.py` (two subcommands,
`titlebar` and `tooltips`), reusing `wowtalents.mkv` and `wowtalents.spells`
unchanged — `locate_window` with `assets/spellbook-title.png`, plus a narrow
sub-template cut from columns 290-470 of the same asset (the word "Spellbook"),
which still matches a window dragged partly off screen. Decoding only keyframes
(`ffmpeg -skip_frame nokey`) gives ~1 fps at roughly 35x realtime, which is what
made a pass over the whole VOD affordable. Full write-up with the per-run
tables: `pipeline/work/priest-search/report.md` (git-ignored).

| Pass | Range (stream time) | Rate | Frames | Result |
|---|---|---|---|---|
| Dense margin | 05:15:00-05:45:00 | 2 fps, real frames | 3600 | 425 spellbook frames in 12 runs, **none inside the priest demo**; 0 sub-template-only hits, so no off-screen or scaled window |
| Whole VOD | 00:00:01-08:33:20 | 1 fps, keyframes | 30798 | 876 spellbook frames in 50 runs; **no priest page anywhere**; 17 runs stage 11 has never seen (section 3) |
| Probe classification | 03:00-06:20, all 541 stage-0 probe frames | 10-60 s | 541 | the `Discipline / Holy / Shadow Magic` tree-name strip matches only 05:24:50-05:29:30 — segment 18 and nothing else |
| Tooltips | 05:23:56-05:29:50, the whole priest demo | 6 fps | 2124 | 1340 dark boxes, 280 outside the talent window, 153 of them >= 150x70 px; every one is a priest *talent* tooltip overhanging the talent window's right edge, or webcam, loading screen, settings panel. **No action-bar and no spellbook tooltip.** |

The negative is not a threshold artefact. Over the 30798-frame pass the
title-bar correlation is >= 0.95 on 842 frames and 0.90-0.95 on 34, and exactly
**2** frames land in 0.85-0.90. There is no ambiguous band to hide a page in.

## 2. What the priest demo actually contains

One appearance, about 5 min 40 s: character creation with **Priest selected**
at 05:23:35-05:23:55 (class icon and the class description panel — flavour text,
no spells), loading screen, ~16 s in Durotar in which the action bar shows about
nine priest spell **icons and no names** (the audio settings window covers most
of it), then the talent window open continuously 05:24:20-05:29:35, then the
client restart at 05:29:38. There was never a moment at which the spellbook
could have been opened. Crops: `view-cc-priest.png`, `view-actionbar.png` in the
scratch directory.

Reading the nine action-bar icons through stage 9's icon matcher would give
Classic icon *file names*, not Forever spell names or text, and nothing that
belongs in the `spell` schema. Not recommended.

## 3. Side finding: stage 11's `WINDOWS` misses 17 spellbook appearances

`WINDOWS` in `pipeline/stages/11_spellbook.py` was built from the 541 stage-0
probe minutes, so a spellbook open for less than a probe step is invisible to
it. The 1 fps pass found 50 spellbook runs, 17 of them outside `WINDOWS`, and
several are pages `2026-09-13-spells-data.md` section 2 records as never opened:

* **06:21:10-06:21:43 — warlock Demonology, with a `Summon Succubus` tooltip.**
  One of the three warlock tree pages listed as missing, and it sits *after* the
  06:20 source-window cutoff, so the assumption that nothing relevant follows
  06:20 is wrong by about 90 seconds.
* **04:39:30 — mage Arcane, page 2/2**; stage 11 only ever read page 1.
* **05:47:55 — druid Feral Combat, page 1/2.**
* **03:24:55-03:36:45 — a level-1 Skyborne character** (General with the four
  Skyborne racials as spellbook rows; a Fire page holding only `Fireball` Rank 1).
  Well before the 03:47 start of the talent segments.
* Mage Frost during the dungeon demo (04:19-04:47), an Undead General page at
  04:20:20, a Troll General page at 05:57:05, Skyborne General with the full
  `Skysight` tooltip at 06:05:05, Night Elf General with a `Shoot Crossbow`
  tooltip at 06:10:16, Tauren General at 05:42:42 and 06:15:22, and a warrior
  "Retaliation" search at 06:16:20.

Crops for all 17 are in `pipeline/work/priest-search/new-windows/` and the two
contact sheets beside them.

## 4. What is next, in order

1. **Record the priest verdict as measured.** `CLAUDE.md` §State, `README.md`
   and the `#/spells` copy all say "priest was never shown"; that is now backed
   by this pass and can be stated as such.
2. **Re-run stage 11 with the 17 windows added** to `WINDOWS` (the table takes
   `(t0, t1, cls, note)`; the classes are legible in the crops, except the
   05:57:05 Troll General page which needs its tab strip read). It closes the
   warlock Demonology gap, adds a second mage Arcane page and a second druid
   Feral Combat page, and adds the Skyborne rows. Extending the source window
   past 06:20 to about 06:22 is required for the warlock page.
3. **Generate `WINDOWS` instead of hand-labelling it.** The keyframe pass costs
   about 40 minutes for the whole VOD and produces the runs directly; a hand
   table built from 60 s probe minutes will keep missing short openings.

## 5. Surprises and decisions

* **Keyframe-only decoding is what makes a whole-VOD sweep cheap.**
  `-skip_frame nokey` plus `fps=1` decodes the stream's one-second keyframes and
  nothing else: 8.5 h in about 40 minutes on one reader, against roughly 8x
  realtime for a full decode. The stage-0 probe grid can be replaced by it.
* **A narrow sub-template was the right way to test "partly off screen", and it
  found nothing.** Zero frames matched the "Spellbook" word without also
  matching the full 733 px bar, in either pass — Xaryu never dragged the window
  past a frame edge.
* **"Priest never shown" was three claims, and only one of them is true.** The
  priest *class* is on screen (character creation, the class description, the
  talent window, an action bar full of icons); the priest *spellbook* is not.
  The spells dataset's `tabsMissing` wording covers this correctly, but the
  shorthand in `CLAUDE.md` does not.
* **The talent-window tooltips that overhang its right edge look exactly like an
  action-bar hover to a naive detector.** 153 of the 2124 priest-demo frames
  carry a large dark box outside `ui.WINDOW`, and every one is a tree-3 talent
  tooltip (`Mind Flay`, `Darkness`, `Devouring Contagion`). Any future
  "tooltips outside the talent window" detector needs that exclusion or it will
  report a hundred false hovers per class.

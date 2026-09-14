# Contributing

The most useful contribution is a corrected reading. Every talent, spell and
racial trait on this site was read out of a video by a machine, so wrong
wording and wrong numbers are expected — and each one is a single JSON entry
away from being fixed for good.

If you only want to report something, open a
[wrong-reading issue](https://github.com/Deradon/wow-forever-talent-calc/issues/new?template=wrong-reading.yml)
and stop reading here. The rest of this file is for fixing it yourself.

## Fixing a talent: the override workflow

Corrections never go into `data/talents/<class>.json` directly. That file is
generated: the pipeline writes it from `data/extracted/<class>.json` (raw
machine output, never hand-edited) plus `data/overrides/<class>.json` (your
corrections). An override is the record of *why* something was changed, and it
survives the next re-run of the extraction; a direct edit does not.

1. **Find the record.** Open `#/review/<class>` on the site — for example
   [`#/review/warrior`](https://deradon.github.io/wow-forever-talent-calc/#/review/warrior).
   It lists every talent worst reading first, next to the tooltip crop it was
   read from. Filter by *queue* for the low-confidence ones, or search by name.
   Compare the crop with the text: the crop is the evidence.

2. **Copy the override.** Press **Copy override** on that row. You get one
   entry, prefilled with the id, the tree and the current name and description:

   ```json
       {
         "talent": "improved-rend",
         "tree": "arms",
         "set": {
           "name": "Improved Rend",
           "description": "Increases the damage of your Rend ability by {0}%.",
           "source": {
             "reviewed": true
           }
         },
         "reason": "TODO: what was wrong; checked against data/review/warrior/arms/improved-rend.png",
         "by": "TODO",
         "at": "2026-09-14T09:00:00Z"
       }
   ```

   **Copy all flagged** does the same for every row the current filter shows.

3. **Paste and edit.** Put the entry inside the `"overrides": [ ... ]` array of
   `data/overrides/<class>.json`, then fix the text in the `set` block and
   replace the two `TODO`s: `reason` says what was wrong and what you checked
   it against, `by` is your GitHub handle or a role like `data-audit`. An
   entry whose `set` you left untouched still counts — that is how a record is
   marked as read and accepted. `{0}`, `{1}` … are rank slots, one per rank
   value; keep them. The full field list, plus `unset`, `rename`, `delete` and
   `add`, is `docs/DATA-SCHEMA.md` section 6.2.

   If the name changes enough that the id is wrong, add `"rename": "<new-id>"`
   as well, and say so in the pull request: ids are part of build links.

4. **Export and validate**, from `pipeline/`:

   ```bash
   uv run stages/08_export.py promote <class>
   uv run python validate.py --check ../data/talents/<class>.json
   uv run python validate.py --overrides ../data/overrides/<class>.json
   uv run pytest
   ```

   The export refuses to write a file that does not validate, and CI runs the
   same `--check` before deploying. Ranks 2+ are recomputed, so a corrected
   rank-1 number fixes the whole progression.

5. **Open a pull request** with `data/extracted/`, `data/overrides/`,
   `data/talents/` and any crops in the same commit, and say in the body what
   you checked the reading against. One class per pull request keeps it
   reviewable.

Race and spell data (`data/races/`, `data/spells/`) has no override mechanism
yet; report those as issues.

## Code

Work in the half you are changing: `web/` is Vite + React + TypeScript with
Tailwind and Vitest, `pipeline/` is Python 3.12 under uv with pytest.
Keep the pure parts pure — rules, URL codecs, text and model helpers under
`web/src/rules`, `web/src/url` and the `*Model.ts` files touch no DOM and carry
the unit tests, while React components stay presentational; the app must build
to static files with no backend and no runtime data fetching beyond its own
JSON. New behaviour needs a test in the same style as its neighbours (a pure
unit test, plus a Playwright case when it is something a visitor clicks), and
`cd web && npx vitest run && npm run build && npx playwright test` plus
`cd pipeline && uv run pytest` must be green before you open the pull
request. Match the file you are editing rather than
reformatting it; comments explain *why*, in English, because the reasoning is
the part nobody can reconstruct. Player-facing text never shows pipeline
vocabulary — no stage numbers, model names, confidences or file paths outside
`#/review/<class>`, which is the maintainers' page.

## Privacy

This is a public repository, and everything in a pull request or an issue is
public forever. Do not commit or paste real names, e-mail addresses, home
directory paths (`/home/<you>/…`, `C:\Users\<you>\…`), hostnames, IP addresses,
account or character names, GPU or hardware readouts, or anything else that
identifies a machine or a person. Crop screenshots so no overlay, chat, name
plate or friends list is in them. The `by` field of an override is a public
attribution: use a handle you are happy to publish, or a role name.

Commit messages are English and describe the change; a `Co-Authored-By` line
for an AI assistant is fine, but never a session URL of any kind.

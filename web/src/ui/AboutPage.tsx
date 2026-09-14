import { changesHash } from '../url/route'
import { ISSUES_URL, REPO_URL } from './site'
import { SITE_TITLE, useTitle } from './title'

/**
 * `#/about`: the honest version of what this site is, in three paragraphs.
 * Player-facing, so it names no stage, no model and no file - what a visitor
 * needs is where the text came from and how much to trust it. The caveat on the
 * landing page is the short form of the middle paragraph; keep the two in step.
 */
export function AboutPage() {
  useTitle(`About - ${SITE_TITLE}`)
  return (
    <div className="panel mx-auto max-w-[70ch] p-5">
      <h1 className="serif mb-3 text-xl text-[var(--gold)]">About this calculator</h1>

      <p className="mb-3">
        This is a fan-made talent calculator for World of Warcraft: Forever, the Classic+ game announced at BlizzCon
        2026. It exists because the talent trees were shown on stream months before anyone could log in and see them:
        you can spend points here, share a build as a link, and compare every tree against the Classic Era one you
        already know. It is not made by Blizzard Entertainment and is not endorsed by them.
      </p>

      <p className="mb-3">
        The talent names, descriptions and icons were read off the BlizzCon demo stream, one tooltip at a time, by a
        program that looks at video frames - nobody at Blizzard handed us a file. Only the first rank of each talent was
        ever on screen, so higher ranks are an estimate based on how the matching Classic Era talent scaled, and the
        point rules (51 points, five per row) are the Classic ones until someone can confirm them in the beta. Each
        tooltip carries its own provenance: open the details inside one to see when it was read and how sure the reader
        was.
      </p>

      <p className="mb-4">
        So treat everything here as a good draft, not as a source. Numbers are the least reliable part, wording is
        second, and a talent nobody hovered on stream is missing altogether - one is, in the mage Fire tree. Where the
        reading was shaky the tooltip says so, in amber. If you find something wrong, a report with the correct text is
        genuinely useful; the data is public and is fixed one record at a time.
      </p>

      <ul className="flex list-none flex-col gap-1 p-0 text-sm">
        <li>
          <a href={changesHash()} data-testid="about-changes-link">
            What changed against Classic Era
          </a>
          <span className="text-[var(--text-dim)]"> - every new, moved, re-ranked and reworded talent.</span>
        </li>
        <li>
          <a href={`${ISSUES_URL}/new/choose`} target="_blank" rel="noreferrer" data-testid="about-issues-link">
            Report a wrong reading
          </a>
          <span className="text-[var(--text-dim)]"> - a form that asks for the talent and what it should say.</span>
        </li>
        <li>
          <a href={REPO_URL} target="_blank" rel="noreferrer" data-testid="about-repo-link">
            Source code and data on GitHub
          </a>
          <span className="text-[var(--text-dim)]"> - MIT licensed, corrections welcome.</span>
        </li>
      </ul>
    </div>
  )
}

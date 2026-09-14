import classesIndex from '../data/classes-index.json'
import './class-switcher.css'
import { includeExamples } from '../data/load'
import { ClassIcon } from './ClassIcon'
import { classColour, classTextColour } from './classIcon'

interface IndexEntry {
  id: string
  origin: string
  className: string
}

const classes: IndexEntry[] = (classesIndex as IndexEntry[]).filter((c) => includeExamples || c.origin === 'talents')

/**
 * The class strip in the class header (brief "UI and UX improvements", idea 2).
 * Removes the only navigation dead end on the site: before this, the way out of
 * a class page was the back link.
 *
 * Every chip is a real `<a href="#/<class>">`, so it is keyboard reachable, can
 * be opened in a new tab, and - because it carries no `t=` - starts an empty
 * build. The build you were on is one Back away, which is exactly the guard the
 * brief asks for and costs nothing: the class page pushes one history entry per
 * editing session (see history.ts).
 *
 * Each chip carries the class crest and the class name in the class colour. The
 * name is hidden below 1320px - the same breakpoint at which the summary column
 * drops under the trees - and the chips become icon-only; the `title` and the
 * `sr-only` name mean nothing is lost when it goes, so the strip never wraps
 * into three lines on a laptop.
 */
interface SwitcherProps {
  current: string
  /** Where a chip goes. Defaults to the class page; `#/changes` passes its own. */
  hrefFor?: (classId: string) => string
  /** The chip's tooltip, which is not "starts an empty build" everywhere. */
  hintFor?: (className: string) => string
}

export function ClassSwitcher({ current, hrefFor, hintFor }: SwitcherProps) {
  if (classes.length <= 1) return null
  return (
    <nav className="class-switcher" aria-label="Switch class" data-testid="class-switcher">
      {classes.map((entry) => {
        const active = entry.id === current
        return (
          <a
            key={entry.id}
            href={hrefFor ? hrefFor(entry.id) : `#/${entry.id}`}
            className="class-chip"
            style={
              {
                '--class-colour': classColour(entry.id),
                '--class-text': classTextColour(entry.id),
              } as React.CSSProperties
            }
            data-testid={`class-chip-${entry.id}`}
            data-active={active}
            aria-current={active ? 'page' : undefined}
            title={hintFor ? hintFor(entry.className) : `${entry.className} - starts an empty build`}
          >
            <ClassIcon classId={entry.id} className={entry.className} size={24} />
            <span className="class-chip-name" aria-hidden="true">
              {entry.className}
            </span>
            <span className="sr-only">{entry.className}</span>
          </a>
        )
      })}
    </nav>
  )
}

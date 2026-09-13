import classesIndex from '../data/classes-index.json'
import { includeExamples } from '../data/load'

interface IndexEntry {
  id: string
  origin: string
  className: string
}

/** The Blizzard class colours; anything not in the list falls back to gold. */
const CLASS_COLOUR: Record<string, string> = {
  druid: '#ff7d0a',
  hunter: '#abd473',
  mage: '#69ccf0',
  paladin: '#f58cba',
  priest: '#ffffff',
  rogue: '#fff569',
  shaman: '#0070de',
  warlock: '#9482c9',
  warrior: '#c79c6e',
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
 */
export function ClassSwitcher({ current }: { current: string }) {
  if (classes.length <= 1) return null
  return (
    <nav className="class-switcher" aria-label="Switch class" data-testid="class-switcher">
      {classes.map((entry) => {
        const active = entry.id === current
        return (
          <a
            key={entry.id}
            href={`#/${entry.id}`}
            className="class-chip"
            style={{ '--class-colour': CLASS_COLOUR[entry.id] ?? 'var(--gold)' } as React.CSSProperties}
            data-testid={`class-chip-${entry.id}`}
            data-active={active}
            aria-current={active ? 'page' : undefined}
            title={`${entry.className} - starts an empty build`}
          >
            <span className="class-chip-initial" aria-hidden="true">
              {entry.className.slice(0, 2)}
            </span>
            <span className="sr-only">{entry.className}</span>
          </a>
        )
      })}
    </nav>
  )
}

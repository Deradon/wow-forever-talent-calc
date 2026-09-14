import { lazy, Suspense, useEffect, useState } from 'react'
import { aboutHash, changesHash, parseHash, racesHash, spellsHash, type Route } from './url/route'
import { ClassPicker, REPO_URL } from './ui/ClassPicker'
import { ShortcutsOverlay } from './ui/ShortcutsOverlay'
import facts from './data/facts.json'
import { checkedLine, SOURCE_LINE } from './ui/trust'

/**
 * The review route is reviewer-only and drags in the registry of all 971 frame
 * crops (data/crops.ts, ~92 kB of paths). Loading it lazily keeps that out of
 * every player's first load (performance review P-2).
 */
/**
 * The calculator itself. Lazy like every other route, and for the same reason
 * the review route is: its stylesheet is 20 kB of tree grid, cell, tooltip and
 * summary-column rules that the landing page, `#/changes`, `#/races` and
 * `#/spells` never draw, and it used to sit in the entry sheet on the critical
 * path of all of them (performance review R-2). The class data is a separate
 * lazy chunk already, so a class page fetches this one alongside it.
 */
const ClassPage = lazy(() => import('./ui/ClassPage').then((m) => ({ default: m.ClassPage })))

const ReviewPage = lazy(() => import('./ui/ReviewPage').then((m) => ({ default: m.ReviewPage })))

/**
 * `#/changes` is a second page with its own table, list and stylesheet, and a
 * player who came for the calculator never opens it. Same deal as the review
 * route: its own chunk, fetched when the route is asked for.
 */
const ChangesPage = lazy(() => import('./ui/ChangesPage').then((m) => ({ default: m.ChangesPage })))

/**
 * `#/races` and `#/races/<race>`: the race/class matrix, the racial traits and
 * the crops they were read from. Same arrangement as `#/changes` - its own
 * chunk, its own stylesheet, its own generated index - so the calculator route
 * carries none of it.
 */
const RacesPage = lazy(() => import('./ui/RacesPage').then((m) => ({ default: m.RacesPage })))

/**
 * `#/spells` and `#/spells/<class>`: the spellbook as the stream showed it.
 * Lazy for the usual reason, and for one more - the spellbook crops are 14 MB,
 * so the class page pulls its own crop URLs one class at a time through
 * `spellCrop.ts` and no other route ever touches them.
 */
const SpellsPage = lazy(() => import('./ui/SpellsPage').then((m) => ({ default: m.SpellsPage })))

/**
 * `#/about`: three paragraphs and three links, reached from the footer of every
 * page. Lazy for the same reason as the rest - a visitor who came to spend
 * talent points should not download it to see the link.
 */
const AboutPage = lazy(() => import('./ui/AboutPage').then((m) => ({ default: m.AboutPage })))

function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash))
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export default function App() {
  const route = useRoute()

  /**
   * Embed mode (brief idea 16): `#/<class>?embed=1` in an iframe on a forum or
   * a wiki. Everything that is site chrome rather than calculator - the site
   * title, the caveat line, the shortcut overlay, the licence footer - is gone,
   * because in an iframe it is either repeated furniture or a dead end. The
   * page itself then drops its own header and summary column and shows a
   * compact points line and a link back out, on the class page.
   */
  if (route.kind === 'class' && route.embed) {
    return (
      <div className="app-shell embed-shell px-3 py-3" data-testid="embed-shell">
        <main id="main" tabIndex={-1}>
          <Suspense fallback={<div className="panel p-4 text-[var(--text-dim)]">Loading...</div>}>
            <ClassPage key={route.classId} classId={route.classId} version={route.version} buildString={route.build} sel={route.sel} embed />
          </Suspense>
        </main>
      </div>
    )
  }

  return (
    <div className="app-shell px-4 py-4">
      {/* preventDefault: the app routes on the hash, so #main must not land in it. */}
      <a
        className="skip-link"
        href="#main"
        onClick={(e) => {
          e.preventDefault()
          document.getElementById('main')?.focus()
        }}
      >
        Skip to the talent trees
      </a>
      <nav className="app-nav mb-4 flex items-baseline justify-between gap-4">
        <a href="#/" className="serif text-xl font-semibold text-[var(--gold)] no-underline">
          WoW Forever Talents
        </a>
        <span className="app-nav-right text-xs text-[var(--text-dim)]">
          {/* The pages that are not the calculator; everything else is one
              class away from the picker. */}
          <a href={changesHash()} data-testid="nav-changes">
            Changes
          </a>
          {' · '}
          <a href={racesHash()} data-testid="nav-races">
            Races
          </a>
          {' · '}
          <a href={spellsHash()} data-testid="nav-spells">
            Spells
          </a>
          {' · '}
          Classic+ talent calculator, unofficial
          <ShortcutsOverlay />
        </span>
      </nav>
      <main id="main" tabIndex={-1}>
        <Suspense fallback={<div className="panel p-4 text-[var(--text-dim)]">Loading...</div>}>
          <Body route={route} />
        </Suspense>
      </main>
      <footer className="app-footer mt-8 text-xs text-[var(--text-dim)]">
        Not affiliated with or endorsed by Blizzard Entertainment. World of Warcraft, talent names, descriptions, icons
        and screenshots are property of Blizzard Entertainment. {SOURCE_LINE} {checkedLine(facts.talents, 'talents')} Code
        MIT,{' '}
        <a href={REPO_URL} target="_blank" rel="noreferrer">
          source on GitHub
        </a>
        .{' '}
        <a href={aboutHash()} data-testid="footer-about">
          About this calculator
        </a>
        .
      </footer>
    </div>
  )
}

function Body({ route }: { route: Route }) {
  switch (route.kind) {
    case 'picker':
      return <ClassPicker />
    case 'class':
      return (
        <ClassPage
          key={route.classId}
          classId={route.classId}
          version={route.version}
          buildString={route.build}
          sel={route.sel}
        />
      )
    case 'changes':
      return <ChangesPage key={route.classId ?? ''} classId={route.classId} />
    case 'races':
      return <RacesPage key={route.raceId ?? ''} raceId={route.raceId} variant={route.variant} />
    case 'spells':
      return <SpellsPage key={route.classId ?? ''} classId={route.classId} />
    case 'about':
      return <AboutPage />
    case 'review':
      return <ReviewPage classId={route.classId} />
    default:
      return (
        <div className="panel p-4">
          Unknown route <code>{route.hash}</code>. <a href="#/">Pick a class</a>.
        </div>
      )
  }
}

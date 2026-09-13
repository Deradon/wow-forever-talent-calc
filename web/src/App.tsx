import { lazy, Suspense, useEffect, useState } from 'react'
import { parseHash, type Route } from './url/route'
import { ClassPicker, REPO_URL } from './ui/ClassPicker'
import { ClassPage } from './ui/ClassPage'
import { ShortcutsOverlay } from './ui/ShortcutsOverlay'

/**
 * The review route is reviewer-only and drags in the registry of all 971 frame
 * crops (data/crops.ts, ~92 kB of paths). Loading it lazily keeps that out of
 * every player's first load (performance review P-2).
 */
const ReviewPage = lazy(() => import('./ui/ReviewPage').then((m) => ({ default: m.ReviewPage })))

/**
 * `#/changes` is a second page with its own table, list and stylesheet, and a
 * player who came for the calculator never opens it. Same deal as the review
 * route: its own chunk, fetched when the route is asked for.
 */
const ChangesPage = lazy(() => import('./ui/ChangesPage').then((m) => ({ default: m.ChangesPage })))

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
          <ClassPage key={route.classId} classId={route.classId} version={route.version} buildString={route.build} sel={route.sel} embed />
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
          Classic+ talent calculator - unofficial, unreviewed data
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
        and frame crops are property of Blizzard Entertainment. Data read from BlizzCon 2026 demo footage, unreviewed.
        Code MIT,{' '}
        <a href={REPO_URL} target="_blank" rel="noreferrer">
          source on GitHub
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

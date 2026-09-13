import { useEffect, useState } from 'react'
import { parseHash, type Route } from './url/route'
import { ClassPicker, REPO_URL } from './ui/ClassPicker'
import { ClassPage } from './ui/ClassPage'
import { ReviewPage } from './ui/ReviewPage'

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
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-4">
      <nav className="mb-4 flex items-baseline justify-between gap-4">
        <a href="#/" className="serif text-xl font-semibold text-[var(--gold)] no-underline">
          WoW Forever Talents
        </a>
        <span className="text-xs text-[var(--text-dim)]">Classic+ talent calculator, data read from BlizzCon 2026 footage</span>
      </nav>
      <Body route={route} />
      <footer className="mt-8 text-xs text-[var(--text-dim)]">
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
      return <ClassPage key={route.classId} classId={route.classId} version={route.version} buildString={route.build} />
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

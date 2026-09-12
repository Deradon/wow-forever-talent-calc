import { displayName, listClasses } from '../data/load'

export function ClassPicker() {
  const classes = listClasses()
  return (
    <div className="panel p-5">
      <h1 className="serif mb-3 text-lg text-[var(--gold)]">Choose a class</h1>
      {classes.length === 0 ? (
        <p className="text-[var(--text-dim)]">
          No class data yet. Real classes appear here as they pass review; run the dev server to see the example class.
        </p>
      ) : (
        <ul className="flex flex-wrap gap-3">
          {classes.map((c) => (
            <li key={c.id}>
              <a href={`#/${c.id}`} className="btn inline-block no-underline" data-testid={`class-${c.id}`}>
                {displayName(c.id)}
                {c.origin !== 'talents' && <span className="ml-2 text-xs text-[var(--text-dim)]">example</span>}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

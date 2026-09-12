import type { Page } from '../data/schema'

interface Props {
  pages: Page[]
  active: string
  counts: Record<string, number>
  budgets?: Record<string, number>
  onSelect: (id: string) => void
}

/** Rendered only when a class has more than one page. */
export function PageTabs({ pages, active, counts, budgets, onSelect }: Props) {
  if (pages.length <= 1) return null
  const activePage = pages.find((p) => p.id === active)
  return (
    <div className="mb-3">
      <div role="tablist" className="flex gap-1">
        {pages.map((p) => (
          <button
            key={p.id}
            role="tab"
            aria-selected={p.id === active}
            className="tab"
            data-testid={`page-${p.id}`}
            onClick={() => onSelect(p.id)}
          >
            {p.name}
            <span className="ml-2 text-xs opacity-80">
              {counts[p.id] ?? 0}
              {budgets?.[p.id] !== undefined ? ` / ${budgets[p.id]}` : ''}
            </span>
          </button>
        ))}
      </div>
      {activePage?.note && <div className="mt-1 text-xs text-[var(--text-dim)]">{activePage.note}</div>}
    </div>
  )
}

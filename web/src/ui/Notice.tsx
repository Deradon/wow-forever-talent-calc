import type { Notice as NoticeData } from '../url/codec'

export function Notices({ notices, onDismiss }: { notices: NoticeData[]; onDismiss: () => void }) {
  if (notices.length === 0) return null
  return (
    <div className="mb-3 flex flex-col gap-2" data-testid="notices">
      {notices.map((n, i) => (
        <div key={i} className="notice flex items-start justify-between gap-3" data-notice={n.kind}>
          <div>
            <strong>{n.kind === 'adjusted' ? 'Build adjusted. ' : ''}</strong>
            {n.message}
            {n.violations && n.violations.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-xs opacity-80">
                {n.violations.slice(0, 8).map((v, j) => (
                  <li key={j}>
                    {v.treeId}/{v.talentId}: {v.reason}
                    {v.detail ? ` (${v.detail})` : ''}
                  </li>
                ))}
                {n.violations.length > 8 && <li>and {n.violations.length - 8} more</li>}
              </ul>
            )}
          </div>
          <button className="btn text-xs" onClick={onDismiss} aria-label="Dismiss notices">
            Dismiss
          </button>
        </div>
      ))}
    </div>
  )
}

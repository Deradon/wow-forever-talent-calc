/**
 * One sentence of a Classic-vs-Forever diff, labelled, with the diff as
 * emphasis inside it.
 *
 * Its own module rather than a helper in `ChangesPage`: the tooltip's nested
 * card renders the same two lines, and `ChangesPage` is a lazy route whose
 * chunk the calculator must never pull in (performance review R-2/K-17).
 */
export function DiffLine({
  label,
  runs,
  side,
  talentId,
}: {
  label: string
  runs: [string, string][]
  side: 'classic' | 'forever'
  talentId?: string
}) {
  if (runs.length === 0) return null
  return (
    <p
      className={`classic-line classic-line-${side} classic-text`}
      data-testid={talentId ? `diff-${side}-${talentId}` : undefined}
    >
      <span className="classic-line-label">{label}</span>
      {runs.map(([op, run], i) => (
        <span key={i} className={op === '-' ? 'diff-del' : op === '+' ? 'diff-add' : undefined}>
          {i > 0 ? ' ' : ''}
          {run}
        </span>
      ))}
    </p>
  )
}

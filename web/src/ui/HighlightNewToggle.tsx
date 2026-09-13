import { setHighlightNew, useHighlightNew } from './highlightNew'
import { changedCount, hasClassicDiff } from './classicDiff'

/**
 * "What's new" switch: dims talents unchanged since Classic across all trees of
 * the class, so it lives with the class-level controls, not inside a tree.
 */
export function HighlightNewToggle({ classId }: { classId: string }) {
  const highlight = useHighlightNew()
  if (!hasClassicDiff(classId)) return null
  return (
    <button
      type="button"
      className="new-toggle"
      data-testid="highlight-new"
      aria-pressed={highlight}
      title={`Dim the talents that are unchanged since Classic (${changedCount(classId)} changed)`}
      onClick={() => setHighlightNew(!highlight)}
    >
      <span aria-hidden="true">&#9733;</span> What's new
    </button>
  )
}

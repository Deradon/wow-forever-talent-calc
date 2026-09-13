import { setHighlightNew, useHighlightNew } from './highlightNew'
import { changedCount, hasClassicDiff } from './classicDiff'

/**
 * "What's new" switch: dims talents unchanged since Classic across all trees of
 * the class, so it lives with the class-level controls, not inside a tree.
 *
 * It is a `.btn` like Search's neighbours Reset and the summary buttons - it
 * used to be a smaller, differently coloured chip left over from the tree panel
 * header it started in, which made the one control row look like two. The blue
 * only appears when it is on, where it means the same blue as the cell markers.
 */
export function HighlightNewToggle({ classId }: { classId: string }) {
  const highlight = useHighlightNew()
  if (!hasClassicDiff(classId)) return null
  return (
    <button
      type="button"
      className="btn new-toggle"
      data-testid="highlight-new"
      aria-pressed={highlight}
      title={`Dim the talents that are unchanged since Classic (${changedCount(classId)} changed)`}
      onClick={() => setHighlightNew(!highlight)}
    >
      <span className="new-toggle-star" aria-hidden="true">
        &#9733;
      </span>{' '}
      What's new
    </button>
  )
}

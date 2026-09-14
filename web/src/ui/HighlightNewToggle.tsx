import { setHighlightNew, useHighlightNew } from './highlightNew'
import { changedCount, hasClassicDiff } from './classicDiff'

/**
 * "Highlight changes" switch: dims talents unchanged since Classic across all
 * trees of the class, so it lives with the class-level controls, not inside a
 * tree.
 *
 * It was called "What's new" and rang every changed cell in one blue, which
 * promised `new` and delivered `changed` (UX review round two, finding 9). The
 * name now says what it does; which kind of change a cell had is the cell's own
 * marker and ring colour.
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
      Highlight changes
    </button>
  )
}

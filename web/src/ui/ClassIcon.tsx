import { useState } from 'react'
import { classIconUrl } from './classIcon'

/**
 * The class crest, with the two-letter initials as the fallback for both
 * "we have no icon for this class" and "the file did not load". Dropping
 * `web/public/icons/` therefore degrades the chips and the cards rather than
 * breaking them, which is the escape hatch `data/icons/SOURCES.md` promises.
 *
 * Always `aria-hidden`: every caller puts the class name next to it, either as
 * visible text or as a `sr-only` span, so a second announcement would only
 * repeat it.
 */
export function ClassIcon({ classId, className, size = 24 }: { classId: string; className: string; size?: number }) {
  const [failed, setFailed] = useState(false)
  const url = classIconUrl(classId)
  const style = { width: `${size}px`, height: `${size}px` }
  if (url === undefined || failed) {
    return (
      <span className="class-icon class-icon-fallback" style={style} aria-hidden="true">
        {className.slice(0, 2)}
      </span>
    )
  }
  return (
    <img
      className="class-icon"
      src={url}
      style={style}
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      draggable={false}
      onError={() => setFailed(true)}
    />
  )
}

import { useEffect, useRef, type ReactNode } from 'react'

/**
 * The dialog shell: a fixed backdrop, a centred panel, focus in on open, Tab
 * trapped inside, Escape and a backdrop press to close, focus back to whatever
 * opened it.
 *
 * It was the shortcuts overlay's private code until the round-two UX review
 * (finding 4) asked for the import panel to stop living in the 320 px summary
 * column, where a pasted Wowhead URL wrapped across three lines and the dropped
 * list pushed the page far below the fold. Two dialogs, one shell - a second
 * focus trap is exactly the duplication the code review keeps finding.
 */
const FOCUSABLE = 'a[href], button:not([disabled]), input, textarea, select, [tabindex]:not([tabindex="-1"])'

interface Props {
  title: string
  titleId: string
  /** CSS width for the panel; the shortcuts list is wider than the import box. */
  width?: string
  /** `<base>-backdrop`, `<base>-dialog` and `<base>-close` test ids. */
  idBase: string
  onClose: () => void
  children: ReactNode
  foot?: ReactNode
}

export function Modal({ title, titleId, width, idBase, onClose, children, foot }: Props) {
  const dialog = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const root = dialog.current
    root?.querySelector<HTMLElement>(FOCUSABLE)?.focus()
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab' || !root) return
      const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.offsetParent !== null)
      if (items.length === 0) return
      const first = items[0]!
      const last = items[items.length - 1]!
      const active = document.activeElement
      if (e.shiftKey && (active === first || !root.contains(active))) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [onClose])

  return (
    <div className="modal-backdrop" data-testid={`${idBase}-backdrop`} onPointerDown={onClose}>
      <div
        ref={dialog}
        className="panel modal-dialog"
        style={width ? { width } : undefined}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-testid={`${idBase}-dialog`}
        onPointerDown={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h2 className="serif text-lg text-[var(--gold)]" id={titleId}>
            {title}
          </h2>
          <button type="button" className="btn" data-testid={`${idBase}-close`} onClick={onClose}>
            Close
          </button>
        </div>
        {children}
        {foot}
      </div>
    </div>
  )
}

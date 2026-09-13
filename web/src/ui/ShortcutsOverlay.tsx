import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * The keyboard-shortcut overlay (brief `docs/briefs/ui-improvements.md`, idea
 * 14). Round 1 gave the calculator a keyboard and a set of modifier gestures
 * and then documented them in an empty summary column and a hint line under the
 * trees - both of which disappear the moment a build exists. `?` is where a
 * player looks, so `?` is where the list lives.
 *
 * It is a dialog, not a panel: focus moves in on open, Tab cycles inside it,
 * Escape closes it and focus goes back to whatever opened it.
 */

interface Shortcut {
  keys: string[]
  what: string
  /** Chords that only make sense with a talent under the pointer or focused. */
  where?: string
}

const GROUPS: { title: string; items: Shortcut[] }[] = [
  {
    title: 'Spending points',
    items: [
      { keys: ['Click'], what: 'Add one point', where: 'talent' },
      { keys: ['Right click'], what: 'Refund one point', where: 'talent' },
      { keys: ['Shift', 'Click'], what: 'Fill to the last rank', where: 'talent' },
      { keys: ['Ctrl', 'Click'], what: 'Empty the talent (Alt works too)', where: 'talent' },
    ],
  },
  {
    title: 'Keyboard in a tree',
    items: [
      { keys: ['Arrows'], what: 'Move between talents' },
      { keys: ['Home', 'End'], what: 'First and last talent of the tree' },
      { keys: ['Enter'], what: 'Add a point (Space too)' },
      { keys: ['Shift', 'Enter'], what: 'Fill to the last rank' },
      { keys: ['Backspace'], what: 'Refund a point (Delete, - too)' },
      { keys: ['Shift', 'Backspace'], what: 'Empty the talent' },
    ],
  },
  {
    title: 'Reading and finding',
    items: [
      { keys: ['/'], what: 'Jump to the search box' },
      { keys: ['Esc'], what: 'Clear the search, or close a tooltip or this dialog' },
      { keys: ['d'], what: 'Show where a tooltip’s numbers were read from', where: 'tooltip open' },
      { keys: ['?'], what: 'Open and close this list' },
    ],
  },
  {
    title: 'Undoing',
    items: [
      { keys: ['Ctrl', 'Z'], what: 'Undo, a Reset included' },
      { keys: ['Ctrl', 'Shift', 'Z'], what: 'Redo' },
    ],
  },
]

const FOCUSABLE = 'a[href], button:not([disabled]), input, [tabindex]:not([tabindex="-1"])'

/** True when the key event came from somewhere that owns its own keystrokes. */
function inTextEntry(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  return Boolean(el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)))
}

export function ShortcutsOverlay() {
  const [open, setOpen] = useState(false)
  const dialog = useRef<HTMLDivElement>(null)
  const opener = useRef<HTMLElement | null>(null)
  const close = useCallback(() => setOpen(false), [])

  // `?` is Shift+/ on most layouts and AltGr+something on others, so the key
  // value is what is checked, never the physical code.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== '?' || e.ctrlKey || e.metaKey) return
      if (inTextEntry(e.target)) return
      e.preventDefault()
      setOpen((v) => {
        if (!v) opener.current = document.activeElement as HTMLElement | null
        return !v
      })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Focus in on open, back to the opener on close, and Tab stays inside.
  useEffect(() => {
    if (!open) {
      opener.current?.focus?.()
      return
    }
    const root = dialog.current
    root?.querySelector<HTMLElement>(FOCUSABLE)?.focus()
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        setOpen(false)
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
  }, [open])

  return (
    <>
      <button
        type="button"
        className="shortcuts-open"
        data-testid="shortcuts-open"
        aria-haspopup="dialog"
        aria-expanded={open}
        title="Keyboard shortcuts (?)"
        onClick={(e) => {
          opener.current = e.currentTarget
          setOpen((v) => !v)
        }}
      >
        ?
      </button>
      {open && (
        <div className="shortcuts-backdrop" data-testid="shortcuts-backdrop" onPointerDown={close}>
          <div
            ref={dialog}
            className="panel shortcuts-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="shortcuts-title"
            data-testid="shortcuts-dialog"
            onPointerDown={(e) => e.stopPropagation()}
          >
            <div className="shortcuts-head">
              <h2 className="serif text-lg text-[var(--gold)]" id="shortcuts-title">
                Keyboard and mouse
              </h2>
              <button type="button" className="btn" data-testid="shortcuts-close" onClick={close}>
                Close
              </button>
            </div>
            <div className="shortcuts-groups">
              {GROUPS.map((group) => (
                <section key={group.title}>
                  <h3 className="shortcuts-group-title">{group.title}</h3>
                  <dl className="shortcuts-list">
                    {group.items.map((item) => (
                      <div key={item.what} className="shortcuts-item">
                        <dt>
                          {item.keys.map((k, i) => (
                            <span key={k}>
                              {i > 0 && <span className="shortcuts-plus">+</span>}
                              <kbd>{k}</kbd>
                            </span>
                          ))}
                        </dt>
                        <dd>
                          {item.what}
                          {item.where && <span className="shortcuts-where"> ({item.where})</span>}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ))}
            </div>
            <p className="shortcuts-foot">Press Escape or ? to close.</p>
          </div>
        </div>
      )}
    </>
  )
}

import { useEffect, useState } from 'react'

/**
 * Copy-to-clipboard with a two-second confirmation and a `failed` state, so a
 * page can offer a select-me textarea when the clipboard is not available
 * (plain http, a locked-down browser, an iframe without the permission).
 *
 * `BuildSummary.tsx` still carries the original of this hook; it should import
 * this one the next time it is touched.
 */
export type CopyState = 'idle' | 'copied' | 'failed'

export function useCopy(): [CopyState, (text: string) => void] {
  const [state, setState] = useState<CopyState>('idle')
  useEffect(() => {
    if (state === 'idle') return
    const t = window.setTimeout(() => setState('idle'), 2000)
    return () => window.clearTimeout(t)
  }, [state])
  return [
    state,
    (text: string) => {
      // No clipboard object at all over plain http, so the fallback has to
      // survive a throw as well as a rejection.
      try {
        navigator.clipboard.writeText(text).then(
          () => setState('copied'),
          () => setState('failed'),
        )
      } catch {
        setState('failed')
      }
    },
  ]
}

export function copyLabel(state: CopyState, idle: string): string {
  return state === 'copied' ? 'Copied!' : state === 'failed' ? 'Copy failed' : idle
}

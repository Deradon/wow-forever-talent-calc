import { useEffect } from 'react'
import { summarizeNotices, type Notice as NoticeData } from '../url/codec'

/**
 * The one bar a player sees when a shared link did not survive the current
 * trees. It is deliberately a summary: encoding positions (`arms #18`), talent
 * slugs, rule reasons and the word "clamped" are internal, and a truncated or
 * hand-edited link used to stack three bars of them above the trees (UX review
 * round two, finding 1). They now go to the console, once per link, for
 * whoever is debugging the link rather than reading the build.
 */
export function Notices({ notices, onDismiss }: { notices: NoticeData[]; onDismiss: () => void }) {
  const summary = summarizeNotices(notices)
  const detail = summary?.detail.join('\n')

  useEffect(() => {
    if (detail) console.info(`[build link] ${detail}`)
  }, [detail])

  if (!summary) return null
  return (
    <div className="mb-3 flex flex-col gap-2" data-testid="notices">
      <div className="notice flex items-start justify-between gap-3" data-notice={summary.kind}>
        <div data-testid="notice-message">{summary.message}</div>
        <button className="btn text-xs" onClick={onDismiss} aria-label="Dismiss notice">
          Dismiss
        </button>
      </div>
    </div>
  )
}

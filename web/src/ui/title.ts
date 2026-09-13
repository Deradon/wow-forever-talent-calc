import { useEffect } from 'react'

export const SITE_TITLE = 'WoW Forever Talent Calculator'

/** Sets document.title while the component is mounted. */
export function useTitle(title: string | undefined): void {
  useEffect(() => {
    if (title) document.title = title
  }, [title])
}

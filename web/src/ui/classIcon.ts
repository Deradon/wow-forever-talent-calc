/**
 * The Blizzard class colours; anything not in the list falls back to gold.
 * The nine keys are also exactly the classes we hold a `classicon_*.jpg` for,
 * so an example class (the fictional tinker) gets neither a colour nor an icon
 * and keeps the initials it always had.
 */
export const CLASS_COLOUR: Record<string, string> = {
  druid: '#ff7d0a',
  hunter: '#abd473',
  mage: '#69ccf0',
  paladin: '#f58cba',
  priest: '#ffffff',
  rogue: '#fff569',
  shaman: '#0070de',
  warlock: '#9482c9',
  warrior: '#c79c6e',
}

/**
 * Blizzard's shaman blue is 1.8:1 against the chip background - unreadable as
 * text, fine as a border or a crest ring. Only that one class needs the
 * override; the other eight clear 4.5:1 on `#141a2c` unchanged.
 */
const CLASS_TEXT: Record<string, string> = { shaman: '#3f9bff' }

export function classColour(classId: string): string {
  return CLASS_COLOUR[classId] ?? 'var(--gold)'
}

export function classTextColour(classId: string): string {
  return CLASS_TEXT[classId] ?? classColour(classId)
}

/**
 * `web/public/icons/classicon_<class>.jpg`, fetched by hand rather than by
 * stage 9 - see `web/public/icons/CLASS-ICONS.md` for the source and the
 * licensing pointer. BASE_URL matters: GitHub Pages serves the app from
 * `/<repo>/`.
 */
export function classIconUrl(classId: string): string | undefined {
  if (!(classId in CLASS_COLOUR)) return undefined
  return `${import.meta.env.BASE_URL}icons/classicon_${classId}.jpg`
}

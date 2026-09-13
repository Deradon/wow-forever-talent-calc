import { useEffect, useState } from 'react'
import spellsIndexJson from '../data/spells-index.json'
import { displayName } from '../data/load'
import type { Spell, SpellData, SpellTooltip } from '../data/schema.spells'
import { hasSpells, loadSpells } from '../data/spells'
import { loadSpellCrops, spellCropUrl, type SpellCrops } from '../data/spellCrop'
import { spellsHash } from '../url/route'
import { ClassIcon } from './ClassIcon'
import { classColour } from './classIcon'
import {
  absentLine,
  cardCountLine,
  cardGapLine,
  coverageLine,
  hasText,
  initials,
  isNew,
  kindLabel,
  levelLine,
  NEW_CAVEAT,
  overviewCards,
  playerNotes,
  rankLabel,
  ranksLine,
  spellGroups,
  spellStamp,
  spellTrustLine,
  spellTrustLines,
  tooltipFacts,
  tooltipRankLine,
  tooltipReadLine,
  type OverviewCard,
  type SpellsIndex,
} from './spellsModel'
import { SITE_TITLE, useTitle } from './title'
import './spells.css'

/**
 * `#/spells` and `#/spells/<class>` - Phase 2d's web half (brief
 * `docs/briefs/beyond-talents.md`, spec in
 * `docs/handover/2026-09-13-spells-data.md` section 5).
 *
 * The page is scoped the way section 6 of that handover asks: **spells seen on
 * stream**, with the coverage record in the header rather than in a footnote.
 * The lists are one level-38 demo character's spellbook, filtered by which tabs
 * happened to be opened, and a page that let a reader mistake that for the
 * game's spell list would be worse than no page.
 *
 * `#/spells` runs off the generated `spells-index.json` alone - no spell file,
 * no crop. `#/spells/<class>` fetches one class file plus that class's crop
 * module, and nothing else in the app ever touches the 14 MB of spellbook
 * crops (`spellCrop.ts`).
 */
export function SpellsPage({ classId }: { classId?: string }) {
  return classId ? <OneClass classId={classId} /> : <Overview />
}

const index = spellsIndexJson as SpellsIndex

// --- the overview ----------------------------------------------------------

function Overview() {
  useTitle(`Spells seen on stream - ${SITE_TITLE}`)
  const cards = overviewCards(index)
  const absent = absentLine(index)

  return (
    <div className="spells-page" data-testid="spells-overview">
      <SpellsHead />
      <p className="spells-lead">
        What the BlizzCon demo's spellbook showed, class by class: the entries that were on screen and the full text of
        every spell that was hovered. Each book belongs to one level-38 character, so a page here is a record of what
        was shown, not a list of what the class has.
      </p>
      <ul className="spells-cards" data-testid="spells-cards">
        {cards.map((card) => (
          <ClassCard key={card.id} card={card} />
        ))}
      </ul>
      {absent && (
        <p className="spells-absent" data-testid="spells-absent">
          {absent}
        </p>
      )}
      <ul className="spells-notes">
        <li>{NEW_CAVEAT}</li>
      </ul>
    </div>
  )
}

function ClassCard({ card }: { card: OverviewCard }) {
  const gap = cardGapLine(card)
  return (
    <li className="panel spells-card" data-testid={`spells-card-${card.id}`}>
      <a
        className="spells-card-title"
        href={card.href}
        style={{ '--class-colour': classColour(card.id) } as React.CSSProperties}
      >
        <ClassIcon classId={card.id} className={card.className} size={34} />
        <span className="serif text-base">{card.className}</span>
        {card.new > 0 && (
          <span className="spells-chip" data-testid={`spells-card-new-${card.id}`}>
            {card.new} new
          </span>
        )}
      </a>
      <p className="spells-card-counts" data-testid={`spells-card-counts-${card.id}`}>
        {cardCountLine(card)}
      </p>
      <p className="spells-card-tabs">{card.tabs.join(', ')}</p>
      {/* The gap is the point of the overview, so it is not a footnote either. */}
      {gap && (
        <p className="spells-card-gap" data-testid={`spells-card-gap-${card.id}`}>
          {gap}
        </p>
      )}
    </li>
  )
}

// --- one class -------------------------------------------------------------

function OneClass({ classId }: { classId: string }) {
  const [data, setData] = useState<SpellData>()
  const [crops, setCrops] = useState<SpellCrops>({})
  const [error, setError] = useState<string>()

  useEffect(() => {
    let alive = true
    if (!hasSpells(classId)) {
      // Priest is the one class the stream never opened, so this is a real
      // answer rather than a 404 - the overview says the same thing.
      setError(`${displayName(classId)}'s spellbook was never on screen, so there is nothing to show.`)
      return
    }
    setError(undefined)
    // The crop URLs ride along with the class file; both are one chunk each.
    Promise.all([loadSpells(classId), loadSpellCrops(classId)])
      .then(([d, c]) => {
        if (!alive) return
        setData(d)
        setCrops(c)
      })
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      alive = false
    }
  }, [classId])

  useTitle(data ? `${data.className} spells seen on stream - ${SITE_TITLE}` : undefined)

  if (error) {
    return (
      <div className="panel p-4">
        <p className="text-[var(--text-dim)]" data-testid="spells-error">
          {error}
        </p>
        <a href={spellsHash()}>All classes</a>
      </div>
    )
  }
  if (!data) return <div className="panel p-4 text-[var(--text-dim)]">Loading {displayName(classId)}...</div>

  const groups = spellGroups(data)
  const trust = spellTrustLines(data.spells)
  const anyNew = data.spells.some(isNew)

  return (
    <div className="spells-page" data-testid={`spells-${data.class}`}>
      <SpellsHead classId={data.class} />
      <div className="panel spells-intro">
        <div className="spells-title-row">
          <ClassIcon classId={data.class} className={data.className} size={36} />
          <h2 className="serif text-xl text-[var(--gold)]" data-testid="spells-title">
            {data.className}
          </h2>
          <span className="spells-level">level {data.observedLevel}</span>
          {/* The calculator is the rest of the site; a spell page is where a
              player wonders what the class's talents do. */}
          <a className="spells-talents-link" href={`#/${data.class}`} data-testid="spells-talents-link">
            {data.className} talents
          </a>
        </div>

        {/* Rule 1: the coverage record is the header, not a footnote. */}
        <p className="spells-coverage" data-testid="spells-coverage">
          {coverageLine(data)}
        </p>
        <p className="spells-trust" data-testid="spells-trust">
          {trust.join(' ')}
        </p>

        <ul className="spells-notes" data-testid="spells-caveats">
          <li>{levelLine(data)}</li>
          <li>{ranksLine(data)}</li>
          {/* Rule 7: one caveat for the New chip, at the top, never per row. */}
          {anyNew && <li data-testid="spells-new-caveat">{NEW_CAVEAT}</li>}
          {playerNotes(data.notes).map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </div>

      {groups.map((group) => (
        <section className="panel spells-group" key={group.id} data-testid={`spells-group-${group.id}`}>
          <h3 className="spells-group-head serif text-base text-[var(--gold)]">
            {group.name}
            <span className="spells-group-count">
              {group.spells.length} {group.spells.length === 1 ? 'entry' : 'entries'}
            </span>
          </h3>
          <ul className="spells-list">
            {group.spells.map((spell) => (
              <SpellRow key={spell.id} spell={spell} crops={crops} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function SpellRow({ spell, crops }: { spell: Spell; crops: SpellCrops }) {
  const iconUrl = spellCropUrl(crops, spell.iconCrop)
  const rank = rankLabel(spell)
  const kind = kindLabel(spell.kind)
  const trust = spellTrustLine(spell)
  const tooltips = spell.tooltips ?? []

  return (
    <li className="spells-row" data-testid={`spell-${spell.id}`} data-kind={spell.kind}>
      <div className="spells-row-head">
        {iconUrl ? (
          <img className="spells-icon" src={iconUrl} width={32} height={32} alt="" aria-hidden="true" />
        ) : (
          <span className="spells-icon spells-icon-fallback" aria-hidden="true">
            {initials(spell.name)}
          </span>
        )}
        <span className="spells-name">{spell.name}</span>
        {rank && <span className="spells-rank">{rank}</span>}
        {kind && <span className="spells-kind">{kind}</span>}
        {isNew(spell) && (
          <span className="spells-chip" data-testid={`spell-new-${spell.id}`}>
            New
          </span>
        )}
        {trust && <span className="spells-trust-line">{trust}</span>}
      </div>
      {/* A row whose tooltip was never hovered shows nothing extra: "no text"
          on 215 of 327 rows would be the loudest thing on the page. */}
      {hasText(spell) && (
        <details className="spells-text" data-testid={`spell-text-${spell.id}`}>
          <summary>
            Full text
            {tooltips.length > 1 && <span className="spells-readings"> ({tooltips.length} readings)</span>}
          </summary>
          {tooltips.map((tooltip, i) => (
            <TooltipCard key={`${spell.id}-${i}`} tooltip={tooltip} crops={crops} />
          ))}
        </details>
      )}
    </li>
  )
}

/**
 * One hover tooltip, verbatim. The header lines are rendered as the game's own
 * pairs; the rank line below is rule 4, which forbids letting a tooltip whose
 * rank could not be established read as rank 1.
 */
function TooltipCard({ tooltip, crops }: { tooltip: SpellTooltip; crops: SpellCrops }) {
  const facts = tooltipFacts(tooltip)
  const stamp = spellStamp(tooltip.source)
  const read = tooltipReadLine(tooltip)
  const frameUrl = spellCropUrl(crops, tooltip.source.crop)

  return (
    <div className="spells-tooltip">
      {facts.length > 0 && (
        <dl className="spells-facts">
          {facts.map((fact) => (
            <div key={`${fact.label}-${fact.value}`}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="spells-tooltip-text">{tooltip.description}</p>
      <p className="spells-tooltip-meta">
        {tooltipRankLine(tooltip)} {read}{' '}
        {frameUrl && (
          <a href={frameUrl} target="_blank" rel="noreferrer" data-testid="spell-frame-link">
            The frame it was read from{stamp ? ` (${stamp})` : ''}
          </a>
        )}
      </p>
    </div>
  )
}

function SpellsHead({ classId }: { classId?: string }) {
  return (
    <div className="spells-head">
      <h1 className="serif text-xl text-[var(--gold)]">Spells seen on stream</h1>
      {classId && (
        <a href={spellsHash()} className="spells-all" data-testid="spells-all-link">
          All classes
        </a>
      )}
    </div>
  )
}

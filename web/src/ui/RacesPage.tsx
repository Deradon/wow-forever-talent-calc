import { useEffect, useState } from 'react'
import racesIndexJson from '../data/races-index.json'
import { raceCrestUrl, raceCropUrl } from '../data/raceCrop'
import { hasRace, loadRace } from '../data/races'
import { factionName, type RaceData, type RaceTrait, type RaceVariant } from '../data/schema.races'
import { racesHash } from '../url/route'
import { ClassIcon } from './ClassIcon'
import { classColour } from './classIcon'
import { displayName } from '../data/load'
import {
  activeVariant,
  cellLabel,
  cellState,
  classicCardTitle,
  classicChipHint,
  classicNoteLines,
  CLASSIC_LABEL,
  initials,
  kindLabel,
  matrixRows,
  newComboCount,
  playerNoteLines,
  raceTrustLines,
  traitDetailLines,
  traitStamp,
  traitTrustLine,
  UNVERIFIED,
  variantClasses,
  variantLore,
  variantTraits,
  type MatrixRow,
  type RacesIndex,
} from './racesModel'
import { SITE_TITLE, useTitle } from './title'
import './races.css'

/**
 * `#/races` and `#/races/<race>` - Phase 2b's web half
 * (`docs/briefs/beyond-talents.md` section (d), spec in
 * `docs/handover/2026-09-13-races-data.md` section 5).
 *
 * `#/races` is the race/class matrix: one row per playable identity, one column
 * per class, the combinations Classic Era did not allow marked. It runs off the
 * generated `races-index.json` alone, so the overview never fetches a race
 * file. `#/races/<race>` fetches exactly one, the way a class page fetches one
 * class chunk, and renders its traits as cards.
 *
 * The page is lazily routed in `App.tsx` and brings its own stylesheet, so a
 * player who only ever opens the calculator pays for none of it.
 */
export function RacesPage({ raceId, variant }: { raceId?: string; variant?: string }) {
  return raceId ? <OneRace raceId={raceId} variant={variant} /> : <Matrix />
}

const index = racesIndexJson as RacesIndex

// --- the matrix ------------------------------------------------------------

function Matrix() {
  useTitle(`Races and the class matrix - ${SITE_TITLE}`)
  const rows = matrixRows(index)
  const newCombos = newComboCount(rows)

  return (
    <div className="races-page" data-testid="races-matrix">
      <RacesHeader />
      <p className="races-lead">
        Races and the classes each can play. {newCombos} combinations are new since Classic Era and carry a gold ring.
        Pick a race for its traits, or a cell for that class's calculator.
      </p>
      <Legend />
      <div className="races-table-wrap">
        <table className="races-table" data-testid="races-table">
          <thead>
            <tr>
              <th scope="col">Race</th>
              {index.classes.map((id) => (
                <th scope="col" key={id} title={displayName(id)}>
                  <ClassIcon classId={id} className={displayName(id)} size={22} />
                  <span className="sr-only">{displayName(id)}</span>
                </th>
              ))}
              <th scope="col" className="races-traits-col">
                Traits
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <MatrixRowView key={row.key} row={row} />
            ))}
          </tbody>
        </table>
      </div>
      <ul className="races-notes" data-testid="races-notes">
        <li>
          The Classic Era comparison is <strong>{UNVERIFIED}</strong>: written from memory, not yet checked against a
          database.
        </li>
      </ul>
    </div>
  )
}

function Legend() {
  return (
    <ul className="races-legend" data-testid="races-legend">
      <li>
        <span className="races-cell-sample races-cell-new" aria-hidden="true" />
        new in Forever
      </li>
      <li>
        <span className="races-cell-sample races-cell-yes" aria-hidden="true" />
        playable in Classic Era too
      </li>
      <li>
        <span className="races-cell-sample races-cell-no" aria-hidden="true" />
        not playable
      </li>
    </ul>
  )
}

function MatrixRowView({ row }: { row: MatrixRow }) {
  return (
    <tr data-testid={`races-row-${row.key}`}>
      <th scope="row">
        <a href={row.href} data-testid={`races-link-${row.key}`}>
          <RaceCrest raceId={row.raceId} name={row.name} size={26} />
          <span className="races-row-name">
            {row.name}
            <span className="races-row-faction" data-faction={row.faction}>
              {factionName(row.faction)}
            </span>
          </span>
        </a>
      </th>
      {index.classes.map((classId) => {
        const state = cellState(row, classId)
        const label = cellLabel(row, displayName(classId), state)
        return (
          <td key={classId} data-state={state} data-testid={`races-cell-${row.key}-${classId}`}>
            {state === 'no' ? (
              <span className="races-cell races-cell-no" title={label} aria-hidden="true" />
            ) : state === 'unknown' ? (
              <span className="races-cell races-cell-unknown" title={label}>
                ?
              </span>
            ) : (
              <a
                className={`races-cell races-cell-${state === 'new' ? 'new' : 'yes'}`}
                href={`#/${classId}`}
                title={label}
                style={{ '--class-colour': classColour(classId) } as React.CSSProperties}
              >
                <ClassIcon classId={classId} className={displayName(classId)} size={22} />
                {state === 'new' && <span className="races-cell-flag" aria-hidden="true" />}
              </a>
            )}
            <span className="sr-only">{label}</span>
          </td>
        )
      })}
      <td className="races-traits-col">
        <a href={row.href}>
          {row.traits}
          {row.newTraits > 0 && <span className="races-new-count"> ({row.newTraits} new)</span>}
        </a>
      </td>
    </tr>
  )
}

/**
 * The race's crest, or its initials. There is no crest crop today (stage 12
 * cuts trait icons and the panel, not the portrait ring), so this is the
 * initials branch in practice - see `raceCrestUrl`.
 */
function RaceCrest({ raceId, name, size }: { raceId: string; name: string; size: number }) {
  const url = raceCrestUrl(raceId)
  const style = { width: `${size}px`, height: `${size}px` }
  if (!url) {
    return (
      <span className="race-crest race-crest-fallback" style={style} aria-hidden="true">
        {initials(name)}
      </span>
    )
  }
  return <img className="race-crest" src={url} style={style} width={size} height={size} alt="" aria-hidden="true" />
}

// --- one race --------------------------------------------------------------

function OneRace({ raceId, variant }: { raceId: string; variant?: string }) {
  const [race, setRace] = useState<RaceData>()
  const [error, setError] = useState<string>()

  useEffect(() => {
    let alive = true
    if (!hasRace(raceId)) {
      setError(`Unknown race "${raceId}".`)
      return
    }
    setError(undefined)
    loadRace(raceId)
      .then((r) => alive && setRace(r))
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      alive = false
    }
  }, [raceId])

  const current = race ? activeVariant(race, variant) : undefined
  useTitle(race ? `${current?.name ?? race.raceName} - ${SITE_TITLE}` : undefined)

  if (error) {
    return (
      <div className="panel p-4">
        <p className="text-[var(--red)]" data-testid="races-error">
          {error}
        </p>
        <a href={racesHash()}>All races</a>
      </div>
    )
  }
  if (!race) return <div className="panel p-4 text-[var(--text-dim)]">Loading {raceId}...</div>

  const traits = variantTraits(race, current)
  const classes = variantClasses(race, current)
  const lore = variantLore(race, current)
  const trust = raceTrustLines(traits)

  return (
    <div className="races-page" data-testid={`race-${race.race}`}>
      <RacesHeader raceId={race.race} />
      <div className="panel races-intro">
        <div className="races-title-row">
          <h2 className="serif text-xl text-[var(--gold)]" data-testid="race-title">
            {current?.name ?? race.raceName}
          </h2>
          <span className="races-faction-chip" data-faction={current?.faction ?? race.faction} data-testid="race-faction">
            {factionName(current?.faction ?? race.faction)}
          </span>
        </div>

        {race.variants && <VariantTabs race={race} current={current} />}

        <div className="races-classes" data-testid="race-classes">
          <span className="races-classes-label">Can be</span>
          {classes.length === 0 ? (
            <span className="races-unknown">unknown - this race's class bar was never on screen.</span>
          ) : (
            classes.map((id) => (
              <a
                key={id}
                className="races-class-chip"
                href={`#/${id}`}
                style={{ '--class-colour': classColour(id) } as React.CSSProperties}
                data-testid={`race-class-${id}`}
              >
                <ClassIcon classId={id} className={displayName(id)} size={20} />
                {displayName(id)}
              </a>
            ))
          )}
        </div>

        {/* Rule 2: the source is stated once for the page, not on every card. */}
        <p className="races-trust" data-testid="race-trust">
          {trust.join(' ')}
        </p>

        <ul className="races-notes">
          {!race.complete && (
            <li data-testid="race-incomplete">
              The trait list is incomplete: some rows of the box were never on screen, so a racial may be missing.
            </li>
          )}
          {(race.notes ?? []).map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </div>

      <ul className="races-traits" data-testid="race-traits">
        {traits.map((trait) => (
          <TraitCard key={trait.id} trait={trait} />
        ))}
      </ul>

      {lore && (
        <details className="panel races-lore" data-testid="race-lore">
          <summary>Lore</summary>
          <p>
            {lore.text}
            {!lore.complete && <span className="races-lore-cut"> [the paragraph ran past the edge of the box]</span>}
          </p>
        </details>
      )}
    </div>
  )
}

function VariantTabs({ race, current }: { race: RaceData; current: RaceVariant | undefined }) {
  return (
    <nav className="races-variants" aria-label="Variant" data-testid="race-variants">
      {race.variants!.map((v) => {
        const active = v.id === current?.id
        return (
          <a
            key={v.id}
            href={racesHash(race.race, v.id)}
            className="races-variant"
            data-active={active}
            data-faction={v.faction}
            aria-current={active ? 'page' : undefined}
            data-testid={`race-variant-${v.id}`}
          >
            {v.name}
          </a>
        )
      })}
    </nav>
  )
}

function TraitCard({ trait }: { trait: RaceTrait }) {
  const iconUrl = raceCropUrl(trait.iconCrop)
  const cropUrl = raceCropUrl(trait.source.crop)
  const stamp = traitStamp(trait)
  const trust = traitTrustLine(trait)
  const details = traitDetailLines(trait)
  const status = trait.classic.status
  const classicNote = classicNoteLines(trait.classic.note)

  return (
    <li className="panel races-trait" data-testid={`trait-${trait.id}`} data-kind={trait.kind}>
      <div className="races-trait-head">
        {iconUrl ? (
          <img className="races-trait-icon" src={iconUrl} width={36} height={36} alt="" aria-hidden="true" />
        ) : (
          <span className="races-trait-icon races-trait-icon-fallback" aria-hidden="true">
            {initials(trait.name)}
          </span>
        )}
        <div className="races-trait-name">
          <h3 className="serif text-base text-[var(--gold)]">{trait.name}</h3>
          <span className="races-kind" data-kind={trait.kind}>
            {kindLabel(trait.kind)}
          </span>
        </div>
        <span
          className="races-chip"
          data-status={status}
          title={classicChipHint(status)}
          data-testid={`trait-chip-${trait.id}`}
        >
          {CLASSIC_LABEL[status] ?? status}
        </span>
      </div>

      {trait.description ? (
        <p className="races-desc">{trait.description}</p>
      ) : (
        /* Rule 3: a racial known only by name renders the reason, not a blank. */
        <p className="races-desc races-desc-missing">
          {playerNoteLines(trait.source.note)[0] ?? 'The description was never on screen.'}
        </p>
      )}

      {trust && <p className="races-trust-line">{trust}</p>}

      {/* Rule 4: the Classic side is a paraphrase written from memory. It is
          nested behind a disclosure and labelled in one word, every time. */}
      {(trait.classic.classicText || classicNote.length > 0) && (
        <details className="races-classic" data-testid={`trait-classic-${trait.id}`}>
          <summary>
            {classicCardTitle(trait.classic)}
            <span className="races-unverified" title="Written from memory, not checked against a client or a database.">
              {UNVERIFIED}
            </span>
          </summary>
          {trait.classic.classicText && <p className="races-classic-text">{trait.classic.classicText}</p>}
          {classicNote.map((line) => (
            <p key={line} className="races-classic-note">
              {line}
            </p>
          ))}
        </details>
      )}

      <details className="races-details" data-testid={`trait-details-${trait.id}`}>
        <summary>Details</summary>
        {details.map((line) => (
          <p key={line}>{line}</p>
        ))}
        {cropUrl && (
          <p>
            <a href={cropUrl} target="_blank" rel="noreferrer" data-testid={`trait-crop-${trait.id}`}>
              The frame it was read from{stamp ? ` (${stamp})` : ''}
            </a>
          </p>
        )}
      </details>
    </li>
  )
}

function RacesHeader({ raceId }: { raceId?: string }) {
  return (
    <div className="races-head">
      <h1 className="serif text-xl text-[var(--gold)]">Races and the class matrix</h1>
      {raceId && (
        <a href={racesHash()} className="races-all" data-testid="races-all-link">
          All races
        </a>
      )}
    </div>
  )
}

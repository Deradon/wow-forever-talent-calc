import type { CSSProperties } from 'react'
import type { ClassData, Tree } from '../data/schema'
import { canAdd, pointsInTree, rankOf, type Build } from '../rules'
import { Arrows } from './Arrows'
import { TalentCell } from './TalentCell'

interface Props {
  cls: ClassData
  tree: Tree
  build: Build
  onAdd: (treeId: string, talentId: string) => void
  onRemove: (treeId: string, talentId: string) => void
  onReset: (treeId: string) => void
}

export function TreePanel({ cls, tree, build, onAdd, onRemove, onReset }: Props) {
  const spent = pointsInTree(build, tree.id)
  const style = { '--rows': tree.rows, '--cols': tree.cols } as CSSProperties
  return (
    <section className="panel p-2" data-testid={`tree-${tree.id}`}>
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <h2 className="serif text-base text-[var(--gold)]">{tree.name}</h2>
        <div className="flex items-center gap-2 text-sm">
          <span data-testid={`tree-points-${tree.id}`}>{spent}</span>
          <button className="btn text-xs" onClick={() => onReset(tree.id)} disabled={spent === 0} aria-label={`Reset ${tree.name}`}>
            Reset
          </button>
        </div>
      </div>
      <div className="tree-grid" style={style}>
        <Arrows tree={tree} build={build} />
        {tree.talents.map((talent) => (
          <TalentCell
            key={talent.id}
            cls={cls}
            tree={tree}
            talent={talent}
            rank={rankOf(build, tree.id, talent.id)}
            addVerdict={canAdd(cls, build, tree.id, talent.id)}
            onAdd={() => onAdd(tree.id, talent.id)}
            onRemove={() => onRemove(tree.id, talent.id)}
          />
        ))}
      </div>
    </section>
  )
}

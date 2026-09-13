/**
 * Word-level diff over whitespace-separated tokens, for the build-time Classic
 * Era diff in `gen-data-index.mjs`.
 *
 * It is a deliberate second copy of `diffWords` in `src/ui/review.ts`. The
 * build script is plain ESM run by node and cannot import TypeScript, and the
 * obvious fix - one copy here, re-exported from review.ts - costs every first
 * load a chunk: importing a `.mjs` from app code makes rolldown split its
 * CommonJS-interop helpers into a separate `rolldown-runtime` chunk that
 * index.html then modulepreloads. A duplicated twenty-line LCS is the cheaper
 * of the two, and `src/data/classicDiff.test.ts` fails the moment the two
 * implementations disagree on anything.
 *
 * Longest common subsequence over the tokens; the strings involved are one
 * tooltip long, so the O(n*m) table is fine.
 */

/**
 * @param {string} a
 * @param {string} b
 * @returns {{ type: 'same' | 'add' | 'del', text: string }[]}
 */
export function diffWords(a, b) {
  const left = a.split(/\s+/).filter(Boolean)
  const right = b.split(/\s+/).filter(Boolean)
  const n = left.length
  const m = right.length
  const lcs = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = left[i] === right[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1])
    }
  }
  const ops = []
  const push = (type, text) => {
    const last = ops[ops.length - 1]
    if (last && last.type === type) last.text += ` ${text}`
    else ops.push({ type, text })
  }
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (left[i] === right[j]) {
      push('same', left[i])
      i++
      j++
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      push('del', left[i])
      i++
    } else {
      push('add', right[j])
      j++
    }
  }
  for (; i < n; i++) push('del', left[i])
  for (; j < m; j++) push('add', right[j])
  return ops
}

/** The op letters used in the generated file: `=` keep, `-` Classic only, `+` Forever only. */
const OP_LETTER = { same: '=', del: '-', add: '+' }

/**
 * The same diff in the shape `classic-diff.json` ships: `[op, text]` pairs.
 * One array of two strings per run costs about a third of what the object form
 * would, and the file is fetched by every class route.
 *
 * @param {string} a
 * @param {string} b
 * @returns {[string, string][]}
 */
export function compactDiff(a, b) {
  return diffWords(a, b).map((op) => [OP_LETTER[op.type], op.text])
}

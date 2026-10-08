import type { SrsRequirement } from '../../api'

export type LineOp = { kind: 'same' | 'added' | 'removed'; text: string; leftNo?: number; rightNo?: number }

/** Line diff via LCS after trimming the common prefix and suffix. */
export function diffLines(leftText: string, rightText: string): LineOp[] {
  const a = leftText.replace(/\r\n/g, '\n').split('\n')
  const b = rightText.replace(/\r\n/g, '\n').split('\n')
  let start = 0
  while (start < a.length && start < b.length && a[start] === b[start]) start++
  let endA = a.length
  let endB = b.length
  while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) {
    endA--
    endB--
  }

  const n = endA - start
  const m = endB - start
  const width = m + 1
  // table[i][j] = LCS length of a[start+i..endA) and b[start+j..endB)
  const table = new Uint32Array((n + 1) * width)
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      table[i * width + j] =
        a[start + i] === b[start + j]
          ? table[(i + 1) * width + j + 1] + 1
          : Math.max(table[(i + 1) * width + j], table[i * width + j + 1])
    }
  }

  const ops: LineOp[] = []
  let leftNo = 1
  let rightNo = 1
  const same = (text: string) => ops.push({ kind: 'same', text, leftNo: leftNo++, rightNo: rightNo++ })
  for (let k = 0; k < start; k++) same(a[k])
  let i = 0
  let j = 0
  while (i < n || j < m) {
    if (i < n && j < m && a[start + i] === b[start + j]) {
      same(a[start + i])
      i++
      j++
    } else if (j < m && (i >= n || table[i * width + j + 1] >= table[(i + 1) * width + j])) {
      ops.push({ kind: 'added', text: b[start + j], rightNo: rightNo++ })
      j++
    } else {
      ops.push({ kind: 'removed', text: a[start + i], leftNo: leftNo++ })
      i++
    }
  }
  for (let k = endA; k < a.length; k++) same(a[k])
  return ops
}

export type DiffHunk = { ops: LineOp[]; hidden: number }

/** Collapse long runs of unchanged lines, keeping `context` lines around each change. */
export function toHunks(ops: LineOp[], context = 3): DiffHunk[] {
  const keep = new Array<boolean>(ops.length).fill(false)
  ops.forEach((op, index) => {
    if (op.kind === 'same') return
    for (let k = Math.max(0, index - context); k <= Math.min(ops.length - 1, index + context); k++) keep[k] = true
  })
  const hunks: DiffHunk[] = []
  let hidden = 0
  let current: LineOp[] = []
  ops.forEach((op, index) => {
    if (keep[index]) {
      if (hidden) {
        if (current.length) hunks.push({ ops: current, hidden: 0 })
        hunks.push({ ops: [], hidden })
        current = []
        hidden = 0
      }
      current.push(op)
    } else {
      hidden++
    }
  })
  if (current.length) hunks.push({ ops: current, hidden: 0 })
  if (hidden) hunks.push({ ops: [], hidden })
  return hunks
}

export type RequirementChange =
  | { kind: 'same'; left: SrsRequirement; right: SrsRequirement }
  | { kind: 'changed'; left: SrsRequirement; right: SrsRequirement }
  | { kind: 'added'; right: SrsRequirement }
  | { kind: 'removed'; left: SrsRequirement }

const normStatement = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

/**
 * Match requirements first by identical statement (even if renumbered), then by id
 * (same id, different wording = changed). Whatever is left is added or removed.
 */
export function diffRequirements(left: SrsRequirement[], right: SrsRequirement[]): RequirementChange[] {
  const unmatchedRight = new Set(right.map((_, index) => index))
  const pairs = new Map<number, number>()

  const byStatement = new Map<string, number[]>()
  right.forEach((req, index) => {
    const key = normStatement(req.statement)
    byStatement.set(key, [...(byStatement.get(key) ?? []), index])
  })
  left.forEach((req, index) => {
    const candidates = byStatement.get(normStatement(req.statement))
    const match = candidates?.find((candidate) => unmatchedRight.has(candidate))
    if (match === undefined) return
    pairs.set(index, match)
    unmatchedRight.delete(match)
  })

  const byId = new Map<string, number>()
  right.forEach((req, index) => {
    if (unmatchedRight.has(index)) byId.set(req.id, index)
  })
  left.forEach((req, index) => {
    if (pairs.has(index)) return
    const match = byId.get(req.id)
    if (match === undefined || !unmatchedRight.has(match)) return
    pairs.set(index, match)
    unmatchedRight.delete(match)
  })

  const changes: RequirementChange[] = left.map((req, index) => {
    const match = pairs.get(index)
    if (match === undefined) return { kind: 'removed', left: req }
    const other = right[match]
    const differs = normStatement(req.statement) !== normStatement(other.statement) || req.type !== other.type
    return { kind: differs ? 'changed' : 'same', left: req, right: other }
  })
  for (const index of unmatchedRight) changes.push({ kind: 'added', right: right[index] })
  return changes
}

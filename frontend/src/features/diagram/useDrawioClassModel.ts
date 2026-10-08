import { useEffect, useRef, useState } from 'react'
import { classModelSignature, parseDrawioClassModel } from './drawioModel'
import type { DrawioParseResult } from './drawioModel'

export type DrawioClassModelState = {
  /** True until the first parse for this diagram has finished, so the view can
   * wait rather than flash "nothing to draw" for a frame. */
  pending: boolean
  result: DrawioParseResult | null
}

/** The class model behind some draw.io XML, parsed off the editing path.
 *
 * The embedded editor autosaves on every change, so the XML arrives far more
 * often than the model actually changes. Two things follow from that:
 *
 * - the parse is debounced, so typing in draw.io does not re-parse per keystroke
 * - a model that comes back unchanged keeps its previous object, because the
 *   canvas lays out afresh for every new model object it is handed - dragging a
 *   box in draw.io must not count as a new model and reset the arrangement
 *
 * `enabled` is false while no view shows the canvas, so a user who stays in the
 * editor never pays for the parse at all.
 */
export function useDrawioClassModel(xml: string, enabled: boolean): DrawioClassModelState {
  const [parsed, setParsed] = useState<{ signature: string; result: DrawioParseResult | null } | null>(null)
  const signature = useRef<string | null>(null)

  useEffect(() => {
    if (!enabled) return
    // The first parse runs straight away so opening the view does not stall;
    // later ones wait for the editor to go quiet.
    const timer = window.setTimeout(
      () => {
        const result = parseDrawioClassModel(xml)
        const next = result ? classModelSignature(result.model) : ''
        if (next === signature.current) return
        signature.current = next
        setParsed({ signature: next, result })
      },
      signature.current === null ? 0 : 300,
    )
    return () => window.clearTimeout(timer)
  }, [xml, enabled])

  return { pending: enabled && parsed === null, result: parsed?.result ?? null }
}

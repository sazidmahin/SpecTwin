import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useTheme } from '../../shared/theme'
import { cn } from '../../shared/ui'

type Props = {
  xml: string
  title: string
  className?: string
  /** When provided the diagram is editable and every change is reported back as draw.io XML. */
  onChange?: (xml: string) => void
}

export type DrawioEmbedHandle = {
  exportImage: (format: 'png' | 'jpeg') => Promise<string>
}

const drawioOrigin = 'https://embed.diagrams.net'

function drawioUrl(dark: boolean) {
  const params = new URLSearchParams({
    embed: '1',
    proto: 'json',
    ui: 'min',
    spin: '1',
    noSaveBtn: '1',
    noExitBtn: '1',
    saveAndExit: '0',
    modified: '0',
    dark: dark ? '1' : '0',
  })
  return `${drawioOrigin}/?${params.toString()}`
}

export const DrawioEmbed = forwardRef<DrawioEmbedHandle, Props>(function DrawioEmbed(
  { xml, title, className = 'h-96', onChange },
  ref,
) {
  const { theme } = useTheme()
  const frame = useRef<HTMLIFrameElement>(null)
  const ready = useRef(false)
  const lastXml = useRef<string | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const pendingExport = useRef<{ resolve: (dataUrl: string) => void; reject: (error: Error) => void } | null>(null)

  useEffect(() => {
    function loadDiagram() {
      lastXml.current = xml
      frame.current?.contentWindow?.postMessage(
        JSON.stringify({ action: 'load', xml, autosave: onChangeRef.current ? 1 : 0, modified: 0 }),
        drawioOrigin,
      )
    }
    function receiveMessage(event: MessageEvent) {
      if (event.origin !== drawioOrigin || event.source !== frame.current?.contentWindow) return
      let message: Record<string, unknown>
      try {
        message = (typeof event.data === 'string' ? JSON.parse(event.data) : event.data) as Record<string, unknown>
      } catch {
        return
      }
      if (message.event === 'init') {
        ready.current = true
        loadDiagram()
        return
      }
      if (message.event === 'load') {
        setStatus('ready')
        return
      }
      if (message.event === 'autosave' && typeof message.xml === 'string') {
        lastXml.current = message.xml
        onChangeRef.current?.(message.xml)
        return
      }
      if (message.event === 'error') {
        setStatus('error')
        pendingExport.current?.reject(new Error(typeof message.message === 'string' ? message.message : 'Diagram export failed'))
        pendingExport.current = null
        return
      }
      if (message.event === 'export') {
        pendingExport.current?.resolve(String(message.data ?? ''))
        pendingExport.current = null
      }
    }
    window.addEventListener('message', receiveMessage)
    // Reload only for XML that did not come from the editor itself, so typing never resets the canvas.
    if (ready.current && xml !== lastXml.current) loadDiagram()
    return () => window.removeEventListener('message', receiveMessage)
  }, [xml])

  useEffect(() => {
    if (status !== 'loading') return
    const timer = window.setTimeout(() => setStatus((current) => (current === 'loading' ? 'error' : current)), 25000)
    return () => window.clearTimeout(timer)
  }, [status, theme])

  useImperativeHandle(ref, () => ({
    exportImage(format) {
      return new Promise<string>((resolve, reject) => {
        if (!ready.current || !frame.current?.contentWindow) {
          reject(new Error('The diagram is still loading. Try again in a moment.'))
          return
        }
        pendingExport.current = { resolve, reject }
        frame.current.contentWindow.postMessage(
          JSON.stringify({ action: 'export', format, xml: lastXml.current ?? xml, background: '#ffffff', spinKey: 'export' }),
          drawioOrigin,
        )
      })
    },
  }))

  return (
    <div className={cn('relative w-full overflow-hidden rounded-xl border border-border bg-surface-2', className)}>
      <iframe
        key={theme}
        ref={frame}
        className="size-full"
        src={drawioUrl(theme === 'dark')}
        title={title}
        onLoad={() => {
          ready.current = false
          setStatus('loading')
        }}
      />
      {status !== 'ready' ? (
        <div className="pointer-events-none absolute inset-0 grid place-items-center bg-surface-2/80 text-[13px] text-fg-2" aria-live="polite">
          {status === 'error' ? (
            <span className="max-w-xs px-4 text-center text-danger">
              The draw.io editor could not be reached. Check your internet connection — you can still download the .drawio file.
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <Loader2 className="size-4 animate-spin" /> Loading diagram editor…
            </span>
          )}
        </div>
      ) : null}
    </div>
  )
})

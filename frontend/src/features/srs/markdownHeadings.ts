export type Heading = { id: string; text: string; level: number }

export function slugifyHeading(text: string) {
  return (
    text
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s-]/gu, '')
      .trim()
      .replace(/\s+/g, '-') || 'section'
  )
}

/** Headings (h2/h3) used for the table of contents; ids match what <Markdown> renders. */
export function extractHeadings(markdown: string): Heading[] {
  const headings: Heading[] = []
  let inFence = false
  for (const line of markdown.split('\n')) {
    if (line.trim().startsWith('```')) inFence = !inFence
    if (inFence) continue
    const match = /^(#{2,3})\s+(.+?)\s*#*$/.exec(line)
    if (match) {
      const text = match[2].replace(/[*_`]/g, '')
      headings.push({ id: slugifyHeading(text), text, level: match[1].length })
    }
  }
  return headings
}

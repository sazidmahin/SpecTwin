import type { ClassModelerResult, NounDecision } from '../../api'
import { Chip, DataTable } from '../../shared/ui'
import type { Tone } from '../../shared/ui'

const decisionTone: Record<string, Tone> = {
  class: 'success',
  interface: 'ai',
  attribute: 'info',
  merged: 'ai',
  value: 'sky',
  rejected: 'muted',
}

const kindTone: Record<string, Tone> = {
  Generalisation: 'ai',
  Interface: 'ai',
  Realization: 'ai',
  'Abstract class': 'ai',
  'Possible states': 'sky',
  Structure: 'info',
  'Structure + behaviour': 'info',
  Behaviour: 'success',
  'Behaviour (passive voice)': 'success',
  Association: 'accent',
  'Non-functional': 'warning',
  'Task statement': 'muted',
  'Not modelled': 'danger',
}

function StepHeading({ step, title, description }: { step: number; title: string; description: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-accent/15 text-xs font-bold text-accent">{step}</span>
      <div>
        <h3 className="font-display text-[14px] font-bold text-fg">{title}</h3>
        <p className="text-xs text-fg-3">{description}</p>
      </div>
    </div>
  )
}

export function Breakdown({ result }: { result: ClassModelerResult }) {
  const { analysis } = result
  const grouped = groupNouns(analysis.nouns)
  // The sentence walk-through only exists for rule-based results.
  const offset = analysis.sentences.length ? 1 : 0
  return (
    <>
      {analysis.sentences.length ? (
        <div className="grid grid-cols-1 gap-3">
          <StepHeading step={1} title="Read each sentence" description="Recognise what kind of statement it is and what it says about the domain." />
          <ol className="grid grid-cols-1 gap-2">
            {analysis.sentences.map((sentence) => (
              <li key={sentence.index} className="rounded-md border border-border bg-surface-2 px-3 py-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] font-bold text-fg-3">S{sentence.index}</span>
                  <Chip tone={kindTone[sentence.kind] ?? 'neutral'}>{sentence.kind}</Chip>
                  <span className="text-[13px] text-fg">{sentence.text}</span>
                </div>
                <ul className="mt-1.5 grid grid-cols-1 gap-0.5 pl-8">
                  {sentence.findings.map((finding) => (
                    <li key={finding} className="font-mono text-[12px] text-fg-2">→ {finding}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-3">
        <StepHeading step={offset + 1} title="Decide every noun" description="Class, attribute of its owner, merged synonym, or rejected — with the reason." />
        {analysis.nouns.length ? (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {Object.entries(grouped).map(([decision, nouns]) => (
              <div key={decision} className="rounded-md border border-border p-3">
                <div className="mb-2 flex items-center gap-2">
                  <Chip tone={decisionTone[decision] ?? 'neutral'}>{decision}</Chip>
                  <span className="text-xs text-fg-3">{nouns.length}</span>
                </div>
                <ul className="grid grid-cols-1 gap-1.5">
                  {nouns.map((noun) => (
                    <li key={noun.name} className="text-[12.5px]">
                      <span className="font-semibold text-fg">{noun.name}</span>
                      {noun.mergedInto ? <span className="text-fg-2"> → {noun.mergedInto}</span> : null}
                      <span className="text-fg-3"> — {noun.reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-fg-3">The model did not return a noun breakdown.</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3">
        <StepHeading step={offset + 2} title="Turn verbs into methods" description="A verb becomes a method on the class that performs it, with the acted-on object as a parameter." />
        {analysis.verbs.length ? (
          <DataTable>
            <thead>
              <tr>
                <th>Sentence</th>
                <th>Subject</th>
                <th>Verb</th>
                <th>Object</th>
                <th>Method</th>
              </tr>
            </thead>
            <tbody>
              {analysis.verbs.map((verb, index) => (
                <tr key={`${verb.verb}-${index}`}>
                  <td>{verb.sentence ? `S${verb.sentence}` : '—'}</td>
                  <td>{verb.subject ?? <span className="text-warning">not stated</span>}</td>
                  <td className="font-mono">{verb.verb}</td>
                  <td>{verb.object ?? '—'}</td>
                  <td className="font-mono text-fg">
                    {verb.method ? `${verb.assignedTo}.${verb.method}` : <span className="text-fg-3">{verb.note ?? 'not assigned'}</span>}
                    {verb.method && verb.note ? <div className="font-sans text-[11px] text-fg-3">{verb.note}</div> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        ) : (
          <p className="text-xs text-fg-3">No behaviour was found in the text.</p>
        )}
      </div>

      {analysis.generalisation.length || analysis.warnings.length ? (
        <div className="grid grid-cols-1 gap-3">
          <StepHeading step={offset + 3} title="Tidy up" description="Generalisation and anything the text left open." />
          <ul className="grid grid-cols-1 gap-1 text-[12.5px]">
            {analysis.generalisation.map((item) => (
              <li key={item} className="text-fg-2">↑ {item}</li>
            ))}
            {analysis.warnings.map((item) => (
              <li key={item} className="text-warning">⚠ {item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  )
}

function groupNouns(nouns: NounDecision[]) {
  const order = ['class', 'interface', 'attribute', 'merged', 'value', 'rejected']
  const groups: Record<string, NounDecision[]> = {}
  for (const noun of nouns) {
    ;(groups[noun.decision] ??= []).push(noun)
  }
  const rank = (decision: string) => (order.includes(decision) ? order.indexOf(decision) : order.length)
  return Object.fromEntries(Object.entries(groups).sort(([a], [b]) => rank(a) - rank(b)))
}

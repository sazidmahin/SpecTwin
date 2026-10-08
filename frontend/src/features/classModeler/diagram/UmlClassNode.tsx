import { Handle, Position } from '@xyflow/react'
import type { Node, NodeProps } from '@xyflow/react'
import type { ModelClass, ModelEnum } from '../../../api'
import { cn } from '../../../shared/ui'

export type UmlNodeData = {
  kind: 'class' | 'enum'
  cls?: ModelClass
  enumeration?: ModelEnum
  parents: { name: string; via: 'extends' | 'implements' }[]
  focus: 'none' | 'selected' | 'related' | 'dimmed'
}
export type UmlNode = Node<UmlNodeData, 'uml'>

const visibilitySymbol: Record<string, string> = { private: '-', public: '+', protected: '#', package: '~' }

const headerTone = {
  entity: 'bg-accent/12 text-fg',
  abstract: 'bg-warning/15 text-fg',
  interface: 'bg-accent2/15 text-fg',
  enumeration: 'bg-sky/15 text-fg',
}
const borderTone = {
  entity: 'border-accent/40',
  abstract: 'border-warning/50',
  interface: 'border-accent2/50 border-dashed',
  enumeration: 'border-sky/50',
}

function StereotypeTag({ label, className }: { label: string; className: string }) {
  return (
    <span className={cn('rounded-full px-1.5 py-px text-[9.5px] font-bold uppercase tracking-[0.08em]', className)}>
      {label}
    </span>
  )
}

const hiddenHandle = '!size-1 !min-h-0 !min-w-0 !border-0 !bg-transparent opacity-0'

export function UmlClassNode({ data }: NodeProps<UmlNode>) {
  const cls = data.cls
  const enumeration = data.enumeration
  const stereotype = enumeration ? 'enumeration' : ((cls?.stereotype as keyof typeof headerTone) ?? 'entity')
  const tone = stereotype in headerTone ? stereotype : 'entity'

  return (
    <div
      className={cn(
        'min-w-40 overflow-hidden rounded-xl border-[1.5px] bg-surface shadow-sm transition-all duration-200',
        borderTone[tone],
        data.focus === 'selected' && 'shadow-lg ring-4 ring-accent/25',
        data.focus === 'related' && 'shadow-md ring-2 ring-accent/15',
        data.focus === 'dimmed' && 'opacity-30',
        'hover:shadow-md',
      )}
    >
      <Handle type="target" position={Position.Top} className={hiddenHandle} isConnectable={false} />
      <Handle type="source" position={Position.Bottom} className={hiddenHandle} isConnectable={false} />

      <div className={cn('px-3 pb-2 pt-2 text-center', headerTone[tone])}>
        <div className="flex min-h-4 items-center justify-center gap-1">
          {tone === 'interface' ? <StereotypeTag label="interface" className="bg-accent2/20 text-accent2-dim" /> : null}
          {tone === 'abstract' ? <StereotypeTag label="abstract" className="bg-warning/25 text-fg-2" /> : null}
          {tone === 'enumeration' ? <StereotypeTag label="enum" className="bg-sky/25 text-fg-2" /> : null}
        </div>
        <div className={cn('font-display text-[14px] font-bold leading-tight', tone === 'abstract' && 'italic')}>
          {cls?.name ?? enumeration?.name}
        </div>
        {data.parents.length ? (
          <div className="mt-1 flex flex-wrap justify-center gap-1">
            {data.parents.map((parent) => (
              <span
                key={`${parent.via}-${parent.name}`}
                className={cn(
                  'rounded-md px-1.5 py-px text-[10px] font-semibold',
                  parent.via === 'extends' ? 'bg-fg/5 text-fg-2' : 'bg-accent2/10 text-accent2-dim',
                )}
              >
                {parent.via} {parent.name}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {enumeration ? (
        <ul className="border-t border-border px-3 py-2 font-mono text-[11.5px] text-fg-2">
          {enumeration.literals.map((literal) => (
            <li key={literal} className="leading-5">
              {literal}
            </li>
          ))}
        </ul>
      ) : cls ? (
        <>
          <ul className="min-h-7 border-t border-border px-3 py-1.5 font-mono text-[11.5px]">
            {cls.attributes.length ? (
              cls.attributes.map((attr) => (
                <li key={attr.id} className="whitespace-nowrap leading-5 text-fg-2">
                  <span className="text-fg-3">{visibilitySymbol[attr.visibility] ?? '-'} </span>
                  {attr.name}: <span className="text-accent-dim">{attr.type}</span>
                </li>
              ))
            ) : (
              <li className="leading-5 text-fg-3/60">no attributes</li>
            )}
          </ul>
          <ul className="min-h-7 border-t border-border px-3 py-1.5 font-mono text-[11.5px]">
            {cls.methods.length ? (
              cls.methods.map((method) => (
                <li key={method.id} className="whitespace-nowrap leading-5 text-fg">
                  <span className="text-fg-3">{visibilitySymbol[method.visibility] ?? '+'} </span>
                  {method.name}(
                  <span className="text-fg-2">
                    {method.parameters.map((param) => `${param.name}: ${param.type}`).join(', ')}
                  </span>
                  ): <span className="text-accent2-dim">{method.returnType}</span>
                </li>
              ))
            ) : (
              <li className="leading-5 text-fg-3/60">no methods</li>
            )}
          </ul>
        </>
      ) : null}
    </div>
  )
}

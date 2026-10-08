/** The Classes tab, editable.
 *
 * Reading the model and changing it happen in the same place, in the notation
 * the cards already use: `name: Type` for an attribute, `name(p: T): R` for an
 * operation. Every change goes through `modelEdits`, and the page turns the new
 * model straight back into draw.io XML - so the canvas, this editor and the
 * draw.io tab are three views of one model rather than three copies.
 */
import { Plus, Trash2 } from 'lucide-react'
import type { ModelClass, ModelEnum, ModelRelationship } from '../../api'
import { Button, Chip, Input, Select, cn } from '../../shared/ui'
import type { ClassModel } from './modelEdits'
import {
  RELATIONSHIP_TYPES,
  STEREOTYPES,
  VISIBILITIES,
  addAttribute,
  addClass,
  addEnum,
  addMethod,
  addRelationship,
  parameterText,
  parseLiterals,
  parseParameterText,
  removeAttribute,
  removeClass,
  removeEnum,
  removeMethod,
  removeRelationship,
  updateAttribute,
  updateClass,
  updateEnum,
  updateMethod,
  updateRelationship,
} from './modelEdits'

type Props = { model: ClassModel; onChange: (model: ClassModel) => void }

const KIND_BORDER: Record<string, string> = {
  entity: 'border-accent/35',
  abstract: 'border-warning/45',
  interface: 'border-dashed border-accent2/50',
}
const KIND_HEAD: Record<string, string> = {
  entity: 'bg-accent/10',
  abstract: 'bg-warning/12',
  interface: 'bg-accent2/12',
}

function RowButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="rounded-md p-1 text-fg-3 transition hover:bg-danger/10 hover:text-danger"
    >
      <Trash2 className="size-3.5" />
    </button>
  )
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-max items-center gap-1 rounded-md px-1 py-0.5 text-[11.5px] font-semibold text-accent transition hover:underline"
    >
      <Plus className="size-3" /> {label}
    </button>
  )
}

function ClassCard({ cls, model, onChange }: { cls: ModelClass } & Props) {
  const kind = cls.stereotype in KIND_BORDER ? cls.stereotype : 'entity'
  return (
    <div className={cn('overflow-hidden rounded-xl border-[1.5px] bg-surface shadow-xs', KIND_BORDER[kind])}>
      <div className={cn('grid grid-cols-1 gap-2 px-3 py-2.5', KIND_HEAD[kind])}>
        <div className="flex items-center gap-2">
          <Input
            inputSize="sm"
            value={cls.name}
            aria-label={`Name of ${cls.name}`}
            onChange={(event) => onChange(updateClass(model, cls.id, { name: event.target.value }))}
            className="font-display font-bold"
          />
          <RowButton label={`Delete class ${cls.name}`} onClick={() => onChange(removeClass(model, cls.id))} />
        </div>
        <Select
          inputSize="sm"
          value={kind}
          aria-label={`Kind of ${cls.name}`}
          onChange={(event) => onChange(updateClass(model, cls.id, { stereotype: event.target.value }))}
        >
          {STEREOTYPES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-3 px-3 py-3">
        <div className="grid grid-cols-1 gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-fg-3">Attributes</span>
          {cls.attributes.map((attribute) => (
            <div key={attribute.id} className="grid grid-cols-1 gap-1 rounded-lg border border-border/60 bg-surface-2 p-1.5">
              <div className="flex items-center gap-1">
                <Input
                  inputSize="sm"
                  value={attribute.name}
                  aria-label="Attribute name"
                  placeholder="name"
                  className="min-w-0 flex-1 font-mono"
                  onChange={(event) => onChange(updateAttribute(model, cls.id, attribute.id, { name: event.target.value }))}
                />
                <Input
                  inputSize="sm"
                  value={attribute.type}
                  aria-label={`Type of ${attribute.name}`}
                  placeholder="String"
                  className="min-w-0 flex-1 font-mono"
                  onChange={(event) => onChange(updateAttribute(model, cls.id, attribute.id, { type: event.target.value }))}
                />
                <RowButton label={`Delete attribute ${attribute.name}`} onClick={() => onChange(removeAttribute(model, cls.id, attribute.id))} />
              </div>
              <div className="w-28">
                <Select
                  inputSize="sm"
                  value={attribute.visibility}
                  aria-label={`Visibility of ${attribute.name}`}
                  onChange={(event) => onChange(updateAttribute(model, cls.id, attribute.id, { visibility: event.target.value }))}
                >
                  {VISIBILITIES.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          ))}
          <AddButton label="Add attribute" onClick={() => onChange(addAttribute(model, cls.id))} />
        </div>

        <div className="grid grid-cols-1 gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-fg-3">Methods</span>
          {cls.methods.map((method) => (
            <div key={method.id} className="grid grid-cols-1 gap-1 rounded-lg border border-border/60 bg-surface-2 p-1.5">
              <div className="flex items-center gap-1">
                <Input
                  inputSize="sm"
                  value={method.name}
                  aria-label="Method name"
                  placeholder="name"
                  className="min-w-0 flex-1 font-mono"
                  onChange={(event) => onChange(updateMethod(model, cls.id, method.id, { name: event.target.value }))}
                />
                <Input
                  inputSize="sm"
                  value={method.returnType}
                  aria-label={`Return type of ${method.name}`}
                  placeholder="void"
                  className="min-w-0 flex-1 font-mono"
                  onChange={(event) => onChange(updateMethod(model, cls.id, method.id, { returnType: event.target.value }))}
                />
                <RowButton label={`Delete method ${method.name}`} onClick={() => onChange(removeMethod(model, cls.id, method.id))} />
              </div>
              <div className="flex items-center gap-1">
                <div className="w-28 shrink-0">
                  <Select
                    inputSize="sm"
                    value={method.visibility}
                    aria-label={`Visibility of ${method.name}`}
                    onChange={(event) => onChange(updateMethod(model, cls.id, method.id, { visibility: event.target.value }))}
                  >
                    {VISIBILITIES.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </Select>
                </div>
                <Input
                  inputSize="sm"
                  defaultValue={parameterText(method)}
                  aria-label={`Parameters of ${method.name}`}
                  placeholder="book: Book, copies: Integer"
                  className="min-w-0 flex-1 font-mono"
                  // On blur, not per keystroke: half-typed text like "book:" would
                  // otherwise be parsed and written back under the caret.
                  onBlur={(event) => onChange(updateMethod(model, cls.id, method.id, { parameters: parseParameterText(event.target.value) }))}
                />
              </div>
            </div>
          ))}
          <AddButton label="Add method" onClick={() => onChange(addMethod(model, cls.id))} />
        </div>
      </div>
    </div>
  )
}

function EnumCard({ item, model, onChange }: { item: ModelEnum } & Props) {
  return (
    <div className="overflow-hidden rounded-xl border-[1.5px] border-sky/45 bg-surface shadow-xs">
      <div className="flex items-center gap-2 bg-sky/10 px-3 py-2.5">
        <Input
          inputSize="sm"
          value={item.name}
          aria-label={`Name of ${item.name}`}
          className="font-display font-bold"
          onChange={(event) => onChange(updateEnum(model, item.id, { name: event.target.value }))}
        />
        <Chip tone="sky">enum</Chip>
        <RowButton label={`Delete enum ${item.name}`} onClick={() => onChange(removeEnum(model, item.id))} />
      </div>
      <div className="grid grid-cols-1 gap-1 px-3 py-3">
        <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-fg-3">Values</span>
        <Input
          inputSize="sm"
          defaultValue={item.literals.join(', ')}
          aria-label={`Values of ${item.name}`}
          placeholder="AVAILABLE, BORROWED, LOST"
          className="font-mono"
          onBlur={(event) => onChange(updateEnum(model, item.id, { literals: parseLiterals(event.target.value) }))}
        />
      </div>
    </div>
  )
}

function RelationshipRow({ rel, model, onChange }: { rel: ModelRelationship } & Props) {
  const ends = [...model.classes.map((cls) => ({ id: cls.id, name: cls.name })), ...model.enums.map((item) => ({ id: item.id, name: item.name }))]
  const carriesMultiplicity = ['association', 'aggregation', 'composition'].includes(rel.type)
  return (
    <div className="grid grid-cols-1 gap-1.5 rounded-xl border border-border bg-surface-2 px-3 py-2.5">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-1.5 sm:grid-cols-[minmax(0,1fr)_9rem_minmax(0,1fr)_auto]">
        <Select
          inputSize="sm"
          value={rel.sourceClassId}
          aria-label="Source class"
          className="min-w-0"
          onChange={(event) => onChange(updateRelationship(model, rel.id, { sourceClassId: event.target.value }))}
        >
          {ends.map((end) => (
            <option key={end.id} value={end.id}>
              {end.name}
            </option>
          ))}
        </Select>
        <Select
          inputSize="sm"
          value={rel.type}
          aria-label="Relationship type"
          className="min-w-0"
          onChange={(event) => onChange(updateRelationship(model, rel.id, { type: event.target.value as ModelRelationship['type'] }))}
        >
          {RELATIONSHIP_TYPES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </Select>
        <Select
          inputSize="sm"
          value={rel.targetClassId}
          aria-label="Target class"
          className="min-w-0"
          onChange={(event) => onChange(updateRelationship(model, rel.id, { targetClassId: event.target.value }))}
        >
          {ends.map((end) => (
            <option key={end.id} value={end.id}>
              {end.name}
            </option>
          ))}
        </Select>
        <RowButton label="Delete relationship" onClick={() => onChange(removeRelationship(model, rel.id))} />
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <Input
          inputSize="sm"
          value={rel.label ?? ''}
          aria-label="Relationship label"
          placeholder="label, e.g. borrows"
          className="min-w-0 flex-1"
          onChange={(event) => onChange(updateRelationship(model, rel.id, { label: event.target.value }))}
        />
        {carriesMultiplicity ? (
          <>
            <Input
              inputSize="sm"
              value={rel.sourceMultiplicity ?? ''}
              aria-label="Source multiplicity"
              placeholder="1"
              className="w-20 shrink-0 font-mono"
              onChange={(event) => onChange(updateRelationship(model, rel.id, { sourceMultiplicity: event.target.value || null }))}
            />
            <span className="text-[11px] text-fg-3">→</span>
            <Input
              inputSize="sm"
              value={rel.targetMultiplicity ?? ''}
              aria-label="Target multiplicity"
              placeholder="0..*"
              className="w-20 shrink-0 font-mono"
              onChange={(event) => onChange(updateRelationship(model, rel.id, { targetMultiplicity: event.target.value || null }))}
            />
          </>
        ) : (
          // Only the "part of" kinds carry counts; the others would show a box
          // the diagram never draws.
          <span className="text-[11px] text-fg-3">no multiplicity for {rel.type}</span>
        )}
      </div>
    </div>
  )
}

export function ClassModelEditor({ model, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 gap-5">
      <div className="grid grid-cols-1 gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-[15px] font-bold text-fg">Classes and enumerations</h3>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => onChange(addClass(model))}>
              <Plus /> Class
            </Button>
            <Button size="sm" variant="secondary" onClick={() => onChange(addEnum(model))}>
              <Plus /> Enum
            </Button>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {model.classes.map((cls) => (
            <ClassCard key={cls.id} cls={cls} model={model} onChange={onChange} />
          ))}
          {model.enums.map((item) => (
            <EnumCard key={item.id} item={item} model={model} onChange={onChange} />
          ))}
        </div>
        {!model.classes.length && !model.enums.length ? (
          <p className="text-[12.5px] text-fg-3">Nothing in the model yet — add a class to start.</p>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-[15px] font-bold text-fg">Relationships</h3>
          <Button size="sm" variant="secondary" disabled={model.classes.length < 2} onClick={() => onChange(addRelationship(model))}>
            <Plus /> Relationship
          </Button>
        </div>
        {model.relationships.length ? (
          <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
            {model.relationships.map((rel) => (
              <RelationshipRow key={rel.id} rel={rel} model={model} onChange={onChange} />
            ))}
          </div>
        ) : (
          <p className="text-[12.5px] text-fg-3">
            {model.classes.length < 2 ? 'Two classes are needed before they can be related.' : 'No relationships yet.'}
          </p>
        )}
      </div>
    </div>
  )
}

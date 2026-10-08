/** A class model written back out as draw.io XML.
 *
 * The other half of `drawioModel.ts`. The rule engine writes this shape on the
 * server (`app/rule_engine/pipeline.py::generate_drawio_xml`), but a model the
 * user edits in the browser has to become XML without a round trip - the
 * draw.io tab, the saved diagram and the downloaded file all read from it.
 *
 * The two must agree: `parseDrawioClassModel(buildDrawioXml(model))` has to give
 * the model back. That is what keeps the Classes editor, the canvas and the
 * draw.io editor showing one model rather than three drifting copies.
 */
import type { ClassModelerResult, ModelClass, ModelEnum, ModelMethod, ModelRelationship } from '../../api'

type ClassModel = ClassModelerResult['model']

const LAYOUT = {
  columns: 3,
  startX: 80,
  startY: 80,
  horizontalGap: 340,
  verticalGap: 260,
  classWidth: 240,
  headerHeight: 32,
  rowHeight: 22,
  dividerHeight: 8,
  minimumClassHeight: 100,
}

const VISIBILITY_SIGN: Record<string, string> = { public: '+', private: '-', protected: '#', package: '~' }
const CARDINALITY_TYPES = new Set<ModelRelationship['type']>(['association', 'aggregation', 'composition'])

/* A draw.io label is escaped twice, and the two levels are not interchangeable.
 *
 * The inner level is HTML: a cell's value is an HTML fragment, where `<br>` is a
 * line break and a type like `List<Book>` has to be written `List&lt;Book&gt;`
 * so it is not read as a tag. The outer level is XML: that whole fragment then
 * becomes an attribute value, where even the `<` of `<br>` must be escaped or
 * the document is not well-formed.
 *
 * Writing them in the wrong order produces either a broken document or a label
 * that renders as markup, so the two have separate functions and `escapeXml`
 * is applied once, at the point the attribute is written. */
function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function escapeXml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function attributeRow(attribute: { name: string; type: string; visibility: string }): string {
  const sign = VISIBILITY_SIGN[attribute.visibility] ?? '-'
  return `${sign} ${escapeHtml(attribute.name)}: ${escapeHtml(attribute.type || 'String')}`
}

function methodRow(method: ModelMethod): string {
  const parameters = method.parameters
    .filter((parameter) => parameter.name)
    .map((parameter) => (parameter.type ? `${parameter.name}: ${parameter.type}` : parameter.name))
    .join(', ')
  const sign = VISIBILITY_SIGN[method.visibility] ?? '+'
  return `${sign} ${escapeHtml(method.name)}(${escapeHtml(parameters)}): ${escapeHtml(method.returnType || 'void')}`
}

function header(name: string, stereotype: string): string {
  return stereotype && stereotype !== 'entity' ? `«${stereotype}» ${escapeHtml(name)}` : escapeHtml(name)
}

/** The inverse of `parseRelationshipType` - the same arrow styles the rule
 * engine writes, so a diagram built here opens identically in diagrams.net. */
function relationshipStyle(type: ModelRelationship['type']): string {
  const base = 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
  const ends: Record<ModelRelationship['type'], string> = {
    association: 'dashed=0;startArrow=none;endArrow=none;',
    composition: 'dashed=0;startArrow=diamondThin;startFill=1;endArrow=none;',
    aggregation: 'dashed=0;startArrow=diamondThin;startFill=0;endArrow=none;',
    inheritance: 'dashed=0;startArrow=none;endArrow=block;endFill=0;',
    dependency: 'dashed=1;startArrow=none;endArrow=open;endFill=0;',
    realization: 'dashed=1;startArrow=none;endArrow=block;endFill=0;',
  }
  return base + (ends[type] ?? ends.association)
}

type Box = { id: string; name: string; title: string; attributeRows: string[]; methodRows: string[] }

function boxesOf(model: ClassModel): Box[] {
  const classes: Box[] = model.classes.map((cls: ModelClass) => ({
    id: cls.id,
    name: cls.name,
    title: header(cls.name, cls.stereotype),
    attributeRows: cls.attributes.map(attributeRow),
    methodRows: cls.methods.map(methodRow),
  }))
  // Enumerations are drawn as their own «enumeration» boxes, their literals in
  // the attributes block - the shape the parser reads them back from.
  const enums: Box[] = model.enums.map((item: ModelEnum) => ({
    id: item.id,
    name: item.name,
    title: header(item.name, 'enumeration'),
    attributeRows: item.literals.map(escapeHtml),
    methodRows: [],
  }))
  // By name, and by name alone - the rule engine orders the same way, so
  // regenerating a model it produced gives byte-identical XML rather than a
  // diff. Sorting on the decorated title would file «interface» Payable under
  // the guillemet instead of under P.
  return [...classes, ...enums].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
}

export function buildDrawioXml(model: ClassModel): string {
  const boxes = boxesOf(model)
  const cells: string[] = ['<mxCell id="0" />', '<mxCell id="1" parent="0" />']

  boxes.forEach((box, index) => {
    const attributeHeight = Math.max(box.attributeRows.length, 1) * LAYOUT.rowHeight
    const methodHeight = Math.max(box.methodRows.length, 1) * LAYOUT.rowHeight
    const height = Math.max(
      LAYOUT.headerHeight + attributeHeight + methodHeight + LAYOUT.dividerHeight,
      LAYOUT.minimumClassHeight,
    )
    const x = LAYOUT.startX + (index % LAYOUT.columns) * LAYOUT.horizontalGap
    const y = LAYOUT.startY + Math.floor(index / LAYOUT.columns) * LAYOUT.verticalGap
    cells.push(
      `<mxCell id="${escapeXml(box.id)}" value="${escapeXml(box.title)}" style="swimlane;fontStyle=1;align=center;verticalAlign=top;` +
        'childLayout=stackLayout;horizontal=1;startSize=32;horizontalStack=0;resizeParent=1;resizeParentMax=0;' +
        'resizeLast=0;collapsible=0;marginBottom=0;rounded=0;whiteSpace=wrap;html=1;" vertex="1" parent="1">' +
        `<mxGeometry x="${x}" y="${y}" width="${LAYOUT.classWidth}" height="${height}" as="geometry" /></mxCell>`,
    )
    const sections: [string, number, string[], number][] = [
      ['attributes', LAYOUT.headerHeight, box.attributeRows.length ? box.attributeRows : [' '], attributeHeight],
      [
        'methods',
        LAYOUT.headerHeight + attributeHeight + LAYOUT.dividerHeight,
        box.methodRows.length ? box.methodRows : [' '],
        methodHeight,
      ],
    ]
    for (const [name, offsetY, rows, sectionHeight] of sections) {
      cells.push(
        `<mxCell id="${escapeXml(box.id)}_${name}" value="${escapeXml(rows.join('<br>'))}" style="text;strokeColor=none;fillColor=none;` +
          'align=left;verticalAlign=top;spacingLeft=8;spacingRight=8;overflow=hidden;rotatable=0;whiteSpace=wrap;html=1;" ' +
          `vertex="1" parent="${escapeXml(box.id)}">` +
          `<mxGeometry x="0" y="${offsetY}" width="${LAYOUT.classWidth}" height="${sectionHeight}" as="geometry" /></mxCell>`,
      )
    }
  })

  const drawn = new Set(boxes.map((box) => box.id))
  const edges = model.relationships
    .filter((rel) => drawn.has(rel.sourceClassId) && drawn.has(rel.targetClassId))
    .slice()
    .sort((a, b) =>
      `${a.sourceClassId}${a.targetClassId}${a.type}${a.label}`.localeCompare(
        `${b.sourceClassId}${b.targetClassId}${b.type}${b.label}`,
      ),
    )

  for (const rel of edges) {
    cells.push(
      `<mxCell id="${escapeXml(rel.id)}" value="${escapeXml(escapeHtml(rel.label ?? ''))}" style="${relationshipStyle(rel.type)}" edge="1" ` +
        `parent="1" source="${escapeXml(rel.sourceClassId)}" target="${escapeXml(rel.targetClassId)}">` +
        '<mxGeometry relative="1" as="geometry" /></mxCell>',
    )
    if (!CARDINALITY_TYPES.has(rel.type)) continue
    const labels: [string, string | null, string][] = [
      ['source_multiplicity', rel.sourceMultiplicity, '-0.85'],
      ['target_multiplicity', rel.targetMultiplicity, '0.85'],
    ]
    for (const [suffix, value, position] of labels) {
      if (!value) continue
      cells.push(
        `<mxCell id="${escapeXml(rel.id)}_${suffix}" value="${escapeXml(escapeHtml(value))}" ` +
          'style="edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];" vertex="1" connectable="0" ' +
          `parent="${escapeXml(rel.id)}">` +
          `<mxGeometry x="${position}" relative="1" as="geometry"><mxPoint as="offset" /></mxGeometry></mxCell>`,
      )
    }
  }

  return (
    '<mxfile host="app.diagrams.net" type="device"><diagram id="class-diagram" name="Class Diagram">' +
    '<mxGraphModel dx="1422" dy="794" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" ' +
    'fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="827" math="0" shadow="0"><root>' +
    cells.join('') +
    '</root></mxGraphModel></diagram></mxfile>'
  )
}

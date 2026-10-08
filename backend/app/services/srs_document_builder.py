"""Turn the approved stages of a generation pipeline run into an IEEE-830 style SRS document.

The builder is pure: it takes the run metadata and the latest payload of every stage and
returns ``(markdown, content_json)``. It never invents content — every line comes from a
stage the user reviewed and approved.
"""

import re
from datetime import datetime
from typing import Any

ENGINE_LABELS = {
    "rule_based": "Rule-Based Engine",
    "ollama": "Local AI (Ollama)",
    "byok": "AI provider (your API key)",
    "srsgen": "SrsGen",
    "ai": "AI generation",
}


POSSESSIVE_ACTIONS = {"have", "has", "contain", "contains", "include", "includes", "own", "owns"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return ", ".join(part for part in (_text(item) for item in value) if part)
    if isinstance(value, dict):
        for key in ("name", "text", "statement", "value", "label"):
            if value.get(key):
                return _text(value[key])
        return ""
    return str(value).strip()


def _cell(value: Any) -> str:
    """Markdown table cell: single line, pipes escaped, dash when empty."""
    cleaned = " ".join(_text(value).split()).replace("|", "\\|")
    return cleaned or "—"


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return lines


def _enabled(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and item.get("enabled", True) is not False]


def _requirement_id(item: dict[str, Any], index: int) -> str:
    return _text(item.get("requirementId") or item.get("id")) or f"REQ-{index + 1:03d}"


def _is_placeholder(value: str) -> bool:
    return not value or value.lower().startswith("unknown")


def _clarification_rows(payload: dict[str, Any]) -> list[list[Any]]:
    questions = [item for item in payload.get("clarificationQuestions", []) if isinstance(item, dict)]
    answers = [item for item in payload.get("answers", []) if isinstance(item, dict)]

    def answer_for(question_id: Any) -> dict[str, Any] | None:
        for answer in answers:
            if str(answer.get("questionStableId") or answer.get("question_id") or answer.get("questionId")) == str(
                question_id
            ):
                return answer
        return None

    rows: list[list[Any]] = []
    for question in questions:
        answer = answer_for(question.get("id"))
        if answer is None:
            resolution = "Unanswered"
        elif answer.get("status") in {"skipped", "not_applicable"} and not answer.get("answerText"):
            resolution = "Skipped"
        else:
            resolution = _text(answer.get("answerText") or answer.get("answer"))
        rows.append([question.get("text") or question.get("question"), resolution])
    return rows


def _attribute_line(attribute: Any) -> str:
    if isinstance(attribute, str):
        return attribute
    if not isinstance(attribute, dict):
        return ""
    name = _text(attribute.get("name"))
    data_type = _text(attribute.get("type") or attribute.get("dataType"))
    return f"{name}: {data_type}" if name and data_type else name


def _method_line(method: Any) -> str:
    if isinstance(method, str):
        return method if method.endswith(")") else f"{method}()"
    if not isinstance(method, dict):
        return ""
    name = _text(method.get("name"))
    if not name:
        return ""
    parameters = method.get("parameters") if isinstance(method.get("parameters"), list) else []
    params = ", ".join(
        part
        for part in (
            (f"{_text(p.get('name'))}: {_text(p.get('type'))}".strip(": ") if isinstance(p, dict) else _text(p))
            for p in parameters
        )
        if part
    )
    return_type = _text(method.get("returnType"))
    return f"{name}({params})" + (f": {return_type}" if return_type and return_type != "void" else "")


def _describe_multiplicity(value: Any) -> str | None:
    """"0..5" -> "up to 5", "1..*" -> "one or more". Mirrors the wording the
    Classes tab uses in the UI (frontend relationshipGuide.describeMultiplicity),
    so the document reads the way the screen the user approved it on reads."""
    text = _text(value)
    if not text:
        return None
    fixed = {"1": "exactly one", "0..1": "at most one", "*": "any number of", "0..*": "any number of", "1..*": "one or more"}
    if text in fixed:
        return fixed[text]
    for pattern, template in (
        (r"^0\.\.(\d+)$", "up to {0}"),
        (r"^(\d+)\.\.\*$", "at least {0}"),
        (r"^(\d+)\.\.(\d+)$", "between {0} and {1}"),
        (r"^(\d+)$", "exactly {0}"),
    ):
        match = re.match(pattern, text)
        if match:
            return template.format(*match.groups())
    return text


def _plural(name: str, count: str | None) -> str:
    if not count or count in {"exactly one", "at most one"} or name.endswith("s"):
        return name
    return f"{name}s"


def _relationship_sentence(relationship: dict[str, Any], source: str, target: str, by_name: dict[str, dict[str, Any]]) -> str:
    """One plain-English sentence for an edge, as the Classes tab explains it."""
    kind = _text(relationship.get("type"))
    target_class = by_name.get(target, {})
    if kind == "inheritance":
        return f"{source} is a {target} and inherits its attributes and operations."
    if kind == "realization":
        methods = [line for line in (_method_line(m) for m in target_class.get("methods") or []) if line]
        promise = f" and must provide {', '.join(methods)}" if methods else ""
        return f"{source} implements the {target} contract{promise}."
    forward = _describe_multiplicity(relationship.get("targetMultiplicity"))
    backward = _describe_multiplicity(relationship.get("sourceMultiplicity"))
    verb = {"composition": "owns", "aggregation": "has", "dependency": "uses"}.get(kind) or _text(relationship.get("label")) or "is linked to"
    sentence = f"Each {source} {verb} {forward + ' ' if forward else ''}{_plural(target, forward)}."
    if kind == "composition":
        sentence += f" A {target} cannot exist without its {source}."
    elif kind == "aggregation":
        sentence += f" A {target} can also exist on its own."
    elif backward:
        sentence += f" Each {target} belongs to {backward} {_plural(source, backward)}."
    if relationship.get("multiplicityAssumed"):
        sentence += " (The count was not stated in the text, so it is assumed.)"
    return sentence


def build_srs_document(
    *,
    title: str,
    project_name: str,
    generation_mode: str,
    provider: str | None,
    model_name: str | None,
    raw_text: str,
    stages: dict[str, dict[str, Any]],
    generated_at: datetime,
    diagram_title: str | None = None,
) -> tuple[str, dict[str, Any]]:
    clarifications = stages.get("clarifications", {})
    final_story = stages.get("final-story", {})
    requirements_payload = stages.get("requirements", {})
    class_model = stages.get("class-model", {})

    requirements = _enabled(requirements_payload.get("requirements"))
    functional = [item for item in requirements if item.get("requirementType", "functional") != "non_functional"]
    non_functional = [item for item in requirements if item.get("requirementType") == "non_functional"]
    classes = _enabled(class_model.get("classes"))
    relationships = _enabled(class_model.get("relationships"))
    enums = _enabled(class_model.get("enums"))
    stories = [item for item in final_story.get("atomicStorySections", []) if isinstance(item, dict)]
    class_names = {str(item.get("id")): _text(item.get("name")) for item in classes}
    classes_by_name = {_text(item.get("name")): item for item in classes}

    # An "actor" that only ever *has* things (e.g. "Each book has a title") is a data entity, not a user class.
    acting = [
        item
        for item in [*requirements, *stories]
        if _text(item.get("action")).lower() not in POSSESSIVE_ACTIONS
    ]
    actors = sorted(
        {
            actor
            for actor in (_text(item.get("actor")) for item in acting)
            if not _is_placeholder(actor) and actor.lower() != "system"
        }
    )

    engine = ENGINE_LABELS.get(generation_mode, generation_mode)
    if generation_mode in {"byok", "ollama"} and (provider or model_name):
        engine = f"{engine} · {' / '.join(part for part in (provider, model_name) if part)}"

    lines: list[str] = [
        f"# {title}",
        "",
        "## Software Requirements Specification",
        "",
        f"**Project:** {project_name}  ",
        f"**Generated:** {generated_at.strftime('%d %B %Y')}  ",
        f"**Engine:** {engine}",
        "",
        "---",
        "",
        "## 1. Introduction",
        "",
        "### 1.1 Purpose",
        "",
        f"This document specifies the software requirements for **{project_name}**. "
        "It was derived from the stakeholder input below and refined through a reviewed, "
        "stage-by-stage generation pipeline: clarifications, a normalised story, requirements "
        "and a domain class model.",
        "",
        "### 1.2 Scope and stakeholder input",
        "",
        *[f"> {line}" if line.strip() else ">" for line in raw_text.strip().splitlines()],
        "",
        "### 1.3 Definitions",
        "",
    ]
    if classes:
        lines.extend(
            f"- **{_text(item.get('name'))}** — {_text(item.get('stereotype')) or 'domain'} concept"
            for item in classes
        )
    else:
        lines.append("- No domain terms were identified.")

    lines.extend(["", "## 2. Overall Description", "", "### 2.1 User classes", ""])
    lines.extend([f"- {actor}" for actor in actors] or ["- No distinct user classes were identified."])

    lines.extend(["", "### 2.2 User stories", ""])
    story_lines = [
        f"{index + 1}. {_text(item.get('normalizedSentence') or item.get('sourceSentence'))}"
        for index, item in enumerate(stories)
        if _text(item.get("normalizedSentence") or item.get("sourceSentence"))
    ]
    lines.extend(story_lines or ["No user stories were produced."])

    clarification_rows = _clarification_rows(clarifications)
    lines.extend(["", "### 2.3 Clarifications", ""])
    if clarification_rows:
        lines.extend(_table(["Question", "Resolution"], clarification_rows))
    else:
        lines.append("No ambiguities required clarification.")

    lines.extend(["", "## 3. Specific Requirements", "", "### 3.1 Functional requirements", ""])
    if functional:
        lines.extend(
            _table(
                ["ID", "Requirement", "Actor", "Source"],
                [
                    [_requirement_id(item, index), item.get("statement"), item.get("actor"), item.get("sourceSentence")]
                    for index, item in enumerate(functional)
                ],
            )
        )
    else:
        lines.append("No functional requirements were identified.")

    lines.extend(["", "### 3.2 Non-functional requirements", ""])
    if non_functional:
        lines.extend(
            _table(
                ["ID", "Requirement", "Category", "Target"],
                [
                    [
                        _requirement_id(item, index),
                        item.get("statement"),
                        item.get("nfrCategory"),
                        " ".join(filter(None, [_text(item.get("metric")), _text(item.get("targetValue"))])),
                    ]
                    for index, item in enumerate(non_functional)
                ],
            )
        )
    else:
        lines.append("No non-functional requirements were identified.")

    lines.extend(["", "## 4. Domain Model", "", "### 4.1 Classes", ""])
    if classes:
        for item in classes:
            stereotype = _text(item.get("stereotype"))
            lines.append(f"#### {_text(item.get('name'))}" + (f" «{stereotype}»" if stereotype else ""))
            lines.append("")
            attributes = [line for line in (_attribute_line(a) for a in item.get("attributes") or []) if line]
            methods = [line for line in (_method_line(m) for m in item.get("methods") or []) if line]
            lines.append("- **Attributes:** " + (", ".join(f"`{a}`" for a in attributes) if attributes else "none"))
            lines.append("- **Operations:** " + (", ".join(f"`{m}`" for m in methods) if methods else "none"))
            # The generalisation lines the Classes tab prints under the class name.
            class_id = str(item.get("id"))
            for label, kinds, own_side, other_side in (
                ("Inherits from", {"inheritance"}, "sourceClassId", "targetClassId"),
                ("Implements", {"realization"}, "sourceClassId", "targetClassId"),
                ("Specialised by", {"inheritance", "realization"}, "targetClassId", "sourceClassId"),
            ):
                related = [
                    class_names.get(str(rel.get(other_side)), "")
                    for rel in relationships
                    if _text(rel.get("type")) in kinds and str(rel.get(own_side)) == class_id
                ]
                related = sorted({name for name in related if name})
                if related:
                    lines.append(f"- **{label}:** " + ", ".join(related))
            sources = item.get("sourceRequirementIds") or []
            if sources:
                lines.append("- **Traces to:** " + ", ".join(str(source) for source in sources))
            lines.append("")
    else:
        lines.extend(["No classes were modelled.", ""])

    lines.extend(["### 4.2 Relationships", ""])
    if relationships:
        lines.extend(
            _table(
                ["Source", "Relationship", "Target", "Multiplicity", "Label", "In plain words"],
                [
                    [
                        class_names.get(str(item.get("sourceClassId")), item.get("sourceClassId")),
                        _text(item.get("type")).replace("_", " "),
                        class_names.get(str(item.get("targetClassId")), item.get("targetClassId")),
                        f"{_text(item.get('sourceMultiplicity')) or '—'} → {_text(item.get('targetMultiplicity')) or '—'}",
                        item.get("label"),
                        _relationship_sentence(
                            item,
                            class_names.get(str(item.get("sourceClassId")), ""),
                            class_names.get(str(item.get("targetClassId")), ""),
                            classes_by_name,
                        ),
                    ]
                    for item in relationships
                ],
            )
        )
    else:
        lines.append("No relationships were modelled.")

    if enums:
        lines.extend(["", "### 4.3 Enumerations", ""])
        lines.extend(
            _table(
                ["Enumeration", "Allowed values", "Used by"],
                [
                    [
                        _text(item.get("name")),
                        ", ".join(f"`{_text(literal)}`" for literal in item.get("literals") or []),
                        ", ".join(
                            sorted(
                                {
                                    _text(cls.get("name"))
                                    for cls in classes
                                    for attribute in cls.get("attributes") or []
                                    if isinstance(attribute, dict) and _text(attribute.get("type")) == _text(item.get("name"))
                                }
                            )
                        )
                        or _text(item.get("owner")),
                    ]
                    for item in enums
                ],
            )
        )

    trace_rows: list[list[Any]] = []
    for index, item in enumerate([*functional, *non_functional]):
        requirement_id = _requirement_id(item, index)
        linked = [
            _text(cls.get("name"))
            for cls in classes
            if requirement_id in [str(source) for source in cls.get("sourceRequirementIds") or []]
        ]
        trace_rows.append([requirement_id, item.get("statement"), ", ".join(linked)])
    lines.extend(["", "## Appendix A. Traceability matrix", ""])
    lines.extend(_table(["Requirement", "Statement", "Realised by"], trace_rows) if trace_rows else ["No requirements to trace."])

    lines.extend(["", "## Appendix B. Class diagram", ""])
    lines.append(
        f"The UML class diagram for this model is saved in **Diagrams** as “{diagram_title}”."
        if diagram_title
        else "The UML class diagram is available from the generation run."
    )
    lines.append("")

    content_json = {
        "source": "pipeline",
        "projectName": project_name,
        "generationMode": generation_mode,
        "provider": provider,
        "modelName": model_name,
        "actors": actors,
        "enums": [
            {"name": _text(item.get("name")), "literals": [_text(literal) for literal in item.get("literals") or []]}
            for item in enums
        ],
        "stories": [_text(item.get("normalizedSentence") or item.get("sourceSentence")) for item in stories],
        "clarifications": [{"question": row[0], "resolution": row[1]} for row in clarification_rows],
        "requirements": [
            {
                "id": _requirement_id(item, index),
                "type": item.get("requirementType", "functional"),
                "statement": _text(item.get("statement")),
                "actor": _text(item.get("actor")) or None,
                "category": _text(item.get("nfrCategory")) or None,
                "source": _text(item.get("sourceSentence")) or None,
            }
            for index, item in enumerate(requirements)
        ],
        "classCount": len(classes),
        "relationshipCount": len(relationships),
    }
    return "\n".join(lines), content_json

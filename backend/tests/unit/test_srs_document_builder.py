"""The published SRS has to carry what the Classes tab shows on screen.

A reader approves a class model in the UI and then gets a document; if the
document drops the enums, the generalisation lines or the plain-English reading
of each edge, it is a thinner artifact than the thing that was reviewed.
"""

from datetime import datetime, timezone

from app.services.srs_document_builder import build_srs_document

STAGES = {
    "clarifications": {"facts": [], "sentences": [], "clarificationQuestions": [], "answers": []},
    "final-story": {
        "atomicStorySections": [{"normalizedSentence": "A member borrows a book.", "actor": "Member", "action": "borrow"}]
    },
    "requirements": {
        "requirements": [
            {"requirementId": "REQ-001", "statement": "A member can borrow books.", "actor": "Member", "requirementType": "functional"}
        ]
    },
    "class-model": {
        "classes": [
            {"id": "c1", "name": "Person", "stereotype": "abstract", "attributes": [{"name": "name", "type": "String"}], "methods": []},
            {
                "id": "c2",
                "name": "Member",
                "stereotype": "entity",
                "attributes": [{"name": "status", "type": "MemberStatus"}],
                "methods": [{"name": "borrow", "parameters": [{"name": "book", "type": "Book"}], "returnType": "void"}],
            },
            {"id": "c3", "name": "Book", "stereotype": "entity", "attributes": [{"name": "title", "type": "String"}], "methods": []},
            {
                "id": "c4",
                "name": "Payable",
                "stereotype": "interface",
                "attributes": [],
                "methods": [{"name": "pay", "parameters": [], "returnType": "Boolean"}],
            },
        ],
        "relationships": [
            {"id": "r1", "sourceClassId": "c2", "targetClassId": "c1", "type": "inheritance"},
            {
                "id": "r2",
                "sourceClassId": "c2",
                "targetClassId": "c3",
                "type": "association",
                "label": "borrows",
                "sourceMultiplicity": "1",
                "targetMultiplicity": "0..5",
            },
            {"id": "r3", "sourceClassId": "c2", "targetClassId": "c4", "type": "realization"},
            {
                "id": "r4",
                "sourceClassId": "c3",
                "targetClassId": "c1",
                "type": "composition",
                "sourceMultiplicity": "1",
                "targetMultiplicity": "1..*",
            },
        ],
        "enums": [{"id": "e1", "name": "MemberStatus", "literals": ["ACTIVE", "SUSPENDED"]}],
    },
}


def _build(stages=None):
    markdown, content = build_srs_document(
        title="Library SRS",
        project_name="Library",
        generation_mode="ai",
        provider="ai",
        model_name=None,
        raw_text="A member can borrow up to five books.",
        stages=stages or STAGES,
        generated_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        diagram_title="Library class model",
    )
    return markdown, content


def _domain_model(markdown: str) -> str:
    return markdown[markdown.index("## 4. Domain Model") : markdown.index("## Appendix A")]


def test_each_class_says_what_it_inherits_implements_and_is_specialised_by() -> None:
    section = _domain_model(_build()[0])
    assert "- **Inherits from:** Person" in section
    assert "- **Implements:** Payable" in section
    # The other end of the same edges, so a parent reads as a parent.
    assert section.count("- **Specialised by:** Member") == 2


def test_relationships_are_also_written_in_plain_words() -> None:
    section = _domain_model(_build()[0])
    assert "Member is a Person and inherits its attributes and operations." in section
    assert "Each Member borrows up to 5 Books. Each Book belongs to exactly one Member." in section
    assert "Member implements the Payable contract and must provide pay(): Boolean." in section
    # Composition and aggregation carry their own lifetime rule.
    assert "A Person cannot exist without its Book." in section


def test_enumerations_get_their_own_subsection_naming_the_classes_that_use_them() -> None:
    markdown, content = _build()
    section = _domain_model(markdown)
    assert "### 4.3 Enumerations" in section
    assert "| MemberStatus | `ACTIVE`, `SUSPENDED` | Member |" in section
    assert content["enums"] == [{"name": "MemberStatus", "literals": ["ACTIVE", "SUSPENDED"]}]


def test_a_model_without_enums_does_not_grow_an_empty_subsection() -> None:
    stages = {**STAGES, "class-model": {**STAGES["class-model"], "enums": []}}
    section = _domain_model(_build(stages)[0])
    assert "4.3 Enumerations" not in section
    assert "### 4.2 Relationships" in section

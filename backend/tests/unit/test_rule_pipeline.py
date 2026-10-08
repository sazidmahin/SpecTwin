import xml.etree.ElementTree as ET

import pytest

from app.rule_engine.pipeline import (
    analyze_text,
    apply_answers,
    generate_class_model,
    generate_drawio_xml,
    generate_final_story,
    generate_requirements,
    validate_class_model,
)


def _flow(text: str):
    analysis = analyze_text(text)
    final_story = generate_final_story(text, analysis["sentences"], analysis["facts"], [])
    requirements = generate_requirements(final_story, analysis["facts"])["requirements"]
    class_model = generate_class_model(requirements, analysis["facts"])
    return analysis, final_story, requirements, class_model


def test_customer_create_order_generates_fr_classes_and_association() -> None:
    analysis, _, requirements, class_model = _flow("A customer can create an order.")

    fact = analysis["facts"][0]
    assert fact["actor"] == "Customer"
    assert fact["action"] == "create"
    assert fact["object"] == "Order"
    assert any(req["requirementId"] == "FR-001" for req in requirements)
    assert {cls["id"] for cls in class_model["classes"]} >= {"class_customer", "class_order"}
    assert class_model["relationships"][0]["type"] == "association"


def test_condition_and_pronoun_resolution_generate_conditional_fr() -> None:
    analysis, _, requirements, _ = _flow("If payment fails, the customer can retry it.")

    fact = analysis["facts"][0]
    assert fact["condition"] == {"subject": "Payment", "operator": "is", "value": "failed"}
    assert fact["actor"] == "Customer"
    assert fact["action"] == "retry"
    assert fact["object"] == "Payment"
    assert requirements[0]["statement"].startswith("If Payment failed")


def test_only_administrator_generates_business_rule_and_method() -> None:
    _, _, requirements, class_model = _flow("Only an administrator can delete a product.")

    assert any(req["requirementType"] == "business_rule" for req in requirements)
    assert {cls["id"] for cls in class_model["classes"]} >= {"class_administrator", "class_product"}
    admin = next(cls for cls in class_model["classes"] if cls["id"] == "class_administrator")
    assert any(method["id"] == "method_administrator_delete_product" for method in admin["methods"])


def test_order_contains_product_generates_composition_and_multiplicity() -> None:
    analysis, _, requirements, class_model = _flow("An order must contain at least one product.")

    fact = analysis["facts"][0]
    assert fact["sourceMultiplicity"] == "1"
    assert fact["targetMultiplicity"] == "1..*"
    assert any(req["requirementType"] == "business_rule" for req in requirements)
    relationship = class_model["relationships"][0]
    assert relationship["type"] == "composition"
    assert relationship["sourceMultiplicity"] == "1"
    assert relationship["targetMultiplicity"] == "1..*"


def test_performance_nfr_is_measurable() -> None:
    analysis, _, requirements, _ = _flow("The system must respond within three seconds.")

    fact = analysis["facts"][0]
    assert fact["nfr"]["category"] == "Performance"
    assert fact["nfr"]["measurable"] is True
    assert fact["nfr"]["targetValue"] == 3
    assert fact["nfr"]["unit"] == "seconds"
    assert requirements[0]["requirementType"] == "non_functional"


def test_passive_deleted_story_generates_missing_actor_question() -> None:
    analysis = analyze_text("Orders can be deleted.")

    fact = analysis["facts"][0]
    assert fact["actor"] is None
    assert "actor" in fact["missingFields"]
    assert analysis["clarificationQuestions"][0]["triggeredRuleId"] == "CLR_MISSING_ACTOR_001"


def test_unknown_entities_are_detected_positionally() -> None:
    analysis = analyze_text("A curator can archive a manuscript.")

    fact = analysis["facts"][0]
    assert fact["actor"] == "Curator"
    assert fact["action"] == "archive"
    assert fact["object"] == "Manuscript"


def test_extended_dictionary_recognizes_additional_action_and_relationship_phrases() -> None:
    enrollment = analyze_text("A customer enrolls an event.")["facts"][0]
    managed = analyze_text("A report is managed by a manager.")["facts"][0]

    assert enrollment["action"] == "register"
    assert managed["actor"] == "Report"
    assert managed["object"] == "Manager"
    assert managed["relationshipType"] == "association"


def test_business_narrative_is_normalized_to_customer_and_administrator_user_stories() -> None:
    raw_text = """
    I have a small online clothing business and I want people to be able to see the clothes I sell.
    If someone likes a dress or a shirt, they should be able to put it in their basket and buy more than one item together.
    When a person buys something, I need to know their name, phone number, email and where the parcel should be sent.
    After payment, they should get some kind of order number so they can ask us about their order later.
    I also need to see all the orders that customers make. My staff should be able to check an order, accept it, pack the items and send it to the customer.
    When we send the parcel, we should be able to keep a tracking number. I need to change the stock and price when needed.
    I also want to know which customers buy often, because later I may give them special discounts or offers.
    """
    analysis = analyze_text(raw_text)

    final_story = generate_final_story(raw_text, analysis["sentences"], analysis["facts"], [])
    stories = [section["normalizedSentence"] for section in final_story["atomicStorySections"]]
    requirements = generate_requirements(final_story, analysis["facts"])["requirements"]
    class_model = generate_class_model(requirements, analysis["facts"])

    assert any(story.startswith("As a customer, I want to create an account") for story in stories)
    assert any("browse available products" in story for story in stories)
    assert any("add products to my shopping cart" in story for story in stories)
    assert any("check and approve an order" in story for story in stories)
    assert any("update product stock and prices" in story for story in stories)
    assert {item["id"] for item in class_model["classes"]} >= {
        "class_customer",
        "class_order",
        "class_product",
        "class_shopping_cart",
        "class_administrator",
    }


def test_xml_generation_is_byte_deterministic() -> None:
    _, _, _, class_model = _flow("A customer can create an order.")

    xml_one, validation_one = generate_drawio_xml(class_model)
    xml_two, validation_two = generate_drawio_xml(class_model)

    assert validation_one["valid"] is True
    assert validation_two["valid"] is True
    assert xml_one == xml_two
    assert "class_customer" in xml_one
    assert "edge_customer_create_order" in xml_one
    assert "swimlane" in xml_one
    assert "$id" not in xml_one

    parsed = ET.fromstring(xml_one)
    customer_cell = parsed.find(".//mxCell[@id='class_customer']")
    assert customer_cell is not None
    assert customer_cell.attrib["value"] == "Customer"
    assert customer_cell.attrib["vertex"] == "1"
    assert customer_cell.find("mxGeometry") is not None


def test_clarification_answer_slot_filling_is_deterministic() -> None:
    analysis = analyze_text("Orders can be deleted.")
    question = analysis["clarificationQuestions"][0]
    answers = [{"questionStableId": question["id"], "answerText": "Administrator", "status": "answered", "appliedSlot": "actor"}]
    merged = apply_answers(analysis["facts"], answers, {question["id"]: question})

    assert merged[0]["actor"] == "Administrator"
    assert "actor" not in merged[0]["missingFields"]


def test_clarification_answer_generates_class_diagram_entities() -> None:
    analysis = analyze_text("Orders can be deleted.")
    question = analysis["clarificationQuestions"][0]
    answers = [{"questionStableId": question["id"], "answerText": "Administrator", "status": "answered", "appliedSlot": "actor"}]
    merged = apply_answers(analysis["facts"], answers, {question["id"]: question})
    final_story = generate_final_story("Orders can be deleted.", analysis["sentences"], merged, answers)
    requirements = generate_requirements(final_story, analysis["facts"])["requirements"]
    class_model = generate_class_model(requirements, analysis["facts"])
    xml, validation = generate_drawio_xml(class_model)

    assert validation["valid"] is True
    assert {item["id"] for item in class_model["classes"]} >= {"class_administrator", "class_order"}
    assert "Administrator" in xml
    assert "Order" in xml


def _relationship_model(
    relationship_type: str,
    *,
    direction: str = "source-to-target",
    source_multiplicity: str | None = None,
    target_multiplicity: str | None = None,
) -> dict:
    return {
        "classes": [
            {"id": "class_child", "name": "Child", "attributes": [], "methods": [], "enabled": True},
            {"id": "class_parent", "name": "Parent", "attributes": [], "methods": [], "enabled": True},
        ],
        "relationships": [
            {
                "id": "edge_child_parent",
                "sourceClassId": "class_child",
                "targetClassId": "class_parent",
                "type": relationship_type,
                "label": relationship_type,
                "sourceMultiplicity": source_multiplicity,
                "targetMultiplicity": target_multiplicity,
                "direction": direction,
                "enabled": True,
            }
        ],
    }


@pytest.mark.parametrize(
    ("relationship_type", "style_fragments"),
    [
        ("composition", ["startArrow=diamondThin", "startFill=1", "endArrow=none"]),
        ("aggregation", ["startArrow=diamondThin", "startFill=0", "endArrow=none"]),
        ("inheritance", ["endArrow=block", "endFill=0", "dashed=0"]),
        ("dependency", ["dashed=1", "endArrow=open"]),
        ("realization", ["dashed=1", "endArrow=block", "endFill=0"]),
    ],
)
def test_xml_uses_predefined_uml_style_for_each_relationship(
    relationship_type: str, style_fragments: list[str]
) -> None:
    xml, validation = generate_drawio_xml(_relationship_model(relationship_type))

    assert validation["valid"] is True
    edge = ET.fromstring(xml).find(".//mxCell[@id='edge_child_parent']")
    assert edge is not None
    assert all(fragment in edge.attrib["style"] for fragment in style_fragments)


@pytest.mark.parametrize(
    ("direction", "style_fragments"),
    [
        ("source-to-target", ["startArrow=none", "endArrow=open"]),
        ("target-to-source", ["startArrow=open", "endArrow=none"]),
        ("bidirectional", ["startArrow=open", "endArrow=open"]),
        ("undirected", ["startArrow=none", "endArrow=none"]),
    ],
)
def test_association_direction_controls_navigability_arrows(
    direction: str, style_fragments: list[str]
) -> None:
    xml, validation = generate_drawio_xml(_relationship_model("association", direction=direction))

    assert validation["valid"] is True
    edge = ET.fromstring(xml).find(".//mxCell[@id='edge_child_parent']")
    assert edge is not None
    assert all(fragment in edge.attrib["style"] for fragment in style_fragments)


def test_cardinality_relationship_renders_both_multiplicity_labels() -> None:
    xml, validation = generate_drawio_xml(
        _relationship_model(
            "composition",
            source_multiplicity="1",
            target_multiplicity="1..*",
        )
    )

    assert validation["valid"] is True
    parsed = ET.fromstring(xml)
    source_label = parsed.find(".//mxCell[@id='edge_child_parent_source_multiplicity']")
    target_label = parsed.find(".//mxCell[@id='edge_child_parent_target_multiplicity']")
    assert source_label is not None and source_label.attrib["value"] == "1"
    assert target_label is not None and target_label.attrib["value"] == "1..*"


def test_invalid_relationship_semantics_are_rejected() -> None:
    validation = validate_class_model(
        _relationship_model("not-a-uml-relation", direction="backwards")
    )

    assert validation["valid"] is False
    assert any("unsupported type" in error for error in validation["errors"])
    assert any("invalid direction" in error for error in validation["errors"])


def test_relationship_to_excluded_class_is_inert_not_an_error() -> None:
    model = _relationship_model("association")
    model["classes"][1]["enabled"] = False

    validation = validate_class_model(model)

    assert validation["valid"] is True
    assert not validation["errors"]


def test_relationship_to_truly_missing_class_is_still_rejected() -> None:
    model = _relationship_model("association")
    model["relationships"][0]["targetClassId"] = "class_ghost"

    validation = validate_class_model(model)

    assert validation["valid"] is False
    assert any("target class is missing or disabled" in error for error in validation["errors"])


def test_xml_drops_edges_that_point_at_an_excluded_class() -> None:
    model = _relationship_model("association")
    model["classes"][1]["enabled"] = False

    xml, validation = generate_drawio_xml(model)

    assert validation["valid"] is True
    assert ET.fromstring(xml).find(".//mxCell[@id='edge_child_parent']") is None


def test_rule_inheritance_has_child_to_parent_direction_without_multiplicity() -> None:
    analysis, _, _, class_model = _flow("A savings account extends an account.")

    assert analysis["facts"][0]["relationshipType"] == "inheritance"
    relationship = class_model["relationships"][0]
    assert relationship["sourceClassId"] == "class_savings_account"
    assert relationship["targetClassId"] == "class_account"
    assert relationship["sourceMultiplicity"] is None
    assert relationship["targetMultiplicity"] is None


def test_primitive_field_nouns_become_attributes_not_classes() -> None:
    _, _, _, class_model = _flow(
        "A member can borrow a book. "
        "A member has a full name, an email address and a membership status."
    )

    classes = {cls["id"]: cls for cls in class_model["classes"]}
    assert set(classes) == {"class_member", "class_book"}
    member_attributes = {attr["name"] for attr in classes["class_member"]["attributes"]}
    assert member_attributes == {"fullName", "emailAddress", "membershipStatus"}
    # No FullName / EmailAddress / MembershipStatus / Status classes were minted.
    assert not any(
        cls["name"] in {"FullName", "EmailAddress", "MembershipStatus", "Status", "Name"}
        for cls in class_model["classes"]
    )


def test_noun_without_behaviour_or_state_is_not_a_class() -> None:
    _, _, _, class_model = _flow(
        "A customer can place an order. The order confirmation appears on the screen."
    )

    names = {cls["name"] for cls in class_model["classes"]}
    assert {"Customer", "Order"}.issubset(names)
    # "screen" is generic; "confirmation" is only name-dropped, never acted on.
    assert "Screen" not in names
    assert "Confirmation" not in names


def test_attribute_only_noun_is_kept_as_a_class() -> None:
    _, _, _, class_model = _flow("A loan has a due date and a return date.")

    loan = next((cls for cls in class_model["classes"] if cls["id"] == "class_loan"), None)
    assert loan is not None
    assert {attr["name"] for attr in loan["attributes"]} == {"dueDate", "returnDate"}


def test_relative_clause_is_not_split_into_a_second_object() -> None:
    analysis = analyze_text("The librarian can remove books that are damaged or lost.")

    objects = {fact["object"] for fact in analysis["facts"]}
    assert objects == {"Book"}
    assert "Lost" not in objects


def test_contraction_is_expanded_so_negation_is_detected() -> None:
    fact = analyze_text("A guest can't delete a review.")["facts"][0]

    assert fact["modality"] == "negative"
    assert fact["negated"] is True


def test_stakeholder_want_sentence_becomes_a_fact() -> None:
    fact = analyze_text("I want customers to be able to track their order.")["facts"][0]

    assert fact["actor"] == "Customer"
    assert fact["action"] == "track"
    assert fact["object"] == "Order"


def test_stakeholder_first_person_maps_to_a_real_actor() -> None:
    fact = analyze_text("I need to see all the orders.")["facts"][0]

    assert fact["actor"] == "Administrator"
    assert fact["action"] == "view"
    assert fact["object"] == "Order"


def test_there_should_be_a_way_for_x_to_y() -> None:
    fact = analyze_text("There should be a way for a manager to reject an order.")["facts"][0]

    assert fact["actor"] == "Manager"
    assert fact["action"] == "reject"
    assert fact["object"] == "Order"


def test_be_able_to_is_stripped_and_goal_clause_dropped() -> None:
    fact = analyze_text(
        "Customers should be able to cancel an order so that they are not charged."
    )["facts"][0]

    assert fact["actor"] == "Customer"
    assert fact["action"] == "cancel"
    assert fact["object"] == "Order"


def test_stakeholder_document_yields_requirements_without_the_narrative_table() -> None:
    raw = (
        "I want patients to be able to book an appointment online. "
        "My staff need to be able to view the daily schedule. "
        "A receptionist can register a new patient."
    )
    analysis = analyze_text(raw)
    final_story = generate_final_story(raw, analysis["sentences"], analysis["facts"], [])
    requirements = generate_requirements(final_story, analysis["facts"])["requirements"]
    class_model = generate_class_model(requirements, analysis["facts"])

    assert final_story["extractionMetadata"]["storySource"] == "rule_facts"
    names = {cls["name"] for cls in class_model["classes"]}
    assert {"Patient", "Staff", "Receptionist", "Appointment"}.issubset(names)
    assert any(
        "book" in req["statement"].lower() and "appointment" in req["statement"].lower()
        for req in requirements
    )

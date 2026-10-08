from app.rule_engine.oop_modeler import analyze_oop_text
from app.rule_engine.pipeline import (
    _quantity_from_text,
    analyze_text,
    generate_class_model,
    generate_final_story,
    generate_requirements,
    validate_drawio_xml,
)

LIBRARY_TASK = (
    "Design a library management system. The library has many books. Each book has a title, an author, an ISBN "
    "and a publication year. A book can be available, borrowed or lost. A library member has a name, an email and "
    "a membership id. A member can borrow up to five books. Members can also reserve books. A librarian is a kind "
    "of staff member. A staff member has an employee id and a salary. The librarian can add, remove and update "
    "books. A loan records the borrow date and the due date. Each loan belongs to exactly one member. The system "
    "calculates the fine for each loan. Members can log in. The system should respond within 2 seconds."
)
BANK_TASK = (
    "Design a banking system. A bank has many customers. A customer has a name, an address and a phone number. "
    "A customer can open one or more accounts. There are two types of accounts: savings accounts and current "
    "accounts. A savings account has an account number, a balance and an interest rate. A current account has an "
    "account number, a balance and an overdraft limit. A customer can deposit money and withdraw money. The bank "
    "calculates the interest for each savings account. Each account contains many transactions."
)


def _classes(result):
    return {cls["name"]: cls for cls in result["model"]["classes"]}


def _attributes(cls):
    return {attr["name"]: attr["type"] for attr in cls["attributes"]}


def _methods(cls):
    return {method["name"]: method for method in cls["methods"]}


def _relationship(result, source, target):
    return next(
        rel for rel in result["model"]["relationships"] if rel["source"] == source and rel["target"] == target
    )


def test_library_task_nouns_become_classes_attributes_and_enum() -> None:
    result = analyze_oop_text(LIBRARY_TASK)
    classes = _classes(result)

    assert set(classes) == {"Book", "Librarian", "Library", "Loan", "Member", "StaffMember"}
    assert _attributes(classes["Book"]) == {
        "title": "String", "author": "String", "isbn": "String", "publicationYear": "Integer", "status": "BookStatus",
    }
    assert result["model"]["enums"][0]["literals"] == ["AVAILABLE", "BORROWED", "LOST"]
    assert _attributes(classes["Loan"])["dueDate"] == "Date"
    assert _attributes(classes["StaffMember"])["salary"] == "Decimal"
    assert result["validation"]["valid"]
    assert validate_drawio_xml(result["drawioXml"])["valid"]


def test_library_task_merges_synonyms_and_rejects_the_system() -> None:
    result = analyze_oop_text(LIBRARY_TASK)
    decisions = {noun["name"]: noun for noun in result["analysis"]["nouns"]}

    assert decisions["LibraryMember"]["decision"] == "merged"
    assert decisions["LibraryMember"]["mergedInto"] == "Member"
    assert decisions["System"]["decision"] == "rejected"
    assert decisions["Author"]["decision"] == "attribute"
    assert any(sentence["kind"] == "Non-functional" for sentence in result["analysis"]["sentences"])


def test_library_task_verbs_become_methods_with_typed_parameters() -> None:
    result = analyze_oop_text(LIBRARY_TASK)
    classes = _classes(result)

    member = _methods(classes["Member"])
    assert member["borrowBook"]["parameters"] == [{"name": "book", "type": "Book"}]
    assert {"reserveBook", "login"} <= set(member)
    # The author's verb is kept ("remove", not the canonical "delete").
    assert {"addBook", "removeBook", "updateBook"} <= set(_methods(classes["Librarian"]))
    # "calculates the fine for each loan" is Loan's data and Loan's behaviour.
    assert "calculateFine" in _methods(classes["Loan"])
    assert _attributes(classes["Loan"])["fine"] == "Decimal"


def test_library_task_relationships_and_multiplicities() -> None:
    result = analyze_oop_text(LIBRARY_TASK)

    borrow = _relationship(result, "Member", "Book")
    assert borrow["targetMultiplicity"] == "0..5"
    assert "borrow" in borrow["label"] and "reserve" in borrow["label"]
    assert _relationship(result, "Librarian", "StaffMember")["type"] == "inheritance"
    assert _relationship(result, "Library", "Book")["type"] == "aggregation"
    assert _relationship(result, "Loan", "Member")["targetMultiplicity"] == "1"


def test_bank_task_generalisation_pulls_shared_attributes_up() -> None:
    result = analyze_oop_text(BANK_TASK)
    classes = _classes(result)

    assert classes["Account"]["stereotype"] == "abstract"
    # Shared fields moved up, plus the reference to its parts.
    assert _attributes(classes["Account"]) == {
        "accountNumber": "String", "balance": "Decimal", "transactions": "List<Transaction>",
    }
    assert set(_attributes(classes["SavingsAccount"])) == {"interestRate", "interest"}
    assert set(_attributes(classes["CurrentAccount"])) == {"overdraftLimit"}
    assert _relationship(result, "CurrentAccount", "Account")["type"] == "inheritance"
    assert _relationship(result, "Customer", "Account")["targetMultiplicity"] == "1..*"
    assert _relationship(result, "Account", "Transaction")["type"] == "composition"
    customer = _methods(classes["Customer"])
    assert customer["deposit"]["parameters"] == [{"name": "amount", "type": "Decimal"}]
    assert "Money" not in classes
    assert "calculateInterest" in _methods(classes["SavingsAccount"])


def test_container_verb_and_unknown_verbs_and_prepositional_objects() -> None:
    shop = analyze_oop_text(
        "Customers can add products to a shopping cart. A shopping cart contains one or more cart items. "
        "A product has a name and a price. An order is placed by a customer. Customers and admins are users."
    )
    classes = _classes(shop)
    assert _methods(classes["ShoppingCart"])["addProduct"]["parameters"] == [{"name": "product", "type": "Product"}]
    assert _relationship(shop, "ShoppingCart", "CartItem")["targetMultiplicity"] == "1..*"
    assert "placeOrder" in _methods(classes["Customer"])
    assert _relationship(shop, "Administrator", "User")["type"] == "inheritance"

    school = analyze_oop_text(
        "A department offers several courses. A course has a title. A teacher teaches one or more courses. "
        "A student can enroll in up to six courses. Students and teachers are persons. A person has a name."
    )
    assert _relationship(school, "Department", "Course")["label"] == "offer"
    assert _relationship(school, "Teacher", "Course")["targetMultiplicity"] == "1..*"
    assert _relationship(school, "Student", "Course")["targetMultiplicity"] == "0..6"
    assert _relationship(school, "Student", "Person")["type"] == "inheritance"


def test_quantity_reads_number_words_and_bounded_phrases() -> None:
    assert _quantity_from_text("up to five books")[0] == "0..5"
    assert _quantity_from_text("no more than 3 items")[0] == "0..3"
    assert _quantity_from_text("one or more line items")[0] == "1..*"
    assert _quantity_from_text("between 2 and 4 seats")[0] == "2..4"
    assert _quantity_from_text("many orders")[0] == "0..*"


def test_rule_pipeline_class_model_fixes() -> None:
    text = (
        "A library member can borrow up to five books. A member has a full name and an email. "
        "Only the librarian can remove books. The system should respond quickly."
    )
    analysis = analyze_text(text)
    story = generate_final_story(text, analysis["sentences"], analysis["facts"], [])
    requirements = generate_requirements(story, analysis["facts"])["requirements"]
    model = generate_class_model(requirements, analysis["facts"])
    classes = {cls["name"]: cls for cls in model["classes"]}

    # Synonym merge: LibraryMember folds into Member.
    assert "LibraryMember" not in classes
    assert model["mergedClasses"] == {"LibraryMember": "Member"}
    # Multiplicity from an action object, and the author's own verb.
    edges = {(rel["sourceClassId"], rel["label"]): rel for rel in model["relationships"]}
    assert edges[("class_member", "borrow")]["targetMultiplicity"] == "0..5"
    librarian_methods = {method["name"]: method for method in classes["Librarian"]["methods"]}
    assert set(librarian_methods) == {"removeBook"}
    assert librarian_methods["removeBook"]["parameters"] == [{"name": "book", "type": "Book"}]
    # NFR story reads as a sentence.
    nfr_section = next(section for section in story["atomicStorySections"] if "performance" in section["normalizedSentence"])
    assert "responseTime a" not in nfr_section["normalizedSentence"]


def test_interfaces_realization_and_abstract_classes() -> None:
    result = analyze_oop_text(
        "Payable is an interface with methods pay and refund. Credit card payments and cash payments implement Payable. "
        "A cash payment has an amount. Shape is an abstract class. Circles and rectangles are shapes. "
        "A circle has a radius. Every shape can calculate its area. Drawable is an interface. Circle implements Drawable."
    )
    classes = _classes(result)

    assert classes["Payable"]["stereotype"] == "interface"
    assert set(_methods(classes["Payable"])) == {"pay", "refund"}
    # An implementing class provides every method of the contract.
    assert {"pay", "refund"} <= set(_methods(classes["CashPayment"]))
    assert _relationship(result, "CreditCardPayment", "Payable")["type"] == "realization"
    assert _relationship(result, "Circle", "Drawable")["type"] == "realization"
    assert classes["Shape"]["stereotype"] == "abstract"
    assert "calculateArea" in _methods(classes["Shape"])
    assert _relationship(result, "Circle", "Shape")["type"] == "inheritance"
    assert _attributes(classes["Circle"])["radius"] == "Decimal"
    assert result["validation"]["valid"]


def test_held_out_tasks_score() -> None:
    """Generality guard: the held-out tasks in oop_eval_cases.py must keep
    scoring at least 95% (they were not the original tuning examples)."""
    from tests.unit.oop_eval import score_case
    from tests.unit.oop_eval_cases import CASES

    ok = total = 0
    for case in CASES:
        passed, count, _ = score_case(case)
        ok += passed
        total += count
    assert ok / total >= 0.95, f"held-out score dropped to {ok}/{total}"


def test_precision_no_false_classes_and_proper_boxes() -> None:
    """Easy/medium tasks: every class is a real one, wholes list their parts,
    subtypes named by an adjective inherit, and junk/value nouns are not classes."""
    from tests.unit.oop_eval import precision_counts, score_case
    from tests.unit.oop_eval_cases_precision import PRECISION_CASES

    correct = predicted = ok = total = 0
    for case in PRECISION_CASES:
        result = analyze_oop_text(case["text"])
        hit, made, false_classes, _ = precision_counts(case, result)
        assert not false_classes, f"{case['name']}: false classes {false_classes}"
        correct += hit
        predicted += made
        passed, count, _ = score_case(case)
        ok += passed
        total += count
    assert correct == predicted
    assert ok / total >= 0.97

    shop = analyze_oop_text(
        "A cinema has several halls. Each hall has a hall number and a capacity. Customers order food. "
        "Stock is updated by the manager. An exercise has a name, sets and repetitions. "
        "A listener can play songs. A premium listener can download songs. A song has a title."
    )
    classes = _classes(shop)
    assert _attributes(classes["Cinema"])["halls"] == "List<Hall>"
    assert _attributes(classes["Exercise"]) == {"name": "String", "sets": "Integer", "repetitions": "Integer"}
    assert not {"Food", "Stock", "Set", "Repetition"} & set(classes)
    assert _relationship(shop, "PremiumListener", "Listener")["type"] == "inheritance"


def test_camel_case_names_and_possessives() -> None:
    result = analyze_oop_text(
        "Define an interface called PaymentMethod that declares pay. Coins and cards implement PaymentMethod. "
        "Each employee's salary is paid monthly. An employee has a name."
    )
    classes = _classes(result)
    assert classes["PaymentMethod"]["stereotype"] == "interface"
    assert _relationship(result, "Coin", "PaymentMethod")["type"] == "realization"
    assert not [name for name in classes if "SSalary" in name or name.endswith("Salary")]

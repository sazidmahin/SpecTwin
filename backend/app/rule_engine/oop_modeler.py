"""Human-style object-oriented analysis of a short requirement text.

This is the textbook noun/verb method (Abbott's textual analysis) a student
applies to an OOP course task such as "A library has many books. Each book has
a title and an ISBN. A member can borrow up to five books...":

1. Read each sentence and recognise what kind of statement it is
   (generalisation, possible states, "has" list, association, behaviour).
2. Collect every noun as a *candidate* and the evidence for it.
3. Decide per candidate: class, attribute of some class, or rejected
   (system boundary, generic word, value with no structure or behaviour).
4. Merge synonyms ("library member" == "member" in a library system).
5. Turn verbs into methods on the class that performs them, with a typed
   parameter for the object they act on.
6. Draw relationships: inheritance, composition/aggregation for "has/contains",
   associations for verbs, with multiplicities read from the quantifiers.
7. Pull attributes shared by every subclass up into the parent.

Everything is offline and deterministic (regex + the v1 dictionaries), and
every decision is recorded in `analysis` so the reasoning can be shown step by
step next to the diagram.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from app.rule_engine.dictionaries import DICTIONARY_VERSION, load_dictionaries
from app.rule_engine.pipeline import (
    RULE_VERSION,
    _action_aliases,
    _narrative_actors,
    _is_attribute_like,
    _nfr_from_sentence,
    _quantity_from_text,
    camel_case,
    class_alias_map,
    common_verb_base,
    domain_words,
    extract_facts,
    generate_drawio_xml,
    normalize_entity,
    normalize_text,
    pascal_case,
    singularize,
    snake_case,
    split_clauses,
    split_sentences,
    verb_lemma,
)

MODELER_VERSION = "oop_modeler_v1"

# Past participles the regular-suffix stripper cannot undo ("written" -> "write").
_IRREGULAR_PARTICIPLES = {
    "written": "write", "taken": "take", "given": "give", "made": "make", "sent": "send",
    "paid": "pay", "bought": "buy", "sold": "sell", "held": "hold", "kept": "keep",
    "chosen": "choose", "driven": "drive", "drawn": "draw", "seen": "see", "done": "do",
    "known": "know", "shown": "show", "told": "tell", "brought": "bring", "built": "build",
    "found": "find", "left": "leave", "read": "read", "led": "lead", "met": "meet",
    "issued": "issue", "placed": "place", "run": "run", "won": "win", "lent": "lend",
}
_SYSTEM_WORDS = {
    "system", "application", "app", "platform", "software", "website", "site", "portal",
    "program", "service", "it", "tool", "solution",
}
_STATE_ATTRIBUTE_WORDS = ("status", "state", "type", "category", "kind", "level", "role", "priority", "mode", "condition")
_COMPOSITION_VERBS = {
    "contains": "composition", "contain": "composition", "consists of": "composition",
    "consist of": "composition", "is composed of": "composition", "are composed of": "composition",
    "is made up of": "composition", "are made up of": "composition", "comprises": "composition",
    "comprise": "composition", "owns": "composition", "own": "composition",
    "includes": "aggregation", "include": "aggregation", "holds": "aggregation", "hold": "aggregation",
    "has": "association", "have": "association", "keeps": "association", "keep": "association",
    "stores": "association", "store": "association", "records": "association", "record": "association",
    "maintains": "association", "maintain": "association", "tracks": "association", "track": "association",
    "is described by": "association", "is identified by": "association", "are identified by": "association",
    "is characterized by": "association", "is characterised by": "association",
}
_POSSESSIVE_VERBS = set(_COMPOSITION_VERBS)
_MODIFYING_VERBS = {"update", "change", "set", "edit", "modify", "reset", "enter", "provide"}
_TYPE_BY_TAIL = {
    "date": "Date", "day": "Date", "birthday": "Date", "deadline": "Date", "dob": "Date",
    "time": "DateTime", "timestamp": "DateTime", "at": "DateTime",
    "price": "Decimal", "cost": "Decimal", "fee": "Decimal", "salary": "Decimal", "amount": "Decimal",
    "balance": "Decimal", "fine": "Decimal", "total": "Decimal", "rate": "Decimal", "tax": "Decimal",
    "discount": "Decimal", "charge": "Decimal", "wage": "Decimal", "budget": "Decimal", "penalty": "Decimal",
    "count": "Integer", "quantity": "Integer", "age": "Integer", "copies": "Integer", "copy": "Integer",
    "stock": "Integer", "capacity": "Integer", "seats": "Integer", "year": "Integer", "floor": "Integer",
    "credits": "Integer", "credit": "Integer", "semester": "Integer", "duration": "Integer",
    "radius": "Decimal", "width": "Decimal", "height": "Decimal", "length": "Decimal", "weight": "Decimal",
    "area": "Decimal", "distance": "Decimal", "speed": "Decimal", "temperature": "Decimal", "latitude": "Decimal",
    "longitude": "Decimal", "percentage": "Decimal", "volume": "Decimal", "mileage": "Decimal", "size": "Decimal",
    "interest": "Decimal", "limit": "Decimal", "overdraft": "Decimal", "grade": "String", "gpa": "Decimal", "marks": "Integer", "score": "Integer",
    "id": "String", "code": "String", "isbn": "String", "number": "String", "email": "String",
}
_PRONOUN_ACTORS = {
    "i", "we", "me", "us", "they", "them", "he", "she", "someone", "somebody", "anyone", "anybody",
    "everyone", "everybody", "people", "the public",
}
_KEEPABLE_ADJECTIVES = {
    "new", "existing", "registered", "authenticated", "authorized", "approved", "verified", "active",
    "current", "single", "optional", "premium", "regular", "guest", "senior", "junior", "full-time",
    "part-time", "temporary", "permanent", "online", "external", "internal", "private", "public",
}
# Mass / value nouns: passed to a method as an amount, never a class of their own.
_VALUE_NOUNS = {
    "money": ("amount", "Decimal"), "cash": ("amount", "Decimal"), "fund": ("amount", "Decimal"),
    "funds": ("amount", "Decimal"), "point": ("points", "Integer"), "points": ("points", "Integer"),
    "credit": ("amount", "Decimal"), "time": ("time", "DateTime"), "information": ("details", "String"),
    "detail": ("details", "String"), "data": ("data", "String"), "feedback": ("feedback", "String"),
    "message": ("message", "String"), "comment": ("comment", "String"), "rating": ("rating", "Integer"),
}
_CONTAINER_VERBS = {"add", "put", "insert", "place", "remove", "delete", "move", "transfer", "drop", "store", "save", "load", "attach"}
# Identifiers the author already wrote in CamelCase ("PaymentMethod") keep
# their casing; set per analysis.
_CAMEL_NAMES: ContextVar[dict[str, str]] = ContextVar("_CAMEL_NAMES", default={})
# Plural nouns that are ordinary words inside a class name ("SalesReport").
_PLURAL_NAME_WORDS = {"sales", "news", "goods", "series", "species", "status", "business", "address", "class", "access", "process", "analysis", "basis", "bus"}
# Counts written as plural nouns in a field list ("sets and repetitions").
_COUNT_NOUNS = {
    "sets", "repetitions", "reps", "laps", "points", "credits", "hours", "minutes", "seconds", "days", "weeks",
    "months", "years", "pages", "copies", "seats", "votes", "likes", "views", "units", "calories", "steps",
    "goals", "wins", "losses", "items", "attempts", "retries", "visits", "stars",
}
_DETERMINERS = {
    "a", "an", "the", "this", "that", "these", "those", "each", "every", "all", "any", "some", "many", "several",
    "multiple", "one", "two", "three", "four", "five", "its", "their", "his", "her", "our", "my", "your", "another",
    "other", "no", "few", "more", "most",
}
_BOOLEAN_PREFIX = re.compile(r"^(?:is|has|can|should)[A-Z]")


def _dictionary_words(name: str) -> set[str]:
    return {str(item).strip().lower() for item in load_dictionaries().get(name, []) if str(item).strip()}


def _modals() -> str:
    dictionaries = load_dictionaries()
    modals = (
        dictionaries.get("permission_modals", [])
        + dictionaries.get("obligation_modals", [])
        + dictionaries.get("negative_modals", [])
    )
    return "(?:" + "|".join(sorted((re.escape(item) for item in modals), key=len, reverse=True)) + ")"


_NP = r"[a-z][a-z0-9'\- ]*?"
_MODAL_WORDS = {"can", "could", "may", "might", "must", "shall", "should", "will", "would", "cannot", "need", "needs"}
_LEAD = r"(?:(?:a|an|the|each|every|all|any|one)\s+)?"


# ---------------------------------------------------------------------------
# Working records
# ---------------------------------------------------------------------------


@dataclass
class _Candidate:
    name: str
    sentences: set[int] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    raw_phrases: list[str] = field(default_factory=list)


@dataclass
class _Possession:
    owner: str
    item: str
    item_text: str
    multiplicity: str | None
    plural: bool
    relation: str
    sentence: int
    quantified: bool = False
    in_field_list: bool = False


@dataclass
class _Action:
    subject: str | None
    verb: str
    obj: str | None
    obj_text: str
    multiplicity: str | None
    sentence: int
    clause: str
    only: bool = False
    negated: bool = False
    owner_hint: str | None = None
    per_instance: bool = False


class _Analysis:
    def __init__(self) -> None:
        self.candidates: dict[str, _Candidate] = {}
        self.possessions: list[_Possession] = []
        self.actions: list[_Action] = []
        self.hierarchy: list[tuple[str, str, int]] = []
        self.abstract_parents: set[str] = set()
        self.interfaces: dict[str, list[str]] = {}
        self.enums: dict[str, dict[str, Any]] = {}
        self.associations: list[dict[str, Any]] = []
        self.sentence_trace: list[dict[str, Any]] = []
        self.warnings: list[str] = []
        self.domains: set[str] = set()
        self.sentence_texts: dict[int, str] = {}
        self.implied: list[str] = []

    def candidate(self, name: str | None, sentence: int, role: str, raw: str | None = None) -> str | None:
        if not name:
            return None
        record = self.candidates.setdefault(name, _Candidate(name=name))
        record.sentences.add(sentence)
        record.roles.add(role)
        if raw and raw not in record.raw_phrases:
            record.raw_phrases.append(raw)
        return name


# ---------------------------------------------------------------------------
# Small language helpers
# ---------------------------------------------------------------------------


def _strip_leading(text: str) -> str:
    return re.sub(
        r"^(?:(?:a|an|the|each|every|all|any|its|their|his|her|our|your|this|that|these|those)\s+)+",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    ).strip(" ,.;:")


def _participle_lemma(word: str) -> str:
    lowered = word.lower()
    if lowered in _IRREGULAR_PARTICIPLES:
        return _IRREGULAR_PARTICIPLES[lowered]
    lemma = verb_lemma(lowered) or lowered
    if lemma != lowered or lowered in _action_aliases():
        return lemma
    # Verbs outside the dictionary: undo the third-person "-s" by hand.
    if re.search(r"[^aeiou]ies$", lowered):
        return lowered[:-3] + "y"
    if re.search(r"(?:ches|shes|xes|sses|zes)$", lowered):
        return lowered[:-2]
    if lowered.endswith("s") and not lowered.endswith(("ss", "us", "is")):
        return lowered[:-1]
    return lowered


def _phrasal(verb: str) -> str:
    """"log in" -> "login", "sign out" -> "logout": the one-word method name a
    person would write for a phrasal verb."""
    lowered = re.sub(r"\s+", " ", verb.strip().lower())
    if " " in lowered:
        canonical = _action_aliases().get(lowered)
        if canonical and " " not in canonical:
            return canonical
        return lowered
    return _participle_lemma(lowered)


def _is_plural_phrase(text: str) -> bool:
    lowered = text.lower()
    if re.search(
        r"\b(?:many|multiple|several|all|various|list of|set of|collection of|group of|one or more|"
        r"zero or more|any number of|some|a number of|up to|at least|at most)\b",
        lowered,
    ):
        return True
    if re.search(r"\b(?:[2-9]|\d{2,}|two|three|four|five|six|seven|eight|nine|ten)\b", lowered):
        return True
    words = re.findall(r"[a-z]+", _strip_leading(lowered))
    if not words:
        return False
    head = words[-1]
    return head.endswith("s") and not head.endswith(("ss", "us", "is")) and singularize(head) != head


def _split_list(text: str) -> list[str]:
    """Split "a title, an author, one or more copies and a status" into items,
    keeping quantity idioms ("one or more") intact."""
    protected = text
    idioms = ["one or more", "zero or more", "one or two", "more or less", "at least", "at most", "no more than"]
    idioms += [phrase for phrase in load_dictionaries().get("quantifiers", {}) if re.search(r"\b(?:or|and)\b", phrase)]
    for idiom in idioms:
        protected = re.sub(re.escape(idiom), idiom.replace(" ", "\x00"), protected, flags=re.IGNORECASE)
    for conjunction in sorted(_dictionary_words("conjunctions") - {"then", "otherwise", "however", "but"}, key=len, reverse=True):
        if " " in conjunction:
            protected = re.sub(rf"\s+{re.escape(conjunction)}\s+", ", ", protected, flags=re.IGNORECASE)
    parts = re.split(r"\s*,\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+|\s*;\s*", protected)
    return [part.replace("\x00", " ").strip(" .") for part in parts if part and part.strip(" .")]


def _attribute_spec(item_text: str) -> tuple[str, str]:
    """Attribute name + type the way a person writes it in a class box:
    "a date of birth" -> dateOfBirth: Date, "the number of copies" ->
    numberOfCopies: Integer, "an ISBN" -> isbn: String."""
    dictionaries = load_dictionaries()
    phrases = {str(key).lower(): value for key, value in dictionaries.get("attribute_phrases", {}).items() if isinstance(value, dict)}
    hints = {str(key).lower(): str(value) for key, value in dictionaries.get("data_type_hints", {}).items()}
    cleaned = _strip_leading(item_text.lower())
    cleaned = re.sub(r"^(?:unique|valid|optional|required|current|total number of)\s+", "", cleaned)
    cleaned = re.sub(r"\s+(?:that|which|who|where|when|for|with|to|in|on|at|by)\b.*$", "", cleaned).strip()
    if cleaned in phrases:
        spec = phrases[cleaned]
        return str(spec.get("name")), str(spec.get("type") or "String")
    words = re.findall(r"[a-z0-9]+", cleaned)[-4:] or ["value"]
    name = camel_case(" ".join(words))
    if words[0] == "number" and "of" in words:
        return name, "Integer"
    if _BOOLEAN_PREFIX.match(name):
        return name, "Boolean"
    tail = words[-1]
    if tail in _COUNT_NOUNS and len(words) == 1:
        return name, "Integer"
    kind = _TYPE_BY_TAIL.get(tail) or hints.get(tail) or hints.get(singularize(tail))
    if kind is None and _is_plural_phrase(cleaned) and not _is_attribute_like(singularize(tail)):
        return name, "List<String>"
    if tail in {"at", "on"} and len(words) > 1:
        kind = "DateTime"
    return name, kind or "String"


def _enum_name(owner: str, attribute: str) -> str:
    return pascal_case(f"{owner} {attribute}")


def _literal(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.strip().upper()).strip("_") or "VALUE"


# ---------------------------------------------------------------------------
# Sentence-level patterns
# ---------------------------------------------------------------------------


def _match_header(text: str) -> bool:
    return bool(
        re.match(
            r"^(?:please\s+)?(?:design|develop|create|build|implement|model|draw|make|write|consider)\b.*"
            r"\b(?:system|application|app|platform|software|program|website|portal)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _match_inheritance(text: str) -> list[tuple[str, str]] | None:
    lowered = re.sub(r"\b(?:also|too|likewise|simply|just|really)\s+", "", text.lower().strip(" ."))
    patterns = [
        rf"^{_LEAD}(?P<child>{_NP})\s+(?:is|are)\s+(?:a|an)?\s*(?:special\s+)?(?:kind|type|sort|subclass|specialization|specialisation|form|subtype)s?\s+of\s+{_LEAD}(?P<parent>{_NP})$",
        rf"^{_LEAD}(?P<child>{_NP})\s+(?:extends|inherits from|is derived from|specializes|specialises|is a subclass of)\s+{_LEAD}(?P<parent>{_NP})$",
        rf"^{_LEAD}(?P<child>{_NP})\s+is\s+(?:a|an)\s+(?P<parent>{_NP})$",
    ]
    for pattern in patterns:
        match = re.match(pattern, lowered)
        if match and " of " not in match.group("parent") and not re.search(r"\b(?:who|that|which|with)\b", match.group("parent")):
            return [(match.group("child"), match.group("parent"))]
    # "There are two types of accounts: savings accounts and current accounts."
    match = re.match(
        rf"^(?:there are|we have|the system has)\s+(?:\w+\s+)?(?:different\s+)?(?:types|kinds|categories|sorts)\s+of\s+(?P<parent>{_NP})\s*[:\-,]\s*(?P<children>.+)$",
        lowered,
    )
    if match:
        return [(child, match.group("parent")) for child in _split_list(match.group("children"))]
    # "Students and teachers are users." / "... are all types of users."
    match = re.match(
        rf"^(?P<children>{_NP}(?:,\s*{_NP})*\s+(?:and|or)\s+{_NP})\s+are\s+(?:all\s+)?(?:(?:types|kinds)\s+of\s+)?(?P<parent>{_NP})$",
        lowered,
    )
    if match and _is_plural_phrase(match.group("parent")):
        return [(child, match.group("parent")) for child in _split_list(match.group("children"))]
    # "A user can be a student or a teacher." - articles mark nouns, i.e. subtypes.
    match = re.match(
        rf"^{_LEAD}(?P<parent>{_NP})\s+(?:can be|is either|may be|is one of|could be)\s+(?:either\s+)?(?P<children>(?:a|an)\s+.+)$",
        lowered,
    )
    if match:
        children = _split_list(match.group("children"))
        if len(children) >= 2 and all(re.match(r"^(?:a|an)\s+", child) for child in children):
            return [(child, match.group("parent")) for child in children]
    return None


_METHOD_LIST_PREFIX = re.compile(
    r"^(?:(?:that|which)\s+)?(?:has|have|declares?|defines?|provides?|contains?|requires?|specifies?|with)?\s*"
    r"(?:(?:a|an|the|one|two|three)\s+)?(?:(?:abstract|public)\s+)?(?:methods?|operations?|functions?|behaviou?rs?)?\s*"
    r"(?:called|named|:)?\s*",
)


def _method_names(text: str | None) -> list[str]:
    """"methods pay and refund" / "a method called calculateArea()" /
    "calculate area and draw" -> ["pay", "refund"] / ["calculateArea"] / ["calculateArea", "draw"]."""
    if not text:
        return []
    cleaned = _METHOD_LIST_PREFIX.sub("", text.strip().lower().strip(" ."))
    names = []
    for item in _split_list(cleaned):
        item = re.sub(r"\(.*?\)", "", item).strip()
        item = re.sub(r"^(?:to\s+|a\s+|an\s+|the\s+|its\s+|their\s+)", "", item)
        words = [word for word in re.findall(r"[a-z0-9]+", item) if word not in {"its", "their", "the", "a", "an", "method", "operation"}]
        if words:
            names.append(camel_case(" ".join(words[:4])))
    return names


def _match_interface(text: str) -> tuple[str, list[str]] | None:
    """"Payable is an interface with methods pay and refund." / "Define an
    interface called Drawable." / "The Shape interface declares area()."
    -> (name, method names)."""
    lowered = text.lower().strip(" .")
    patterns = [
        rf"^{_LEAD}(?P<name>{_NP})\s+(?:is|should be|must be|will be|acts as)\s+(?:an?\s+)?interface\b\s*(?P<methods>.*)$",
        r"^(?:define|create|design|there is|there should be|we need|add)\s+(?:an?\s+)?interface\s+(?:called\s+|named\s+)?(?P<name>[a-z][a-z0-9\-]*(?:\s+[a-z][a-z0-9\-]*)?)\b\s*(?P<methods>.*)$",
        rf"^{_LEAD}(?P<name>{_NP})\s+interface\s+(?P<methods>(?:declares|defines|has|provides|contains|specifies|requires)\b.*)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, lowered)
        if match:
            name = match.group("name").strip()
            if name and name not in _SYSTEM_WORDS:
                return name, _method_names(match.group("methods"))
    return None


def _match_abstract(text: str) -> str | None:
    """"Shape is an abstract class." / "Employee should be abstract.\""""
    match = re.match(
        rf"^{_LEAD}(?P<name>{_NP})\s+(?:is|should be|must be|will be)\s+(?:an?\s+)?abstract(?:\s+(?:class|concept|type|entity))?$",
        text.lower().strip(" ."),
    )
    return match.group("name") if match else None


def _match_realization(text: str) -> tuple[list[str], str, list[str]] | None:
    """"Credit card payments and cash payments implement Payable." ->
    (implementers, interface, extra methods)."""
    lowered = text.lower().strip(" .")
    match = re.match(
        r"^(?:both\s+|all\s+)?(?P<children>.+?)\s+(?:(?:must|should|can|will|shall)\s+)?(?:implements?|realizes?|realises?|conforms? to)\s+"
        r"(?:the\s+)?(?P<iface>[a-z][a-z0-9\-]*(?:\s+[a-z][a-z0-9\-]*)?)(?:\s+interface)?(?:\s+(?:by providing|and provides?|with)\s+(?P<methods>.+))?$",
        lowered,
    )
    if not match:
        return None
    children = [child for child in _split_list(match.group("children")) if child and child not in _SYSTEM_WORDS]
    if not children:
        return None
    return children, match.group("iface"), _method_names(match.group("methods"))


def _match_states(text: str) -> tuple[str, str, list[str]] | None:
    """"A book can be available, borrowed or lost." / "The status of an order
    can be pending, shipped or delivered." -> (owner, attribute, literals)."""
    lowered = text.lower().strip(" .")
    attribute_words = "|".join(_STATE_ATTRIBUTE_WORDS)
    verbs = r"(?:can be|could be|may be|is either|are either|is one of|must be one of|can have the values?|is|are)"
    patterns = [
        rf"^(?:the\s+)?(?P<attr>{attribute_words})\s+of\s+{_LEAD}(?P<owner>{_NP})\s+{verbs}\s*:?\s*(?:either\s+)?(?P<list>.+)$",
        rf"^{_LEAD}(?P<owner>{_NP})(?:'s)?\s+(?P<attr>{attribute_words})\s+{verbs}\s*:?\s*(?:either\s+)?(?P<list>.+)$",
        rf"^{_LEAD}(?P<owner>{_NP})\s+(?:can be|could be|may be|is either|are either|is always|is one of)\s+(?:either\s+)?(?P<list>.+)$",
    ]
    state_words = _dictionary_words("state_words")
    for pattern in patterns:
        match = re.match(pattern, lowered)
        if not match:
            continue
        items = _split_list(match.group("list"))
        if len(items) < 2 or any(re.match(r"^(?:a|an|the)\s", item) or len(item.split()) > 2 for item in items):
            continue
        groups = match.groupdict()
        attribute = groups.get("attr") or "status"
        looks_like_states = any(
            item in state_words or re.search(r"(?:ed|able|ing|ive|ful|ent|ant|ic|al)$", item) for item in items
        )
        if groups.get("attr") or looks_like_states:
            return groups["owner"], attribute, items
    return None


def _match_possession(text: str, modals: str) -> tuple[str, str, str, str] | None:
    """"Each book has a title, an author and an ISBN." -> (owner, verb, list, rest)."""
    lowered = text.lower().strip(" .")
    verbs = "|".join(sorted((re.escape(verb) for verb in _POSSESSIVE_VERBS), key=len, reverse=True))
    match = re.match(
        rf"^{_LEAD}(?P<owner>{_NP})\s+(?:(?:{modals})\s+)?(?:also\s+)?(?P<verb>{verbs})\s+(?P<list>.+)$",
        lowered,
    )
    owner = verb = items = None
    if match:
        owner, verb, items = match.group("owner"), match.group("verb"), match.group("list")
    else:
        # "For each book, the system stores the title and the author."
        match = re.match(
            rf"^for\s+(?:each|every|a|an|the)?\s*(?P<owner>{_NP}),?\s+(?:the\s+)?(?:system|application|we)\s+"
            rf"(?:(?:{modals})\s+)?(?P<verb>stores?|records?|keeps?|tracks?|maintains?|needs?|holds?)\s+(?P<list>.+)$",
            lowered,
        )
        if match:
            owner, verb, items = match.group("owner"), "has", match.group("list")
        else:
            # "The system stores the name and address of each customer."
            match = re.match(
                rf"^(?:the\s+)?(?:system|application)\s+(?:(?:{modals})\s+)?(?:stores?|records?|keeps? track of|keeps?|tracks?|maintains?)\s+"
                rf"(?P<list>.+?)\s+(?:of|for)\s+(?:each|every|a|an|the|all)\s+(?P<owner>{_NP})$",
                lowered,
            )
            if match:
                owner, verb, items = match.group("owner"), "has", match.group("list")
    if not owner or not items:
        return None
    if owner.strip() in _SYSTEM_WORDS:
        return None
    # The owner is a plain noun phrase: a modal or a determiner inside it means
    # the "has/records" word was really a noun later in the sentence ("a nurse
    # can update the medical record of a patient").
    owner_words = owner.split()
    if len(owner_words) > 4 or any(word in _MODAL_WORDS or word in {"a", "an", "the", "of", "to"} for word in owner_words):
        return None
    # A possession list can run on into a behaviour ("... and can borrow books").
    rest = ""
    split = re.search(rf"(?:,\s*|\s+)(?:and\s+)?(?:(?:{modals})\s+)", items)
    if split:
        rest = items[split.start():].strip(" ,")
        rest = re.sub(r"^(?:and\s+)", "", rest)
        items = items[: split.start()]
    items = re.sub(
        r"^(?:the\s+)?(?:following\s+)?(?:details|information|info|attributes|properties|fields|data)\s*(?:such as|like|including|:|-)?\s*",
        "",
        items.strip(),
    )
    items = re.sub(r"\s*(?:such as|including|like|namely)\s+", ", ", items)
    return owner, verb, items, rest


def _match_association(text: str, modals: str) -> tuple[str, str, str, str, str] | None:
    """"Each loan belongs to exactly one member." / "An order is placed by a
    customer." -> (subject, relation, target, quantity text, verb)."""
    lowered = text.lower().strip(" .")
    match = re.match(
        rf"^{_LEAD}(?P<a>{_NP})\s+(?:(?:{modals})\s+)?(?P<rel>belongs? to|is assigned to|are assigned to|is associated with|"
        rf"is linked to|is related to|is issued to|is part of|are part of|is owned by|are owned by)\s+"
        rf"(?P<b>.+)$",
        lowered,
    )
    if match:
        return match.group("a"), match.group("rel"), match.group("b"), match.group("b"), ""
    match = re.match(
        rf"^{_LEAD}(?P<a>{_NP})\s+(?:is|are|can be|must be|should be|will be|may be|gets|get)\s+"
        rf"(?P<verb>[a-z]+(?:ed|en)|{'|'.join(_IRREGULAR_PARTICIPLES)})\s+by\s+(?P<b>.+)$",
        lowered,
    )
    if match:
        return match.group("a"), "passive", match.group("b"), match.group("b"), match.group("verb")
    match = re.match(
        rf"^{_LEAD}(?P<a>{_NP})\s+(?:is|are|can be|must be|will be|gets|get)\s+"
        rf"(?P<verb>[a-z]+(?:ed|en)|{'|'.join(_IRREGULAR_PARTICIPLES)})\s+(?P<prep>in|at|on|to|into|for|with|from|under)\s+(?P<b>.+)$",
        lowered,
    )
    if match:
        return match.group("a"), f"weak:{match.group('verb')} {match.group('prep')}", match.group("b"), match.group("b"), match.group("verb")
    return None


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


def _class_name(analysis: _Analysis | None, raw: str | None, keep_adjective: bool = True) -> str | None:
    """Class name for a noun phrase. Actor synonyms map onto one class
    ("admins" -> Administrator); a qualifying adjective is kept when it is part
    of the name ("current account" -> CurrentAccount, not Account)."""
    if not raw:
        return None
    text = re.sub(r"\s+", " ", raw.strip().lower()).strip(" ,.;:")
    stripped = _strip_leading(text)
    if text in _SYSTEM_WORDS or stripped in _SYSTEM_WORDS:
        return "System"
    # Only pronouns ("they", "someone") and abbreviations ("admins") are
    # renamed; a real noun the author chose ("persons", "employees") stays.
    actors = _narrative_actors()
    for key in (text, stripped):
        if key in actors and (key in _PRONOUN_ACTORS or "admin" in key):
            return actors[key]
    words = re.sub(
        r"^(?:(?:one or more|zero or more|many|multiple|several|some|two|three|up to \w+|at least \w+)\s+)", "", stripped
    ).split()
    if keep_adjective and len(words) >= 2 and words[0] in _KEEPABLE_ADJECTIVES:
        rest = normalize_entity(" ".join(words[1:]))
        if rest:
            return _restore_camel(pascal_case(words[0]) + rest)
    return _restore_camel(normalize_entity(raw))


def _restore_camel(name: str | None) -> str | None:
    if not name:
        return name
    return _CAMEL_NAMES.get().get(name.lower(), name)


def _record_possession(analysis: _Analysis, owner: str, verb: str, items_text: str, index: int, findings: list[str]) -> None:
    relation = _COMPOSITION_VERBS.get(verb, "association")
    items = _split_list(items_text)
    # A list that also names a single simple value ("a name, sets and
    # repetitions") is a field list: its bare plurals are fields too.
    singular_field = [
        not _is_plural_phrase(item) and _is_attribute_like(_class_name(None, item, keep_adjective=False)) for item in items
    ]
    for position, item in enumerate(items):
        multiplicity, _ = _quantity_from_text(item)
        cleaned = re.sub(r"^(?:a\s+)?(?:list|set|collection|group|series|number)\s+of\s+", "", item.strip()) if re.match(
            r"^(?:a\s+)?(?:list|set|collection|group|series)\s+of\s+", item.strip()
        ) else item
        name = _class_name(None, cleaned, keep_adjective=False)
        if not name or name == "System":
            continue
        plural = _is_plural_phrase(item)
        quantified = multiplicity is not None or bool(
            re.search(r"\b(?:many|several|multiple|various|some|a number of|any number of|list of|set of|collection of|\d+)\b", item.lower())
        )
        in_field_list = any(flag for other, flag in enumerate(singular_field) if other != position)
        analysis.possessions.append(
            _Possession(owner=owner, item=name, item_text=item, multiplicity=multiplicity, plural=plural, relation=relation,
                        sentence=index, quantified=quantified, in_field_list=in_field_list)
        )
        analysis.candidate(name, index, "possessed", item)
        findings.append(f"{owner} {verb} → {item.strip()}")


def _record_action(analysis: _Analysis, action: _Action, findings: list[str]) -> None:
    analysis.actions.append(action)
    if action.subject:
        analysis.candidate(action.subject, action.sentence, "subject")
    if action.obj:
        analysis.candidate(action.obj, action.sentence, "object", action.obj_text)
    who = action.subject or "(unknown actor)"
    what = f" {action.obj}" if action.obj else ""
    findings.append(f"{who} —{action.verb}→{what}")


def obj_phrase(fact: dict[str, Any], clause_text: str) -> str:
    """The object as written ("the fine"), falling back to the entity name."""
    obj = str(fact.get("object") or "")
    words = re.findall(r"[A-Z][a-z0-9]*", obj)
    phrase = " ".join(word.lower() for word in words)
    return phrase if phrase and phrase in clause_text.lower() else (phrase or obj)


def _analyse_sentence(analysis: _Analysis, sentence: dict[str, Any], modals: str) -> None:
    index = sentence["sentenceIndex"]
    text = sentence["normalizedText"]
    findings: list[str] = []
    kind = "Behaviour"

    if _match_header(text):
        analysis.sentence_trace.append(
            {"index": index, "text": sentence["text"], "kind": "Task statement", "findings": [
                "Names the system being designed; the system itself is the boundary, not a class."
            ]}
        )
        return

    interface = _match_interface(text)
    if interface:
        raw_name, methods = interface
        name = _class_name(analysis, raw_name, keep_adjective=False)
        if name:
            analysis.candidate(name, index, "interface", raw_name)
            declared = analysis.interfaces.setdefault(name, [])
            declared.extend(method for method in methods if method not in declared)
            findings.append(f"{name} is an interface" + (f" declaring {', '.join(m + '()' for m in methods)}" if methods else ""))
            analysis.sentence_trace.append({"index": index, "text": sentence["text"], "kind": "Interface", "findings": findings})
            return

    realization = _match_realization(text)
    if realization:
        raw_children, raw_iface, methods = realization
        iface = _class_name(analysis, raw_iface, keep_adjective=False)
        if iface:
            analysis.candidate(iface, index, "interface", raw_iface)
            declared = analysis.interfaces.setdefault(iface, [])
            declared.extend(method for method in methods if method not in declared)
            for raw_child in raw_children:
                child = _class_name(analysis, raw_child)
                if child and child != iface:
                    analysis.candidate(child, index, "child", raw_child)
                    analysis.hierarchy.append((child, iface, index))
                    findings.append(f"{child} implements {iface}")
            if findings:
                analysis.sentence_trace.append({"index": index, "text": sentence["text"], "kind": "Realization", "findings": findings})
                return

    abstract = _match_abstract(text)
    if abstract:
        name = _class_name(analysis, abstract)
        if name and name != "System":
            analysis.candidate(name, index, "parent", abstract)
            analysis.abstract_parents.add(name)
            analysis.sentence_trace.append({"index": index, "text": sentence["text"], "kind": "Abstract class",
                                            "findings": [f"{name} is abstract - it is never instantiated directly"]})
            return

    inheritance = _match_inheritance(text)
    if inheritance:
        for raw_child, raw_parent in inheritance:
            child = _class_name(analysis, raw_child)
            parent = _class_name(analysis, raw_parent)
            if not child or not parent or child == parent:
                continue
            analysis.candidate(child, index, "child", raw_child)
            analysis.candidate(parent, index, "parent", raw_parent)
            analysis.hierarchy.append((child, parent, index))
            findings.append(f"{child} is a kind of {parent}")
            if re.search(r"\b(?:types|kinds|categories|sorts)\s+of\b", text, flags=re.IGNORECASE):
                analysis.abstract_parents.add(parent)
        if findings:
            analysis.sentence_trace.append({"index": index, "text": sentence["text"], "kind": "Generalisation", "findings": findings})
            return

    states = _match_states(text)
    if states:
        raw_owner, attribute, literals = states
        owner = _class_name(analysis, raw_owner)
        if owner and owner != "System":
            analysis.candidate(owner, index, "enum_owner", raw_owner)
            enum_name = _enum_name(owner, attribute)
            record = analysis.enums.setdefault(enum_name, {"owner": owner, "attribute": camel_case(attribute), "literals": []})
            for literal in literals:
                value = _literal(literal)
                if value not in record["literals"]:
                    record["literals"].append(value)
            findings.append(f"{owner}.{camel_case(attribute)} takes one of: {', '.join(record['literals'])} → enumeration {enum_name}")
            analysis.sentence_trace.append({"index": index, "text": sentence["text"], "kind": "Possible states", "findings": findings})
            return

    possession = _match_possession(text, modals)
    if possession:
        raw_owner, verb, items, rest = possession
        owner = _class_name(analysis, raw_owner)
        if owner and owner != "System":
            analysis.candidate(owner, index, "owner", raw_owner)
            _record_possession(analysis, owner, verb, items, index, findings)
            if rest:
                text = f"{raw_owner} {rest}"
                kind = "Structure + behaviour"
            else:
                analysis.sentence_trace.append({"index": index, "text": sentence["text"], "kind": "Structure", "findings": findings})
                return
        else:
            kind = "Structure"

    association = _match_association(text, modals)
    if association and not findings:
        raw_a, relation, raw_b, quantity_text, verb = association
        a = _class_name(analysis, raw_a)
        b = _class_name(analysis, raw_b)
        if a and b and a != b and "System" not in (a, b):
            multiplicity, _ = _quantity_from_text(quantity_text)
            if relation == "passive":
                lemma = _participle_lemma(verb)
                _record_action(
                    analysis,
                    _Action(subject=b, verb=lemma, obj=a, obj_text=raw_a, multiplicity=None, sentence=index, clause=text),
                    findings,
                )
                analysis.sentence_trace.append({"index": index, "text": sentence["text"], "kind": "Behaviour (passive voice)", "findings": findings})
                return
            if relation.startswith("weak:"):
                # Only drawn when both ends turn out to be classes on their own.
                analysis.candidate(a, index, "subject", raw_a)
                analysis.candidate(b, index, "object", raw_b)
                analysis.associations.append(
                    {"source": a, "target": b, "label": relation[5:], "targetMultiplicity": multiplicity or "1", "sentence": index, "weak": True}
                )
                findings.append(f"{a} {relation[5:]} {b}")
                analysis.sentence_trace.append({"index": index, "text": sentence["text"], "kind": "Association", "findings": findings})
                return
            analysis.candidate(a, index, "owner" if relation.endswith("part of") else "subject", raw_a)
            analysis.candidate(b, index, "object", raw_b)
            if relation.endswith("part of"):
                analysis.possessions.append(
                    _Possession(owner=b, item=a, item_text=raw_a, multiplicity=None, plural=True, relation="composition", sentence=index)
                )
                findings.append(f"{a} is part of {b} (composition)")
            else:
                analysis.associations.append(
                    {"source": a, "target": b, "label": re.sub(r"^(?:is|are)\s+", "", relation), "targetMultiplicity": multiplicity or "1", "sentence": index}
                )
                findings.append(f"{a} {relation} {b} [{multiplicity or '1'}]")
            analysis.sentence_trace.append({"index": index, "text": sentence["text"], "kind": "Association", "findings": findings})
            return

    nfr = _nfr_from_sentence(sentence)
    subject_word = (re.findall(r"[a-z]+", _strip_leading(text.lower())) or [""])[0]
    if nfr and (subject_word in _SYSTEM_WORDS or not re.search(rf"\b{modals}\b", text, flags=re.IGNORECASE)):
        analysis.sentence_trace.append(
            {"index": index, "text": sentence["text"], "kind": "Non-functional", "findings": [
                f"{nfr['category']} quality requirement - a constraint on the system, not a class, attribute or method."
            ]}
        )
        return

    working = {**sentence, "text": text, "normalizedText": text}
    clauses = split_clauses([working])
    facts = extract_facts([working], clauses)
    handled_clauses = {fact["sourceClauseId"] for fact in facts}
    for fact in facts:
        if fact.get("nfr"):
            continue
        raw_action = str(fact.get("rawAction") or fact.get("action") or "").strip()
        if not raw_action:
            continue
        subject = _written_subject(analysis, fact.get("actor"), str(fact.get("sourceText") or text), raw_action, modals)
        obj = fact.get("object")
        if subject and subject.lower() in _SYSTEM_WORDS:
            subject = "System"
        multiplicity = fact.get("targetMultiplicity")
        if not obj:
            # "A student can enroll in up to six courses" - the object sits
            # behind a preposition the fact rules stop at.
            prepositional = re.search(
                rf"\b{re.escape(raw_action.lower())}\s+(?:in|into|for|on|to|with|at|from|onto)\s+(?P<obj>.+)$",
                str(fact.get("sourceText") or text).lower(),
            )
            if prepositional:
                obj = _class_name(analysis, prepositional.group("obj"), keep_adjective=False)
                multiplicity, _ = _quantity_from_text(prepositional.group("obj"))
        relation_type = fact.get("relationshipType")
        if relation_type in {"inheritance", "realization"} and subject and obj:
            analysis.candidate(subject, index, "child")
            analysis.candidate(obj, index, "interface" if relation_type == "realization" else "parent")
            if relation_type == "realization":
                analysis.interfaces.setdefault(obj, [])
            analysis.hierarchy.append((subject, obj, index))
            findings.append(f"{subject} {'implements' if relation_type == 'realization' else 'is a kind of'} {obj}")
            continue
        if relation_type and raw_action.lower() in _POSSESSIVE_VERBS and subject and obj and subject != "System":
            analysis.candidate(subject, index, "owner")
            _record_possession(analysis, subject, raw_action.lower(), fact["sourceText"].split(raw_action, 1)[-1], index, findings)
            continue
        verb = _phrasal(verb_lemma(raw_action) or str(fact.get("action")))
        clause_text = str(fact.get("sourceText") or text)
        owner_hint = None
        per_instance = False
        if obj:
            linked = re.search(
                rf"\b{re.escape(raw_action.split()[0].lower())}\w*\s+.*?\b(?:for|of)\s+(?:a|an|the)\s+(?P<target>{_NP})(?=$|[,.;]|\s+(?:and|or|when|if|by|with)\b)",
                str(fact.get("sourceText") or text).lower(),
            )
            target = _class_name(analysis, linked.group("target"), keep_adjective=False) if linked else None
            if target and target not in {obj, subject, "System"}:
                analysis.associations.append({"source": obj, "target": target, "label": "for", "targetMultiplicity": "1", "sentence": index, "weak": True})
            # "The system calculates the fine for each loan": the fine is a
            # value kept per Loan, so it is Loan's data (and Loan's method).
            owner_match = re.search(
                rf"\b(?:for\s+(?:each|every|all)|of\s+(?:each|every|the|a|an))\s+(?P<owner>{_NP})(?=$|[,.;]|\s+(?:and|or|when|if|by|with)\b)",
                clause_text.lower(),
            )
            owner = _class_name(analysis, owner_match.group("owner")) if owner_match else None
            if owner and owner not in {obj, "System", subject}:
                owner_hint = owner
                per_instance = owner_match.group(0).startswith("for")
                analysis.candidate(owner, index, "owner")
                _record_possession(analysis, owner, "has", obj_phrase(fact, clause_text), index, findings)
        _record_action(
            analysis,
            _Action(
                subject=subject,
                verb=verb,
                obj=obj,
                obj_text=clause_text,
                multiplicity=multiplicity,
                sentence=index,
                clause=clause_text,
                only=str(fact.get("matchedRuleId", "")).startswith("EXT_ONLY_"),
                negated=bool(fact.get("negated")),
                owner_hint=owner_hint,
                per_instance=per_instance,
            ),
            findings,
        )
    for clause in clauses:
        if clause["id"] in handled_clauses:
            continue
        clause_text = clause["normalizedText"].strip().lower()
        # Intransitive behaviour the fact rules need an object for ("A member can log in").
        match = re.match(
            rf"^{_LEAD}(?P<subject>{_NP})\s+(?:{modals})\s+(?P<verb>[a-z]+(?:\s+(?:in|out|up|on|off|back|down))?)$",
            clause_text,
        )
        if match:
            subject = _class_name(analysis, match.group("subject"))
            if subject:
                _record_action(
                    analysis,
                    _Action(subject=subject, verb=_phrasal(match.group("verb")), obj=None, obj_text="", multiplicity=None,
                            sentence=index, clause=clause["normalizedText"]),
                    findings,
                )
            continue
        # Any other verb joining two nouns ("A department offers several
        # courses", "A teacher teaches one or more courses") is still an
        # association, even when the verb is not in the action dictionary.
        guess = _guess_svo(clause_text, modals)
        if guess:
            raw_subject, raw_verb, raw_object = guess
            subject = _class_name(analysis, raw_subject)
            obj = _class_name(analysis, raw_object, keep_adjective=False)
            if subject and obj and subject != obj:
                multiplicity, _ = _quantity_from_text(raw_object)
                _record_action(
                    analysis,
                    _Action(subject=subject, verb=_participle_lemma(raw_verb), obj=obj, obj_text=raw_object,
                            multiplicity=multiplicity, sentence=index, clause=clause["normalizedText"]),
                    findings,
                )
    _share_trailing_object(analysis, index)
    analysis.sentence_trace.append(
        {"index": index, "text": sentence["text"], "kind": kind if findings else "Not modelled", "findings": findings or [
            "No actor/verb/object or structure pattern recognised in this sentence."
        ]}
    )


def _share_trailing_object(analysis: _Analysis, index: int) -> None:
    """"Users can like and comment on posts": English states a shared object
    once, after the last verb. A bare verb of this sentence with no object of
    its own takes the object of the next verb by the same subject."""
    actions = [action for action in analysis.actions if action.sentence == index]
    for position, action in enumerate(actions):
        if action.obj or " " in action.verb or not re.search(rf"\b{re.escape(action.verb)}\w*\s*(?:,|\band\b|\bor\b)", action.clause.lower()):
            continue
        following = next(
            (later for later in actions[position + 1:] if later.subject == action.subject and later.obj),
            None,
        )
        if following:
            action.obj = following.obj
            action.obj_text = following.obj_text
            action.multiplicity = following.multiplicity


_NON_VERBS = {"is", "are", "was", "were", "be", "been", "has", "have", "the", "a", "an", "and", "or", "of", "not", "only", "also"}


def _guess_svo(clause: str, modals: str) -> tuple[str, str, str] | None:
    """Subject - verb - object for a verb the dictionary does not know. Without
    a modal the verb must carry the third-person "-s" ("teaches", "offers")."""
    body = re.sub(rf"^{_LEAD}", "", clause.strip())
    modal_match = re.search(rf"\s(?P<modal>{modals})\s", f" {body} ")
    for subject_length in (1, 2, 3):
        words = body.split()
        if len(words) <= subject_length + 1:
            return None
        subject = " ".join(words[:subject_length])
        rest = " ".join(words[subject_length:])
        has_modal = False
        if modal_match and rest.startswith(modal_match.group("modal") + " "):
            rest = rest[len(modal_match.group("modal")) + 1:]
            has_modal = True
        verb, _, obj = rest.partition(" ")
        obj = re.sub(r"^(?:in|into|for|on|to|with|at|from)\s+", "", obj).strip()
        if not obj or verb in _NON_VERBS or any(word in _NON_VERBS - {"and", "or"} for word in subject.split()):
            continue
        if has_modal or re.search(r"(?:[^su]s|ches|shes|xes)$", verb):
            return subject, verb, obj
    return None


def _written_subject(analysis: _Analysis, actor: str | None, clause: str, raw_action: str, modals: str) -> str | None:
    """The subject as the author wrote it. The fact rules map colloquial
    words onto roles ("persons" -> User, "employees" -> Staff); a model of the
    domain keeps the author's own noun (Person, Employee)."""
    if not actor:
        return actor
    words = set(re.findall(r"[a-z]+", clause.lower()))
    actor_words = {word.lower() for word in re.findall(r"[A-Z][a-z0-9]*", actor)}
    if actor_words & (words | {singularize(word) for word in words}):
        return actor
    match = re.match(
        rf"^(?:only\s+)?{_LEAD}(?P<subject>{_NP})\s+(?:(?:{modals})\s+)?{re.escape(raw_action.lower())}\b",
        clause.lower(),
    )
    if match:
        written = _class_name(analysis, match.group("subject"))
        if written and written != "System":
            return written
    return actor


_FIRST_PREDICATE = (
    r"(?:belongs? to|is assigned to|are assigned to|is linked to|is associated with|is part of|are part of|"
    r"is owned by|is placed by|is created by|is managed by|is an?|are|is)"
)
_SECOND_PREDICATE = r"(?:has|have|contains?|consists? of|includes?|records?|stores?|belongs? to|can|must|should|may|will)"


def _split_predicates(sentence: dict[str, Any]) -> list[dict[str, Any]]:
    """"A section belongs to a course and has a room" -> "A section belongs
    to a course" + "A section has a room": each predicate is its own fact."""
    text = sentence["normalizedText"]
    match = None
    for candidate in re.finditer(r"\s*,?\s+and\s+(?P<word>[a-z]+)\b", text, flags=re.IGNORECASE):
        word = candidate.group("word").lower()
        second_ok = re.fullmatch(_SECOND_PREDICATE, word) or (
            word.endswith("s") and common_verb_base(word) not in (None, word)
        )
        if not second_ok:
            continue
        match = re.match(
            rf"^(?P<subject>{_LEAD}[a-z][a-z0-9'\- ]*?)\s+(?P<first>{_FIRST_PREDICATE}\s+.+)$",
            text[: candidate.start()],
            flags=re.IGNORECASE,
        )
        if match:
            second = text[candidate.start("word"):]
            break
    if not match or re.search(r"\b(?:and|or)\b", match.group("subject"), flags=re.IGNORECASE):
        return [sentence]
    subject = match.group("subject")
    return [
        {**sentence, "normalizedText": f"{subject} {match.group('first')}"},
        {**sentence, "normalizedText": f"{subject} {second}"},
    ]


def _resolve_pronoun_subjects(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """"Members can borrow books. They can also reserve books." - "they" is
    the previous sentence's subject, not a generic User."""
    resolved: list[dict[str, Any]] = []
    previous_subject: str | None = None
    for sentence in sentences:
        text = sentence["normalizedText"]
        match = re.match(r"^(they|he|she|it)\b", text, flags=re.IGNORECASE)
        if match and previous_subject:
            text = previous_subject + text[match.end():]
            sentence = {**sentence, "normalizedText": text}
        subject = re.match(rf"^({_LEAD}[a-z][a-z\- ]*?)\s+(?:{_modals()}|is|are|has|have|belongs|can|[a-z]+s)\b", text, flags=re.IGNORECASE)
        if subject and subject.group(1).strip().lower() not in _SYSTEM_WORDS | {"there", "for"}:
            previous_subject = subject.group(1).strip()
        resolved.append(sentence)
    return resolved


def _decide(analysis: _Analysis) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Class / attribute / rejected per candidate, with the reason a person
    would give. Returns (decisions, aliases)."""
    generic = _dictionary_words("generic_nouns") | _dictionary_words("stopwords") | _dictionary_words("temporal_markers")
    actor_hints = _dictionary_words("actor_hints")
    state_words = _dictionary_words("state_words")

    names = list(analysis.candidates)
    mentions = {name: {str(i) for i in record.sentences} for name, record in analysis.candidates.items()}
    first_seen = {name: min(record.sentences) for name, record in analysis.candidates.items() if record.sentences}
    defined_in_hierarchy = {child for child, _, _ in analysis.hierarchy} | {parent for _, parent, _ in analysis.hierarchy}
    aliases = class_alias_map(names, mentions, analysis.domains, first_seen=first_seen, protected=defined_in_hierarchy)
    for alias, target in aliases.items():
        source = analysis.candidates.pop(alias)
        merged = analysis.candidates.setdefault(target, _Candidate(name=target))
        merged.sentences |= source.sentences
        merged.roles |= source.roles
        merged.raw_phrases += [phrase for phrase in source.raw_phrases if phrase not in merged.raw_phrases]

    def canon(name: str | None) -> str | None:
        return aliases.get(name, name) if name else name

    for possession in analysis.possessions:
        possession.owner = canon(possession.owner) or possession.owner
        possession.item = canon(possession.item) or possession.item
    for action in analysis.actions:
        action.subject = canon(action.subject)
        action.obj = canon(action.obj)
    analysis.hierarchy = [(canon(c) or c, canon(p) or p, i) for c, p, i in analysis.hierarchy]
    analysis.interfaces = {canon(name) or name: methods for name, methods in analysis.interfaces.items()}
    for association in analysis.associations:
        association["source"] = canon(association["source"])
        association["target"] = canon(association["target"])
    for enum in analysis.enums.values():
        enum["owner"] = canon(enum["owner"])

    owners = {p.owner for p in analysis.possessions}
    subjects = {a.subject for a in analysis.actions if a.subject and a.subject != "System"}
    hierarchy_members = (
        {c for c, _, _ in analysis.hierarchy} | {p for _, p, _ in analysis.hierarchy} | set(analysis.interfaces)
    )
    enum_owners = {e["owner"] for e in analysis.enums.values()}
    association_ends = {a["source"] for a in analysis.associations if not a.get("weak")} | {
        a["target"] for a in analysis.associations if not a.get("weak")
    }
    acted_on_by_class = {a.obj for a in analysis.actions if a.obj and a.subject and a.subject != "System" and not a.owner_hint}
    acted_on_by_system = {a.obj for a in analysis.actions if a.obj and (not a.subject or a.subject == "System")}
    # Plural items become collections of a class only when counted ("many
    # books") or named on their own - not inside a field list.
    collections = {p.item for p in analysis.possessions if p.plural and (p.quantified or not p.in_field_list)}
    field_list_plurals = {p.item for p in analysis.possessions if p.plural and p.in_field_list and not p.quantified}
    strong_evidence = owners | subjects | hierarchy_members | enum_owners | association_ends

    decisions: dict[str, dict[str, Any]] = {}
    for name, record in analysis.candidates.items():
        lowered = snake_case(name).replace("_", " ")
        junk = _junk_name_reason(name)
        if junk and name not in analysis.interfaces:
            decisions[name] = {"decision": "rejected", "reason": junk}
            continue
        if name == "System" or lowered in _SYSTEM_WORDS:
            decisions[name] = {"decision": "rejected", "reason": "The system itself is the boundary being designed, not a class inside it."}
            continue
        if lowered in analysis.domains and not (name in owners or name in subjects or name in association_ends or name in hierarchy_members):
            decisions[name] = {"decision": "rejected", "reason": "Domain / system name with no data or behaviour of its own."}
            continue
        if lowered in _VALUE_NOUNS and name not in owners:
            decisions[name] = {"decision": "value", "reason": "An amount/value handed to a method (e.g. deposit(amount)), not a class."}
            continue
        if (lowered in generic or lowered in state_words) and not (name in strong_evidence or len(record.sentences) > 1):
            decisions[name] = {"decision": "rejected", "reason": "Generic or UI/state word, too vague to be a domain class."}
            continue
        if name in owners:
            decisions[name] = {"decision": "class", "reason": "Owns data of its own (\"has ...\")."}
        elif name in analysis.interfaces:
            decisions[name] = {"decision": "interface", "reason": "Declared as an interface - a contract other classes implement."}
        elif name in hierarchy_members:
            decisions[name] = {"decision": "class", "reason": "Takes part in an \"is a kind of\" hierarchy."}
        elif _is_attribute_like(name):
            decisions[name] = {"decision": "attribute", "reason": "A simple value (name, date, amount, ...), so it is a field of its owner."}
        elif name in subjects:
            decisions[name] = {"decision": "class", "reason": "Performs actions (it is the subject of a verb)."}
        elif name in enum_owners or name in association_ends:
            decisions[name] = {"decision": "class", "reason": "Has states or is linked to another class."}
        elif name in field_list_plurals and name not in strong_evidence and name not in acted_on_by_class:
            decisions[name] = {"decision": "attribute", "reason": "A plural value listed among other fields (e.g. \"sets and repetitions\"), so it is a field."}
        elif name not in strong_evidence and _only_possessive_mentions(name, record, analysis):
            decisions[name] = {"decision": "value", "reason": "Always written as \"its/their ...\" - a value belonging to the subject, not a separate class."}
        elif name not in strong_evidence and _only_mass_mentions(name, record, analysis):
            decisions[name] = {"decision": "value", "reason": "Used once without an article (\"order food\", \"stock is updated\") - an uncountable value, not an object."}
        elif name in acted_on_by_class or name in collections:
            decisions[name] = {"decision": "class", "reason": "Another class acts on it or keeps many of them."}
        elif name in {p.item for p in analysis.possessions}:
            decisions[name] = {"decision": "attribute", "reason": "Only ever mentioned as a single property of its owner, with no structure or behaviour of its own."}
        elif name in acted_on_by_system:
            decisions[name] = {"decision": "class", "reason": "The system manages it as a record."}
        elif name.lower() in actor_hints:
            decisions[name] = {"decision": "class", "reason": "A user role of the system."}
        else:
            decisions[name] = {"decision": "rejected", "reason": "Mentioned, but has no structure, behaviour or links."}
    return decisions, aliases


def _junk_name_reason(name: str) -> str | None:
    """A class name must be a clean noun phrase. Parsing slips produce names
    that swallowed a verb ("MonthlyProducesPayslip", "Headed") or a plural
    modifier ("EmployeesWork"); those are never classes."""
    words = [word.lower() for word in re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", name)]
    if not words:
        return "Empty name."
    for position, word in enumerate(words):
        final = position == len(words) - 1
        base = common_verb_base(word)
        if base and base != word and (word.endswith("ed") or (not final and word.endswith("s"))):
            return f"\"{name}\" contains the verb form \"{word}\" - a parsing slip, not a noun phrase."
        # "savings account", "sports club" are real compounds; a plural
        # followed by a bare verb ("EmployeesWork") is a subject+verb slip.
        if (
            not final
            and word.endswith("s")
            and not word.endswith("ss")
            and word not in _PLURAL_NAME_WORDS
            and singularize(word) != word
            and common_verb_base(words[-1]) == words[-1]
            and position == len(words) - 2
        ):
            return f"\"{name}\" reads as a subject followed by a verb (\"{word} {words[-1]}\") - a parsing slip, not a noun phrase."
        if len(word) == 1 and word not in {"a", "i"} and len(words) > 1:
            return f"\"{name}\" contains a stray letter - a parsing slip."
    return None


def _only_mass_mentions(name: str, record: _Candidate, analysis: _Analysis) -> bool:
    """True when every mention of `name` is a bare singular noun with no
    article or count ("customers order food", "stock is updated") - an
    uncountable value rather than a thing with its own identity."""
    if len(record.sentences) != 1:
        return False
    phrase = " ".join(word.lower() for word in re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", name))
    text = analysis.sentence_texts.get(next(iter(record.sentences)), "").lower()
    mentions = list(re.finditer(rf"(?:^|\b([a-z0-9']+)\s+){re.escape(phrase)}(?![a-z])", text))
    if not mentions:
        return False
    return all((match.group(1) or "") not in _DETERMINERS and not re.fullmatch(r"\d+", match.group(1) or "") for match in mentions)


def _only_possessive_mentions(name: str, record: _Candidate, analysis: _Analysis) -> bool:
    phrase = " ".join(word.lower() for word in re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", name))
    found = False
    for index in record.sentences:
        text = analysis.sentence_texts.get(index, "").lower()
        for match in re.finditer(rf"(?:^|\b([a-z0-9']+)\s+){re.escape(phrase)}s?(?![a-z])", text):
            found = True
            if (match.group(1) or "") not in {"its", "their", "his", "her", "your", "my", "our"}:
                return False
    return found


def _plural_word(name: str) -> str:
    if re.search(r"[^aeiou]y$", name):
        return name[:-1] + "ies"
    if re.search(r"(?:s|x|z|ch|sh)$", name):
        return name + "es"
    return name + "s"


def _indirect_container(action: _Action, classes: dict[str, Any], aliases: dict[str, str]) -> str | None:
    """The class named by "to/into/from the <X>" after the verb, if any."""
    for match in re.finditer(
        r"\b(?:to|into|onto|in|from)\s+(?:a|an|the|their|his|her|its|my|our|your)?\s*([a-z][a-z \-]*?)(?=$|[,.;]|\s+(?:and|or|when|if|by|with|for|before|after)\b)",
        action.clause.lower(),
    ):
        name = _class_name(None, match.group(1))
        name = aliases.get(name or "", name)
        if name in classes and name not in {action.subject, action.obj}:
            return name
    return None


def _method(name: str, parameters: list[dict[str, str]] | None = None, source: int | None = None) -> dict[str, Any]:
    return {"name": name, "parameters": parameters or [], "returnType": "void", "visibility": "public", "sentence": source}


def analyze_oop_text(raw_text: str) -> dict[str, Any]:
    """Run the full human-style analysis. Returns the class model (classes,
    relationships, enums), the draw.io XML, and the step-by-step analysis."""
    normalized = normalize_text(raw_text)["normalizedText"]
    # "the employee's salary" -> "the salary of employee": the owner is named
    # the way the "of each X" rule already reads.
    normalized = re.sub(r"\b([A-Za-z]+)'s\s+([A-Za-z]+)\b", r"\2 of \1", normalized)
    _CAMEL_NAMES.set({word.lower(): word for word in re.findall(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+\b", raw_text)})
    sentences = _resolve_pronoun_subjects(split_sentences(normalized))
    analysis = _Analysis()
    analysis.sentence_texts = {sentence["sentenceIndex"]: sentence["normalizedText"] for sentence in sentences}
    analysis.domains = domain_words([sentence["text"] for sentence in sentences])
    modals = _modals()
    for sentence in sentences:
        for part in _split_predicates(sentence):
            _analyse_sentence(analysis, part, modals)

    decisions, aliases = _decide(analysis)
    class_names = sorted(name for name, decision in decisions.items() if decision["decision"] in {"class", "interface"})
    classes: dict[str, dict[str, Any]] = {
        name: {"name": name, "attributes": {}, "methods": {}, "abstract": name in analysis.abstract_parents,
               "interface": name in analysis.interfaces, "sentences": set()}
        for name in class_names
    }
    for name in class_names:
        classes[name]["sentences"] = set(analysis.candidates[name].sentences)
    # "A premium listener can download songs" next to a Listener class: the
    # adjective names a special kind of Listener.
    in_hierarchy = {child for child, _, _ in analysis.hierarchy}
    for name in class_names:
        words = re.findall(r"[A-Z][a-z0-9]*", name)
        if len(words) >= 2 and words[0].lower() in _KEEPABLE_ADJECTIVES and name not in in_hierarchy:
            base = "".join(words[1:])
            if base in classes and base not in analysis.interfaces:
                analysis.hierarchy.append((name, base, 0))
                analysis.implied.append(f"{name} is a kind of {base} (implied by the adjective \"{words[0].lower()}\")")

    relationships: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add_relationship(source: str, target: str, kind: str, label: str, target_mult: str | None, source_mult: str | None = "1") -> None:
        if source not in classes or target not in classes or (source == target and kind in {"inheritance", "realization"}):
            return
        key = (source, target, kind if kind in {"inheritance", "realization", "dependency"} else "link")
        if kind not in {"inheritance", "realization", "dependency"} and (target, source, "link") in relationships:
            key = (target, source, "link")
        existing = relationships.get(key)
        if existing:
            if label and label not in existing["labels"]:
                existing["labels"].append(label)
            rank = {"composition": 3, "aggregation": 2, "association": 1}
            if rank.get(kind, 0) > rank.get(existing["type"], 0):
                existing["type"] = kind
            if target_mult and existing.get("assumed") and key[0] == source:
                existing["targetMultiplicity"] = target_mult
                existing["assumed"] = False
            return
        relationships[key] = {
            "source": source,
            "target": target,
            "type": kind,
            "labels": [label] if label else [],
            "sourceMultiplicity": source_mult if kind in {"association", "aggregation", "composition"} else None,
            "targetMultiplicity": (target_mult or "0..*") if kind in {"association", "aggregation", "composition"} else None,
            "assumed": target_mult is None,
        }

    # Attributes and structural relationships from "has" lists.
    attribute_decisions: dict[str, str] = {}
    for possession in analysis.possessions:
        owner = possession.owner
        if owner not in classes:
            continue
        decision = decisions.get(possession.item, {}).get("decision")
        if decision == "class" and possession.item != owner:
            kind = possession.relation
            if kind == "association" and possession.plural:
                kind = "aggregation"
            multiplicity = possession.multiplicity or ("0..*" if possession.plural else "1")
            add_relationship(owner, possession.item, kind, "" if kind != "association" else "has", multiplicity)
            continue
        name, kind = _attribute_spec(possession.item_text)
        classes[owner]["attributes"].setdefault(name, {"type": kind, "sentence": possession.sentence})
        attribute_decisions[possession.item] = owner

    # Enumerations become a typed attribute on their owner.
    enums_out = []
    for enum_name, enum in sorted(analysis.enums.items()):
        owner = enum["owner"]
        if owner not in classes:
            continue
        classes[owner]["attributes"][enum["attribute"]] = {"type": enum_name, "sentence": None}
        enums_out.append({"id": f"enum_{snake_case(enum_name)}", "name": enum_name, "literals": enum["literals"], "owner": owner})

    # Behaviour: verbs become methods on the class that performs them.
    verb_trace = []
    unassigned: list[str] = []
    for action in analysis.actions:
        subject = action.subject if action.subject in classes else None
        obj = action.obj
        obj_is_class = obj in classes
        attribute_owner = attribute_decisions.get(obj or "")
        verb_words = action.verb.split()
        container = _indirect_container(action, classes, aliases) if subject and obj_is_class else None
        if action.owner_hint in classes and not obj_is_class and subject and subject != action.owner_hint and not action.per_instance:
            # "a nurse can update the medical record of a patient" ->
            # Nurse.updateMedicalRecord(patient: Patient); the record is the
            # patient's data.
            owner = subject
            method_name = camel_case(f"{action.verb} {obj}")
            parameters = [{"name": camel_case(action.owner_hint), "type": action.owner_hint}]
            add_relationship(subject, action.owner_hint, "association", verb_words[0], None)
        elif action.owner_hint in classes and not obj_is_class:
            # "... calculates the fine for each loan" -> Loan.calculateFine():
            # a value computed per instance is that instance's responsibility.
            owner = action.owner_hint
            method_name = camel_case(f"{action.verb} {obj}")
            parameters = []
        elif container and verb_words[0] in _CONTAINER_VERBS:
            # "add products to the shopping cart" -> ShoppingCart.addProduct(product)
            owner = container
            method_name = camel_case(f"{action.verb} {obj}")
            parameters = [{"name": camel_case(obj), "type": obj}]
            add_relationship(subject, container, "association", "uses", None)
            add_relationship(container, obj, "aggregation", "", "0..*")
        elif subject and (obj or "").lower() in _VALUE_NOUNS:
            owner = subject
            value_name, value_type = _VALUE_NOUNS[(obj or "").lower()]
            method_name = camel_case(action.verb)
            parameters = [{"name": value_name, "type": value_type}]
        elif subject:
            if obj_is_class:
                # A class acting on its own kind ("a user can follow other
                # users") is a reflexive association.
                method_name = camel_case(f"{action.verb} {obj}")
                parameters = [{"name": camel_case(obj), "type": obj}]
                add_relationship(subject, obj, "association", verb_words[0], action.multiplicity)
            elif obj and obj != subject:
                attr_name, attr_type = _attribute_spec(obj)
                method_name = camel_case(f"{action.verb} {obj}")
                parameters = [{"name": attr_name, "type": attr_type}] if verb_words[0] in _MODIFYING_VERBS else []
            else:
                method_name = camel_case(action.verb)
                parameters = []
            owner = subject
        elif obj_is_class:
            # "The system notifies the customer" / "Books can be reserved": the
            # object is the one whose state changes.
            owner = obj
            method_name = camel_case(action.verb)
            parameters = []
        elif attribute_owner in classes:
            owner = attribute_owner
            method_name = camel_case(f"{action.verb} {obj}")
            parameters = []
        else:
            target = None
            for match in re.finditer(r"\b(?:for|of|to|on)\s+(?:each|every|a|an|the|all)?\s*([a-z][a-z ]*?)(?=$|[,.;]|\s+(?:and|or|when|if|by|with)\b)", action.clause.lower()):
                candidate = aliases.get(normalize_entity(match.group(1)) or "", normalize_entity(match.group(1)))
                if candidate in classes:
                    target = candidate
                    break
            if not target:
                unassigned.append(f"\"{action.clause}\" - no class owns this behaviour")
                verb_trace.append({"verb": action.verb, "subject": action.subject, "object": obj, "assignedTo": None, "method": None, "sentence": action.sentence})
                continue
            owner = target
            method_name = camel_case(f"{action.verb} {obj}" if obj else action.verb)
            parameters = []
        if action.negated:
            verb_trace.append({"verb": action.verb, "subject": action.subject, "object": obj, "assignedTo": owner, "method": None,
                               "sentence": action.sentence, "note": "Negative rule (cannot) - a constraint, not a method."})
            continue
        classes[owner]["methods"].setdefault(method_name, _method(method_name, parameters, action.sentence))
        classes[owner]["sentences"].add(action.sentence)
        verb_trace.append({
            "verb": action.verb, "subject": action.subject, "object": obj, "assignedTo": owner,
            "method": f"{method_name}({', '.join(p['name'] + ': ' + p['type'] for p in parameters)})",
            "sentence": action.sentence,
            **({"note": f"Only {owner} may do this."} if action.only else {}),
        })

    for association in analysis.associations:
        add_relationship(association["source"], association["target"], "association", association["label"],
                         association["targetMultiplicity"], "0..*")

    for name, declared in analysis.interfaces.items():
        if name in classes:
            for method in declared:
                classes[name]["methods"].setdefault(method, _method(method))
    for child, parent, _ in analysis.hierarchy:
        if parent in analysis.interfaces:
            add_relationship(child, parent, "realization", "", None)
            if child in classes and parent in classes:
                # An implementing class provides every method of the contract.
                for method, spec in classes[parent]["methods"].items():
                    classes[child]["methods"].setdefault(method, dict(spec))
        else:
            add_relationship(child, parent, "inheritance", "", None)

    # Generalisation: a field every subclass repeats belongs on the parent;
    # a field the parent already has is inherited, not redeclared.
    children_of: dict[str, list[str]] = {}
    for (source, target, kind), _ in relationships.items():
        if kind == "inheritance":
            children_of.setdefault(target, []).append(source)
    pulled_up: list[str] = []
    for parent, children in children_of.items():
        if len(children) >= 2:
            common = set.intersection(*(set(classes[child]["attributes"]) for child in children))
            for attribute in sorted(common):
                spec = classes[children[0]]["attributes"][attribute]
                classes[parent]["attributes"].setdefault(attribute, spec)
                pulled_up.append(f"{attribute} moved up from {', '.join(sorted(children))} to {parent}")
            contract_methods = {
                method
                for child, iface, _ in analysis.hierarchy
                if iface in analysis.interfaces and child in children and iface in classes
                for method in classes[iface]["methods"]
            }
            shared_methods = set.intersection(*(set(classes[child]["methods"]) for child in children)) - contract_methods
            for method in sorted(shared_methods):
                classes[parent]["methods"].setdefault(method, classes[children[0]]["methods"][method])
                pulled_up.append(f"{method}() moved up from {', '.join(sorted(children))} to {parent}")
        for child in children:
            for attribute in list(classes[child]["attributes"]):
                if attribute in classes[parent]["attributes"]:
                    del classes[child]["attributes"][attribute]
            for method in list(classes[child]["methods"]):
                if method in classes[parent]["methods"]:
                    del classes[child]["methods"][method]

    # A whole keeps a reference to its parts ("floors: List<Floor>"), and a
    # "belongs to exactly one" link is a reference field ("member: Member") -
    # the fields an OOP answer writes for these relationships.
    belongs_to = {(a["source"], a["target"]) for a in analysis.associations}
    for rel in relationships.values():
        source, target = rel["source"], rel["target"]
        if source not in classes or target not in classes or source == target:
            continue
        many = (rel.get("targetMultiplicity") or "").endswith(("*", "..0")) or bool(
            re.search(r"\.\.(?:[2-9]|\d{2,})$", rel.get("targetMultiplicity") or "")
        ) or (rel.get("targetMultiplicity") or "").isdigit() and int(rel["targetMultiplicity"]) > 1
        if rel["type"] in {"aggregation", "composition"}:
            field_name = camel_case(_plural_word(target) if many else target)
            classes[source]["attributes"].setdefault(field_name, {"type": f"List<{target}>" if many else target, "sentence": None})
        elif rel["type"] == "association" and (source, target) in belongs_to and not many:
            classes[source]["attributes"].setdefault(camel_case(target), {"type": target, "sentence": None})

    # A class with no field, no behaviour and no link never earned its box.
    linked = {r["source"] for r in relationships.values()} | {r["target"] for r in relationships.values()}
    for name in list(classes):
        cls = classes[name]
        if not cls["attributes"] and not cls["methods"] and name not in linked:
            decisions[name] = {"decision": "rejected", "reason": "Ended up with no attributes, methods or relationships."}
            del classes[name]

    return _package(analysis, sentences, decisions, aliases, classes, relationships, enums_out, verb_trace, unassigned, analysis.implied + pulled_up)


def _package(
    analysis: _Analysis,
    sentences: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    aliases: dict[str, str],
    classes: dict[str, dict[str, Any]],
    relationships: dict[tuple[str, str, str], dict[str, Any]],
    enums: list[dict[str, Any]],
    verb_trace: list[dict[str, Any]],
    unassigned: list[str],
    pulled_up: list[str],
) -> dict[str, Any]:
    class_list = []
    for name in sorted(classes):
        cls = classes[name]
        class_id = f"class_{snake_case(name)}"
        class_list.append(
            {
                "id": class_id,
                "name": name,
                "stereotype": "interface" if cls.get("interface") else "abstract" if cls["abstract"] else "entity",
                "attributes": [
                    {"id": f"attr_{snake_case(name)}_{snake_case(attr)}", "name": attr, "type": spec["type"], "visibility": "private"}
                    for attr, spec in cls["attributes"].items()
                ],
                "methods": [
                    {"id": f"method_{snake_case(name)}_{snake_case(method)}", **{k: v for k, v in spec.items() if k != "sentence"}}
                    for method, spec in cls["methods"].items()
                ],
                "sourceSentences": sorted(i for i in cls["sentences"] if i is not None),
                "enabled": True,
            }
        )
    relationship_list = []
    for index, rel in enumerate(relationships.values(), start=1):
        if rel["source"] not in classes or rel["target"] not in classes:
            continue
        relationship_list.append(
            {
                "id": f"edge_{index:03d}_{snake_case(rel['source'])}_{snake_case(rel['target'])}",
                "sourceClassId": f"class_{snake_case(rel['source'])}",
                "targetClassId": f"class_{snake_case(rel['target'])}",
                "source": rel["source"],
                "target": rel["target"],
                "type": rel["type"],
                "label": " / ".join(rel["labels"]),
                "sourceMultiplicity": rel["sourceMultiplicity"],
                "targetMultiplicity": rel["targetMultiplicity"],
                "direction": "source-to-target" if rel["type"] == "association" else "undirected",
                "multiplicityAssumed": bool(rel.get("assumed")) and rel["type"] in {"association", "aggregation", "composition"},
                "enabled": True,
            }
        )
    model = {"classes": class_list, "relationships": relationship_list, "enums": enums}
    drawio_xml, validation = build_model_drawio(model)

    nouns = []
    for name, decision in sorted(decisions.items()):
        record = analysis.candidates.get(name)
        nouns.append(
            {
                "name": name,
                "decision": decision["decision"] if name in classes or decision["decision"] != "class" else "rejected",
                "reason": decision["reason"],
                "phrases": record.raw_phrases[:3] if record else [],
                "sentences": sorted(record.sentences) if record else [],
            }
        )
    for alias, target in sorted(aliases.items()):
        nouns.append({"name": alias, "decision": "merged", "reason": f"Same entity as {target}; merged into it.", "mergedInto": target, "phrases": [], "sentences": []})

    warnings = list(analysis.warnings) + [f"Unassigned behaviour: {item}" for item in unassigned]
    assumed = [r for r in relationship_list if r["multiplicityAssumed"]]
    if assumed:
        warnings.append(
            f"{len(assumed)} relationship multiplicit{'y was' if len(assumed) == 1 else 'ies were'} not stated in the text; defaulted to 1 → 0..*."
        )
    return {
        "model": model,
        "drawioXml": drawio_xml,
        "validation": validation,
        "analysis": {
            "domain": sorted(analysis.domains),
            "sentences": sorted(analysis.sentence_trace, key=lambda item: item["index"]),
            "nouns": nouns,
            "verbs": verb_trace,
            "generalisation": pulled_up,
            "warnings": warnings,
        },
        "metadata": {"engine": MODELER_VERSION, "dictionaryVersionId": DICTIONARY_VERSION, "ruleVersionId": RULE_VERSION,
                     "sentenceCount": len(sentences)},
    }


def build_model_drawio(model: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """draw.io XML for a modeler result; enumerations are drawn as their own
    «enumeration» boxes next to the classes."""
    classes = [dict(cls) for cls in model.get("classes", [])]
    used_ids = {cls["id"] for cls in classes}
    for enum in model.get("enums", []):
        enum_id = enum.get("id") or f"enum_{snake_case(enum['name'])}"
        if enum_id in used_ids:
            continue
        used_ids.add(enum_id)
        classes.append(
            {
                "id": enum_id,
                "name": enum["name"],
                "stereotype": "enumeration",
                "attributes": [
                    {"id": f"{enum_id}_{snake_case(literal)}", "name": literal, "type": ""} for literal in enum.get("literals", [])
                ],
                "methods": [],
                "enabled": True,
            }
        )
    canonical = {"classes": classes, "relationships": model.get("relationships", [])}
    return generate_drawio_xml(canonical)

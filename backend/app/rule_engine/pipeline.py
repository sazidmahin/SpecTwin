import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from copy import deepcopy
from html import escape
from typing import Any

from app.rule_engine.dictionaries import DICTIONARY_VERSION, load_dictionaries

RULE_VERSION = "rules_v1"
STAGES = ["input", "clarifications", "final-story", "requirements", "class-model", "xml"]
STAGE_STATUSES = {"DRAFT", "READY_FOR_REVIEW", "APPROVED", "STALE", "FAILED"}
RELATIONSHIP_TYPE_ALIASES = {
    "association": "association",
    "aggregation": "aggregation",
    "composition": "composition",
    "dependency": "dependency",
    "inheritance": "inheritance",
    "generalization": "inheritance",
    "extends": "inheritance",
    "inherits": "inheritance",
    "realization": "realization",
    "implementation": "realization",
    "implements": "realization",
}
RELATIONSHIP_TYPES = frozenset(RELATIONSHIP_TYPE_ALIASES.values())
CARDINALITY_RELATIONSHIP_TYPES = frozenset({"association", "aggregation", "composition"})
ASSOCIATION_DIRECTIONS = frozenset(
    {"undirected", "source-to-target", "target-to-source", "bidirectional"}
)
MULTIPLICITY_PATTERN = re.compile(r"^(?:\*|\d+|\d+\.\.(?:\d+|\*))$")


def normalize_relationship_type(value: Any) -> str | None:
    return RELATIONSHIP_TYPE_ALIASES.get(str(value or "").strip().lower())


def normalize_association_direction(value: Any) -> str | None:
    direction = str(value or "undirected").strip().lower()
    if direction in {"none", "unspecified"}:
        direction = "undirected"
    return direction if direction in ASSOCIATION_DIRECTIONS else None


def relationship_drawio_style(relationship_type: str, direction: str = "undirected") -> str:
    canonical_type = normalize_relationship_type(relationship_type)
    if canonical_type is None:
        raise ValueError(f"Unsupported relationship type: {relationship_type}")
    base = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;"
    if canonical_type == "association":
        canonical_direction = normalize_association_direction(direction)
        if canonical_direction is None:
            raise ValueError(f"Invalid association direction: {direction}")
        arrows = {
            "source-to-target": "startArrow=none;endArrow=open;endFill=0;",
            "target-to-source": "startArrow=open;startFill=0;endArrow=none;",
            "bidirectional": "startArrow=open;startFill=0;endArrow=open;endFill=0;",
            "undirected": "startArrow=none;endArrow=none;",
        }
        return base + "dashed=0;" + arrows[canonical_direction]
    styles = {
        "composition": "dashed=0;startArrow=diamondThin;startFill=1;endArrow=none;",
        "aggregation": "dashed=0;startArrow=diamondThin;startFill=0;endArrow=none;",
        "inheritance": "dashed=0;startArrow=none;endArrow=block;endFill=0;",
        "dependency": "dashed=1;startArrow=none;endArrow=open;endFill=0;",
        "realization": "dashed=1;startArrow=none;endArrow=block;endFill=0;",
    }
    return base + styles[canonical_type]


def snake_case(value: str) -> str:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    words = re.findall(r"[A-Za-z0-9]+", expanded)
    return "_".join(word.lower() for word in words) or "unknown"


def pascal_case(value: str | None) -> str:
    if not value:
        return "Unknown"
    # Split existing camelCase / PascalCase runs so "receive EmailReminder"
    # becomes "ReceiveEmailReminder", not "ReceiveEmailreminder".
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    words = re.findall(r"[A-Za-z0-9]+", spaced)
    return "".join(word[:1].upper() + word[1:].lower() for word in words) or "Unknown"


def camel_case(value: str) -> str:
    pascal = pascal_case(value)
    return pascal[:1].lower() + pascal[1:]


def singularize(value: str) -> str:
    cleaned = value.strip()
    lowered = cleaned.lower()
    if lowered.endswith("ies") and len(lowered) > 3:
        return cleaned[:-3] + "y"
    if lowered.endswith("sses"):
        return cleaned[:-2]
    if lowered.endswith("uses") and len(lowered) > 4:
        # "statuses" -> "status", "buses" -> "bus", "viruses" -> "virus" - the
        # singular itself ends in "-us", so only the plural "-es" comes off.
        return cleaned[:-2]
    if lowered.endswith(("us", "is", "ss")):
        # Already singular: "status", "campus", "virus", "analysis", "basis",
        # "crisis" - the trailing "s" is part of the word, not a plural marker.
        return cleaned
    if lowered.endswith("s") and len(lowered) > 3:
        return cleaned[:-1]
    return cleaned


_ENTITY_CUT_WORDS = (
    "that",
    "which",
    "who",
    "whom",
    "whose",
    "when",
    "where",
    "before",
    "after",
    "while",
    "with",
    "within",
    "without",
    "into",
    "onto",
    "from",
    "for",
    "per",
    "via",
    "using",
    "based",
    "so",
    "because",
    "unless",
    "until",
    "at",
    "on",
    "in",
    "by",
    "as",
    "to",
    "of",
    "off",
    "up",
    "i",
    "we",
    "than",
    "including",
    "containing",
    "namely",
    "and",
    "or",
    "but",
)
_ENTITY_LEADING_NOISE = (
    "at least one",
    "at most one",
    "exactly one",
    "zero or one",
    "one or more",
    "zero or more",
    "a specific number of",
    "a number of",
    "up to",
    "a",
    "an",
    "the",
    "one",
    "each",
    "every",
    "any",
    "some",
    "all",
    "many",
    "multiple",
    "several",
    "single",
    "optional",
    "new",
    "existing",
    "valid",
    "invalid",
    "registered",
    "authenticated",
    "authorized",
    "logged-in",
    "approved",
    "verified",
    "active",
    "current",
    "selected",
    "given",
    "specific",
    "particular",
    "certain",
    "relevant",
    "corresponding",
    "respective",
    "other",
    "another",
    "different",
    "same",
    "their",
    "his",
    "her",
    "its",
    "our",
    "your",
    "this",
    "that",
    "these",
    "those",
)


_TRAILING_ENTITY_NOISE = (
    "online", "offline", "remotely", "digitally", "manually", "automatically",
    "directly", "instantly", "securely", "easily", "quickly", "properly",
    "correctly", "successfully", "later", "now", "today", "anytime", "anywhere",
    "here", "there", "too", "also", "as well", "please",
)


def normalize_entity(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    if not cleaned:
        return None
    # Strip a leading quantity phrase ("up to five books" -> "five books").
    cleaned = re.sub(
        r"^(?:up to|at least|at most|no more than|no less than|not more than|not less than|"
        r"more than|less than|fewer than|about|around|approximately|exactly|"
        r"one or more|one or many|zero or more|one or two)\s+",
        "",
        cleaned,
    )
    # Drop everything from the first relative pronoun / preposition / conjunction onward.
    tokens = cleaned.split(" ")
    trimmed: list[str] = []
    for token in tokens:
        if re.sub(r"[^a-z]", "", token) in _ENTITY_CUT_WORDS and trimmed:
            break
        trimmed.append(token)
    phrase = " ".join(trimmed).strip(" ,.;:-")
    # Strip leading determiners / quantifiers / weak adjectives, repeatedly.
    changed = True
    while changed and phrase:
        changed = False
        phrase = re.sub(
            r"^(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|first|second|third)\s+",
            "",
            phrase,
        )
        for noise in sorted(_ENTITY_LEADING_NOISE, key=len, reverse=True):
            if phrase == noise:
                phrase = ""
                changed = True
                break
            if phrase.startswith(noise + " "):
                phrase = phrase[len(noise) + 1 :]
                changed = True
                break
    if not phrase:
        return None
    # A phrase that still starts with a preposition has no head noun of its own.
    if re.match(r"^(?:with|to|for|of|on|at|in|by|from|about|into|as)\b", phrase):
        return None
    # Drop trailing adverbs ("book an appointment online" -> "appointment").
    phrase = re.sub(rf"(?:\s+(?:{'|'.join(_TRAILING_ENTITY_NOISE)}))+$", "", phrase)
    if not phrase:
        return None
    # Keep at most the trailing three words as the noun phrase (head + up to two modifiers).
    words = phrase.split(" ")[-3:]
    # A determiner can survive into that tail when it followed a comma
    # ("title, an isbn, a due date"); drop it so we don't PascalCase "ADueDate".
    while len(words) > 1 and re.sub(r"[^a-z]", "", words[0]) in {"a", "an", "the", "one"}:
        words = words[1:]
    words[-1] = singularize(words[-1])
    return pascal_case(" ".join(words))


# Written-out forms of common contractions so the modal / negation dictionaries
# (which list "cannot", "must not", "does not", …) match consistently.
_CONTRACTIONS = {
    "can't": "cannot",
    "won't": "will not",
    "shan't": "shall not",
    "ain't": "is not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't": "has not",
    "hadn't": "had not",
    "wouldn't": "would not",
    "shouldn't": "should not",
    "couldn't": "could not",
    "mustn't": "must not",
    "mightn't": "might not",
    "needn't": "need not",
    "it's": "it is",
    "that's": "that is",
    "there's": "there is",
    "who's": "who is",
    "what's": "what is",
    "let's": "let us",
    "we're": "we are",
    "they're": "they are",
    "you're": "you are",
    "i'm": "i am",
    "we've": "we have",
    "they've": "they have",
    "you've": "you have",
    "i've": "i have",
    "we'll": "we will",
    "they'll": "they will",
    "you'll": "you will",
    "i'll": "i will",
}
_CONTRACTION_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(key) for key in _CONTRACTIONS) + r")\b",
    flags=re.IGNORECASE,
)


def _expand_contractions(text: str) -> str:
    return _CONTRACTION_PATTERN.sub(lambda match: _CONTRACTIONS[match.group(0).lower()], text)


def normalize_text(raw_text: str) -> dict[str, Any]:
    normalized = unicodedata.normalize("NFKC", raw_text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    # Straighten smart quotes / dashes so downstream regexes see plain ASCII.
    normalized = normalized.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}))
    normalized = re.sub(r"\s*&\s*", " and ", normalized)
    normalized = _expand_contractions(normalized)
    normalized = re.sub(r"[ \t\f\v]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = re.sub(r"\n+", "\n", normalized).strip()
    return {
        "rawText": raw_text,
        "normalizedText": normalized,
        "matchedRuleIds": [
            "TXT_UNICODE_NFKC_001",
            "TXT_WHITESPACE_COLLAPSE_001",
            "TXT_PUNCTUATION_ASCII_001",
            "TXT_CONTRACTION_EXPAND_001",
        ],
    }


_SENTENCE_ABBREVIATIONS = (
    "e.g.",
    "i.e.",
    "etc.",
    "vs.",
    "no.",
    "approx.",
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "fig.",
    "cf.",
    "al.",
    "inc.",
    "ltd.",
    "co.",
    "corp.",
    "dept.",
    "est.",
    "min.",
    "max.",
    "sec.",
    "req.",
    "spec.",
    "ref.",
    "u.s.",
    "u.k.",
    "u.n.",
    "ph.d.",
    "b.sc.",
    "m.sc.",
)


def _protect_abbreviations(text: str) -> str:
    protected = text
    for abbreviation in _SENTENCE_ABBREVIATIONS:
        # \b so "ms." only matches the title, never the tail of "items."/"terms."
        protected = re.sub(
            rf"\b{re.escape(abbreviation)}",
            abbreviation.replace(".", "․"),
            protected,
            flags=re.IGNORECASE,
        )
    # Keep decimals such as "99.9%" or "1.5 seconds" on one sentence.
    protected = re.sub(r"(?<=\d)\.(?=\d)", "․", protected)
    return protected


def split_sentences(normalized_text: str) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    protected = _protect_abbreviations(normalized_text)
    index = 0
    for raw_line in protected.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # Strip common list bullets/numbering so "- Users can..." parses cleanly.
        line = re.sub(r"^\s*(?:[-*•‣◦]|\d+[.)]|[a-z][.)])\s+", "", line)
        if not line:
            continue
        for match in re.finditer(r"[^.!?]+(?:[.!?]+|$)", line):
            fragment = match.group(0).strip()
            if not fragment:
                continue
            index += 1
            restored = fragment.replace("․", ".")
            parts.append(
                {
                    "id": f"sentence_{index:03d}",
                    "text": restored,
                    "normalizedText": restored.rstrip(".!?").strip(),
                    "sentenceIndex": index,
                    "startOffset": match.start(),
                    "endOffset": match.end(),
                    "matchedRuleId": "SPL_SENTENCE_TERMINATOR_001",
                }
            )
    return parts


def _split_clause_text(text: str) -> list[str]:
    """Split a sentence into clauses without shredding noun lists.

    Splits on semicolons, "then", and "but" (adversative coordinators almost
    always join two full independent clauses), and on coordinating conjunctions
    when the following fragment looks like a new predicate (starts with a modal
    or a known action verb). This keeps "name, email, and phone number" together
    while still separating "the user can log in and the admin can approve".

    A bare verb with nothing after it ("reject") or a buffer that already ends in
    one ("The manager can approve") is a different case: English states the
    object once, at the end of a coordinated verb list ("approve, reject, or
    forward the request"), so those pieces are merged with "and" instead of
    split - which lets _expand_action_object / the dedicated and-joined-verbs
    match in extract_facts distribute the shared object across every verb.
    """
    action_vocab = set(_action_aliases())
    modal_words = {
        word
        for phrase in (
            load_dictionaries().get("permission_modals", [])
            + load_dictionaries().get("obligation_modals", [])
            + load_dictionaries().get("negative_modals", [])
        )
        for word in phrase.lower().split()
    }

    def _words(fragment: str) -> list[str]:
        return re.findall(r"[a-zA-Z']+", fragment.lower())

    def has_modal(fragment: str) -> bool:
        return any(word in modal_words for word in _words(fragment)[:4])

    def _is_action_word(word: str) -> bool:
        return word in action_vocab or singularize(word) in action_vocab

    def is_bare_verb_tail(fragment: str) -> bool:
        """True when `fragment` ends in a known action verb with nothing stated
        after it - it is still waiting for the object a later coordinated verb
        will supply. After a modal only the first word is the verb, so in "can
        borrow books" the "books" is the object even though "book" is a verb."""
        words = _words(fragment)
        if not words or not _is_action_word(words[-1]):
            return False
        modal_positions = [index for index, word in enumerate(words) if word in modal_words]
        if modal_positions:
            return modal_positions[-1] == len(words) - 2
        return len(words) == 1

    determiners = {
        "a", "an", "the", "their", "his", "her", "its", "my", "our", "your", "each", "every", "all",
        "some", "any", "one", "two", "three", "several", "many", "multiple", "other", "another", "new",
    }

    def looks_like_predicate(fragment: str) -> bool:
        words = _words(fragment)
        head = words[:4]
        if any(word in modal_words or _is_action_word(word) for word in head):
            return True
        # "... and prescribe medicines" / "... and enters a PIN": a general
        # English verb opening the piece, confirmed either by a determiner
        # right after it or by a modal earlier in the sentence. A plural first
        # word ("sales reports") or a known field phrase is a noun list.
        if len(words) < 2 or common_verb_base(words[0]) is None:
            return False
        if words[1] in determiners or re.fullmatch(r"\d+", words[1]):
            return True
        if _is_attribute_like(" ".join(words)):
            return False
        return segment_has_modal and not (words[0].endswith("s") and common_verb_base(words[0]) != words[0][:-1])

    def _looks_like_bare_noun_phrase(fragment: str) -> bool:
        """True for a short, plain noun phrase like "due date" or "phone
        number" - even when its head word ("return" in "return date") is
        coincidentally also a recognized action verb elsewhere. A genuine new
        clause always has an article/determiner somewhere before its object
        ("update the status"); a bare 2-3 word compound noun never does."""
        candidate = re.sub(r"^(?:a|an|the)\s+", "", fragment.strip(), flags=re.IGNORECASE)
        if not candidate or len(candidate.split()) > 3:
            return False
        if re.search(r"\b(?:a|an|the)\b", candidate, flags=re.IGNORECASE):
            return False
        return _is_attribute_like(candidate)

    # A relative / subordinate clause ("books that are damaged or lost") modifies
    # the noun before it and must never be split on its internal and/or/comma.
    relative_pattern = re.compile(
        r"\s+\b(?:that|which|who|whom|whose|where|when|because|so that|in order to)\b\s+",
        flags=re.IGNORECASE,
    )

    # Quantity idioms that contain "or"/"and" must stay atomic across the split
    # ("one or more line items" is one object, not "one" + "more line items").
    quantity_idioms = [
        phrase
        for phrase in load_dictionaries().get("quantifiers", {})
        if re.search(r"\b(?:or|and)\b", phrase)
    ] + ["one or two", "more or less", "at least", "at most", "no more than"]

    def _protect_quantity(value: str) -> str:
        for idiom in quantity_idioms:
            value = re.sub(re.escape(idiom), idiom.replace(" ", "\x00"), value, flags=re.IGNORECASE)
        return value

    # Hard breaks first.
    segments = [segment.strip() for segment in re.split(r"\s*;\s*|\s*,?\s+\b(?:then|but)\b\s*,?\s*", text) if segment.strip()]
    result: list[str] = []
    for segment in segments:
        segment_has_modal = any(word in modal_words for word in _words(segment))
        segment = _protect_quantity(segment)
        relative_tail = ""
        relative_match = relative_pattern.search(segment)
        if relative_match:
            relative_tail = segment[relative_match.start():]
            segment = segment[: relative_match.start()].strip()
        pieces = re.split(r"\s*,?\s+\b(?:and|or)\b\s+|\s*,\s+", segment) if segment else []
        buffer = pieces[0].strip() if pieces else segment
        segment_result: list[str] = []
        pending_bare_verbs: list[str] = []
        for piece in pieces[1:]:
            piece = piece.strip()
            if not piece:
                continue
            if _looks_like_bare_noun_phrase(piece):
                # A short, plain noun phrase ("return date", "phone number") -
                # even when its head word ("return") is coincidentally also a
                # recognized action verb elsewhere. Never a new clause with an
                # elided subject; keep it in the current object/attribute list.
                buffer = f"{buffer}, {piece}" if buffer else piece
                continue
            piece_words = _words(piece)
            piece_is_bare_verb = len(piece_words) == 1 and _is_action_word(piece_words[0])
            if has_modal(piece):
                # A genuine new clause: flush anything still waiting for a
                # shared object first (best effort - none ever arrived).
                if buffer and is_bare_verb_tail(buffer) and pending_bare_verbs:
                    pending_bare_verbs.insert(0, buffer)
                    buffer = ""
                if pending_bare_verbs:
                    segment_result.extend(pending_bare_verbs)
                    pending_bare_verbs = []
                if buffer:
                    segment_result.append(buffer)
                buffer = piece
                continue
            if piece_is_bare_verb:
                pending_bare_verbs.append(piece)
                continue
            if pending_bare_verbs or (buffer and is_bare_verb_tail(buffer)):
                # This piece states the object the accumulated bare verbs (or
                # the buffer's own trailing bare verb) were sharing.
                buffer = " and ".join([buffer, *pending_bare_verbs, piece]) if buffer else " and ".join([*pending_bare_verbs, piece])
                pending_bare_verbs = []
            elif looks_like_predicate(piece):
                if buffer:
                    segment_result.append(buffer)
                buffer = piece
            else:
                buffer = f"{buffer}, {piece}" if buffer else piece
        if pending_bare_verbs:
            # Bare verbs with no object ever supplied - keep them as their own
            # minimal clauses rather than silently dropping them.
            if buffer:
                segment_result.append(buffer)
            segment_result.extend(pending_bare_verbs)
            buffer = ""
        if buffer:
            segment_result.append(buffer)
        if relative_tail:
            if segment_result:
                segment_result[-1] = f"{segment_result[-1]}{relative_tail}"
            else:
                segment_result.append(relative_tail.strip())
        result.extend(part.replace("\x00", " ") for part in segment_result)
    return result or [text]


_RELATIVE_CLAUSE_RE = re.compile(
    r"\s+\b(?:that|which|who|whom|whose|where|when)\b\s+.*$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _strip_relative_clause(phrase: str | None) -> str:
    """Drop a trailing relative clause so its internal and/or is not mistaken
    for a coordinated object list."""
    return _RELATIVE_CLAUSE_RE.sub("", phrase or "").strip()


# ---------------------------------------------------------------------------
# Stakeholder ("real people") voice — colloquial requirement sentences.
# ---------------------------------------------------------------------------

def _narrative_actors() -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in load_dictionaries().get("narrative_actors", {}).items()}


def resolve_actor(raw: str | None) -> str | None:
    """normalize_entity, but first map a colloquial subject
    ("I", "we", "people", "my staff") onto a real actor class."""
    if not raw:
        return None
    lowered = re.sub(r"\s+", " ", raw.strip().lower()).strip(" ,.;:")
    aliases = _narrative_actors()
    if lowered in aliases:
        return aliases[lowered]
    without_article = re.sub(r"^(?:a|an|the|our|my|your|their)\s+", "", lowered)
    if without_article in aliases:
        return aliases[without_article]
    return normalize_entity(raw)


_GOAL_CLAUSE_RE = re.compile(
    r"\s*[,;]?\s*\b(?:so that|so (?:they|we|i|you|it|he|she)\b|so as to|in order (?:to|that)|"
    r"because|since|as this|which means|thereby|hence)\b.*$",
    flags=re.IGNORECASE | re.DOTALL,
)
_ABILITY_RE = re.compile(
    r"\b(?:be able to|have the ability to|has the ability to|have the option to|"
    r"the ability to|the option to|a way to|the possibility to|be allowed to)\s+",
    flags=re.IGNORECASE,
)
_NARRATIVE_WANT = (
    r"(?:really\s+|also\s+|just\s+|simply\s+)*"
    r"(?:want|wants|wanted|need|needs|needed|would like|would love|'d like|wish|wishes|"
    r"expect|expects|require|requires|hope|hopes|intend|intends|plan|plans|prefer|prefers)"
)
_NARRATIVE_INTENT_RE = re.compile(
    rf"^(?P<narrator>i|we|the business|the company|the owner|the business owner|management|"
    rf"my (?:staff|team|company|business)|our (?:staff|team))\s+{_NARRATIVE_WANT}\s+"
    rf"(?:that\s+|to\s+see\s+that\s+)?"
    rf"(?:(?P<beneficiary>[a-z][\w' -]*?)\s+(?:to be able to|to|should be able to|should|"
    rf"can|could|must|will|would)\s+)?"
    rf"(?P<rest>.+)$",
    flags=re.IGNORECASE,
)
_PROVISION_RE = re.compile(
    r"^(?:there|it)\s+(?:should|must|shall|needs to|has to|ought to|will|would)\s+be\s+"
    r"(?:a\s+(?:way|option|means|mechanism|feature|screen|page|button|form|facility)\s+)?"
    r"(?:possible\s+)?for\s+(?P<actor>[a-z][\w' -]*?)\s+to\s+(?P<rest>.+)$",
    flags=re.IGNORECASE,
)


def denarrate_clause(text: str) -> str:
    """Rewrite one colloquial stakeholder clause into the plain
    "<actor> <modal> <action> <object>" shape the fact rules already parse.

    "I want people to be able to see the clothes I sell"
        -> "User can see the clothes"
    "Customers should be able to put items in their basket"
        -> "Customers should put items in their basket"
    "There should be a way for a manager to approve orders"
        -> "manager can approve orders"
    Anything it does not recognise is returned unchanged.
    """
    cleaned = _GOAL_CLAUSE_RE.sub("", text).strip(" ,;:")
    # "Members can also reserve books" - an adverb between the modal and the
    # verb would otherwise be read as the action ("also") with "reserve books"
    # as its object.
    cleaned = re.sub(
        rf"\b({_modal_pattern()})\s+(?:also|additionally|then|always|easily|simply|just|quickly|directly|now)\s+",
        r"\1 ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # A leading "if/when someone …" trigger left after clause splitting — keep the
    # predicate, drop the trigger word (the condition, if structured, is captured
    # elsewhere from the full sentence).
    cleaned = re.sub(r"^(?:if|when|whenever|once|after|before|while|as soon as)\s+", "", cleaned, flags=re.IGNORECASE)

    provision = _PROVISION_RE.match(cleaned)
    if provision:
        actor = provision.group("actor").strip()
        rest = _ABILITY_RE.sub("", provision.group("rest")).strip()
        return f"{actor} can {rest}"

    intent = _NARRATIVE_INTENT_RE.match(cleaned)
    if intent:
        rest = _ABILITY_RE.sub("", intent.group("rest")).strip()
        rest = re.sub(r"^(?:to|that|it|us|them)\s+", "", rest, flags=re.IGNORECASE).strip()
        beneficiary = (intent.group("beneficiary") or "").strip()
        # "need to be able to view …" — the regex can capture "to be able" as the
        # beneficiary; that is scaffolding, not a person.
        if re.match(r"^(?:to|be|able|the ability|a way|an option)\b", beneficiary, re.IGNORECASE):
            beneficiary = ""
        if beneficiary:
            return f"{beneficiary} can {rest}"
        actor = resolve_actor(intent.group("narrator")) or "Stakeholder"
        return f"{actor} can {rest}"

    return _ABILITY_RE.sub("", cleaned)


def split_clauses(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clauses: list[dict[str, Any]] = []
    for sentence in sentences:
        raw_parts = [part for part in _split_clause_text(sentence["normalizedText"]) if part.strip()]
        if not raw_parts:
            raw_parts = [sentence["normalizedText"]]
        for clause_index, text in enumerate(raw_parts, start=1):
            clauses.append(
                {
                    "id": f"clause_{sentence['sentenceIndex']:03d}_{clause_index:03d}",
                    "sentenceId": sentence["id"],
                    "text": text,
                    "normalizedText": text,
                    "sentenceIndex": sentence["sentenceIndex"],
                    "clauseIndex": clause_index,
                    "startOffset": sentence["text"].lower().find(text.lower()),
                    "endOffset": sentence["text"].lower().find(text.lower()) + len(text),
                    "matchedRuleId": "SPL_CLAUSE_COMMA_CONJUNCTION_001",
                }
            )
    return clauses


def tokenize(text: str) -> list[dict[str, Any]]:
    tokens = []
    for index, match in enumerate(re.finditer(r"[A-Za-z0-9']+", text), start=1):
        tokens.append(
            {
                "index": index,
                "text": match.group(0),
                "normalized": match.group(0).lower(),
                "startOffset": match.start(),
                "endOffset": match.end(),
                "matchedRuleId": "TOK_WORD_001",
            }
        )
    return tokens


def _action_aliases() -> dict[str, str]:
    dictionaries = load_dictionaries()
    aliases = {
        key.lower(): value
        for dictionary_name in ("action_aliases", "action_aliases_extra")
        for key, value in dictionaries.get(dictionary_name, {}).items()
    }
    # irregular_verbs.json ("made" -> "make", "sent" -> "send", ...) was loaded
    # nowhere - every irregular past tense fell through as an "Unknown action".
    # Wire it in, self-mapping the base form too so "make"/"leave"/"run"/"build"
    # resolve as canonical actions in their own right.
    for inflected, base in dictionaries.get("irregular_verbs", {}).items():
        base_lower = str(base).strip().lower()
        if not base_lower:
            continue
        aliases.setdefault(base_lower, base_lower)
        aliases[str(inflected).strip().lower()] = aliases[base_lower]
    return aliases


def _regular_verb_bases(word: str) -> list[str]:
    """Candidate base forms for a possibly-inflected regular verb, tried in
    order: "generated" -> ["generat", "generate"], "processes" -> ["process",
    "processe"], "stopped" -> ["stopp", "stoppe", "stop"]. Cheap suffix
    stripping, not a full morphological analyzer - just enough to recover a
    base form already present as an action dictionary key, so a verb that's
    listed in only one tense (e.g. action_aliases.json has "generate" but not
    "generated"/"generating") still resolves instead of being flagged unknown.
    """
    candidates: list[str] = []
    if word.endswith("ied") and len(word) > 4:
        candidates.append(word[:-3] + "y")
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            stem = word[: -len(suffix)]
            candidates.append(stem)
            candidates.append(stem + "e")
            if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
                candidates.append(stem[:-1])
    if word.endswith("es") and len(word) > 4:
        candidates.append(word[:-2])
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        candidates.append(word[:-1])
    return candidates


def _relationship_phrases() -> dict[str, str]:
    dictionaries = load_dictionaries()
    phrases = {
        key.lower(): value
        for dictionary_name in ("relationship_phrases", "relationship_phrases_extra")
        for key, value in dictionaries.get(dictionary_name, {}).items()
    }
    return phrases


def _nfr_keywords() -> dict[str, Any]:
    return load_dictionaries().get("nfr_keywords", {})


def _articles_pattern() -> str:
    articles = [str(item).strip().lower() for item in load_dictionaries().get("articles", []) if str(item).strip()]
    ordered = sorted({re.escape(item) for item in articles or ["a", "an", "the"]}, key=len, reverse=True)
    return r"(?:" + "|".join(ordered) + r")\s+"


def _modal_pattern() -> str:
    dictionaries = load_dictionaries()
    modals = (
        dictionaries.get("permission_modals", [])
        + dictionaries.get("obligation_modals", [])
        + dictionaries.get("negative_modals", [])
    )
    ordered = sorted([re.escape(item) for item in modals], key=len, reverse=True)
    return r"(?:" + "|".join(ordered) + r")"


def _common_verbs() -> set[str]:
    """General English verbs (common_verbs.json). A verb found here but not in
    the action alias tables is a real verb with no synonym mapping - it keeps
    its own base form instead of being reported as unknown."""
    return {str(item).strip().lower() for item in load_dictionaries().get("common_verbs", []) if str(item).strip()}


def common_verb_base(word: str) -> str | None:
    """Base form of `word` when it is an inflection of a common verb."""
    lowered = word.strip().lower()
    verbs = _common_verbs()
    if lowered in verbs:
        return lowered
    irregular = {str(k).lower(): str(v).lower() for k, v in load_dictionaries().get("irregular_verbs", {}).items()}
    if irregular.get(lowered) in verbs:
        return irregular[lowered]
    for candidate in _regular_verb_bases(lowered):
        if candidate in verbs:
            return candidate
    return None


def _is_recognized_action_word(word: str) -> bool:
    """True when `word` (in any inflection) resolves to a known action -
    the same recognition _canonical_action ends up using, exposed separately
    so the various "does this look like a verb" gates before it agree with
    what it can actually canonicalize."""
    aliases = _action_aliases()
    if word in aliases or singularize(word) in aliases:
        return True
    if any(candidate in aliases for candidate in _regular_verb_bases(word)):
        return True
    return common_verb_base(word) is not None


def _canonical_action(raw_action: str | None) -> tuple[str | None, str, list[str]]:
    if raw_action is None:
        return None, "EXT_NO_ACTION_001", []
    lowered = raw_action.strip().lower()
    aliases = _action_aliases()
    canonical = aliases.get(lowered)
    if canonical:
        return canonical, "EXT_ACTION_ALIAS_001", []
    for candidate in _regular_verb_bases(lowered):
        canonical = aliases.get(candidate)
        if canonical:
            return canonical, "EXT_ACTION_ALIAS_001", []
    base = common_verb_base(lowered)
    if base:
        return base, "EXT_ACTION_COMMON_VERB_001", []
    head, _, particle = lowered.partition(" ")
    if particle and (head in aliases or common_verb_base(head)):
        head_base = verb_lemma(head) or head
        return f"{head_base} {particle}", "EXT_ACTION_PHRASAL_VERB_001", []
    return lowered, "EXT_UNKNOWN_ACTION_001", [f'Unknown action "{raw_action}".']


_PHRASAL_PARTICLES = {"out", "up", "off", "down", "back", "over", "away"}
_PHRASAL_IN_ON = {
    "check in", "log in", "sign in", "fill in", "hand in", "turn in", "check on", "log on", "sign on",
    "turn on", "switch on", "try on", "take on", "put on", "drop in", "plug in", "clock in",
}


def _absorb_phrasal_particle(raw_action: str, object_group: str | None) -> tuple[str, str | None]:
    """"log" + "in to the system" -> "log in" + "to the system".

    The action/object regexes capture a single bare verb, so a phrasal verb's
    particle ("log in", "sign up", "check out", "back up") is mistaken for the
    start of the object and the verb itself is left unrecognized. Recombine the
    verb with the next word whenever that pair is itself a known action; falls
    back unchanged when it isn't.
    """
    object_words = (object_group or "").split()
    if not object_words or " " in raw_action.strip():
        return raw_action, object_group
    particle = object_words[0].lower()
    combined = f"{raw_action.strip().lower()} {particle}"
    if combined in _action_aliases():
        return combined, " ".join(object_words[1:])
    # A general phrasal verb: the particle directly follows a known verb and an
    # object still follows it ("checks out guests"). "in"/"on" double as plain
    # prepositions ("enroll in courses"), so they only count for known pairs.
    base = verb_lemma(raw_action) or raw_action.strip().lower()
    phrasal = particle in _PHRASAL_PARTICLES or f"{base} {particle}" in _PHRASAL_IN_ON
    # "up to five", "out of stock", "over 100": a quantity or preposition
    # follows, so the word is not a particle.
    follows = object_words[1].lower() if len(object_words) > 1 else ""
    if follows in {"to", "of", "from", "than", "with"} or re.fullmatch(r"\d+", follows) or follows in NUMBER_WORDS:
        phrasal = False
    if phrasal and len(object_words) > 1 and _is_recognized_action_word(raw_action.strip().lower()):
        return f"{raw_action.strip()} {particle}", " ".join(object_words[1:])
    return raw_action, object_group


def _split_coordinated(phrase: str) -> list[str]:
    # "one or more accounts" is one quantified object, not "one" + "more accounts".
    protected = phrase or ""
    for idiom in ("one or more", "zero or more", "one or many", "one or two", "zero or one", "more or less"):
        protected = re.sub(re.escape(idiom), idiom.replace(" ", "\x00"), protected, flags=re.IGNORECASE)
    parts = [
        re.sub(r"^(?:a|an|the)\s+", "", part.replace("\x00", " ").strip(), flags=re.IGNORECASE)
        for part in re.split(r"\s*,\s*|\s+\band\b\s+|\s+\bor\b\s+", protected)
        if part.strip()
    ]
    return parts or ([phrase.strip()] if phrase and phrase.strip() else [])


def _expand_action_object(raw_action: str | None, raw_object: str | None) -> list[tuple[str, str]]:
    """Turn "create and update the order" / "view the order and the invoice" into pairs."""
    actions = _split_coordinated(raw_action or "") or [(raw_action or "").strip()]
    objects = _split_coordinated(raw_object or "") or [(raw_object or "").strip()]
    actions = [item for item in actions if item][:4] or [""]
    objects = [item for item in objects if item][:6] or [""]
    if len(actions) > 1 and len(objects) == 1:
        return [(action, objects[0]) for action in actions]
    if len(objects) > 1 and len(actions) == 1:
        return [(actions[0], obj) for obj in objects]
    if len(actions) == len(objects) and len(actions) > 1:
        return list(zip(actions, objects))
    return [(actions[0], objects[0])]


_BASE_CONDITION_TRIGGERS = ("if", "when", "whenever", "unless", "once", "after", "before", "while", "as soon as")


def _condition_triggers() -> str:
    """Trigger words for a subordinate condition: the built-in set plus
    conditional_markers.json ("provided that", "in case", ...)."""
    markers = {str(item).strip().lower() for item in load_dictionaries().get("conditional_markers", []) if str(item).strip()}
    ordered = sorted({re.escape(item) for item in markers.union(_BASE_CONDITION_TRIGGERS)}, key=len, reverse=True)
    return r"(?:" + "|".join(ordered) + r")"


_CONDITION_SPECIFIC_STATE_RE = re.compile(
    r"\b(?:if|when|unless)\s+(?:the\s+|a\s+|an\s+)?(?P<subject>[a-zA-Z][\w -]*?)\s+"
    r"(?P<verb>fails|failed|is failed|succeeds|expires|is invalid|is valid)\b",
    re.IGNORECASE,
)


def _condition_state_pattern() -> str:
    words = {str(item).lower() for item in load_dictionaries().get("state_words", [])}
    return "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))


def _condition_match(text: str) -> re.Match[str] | None:
    """Find a subordinate condition clause ("if payment fails", "once the order
    is shipped") anywhere in `text`. Tries the original narrow if/when/unless +
    specific-verb wording first (unchanged, so existing phrasing is untouched),
    then falls back to a broader trigger set ("once", "after", "before",
    "while", "whenever", "as soon as") paired with a generic "is/are/was/were/
    has been/have been <state>" pattern, where <state> is a known state word
    (confirmed, shipped, approved, cancelled, ...). Without this, a clause like
    "once the payment is confirmed" fell through to the plain fact parser, which
    has no way to represent a subordinate condition and produced a bogus
    standalone fact instead (e.g. actor "PaymentIs").
    """
    specific = _CONDITION_SPECIFIC_STATE_RE.search(text)
    if specific:
        return specific
    state_pattern = _condition_state_pattern()
    if not state_pattern:
        return None
    return re.search(
        rf"\b{_condition_triggers()}\s+(?:the\s+|a\s+|an\s+)?(?P<subject>[a-zA-Z][\w -]*?)\s+"
        rf"(?:is|are|was|were|has been|have been)\s+(?P<state>{state_pattern})\b",
        text,
        re.IGNORECASE,
    )


def _condition_from_text(text: str) -> dict[str, Any] | None:
    match = _condition_match(text)
    if not match:
        return None
    groups = match.groupdict()
    if groups.get("verb"):
        verb = groups["verb"].lower().replace("is ", "")
        value = "failed" if verb in {"fails", "failed"} else verb
    else:
        # "is confirmed"/"is shipped" (kept together, unlike the plain-verb
        # branch above) so condition_to_text's simple "<subject> <value>" join
        # reads as "the Payment is confirmed" rather than "Payment confirmed".
        value = f"is {groups['state'].lower()}"
    return {"subject": normalize_entity(match.group("subject")), "operator": "is", "value": value}


NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "thirty": 30, "fifty": 50, "hundred": 100,
}
_NUMBER_WORD_RE = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b")


def _digits_for_number_words(text: str) -> str:
    return _NUMBER_WORD_RE.sub(lambda match: str(NUMBER_WORDS[match.group(1)]), text)


def _quantity_from_text(text: str) -> tuple[str | None, str | None]:
    """Multiplicity from a quantity phrase. Multi-word dictionary idioms
    ("one or more", "at least one") win first, then numeric bounds - with
    number words read as digits, so "up to five books" is 0..5 - and only then
    single-word quantifiers ("many", "optional"). Checking single words last
    keeps "no" from swallowing "no more than 3"."""
    lowered = text.lower()
    quantifiers = load_dictionaries().get("quantifiers", {})
    ordered = sorted(quantifiers.items(), key=lambda item: len(item[0]), reverse=True)
    for phrase, multiplicity in ordered:
        if " " in phrase and re.search(rf"\b{re.escape(phrase)}\b", lowered):
            return multiplicity, "MUL_QUANTIFIER_DICTIONARY_001"
    numeric = _digits_for_number_words(lowered)
    patterns = [
        (r"\bbetween\s+(\d+)\s+and\s+(\d+)", "{0}..{1}", "MUL_BETWEEN_NUMBER_001"),
        (r"\bexactly\s+(\d+)", "{0}", "MUL_EXACT_NUMBER_001"),
        (r"\b(?:at least|minimum(?: of)?|no fewer than|no less than)\s+(\d+)", "{0}..*", "MUL_AT_LEAST_NUMBER_001"),
        (r"\b(?:at most|no more than|not more than)\s+(\d+)", "0..{0}", "MUL_AT_MOST_NUMBER_001"),
        (r"\b(?:maximum(?: of)?|up to|a maximum of)\s+(\d+)", "0..{0}", "MUL_MAX_NUMBER_001"),
        (r"\b(\d+)\s+or\s+more\b", "{0}..*", "MUL_AT_LEAST_NUMBER_001"),
        (r"^(?:(?:a|an|the|has|have|with|of|contains?|holds?)\s+)*(\d+)\s+[a-z]", "{0}", "MUL_EXACT_NUMBER_001"),
    ]
    for pattern, template, rule_id in patterns:
        match = re.search(pattern, numeric)
        if match:
            return template.format(*match.groups()), rule_id
    for phrase, multiplicity in ordered:
        if " " not in phrase and re.search(rf"\b{re.escape(phrase)}\b", lowered):
            return multiplicity, "MUL_QUANTIFIER_DICTIONARY_001"
    return None, None


def _modality(text: str) -> tuple[str, bool]:
    lowered = text.lower()
    for phrase in load_dictionaries().get("negative_modals", []):
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            return "negative", True
    for phrase in load_dictionaries().get("obligation_modals", []):
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            return "obligation", False
    return "permission", False


def _nfr_from_sentence(sentence: dict[str, Any]) -> dict[str, Any] | None:
    text = sentence["normalizedText"]
    lowered = text.lower()
    for category, config in _nfr_keywords().items():
        if any(re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in config.get("keywords", [])):
            number_match = re.search(r"\b(?:within|under|less than|no more than)\s+(?P<number>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?P<unit>seconds?|minutes?|hours?|ms|milliseconds?)\b", lowered)
            words_to_numbers = {
                "one": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
                "seven": 7,
                "eight": 8,
                "nine": 9,
                "ten": 10,
            }
            metric = config.get("metric")
            target = None
            unit = None
            measurable = False
            if number_match:
                raw_number = number_match.group("number")
                target = int(raw_number) if raw_number.isdigit() else words_to_numbers[raw_number]
                unit = number_match.group("unit")
                measurable = True
            return {
                "category": category,
                "metric": metric,
                "operator": "<=" if measurable else None,
                "targetValue": target,
                "unit": unit,
                "measurable": measurable,
                "matchedRuleId": f"NFR_{category.upper()}_KEYWORD_001",
                "warnings": [] if measurable else [f"No numeric {category.lower()} target was found."],
            }
    return None


def _fact_template(
    *,
    fact_index: int,
    sentence: dict[str, Any],
    clause: dict[str, Any],
    actor: str | None,
    action: str | None,
    object_name: str | None,
    raw_action: str | None,
    matched_rule_id: str,
    extraction_type: str,
    condition: dict[str, Any] | None = None,
    relationship_type: str | None = None,
    source_multiplicity: str | None = None,
    target_multiplicity: str | None = None,
    nfr: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    modality, negated = _modality(clause["text"])
    missing = []
    if actor is None and nfr is None:
        missing.append("actor")
    if action is None and nfr is None:
        missing.append("action")
    if object_name is None and nfr is None:
        missing.append("object")
    return {
        "id": f"fact_{fact_index:03d}",
        "sourceText": clause["text"],
        "sourceSentenceId": sentence["id"],
        "sourceSentenceText": sentence.get("text") or sentence.get("normalizedText") or clause["text"],
        "sourceClauseId": clause["id"],
        "sentenceIndex": sentence["sentenceIndex"],
        "clauseIndex": clause["clauseIndex"],
        "actor": actor,
        "action": action,
        "rawAction": raw_action,
        "object": object_name,
        "indirectObject": None,
        "condition": condition,
        "trigger": None,
        "precondition": None,
        "postcondition": None,
        "modality": modality,
        "negated": negated,
        "quantity": target_multiplicity,
        "sourceMultiplicity": source_multiplicity,
        "targetMultiplicity": target_multiplicity,
        "temporalConstraint": None,
        "state": None,
        "previousState": None,
        "nextState": None,
        "relationshipType": relationship_type,
        "nfr": nfr,
        "matchedRuleId": matched_rule_id,
        "extractionType": extraction_type,
        "missingFields": missing,
        "warnings": warnings or [],
    }


def extract_facts(sentences: list[dict[str, Any]], clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    known_entities: list[str] = []
    sentence_lookup = {sentence["id"]: sentence for sentence in sentences}
    modal_pattern = _modal_pattern()
    article = _articles_pattern()

    for clause in clauses:
        sentence = sentence_lookup[clause["sentenceId"]]
        # Rewrite stakeholder voice ("I want people to be able to see …") into the
        # plain "<actor> <modal> <action> <object>" shape the rules below parse.
        text = denarrate_clause(clause["normalizedText"].strip())
        lowered = text.lower()
        fact_index = len(facts) + 1
        condition = _condition_from_text(sentence["normalizedText"])
        # A clause that is itself entirely the subordinate condition trigger
        # ("once the payment is confirmed") has already been captured above and
        # attached to every clause of this sentence via `condition` - it is not
        # a requirement of its own. Emitting a second, standalone fact from its
        # leftover words (after denarrate_clause strips the trigger word) would
        # just mangle the same condition into a bogus fact (e.g. actor
        # "PaymentIs"), so skip it here instead.
        clause_source = clause["normalizedText"].strip()
        clause_condition_match = _condition_match(clause_source)
        if clause_condition_match and clause_condition_match.start() == 0:
            trailing = clause_source[clause_condition_match.end():].strip(" ,;:.")
            if not trailing:
                continue
        nfr = _nfr_from_sentence(sentence)

        if nfr and ("system" in lowered or nfr["category"]):
            facts.append(
                _fact_template(
                    fact_index=fact_index,
                    sentence=sentence,
                    clause=clause,
                    actor="System",
                    action=nfr.get("metric") or "satisfy",
                    object_name=nfr["category"],
                    raw_action=nfr.get("metric"),
                    matched_rule_id=nfr["matchedRuleId"],
                    extraction_type="DICTIONARY_PATTERN",
                    nfr=nfr,
                    warnings=nfr["warnings"],
                )
            )
            known_entities.extend(["System", nfr["category"]])
            continue

        # Passive voice with an explicit agent ("An email shall be sent by the
        # system to the customer") - the bare passive_match below requires
        # nothing at all after the verb, so this construction used to fall
        # through to active_match, which mis-parsed the "by ... to ..." tail
        # into a bogus actor/action/object triple.
        passive_agent_match = re.match(
            rf"^(?:{article})?(?P<direct_object>[a-zA-Z][\w -]*?)\s+{modal_pattern}\s+be\s+(?P<action>[a-zA-Z]+)\s+by\s+"
            rf"(?:{article})?(?P<actor>[a-zA-Z][\w -]*?)(?:\s+to\s+(?:{article})?(?P<recipient>[a-zA-Z][\w -]*))?$",
            text,
            flags=re.IGNORECASE,
        )
        if passive_agent_match:
            raw_action = passive_agent_match.group("action")
            actor = resolve_actor(passive_agent_match.group("actor"))
            recipient = passive_agent_match.group("recipient")
            # The recipient of a communication verb ("send an email to the
            # customer") is the actionable relationship target, matching how
            # "notify the customer" is modeled elsewhere in this file; fall
            # back to the passive subject itself when there is no recipient.
            object_name = normalize_entity(recipient) if recipient else normalize_entity(passive_agent_match.group("direct_object"))
            action, _, warnings = _canonical_action(raw_action)
            facts.append(
                _fact_template(
                    fact_index=fact_index,
                    sentence=sentence,
                    clause=clause,
                    actor=actor,
                    action=action,
                    object_name=object_name,
                    raw_action=raw_action,
                    matched_rule_id="EXT_PASSIVE_WITH_AGENT_001",
                    extraction_type="PASSIVE_PATTERN",
                    warnings=warnings,
                )
            )
            known_entities.extend([item for item in [actor, object_name] if item])
            continue

        passive_match = re.match(
            rf"^(?:{article})?(?P<object>[a-zA-Z][\w -]*?)\s+{modal_pattern}\s+be\s+(?P<action>[a-zA-Z]+)$",
            text,
            flags=re.IGNORECASE,
        )
        if passive_match:
            raw_action = passive_match.group("action")
            object_name = normalize_entity(passive_match.group("object"))
            action, _, warnings = _canonical_action(raw_action)
            facts.append(
                _fact_template(
                    fact_index=fact_index,
                    sentence=sentence,
                    clause=clause,
                    actor=None,
                    action=action,
                    object_name=object_name,
                    raw_action=raw_action,
                    matched_rule_id="EXT_PASSIVE_OBJECT_ACTION_001",
                    extraction_type="PASSIVE_PATTERN",
                    warnings=warnings,
                )
            )
            if object_name:
                known_entities.append(object_name)
            continue

        relationship_match = None
        relationship_type = None
        for phrase, rel_type in sorted(_relationship_phrases().items(), key=lambda item: len(item[0]), reverse=True):
            pattern = rf"^(?:{article})?(?P<source>[a-zA-Z][\w -]*?)\s+(?:{modal_pattern}\s+)?{re.escape(phrase)}\s+(?P<object>.+)$"
            relationship_match = re.match(pattern, text, flags=re.IGNORECASE)
            if relationship_match:
                relationship_type = rel_type
                raw_action = phrase
                break
        if relationship_match and relationship_type:
            actor = resolve_actor(relationship_match.group("source"))
            action, _, action_warnings = _canonical_action(raw_action)
            # "a member has a full name, an email address and a membership
            # status" names three separate fields, not one combined object -
            # split the coordinated list so each becomes its own fact instead
            # of being mashed into a single, mangled entity name.
            for object_text in _split_coordinated(relationship_match.group("object")):
                object_name = normalize_entity(object_text)
                if not object_name:
                    continue
                warnings = list(action_warnings)
                source_multiplicity = None
                target_multiplicity = None
                multiplicity_rule = None
                if relationship_type in CARDINALITY_RELATIONSHIP_TYPES:
                    target_multiplicity, multiplicity_rule = _quantity_from_text(text)
                    source_multiplicity = "1"
                    if target_multiplicity is None:
                        target_multiplicity = "0..*"
                        warnings.append("Default multiplicity applied.")
                facts.append(
                    _fact_template(
                        fact_index=len(facts) + 1,
                        sentence=sentence,
                        clause=clause,
                        actor=actor,
                        action=action,
                        object_name=object_name,
                        raw_action=raw_action,
                        matched_rule_id="REL_PHRASE_DICTIONARY_001" if multiplicity_rule is None else multiplicity_rule,
                        extraction_type="PHRASE_PATTERN",
                        relationship_type=relationship_type,
                        source_multiplicity=source_multiplicity,
                        target_multiplicity=target_multiplicity,
                        warnings=warnings,
                    )
                )
                known_entities.extend([item for item in [actor, object_name] if item])
            continue

        # "The system shall allow/enable/permit/let <actor> to <action> <object>"
        grant_match = re.match(
            rf"^(?:{article})?[a-zA-Z][\w -]*?\s+(?:{modal_pattern}\s+)?(?:allow|allows|enable|enables|permit|permits|let|lets|give|gives|grant|grants)\s+(?:{article})?(?P<actor>[a-zA-Z][\w -]*?)\s+(?:to\s+|the\s+ability\s+to\s+|permission\s+to\s+)(?P<action>[a-zA-Z][\w ]*?)\s+(?:{article})?(?P<object>[a-zA-Z][\w ,-]*)$",
            text,
            flags=re.IGNORECASE,
        )
        if grant_match:
            for action_name, object_name in _expand_action_object(grant_match.group("action"), grant_match.group("object")):
                canonical_action, action_rule_id, action_warnings = _canonical_action(action_name)
                actor = resolve_actor(grant_match.group("actor"))
                normalized_object = normalize_entity(object_name)
                facts.append(
                    _fact_template(
                        fact_index=len(facts) + 1,
                        sentence=sentence,
                        clause=clause,
                        actor=actor,
                        action=canonical_action,
                        object_name=normalized_object,
                        raw_action=action_name,
                        matched_rule_id="EXT_SYSTEM_GRANTS_ACTOR_ACTION_OBJECT_001",
                        extraction_type="EXACT_PATTERN" if action_rule_id != "EXT_UNKNOWN_ACTION_001" else "POSITIONAL_GUESS",
                        condition=condition,
                        warnings=action_warnings,
                    )
                )
                known_entities.extend([item for item in [actor, normalized_object] if item])
            continue

        # "<actor> <modal> <verb1> and <verb2> (and <verb3> ...) <object>" - a
        # coordinated verb list sharing one trailing object ("approve, reject, or
        # forward the request", already normalized to "and" by _split_clause_text,
        # or a sentence written that way directly: "generate and email an
        # invoice"). The generic active_match below can't parse this: its action
        # and object groups are both permissive, so a lazy engine always picks the
        # shortest possible action and dumps every other verb into the object.
        # Each candidate verb is validated against the action dictionary so this
        # never misfires on an ordinary "<actor> <modal> <verb> <object>" clause.
        and_verb_list_match = re.match(
            rf"^(?:{article})?(?P<actor>[a-zA-Z][\w -]*?)\s+{modal_pattern}\s+"
            rf"(?P<verbs>[a-zA-Z]+(?:\s+and\s+[a-zA-Z]+)+)\s+(?:{article})?(?P<object>[a-zA-Z][\w ,-]*)$",
            text,
            flags=re.IGNORECASE,
        )
        if and_verb_list_match:
            verb_tokens = [token.strip() for token in and_verb_list_match.group("verbs").split(" and ")]
            if verb_tokens and all(_is_recognized_action_word(token.lower()) for token in verb_tokens):
                actor = resolve_actor(and_verb_list_match.group("actor"))
                object_group = _strip_relative_clause(and_verb_list_match.group("object"))
                for action_name, object_name in _expand_action_object(" and ".join(verb_tokens), object_group):
                    action, action_rule_id, warnings = _canonical_action(action_name)
                    normalized_object = normalize_entity(object_name)
                    facts.append(
                        _fact_template(
                            fact_index=len(facts) + 1,
                            sentence=sentence,
                            clause=clause,
                            actor=actor,
                            action=action,
                            object_name=normalized_object,
                            raw_action=action_name,
                            matched_rule_id="EXT_AND_JOINED_VERB_LIST_001",
                            extraction_type="EXACT_PATTERN" if action_rule_id != "EXT_UNKNOWN_ACTION_001" else "POSITIONAL_GUESS",
                            condition=condition,
                            warnings=warnings,
                        )
                    )
                    known_entities.extend([item for item in [actor, normalized_object] if item])
                continue

        only_match = re.match(
            rf"^only\s+(?:{article})?(?P<actor>[a-zA-Z][\w -]*?)\s+{modal_pattern}\s+(?P<action>[a-zA-Z][\w ]*?)\s+(?:{article})?(?P<object>[a-zA-Z][\w ,-]*)$",
            text,
            flags=re.IGNORECASE,
        )
        active_match = re.match(
            rf"^(?:{article})?(?P<actor>[a-zA-Z][\w -]*?)\s+{modal_pattern}\s+(?P<action>[a-zA-Z][\w ]*?)\s+(?:{article})?(?P<object>[a-zA-Z][\w ,-]*)$",
            text,
            flags=re.IGNORECASE,
        )
        # Declarative present tense without a modal: "The system sends a confirmation email".
        present_match = None
        first_word = (re.findall(r"[a-zA-Z]+", text) or [""])[0].lower()
        opens_with_verb = bool(first_word) and (
            common_verb_base(first_word) == first_word or first_word in _action_aliases()
        ) and first_word not in {"a", "an", "the"}
        if not (only_match or active_match) and not opens_with_verb:
            candidate = re.match(
                rf"^(?:{article})?(?P<actor>[a-zA-Z][\w -]*?)\s+(?P<action>[a-zA-Z]+(?:e?s)?)\s+(?:{article})?(?P<object>[a-zA-Z][\w ,-]*)$",
                text,
                flags=re.IGNORECASE,
            )
            if candidate:
                head_action = candidate.group("action").strip().lower()
                if _is_recognized_action_word(head_action):
                    present_match = candidate

        match = only_match or active_match or present_match
        if match:
            raw_action = match.group("action").strip()
            actor = resolve_actor(match.group("actor"))
            # "remove books that are damaged or lost" — the object is just "books";
            # the relative clause is a filter, not a second object.
            object_group = _strip_relative_clause(match.group("object"))
            raw_action, object_group = _absorb_phrasal_particle(raw_action, object_group)
            for action_name, object_name in _expand_action_object(raw_action, object_group):
                action, action_rule_id, warnings = _canonical_action(action_name)
                normalized_object = normalize_entity(object_name)
                # "borrow up to five books" bounds how many Books one actor
                # handles - the same multiplicity a "has" phrase would carry.
                target_multiplicity, _ = _quantity_from_text(object_name or "")
                if normalized_object and normalized_object.lower() in load_dictionaries().get("pronouns", {}).get("objectPronouns", []):
                    if len(set(known_entities)) == 1:
                        normalized_object = known_entities[-1]
                    elif condition and condition.get("subject"):
                        normalized_object = condition["subject"]
                    else:
                        warnings = warnings + [f'Pronoun "{object_name}" has multiple possible references.']
                facts.append(
                    _fact_template(
                        fact_index=len(facts) + 1,
                        sentence=sentence,
                        clause=clause,
                        actor=actor,
                        action=action,
                        object_name=normalized_object,
                        raw_action=action_name,
                        matched_rule_id="EXT_ONLY_ACTOR_CAN_ACTION_OBJECT_001"
                        if only_match
                        else "EXT_PRESENT_TENSE_ACTION_001"
                        if present_match
                        else action_rule_id,
                        extraction_type="EXACT_PATTERN" if action_rule_id != "EXT_UNKNOWN_ACTION_001" else "POSITIONAL_GUESS",
                        condition=condition,
                        source_multiplicity="1" if target_multiplicity else None,
                        target_multiplicity=target_multiplicity,
                        warnings=warnings,
                    )
                )
                known_entities.extend(
                    [item for item in [actor, normalized_object] if item and item not in {"It", "This", "That"}]
                )
            continue

        if passive_match:
            raw_action = passive_match.group("action")
            object_name = normalize_entity(passive_match.group("object"))
            action, _, warnings = _canonical_action(raw_action)
            if action is None and raw_action:
                action = raw_action
            facts.append(
                _fact_template(
                    fact_index=fact_index,
                    sentence=sentence,
                    clause=clause,
                    actor=None,
                    action=action,
                    object_name=object_name,
                    raw_action=raw_action,
                    matched_rule_id="EXT_PASSIVE_OBJECT_ACTION_001",
                    extraction_type="PASSIVE_PATTERN",
                    warnings=warnings,
                )
            )
            if object_name:
                known_entities.append(object_name)
            continue

        tokens = tokenize(text)
        # A bare noun list ("name, email, and phone number") is attributes, not a fact.
        primitive_nouns = {item.lower() for item in load_dictionaries().get("primitive_attributes", [])}
        action_token = next(
            (
                token
                for token in tokens
                if token["normalized"] in _action_aliases() and token["normalized"] not in primitive_nouns
            ),
            None,
        )
        if action_token is None and tokens and common_verb_base(tokens[0]["normalized"]):
            # A coordinated clause whose subject was elided ("... and
            # prescribe medicines") opens with its verb.
            action_token = tokens[0]
        has_modal = re.search(rf"\b{modal_pattern}\b", text, flags=re.IGNORECASE) is not None
        if action_token and (has_modal or len(tokens) <= 6):
            before = " ".join(token["text"] for token in tokens[: action_token["index"] - 1])
            after = text[action_token["endOffset"]:].strip(" .")
            # Drop a trailing modal so "the librarian can" resolves to "Librarian".
            before = re.sub(rf"\s+{modal_pattern}\s*$", "", before, flags=re.IGNORECASE).strip()
            raw_action, after = _absorb_phrasal_particle(action_token["text"], after)
            actor = resolve_actor(before) or None
            for action_name, object_text in _expand_action_object(raw_action, _strip_relative_clause(after)):
                action, _, warnings = _canonical_action(action_name)
                facts.append(
                    _fact_template(
                        fact_index=len(facts) + 1,
                        sentence=sentence,
                        clause=clause,
                        actor=actor,
                        action=action,
                        object_name=normalize_entity(object_text) or None,
                        raw_action=action_name,
                        matched_rule_id="EXT_POSITIONAL_ACTION_001",
                        extraction_type="POSITIONAL_GUESS",
                        condition=condition,
                        warnings=warnings,
                    )
                )

    # An elided subject in a coordinated clause ("...shall notify the warehouse
    # and update the inventory") leaves the second clause with no actor of its
    # own - it shares the previous clause's subject. Fill it in per sentence, in
    # textual order, but only for a genuine action+object predicate - never for
    # a passive-voice fact, where a missing actor is a deliberate, separate
    # clarification question, not an ellipsis to resolve here.
    last_actor_by_sentence: dict[int, str] = {}
    for fact in facts:
        sentence_index = fact.get("sentenceIndex")
        if fact.get("actor"):
            last_actor_by_sentence[sentence_index] = fact["actor"]
        elif (
            fact.get("extractionType") != "PASSIVE_PATTERN"
            and fact.get("action")
            and fact.get("object")
            and sentence_index in last_actor_by_sentence
        ):
            fact["actor"] = last_actor_by_sentence[sentence_index]
            fact["missingFields"] = [field for field in fact.get("missingFields", []) if field != "actor"]
            fact.setdefault("warnings", []).append("Actor inferred from the preceding clause in this sentence.")
    return facts


_VAGUE_QUANTITY_TERMS = (
    "some",
    "several",
    "a few",
    "a number of",
    "multiple",
    "many",
    "various",
    "a lot of",
    "lots of",
    "certain",
)
_VAGUE_TIME_TERMS = (
    "quickly",
    "fast",
    "soon",
    "regularly",
    "periodically",
    "frequently",
    "in real time",
    "real-time",
    "immediately",
    "as soon as possible",
    "from time to time",
)


def _clarification(
    *,
    sequence: int,
    text: str,
    fact: dict[str, Any],
    category: str,
    reason: str,
    rule_id: str,
    answer_mapping: str,
    suggested_options: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"CLR-{sequence:03d}",
        "text": text,
        "category": category,
        "sourceSentence": fact.get("sourceSentenceText") or fact.get("sourceText"),
        "sourceClause": fact.get("sourceText"),
        "sourceSentenceId": fact.get("sourceSentenceId"),
        "sentenceIndex": fact.get("sentenceIndex"),
        "reason": reason,
        "triggeredRuleId": rule_id,
        "relatedActor": fact.get("actor"),
        "relatedAction": fact.get("action"),
        "relatedObject": fact.get("object"),
        "suggestedOptions": suggested_options or [],
        "sourceFactId": fact["id"],
        "answerMapping": answer_mapping,
    }


def generate_clarifications(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []

    # Cross-fact: the same actor/action/object asserted both positively and negatively.
    polarity: dict[tuple[str, str, str], set[str]] = {}
    for fact in facts:
        key = (
            str(fact.get("actor") or ""),
            str(fact.get("action") or ""),
            str(fact.get("object") or ""),
        )
        if all(key):
            polarity.setdefault(key, set()).add("negative" if fact.get("negated") else "positive")
    conflicting_keys = {key for key, signs in polarity.items() if len(signs) > 1}
    seen_conflicts: set[tuple[str, str, str]] = set()

    for fact in facts:
        actor = fact.get("actor")
        action = fact.get("action")
        object_name = fact.get("object")
        source_clause = str(fact.get("sourceText") or "")
        lowered = source_clause.lower()

        if action and object_name and not actor:
            questions.append(
                _clarification(
                    sequence=len(questions) + 1,
                    text=f"Who can {action} the {object_name}?",
                    fact=fact,
                    category="Missing Actor",
                    reason="Action and object were found, but the actor was missing.",
                    rule_id="CLR_MISSING_ACTOR_001",
                    answer_mapping="actor",
                )
            )
        elif actor and action and not object_name:
            questions.append(
                _clarification(
                    sequence=len(questions) + 1,
                    text=f"What can the {actor} {action}?",
                    fact=fact,
                    category="Missing Object",
                    reason="Actor and action were found, but the object was missing.",
                    rule_id="CLR_MISSING_OBJECT_001",
                    answer_mapping="object",
                )
            )
        elif actor and object_name and not action:
            questions.append(
                _clarification(
                    sequence=len(questions) + 1,
                    text=f"What does the {actor} do with the {object_name}?",
                    fact=fact,
                    category="Missing Action",
                    reason="Actor and object were found, but the action was missing.",
                    rule_id="CLR_MISSING_ACTION_001",
                    answer_mapping="action",
                )
            )
        elif any("Unknown action" in warning for warning in fact.get("warnings", [])):
            questions.append(
                _clarification(
                    sequence=len(questions) + 1,
                    text=f'What does "{fact.get("rawAction")}" mean in this story?',
                    fact=fact,
                    category="Unknown Action",
                    reason="The probable action is not in the action dictionary.",
                    rule_id="CLR_UNKNOWN_ACTION_001",
                    answer_mapping="canonicalAction",
                )
            )

        if any("multiple possible references" in warning for warning in fact.get("warnings", [])):
            questions.append(
                _clarification(
                    sequence=len(questions) + 1,
                    text=f"Which entity does the pronoun in “{source_clause}” refer to?",
                    fact=fact,
                    category="Pronoun Reference",
                    reason="A pronoun in this clause could point to more than one entity.",
                    rule_id="CLR_AMBIGUOUS_PRONOUN_001",
                    answer_mapping="object",
                )
            )

        nfr = fact.get("nfr")
        if nfr and not nfr.get("measurable"):
            category = str(nfr.get("category") or "quality")
            questions.append(
                _clarification(
                    sequence=len(questions) + 1,
                    text=f"What measurable {category.lower()} target should be used?",
                    fact=fact,
                    category="Vague Metric",
                    reason=f"A {category.lower()} keyword was found but no numeric target was given.",
                    rule_id="CLR_VAGUE_NFR_TARGET_001",
                    answer_mapping="nfrTarget",
                )
            )

        if (
            action
            and object_name
            and not re.search(r"\b\d", lowered)
            and any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in _VAGUE_QUANTITY_TERMS)
        ):
            questions.append(
                _clarification(
                    sequence=len(questions) + 1,
                    text=f"How many {object_name} are expected (give a number or range)?",
                    fact=fact,
                    category="Ambiguous Quantity",
                    reason="A vague quantifier was used instead of a concrete number.",
                    rule_id="CLR_VAGUE_QUANTIFIER_001",
                    answer_mapping="quantity",
                )
            )

        if not nfr and any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in _VAGUE_TIME_TERMS):
            questions.append(
                _clarification(
                    sequence=len(questions) + 1,
                    text="What is the exact timing or frequency this requires?",
                    fact=fact,
                    category="Vague Timing",
                    reason="A vague time or frequency word was used without a concrete value.",
                    rule_id="CLR_VAGUE_TIMING_001",
                    answer_mapping="temporalConstraint",
                )
            )

        key = (str(actor or ""), str(action or ""), str(object_name or ""))
        if all(key) and key in conflicting_keys and key not in seen_conflicts:
            seen_conflicts.add(key)
            questions.append(
                _clarification(
                    sequence=len(questions) + 1,
                    text=f"Can the {actor} {action} the {object_name} or not? The text says both.",
                    fact=fact,
                    category="Conflicting Rule",
                    reason="This actor/action/object is stated as both allowed and not allowed.",
                    rule_id="CLR_CONFLICTING_MODALITY_001",
                    answer_mapping="note",
                )
            )

    return questions


def analyze_text(raw_text: str) -> dict[str, Any]:
    normalized = normalize_text(raw_text)
    sentences = split_sentences(normalized["normalizedText"])
    clauses = split_clauses(sentences)
    facts = extract_facts(sentences, clauses)
    questions = generate_clarifications(facts)
    return {
        "dictionaryVersionId": DICTIONARY_VERSION,
        "ruleVersionId": RULE_VERSION,
        "normalization": normalized,
        "sentences": sentences,
        "clauses": clauses,
        "facts": facts,
        "clarificationQuestions": questions,
    }


def apply_answers(facts: list[dict[str, Any]], answers: list[dict[str, Any]], question_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    merged = deepcopy(facts)
    fact_lookup = {fact["id"]: fact for fact in merged}
    for answer in sorted(answers, key=lambda item: item.get("createdAt", "")):
        question = question_lookup.get(answer["questionStableId"])
        if not question or answer.get("status") in {"skipped", "not_applicable"}:
            continue
        fact = fact_lookup.get(question.get("sourceFactId"))
        if not fact:
            continue
        value = answer.get("answerText")
        slot = answer.get("appliedSlot") or question.get("answerMapping")
        if not value or not slot:
            continue
        if slot == "canonicalAction":
            fact["action"] = camel_case(value) if " " in value else value.strip()
        elif slot == "nfrTarget":
            fact.setdefault("nfr", {})["targetValue"] = value
            fact["nfr"]["measurable"] = True
            fact["nfr"]["warnings"] = []
        elif slot in {"actor", "object"}:
            fact[slot] = normalize_entity(value)
        else:
            fact[slot] = value.strip()
        if slot in fact.get("missingFields", []):
            fact["missingFields"] = [field for field in fact["missingFields"] if field != slot]
        fact["extractionType"] = "CLARIFICATION_ANSWER"
    return merged


def condition_to_text(condition: dict[str, Any] | None) -> str | None:
    if not condition:
        return None
    return " ".join(str(part) for part in [condition.get("subject"), condition.get("value")] if part)


def _business_narrative_story_sections(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn familiar business-language intents into reviewable user stories.

    These rules are intentionally dictionary-driven: product teams can extend the
    supported phrases without changing the parser or the downstream UML pipeline.
    """
    patterns = load_dictionaries().get("business_narrative_patterns", [])
    sections: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for sentence in sentences:
        source_sentence = str(sentence.get("text") or sentence.get("normalizedText") or "")
        for pattern in patterns:
            if not isinstance(pattern, dict):
                continue
            expression = pattern.get("pattern")
            actor = pattern.get("actor")
            action = pattern.get("action")
            object_name = pattern.get("object")
            want = pattern.get("want")
            goal = pattern.get("goal")
            if not all(isinstance(item, str) and item for item in [expression, actor, action, object_name, want, goal]):
                continue
            if not re.search(expression, source_sentence, flags=re.IGNORECASE):
                continue
            key = (actor, action, object_name)
            if key in seen:
                continue
            seen.add(key)
            index = len(sections) + 1
            sections.append(
                {
                    "id": f"US-001-S{index}",
                    "actor": actor,
                    "action": action,
                    "object": object_name,
                    "condition": None,
                    "trigger": None,
                    "quantity": None,
                    "modality": "should",
                    "negation": False,
                    "temporalConstraint": None,
                    "sentenceIndex": sentence.get("sentenceIndex"),
                    "normalizedSentence": f"As a {actor.lower()}, I want to {want}, so that {goal}.",
                    "sourceFactId": f"NAR-{index:03d}",
                    "sourceSentence": source_sentence,
                    "warnings": [],
                    "matchedRuleId": str(pattern.get("id") or "NAR_BUSINESS_INTENT_001"),
                }
            )
    return sections


def _indefinite_article(word: str | None) -> str:
    """"a"/"an" for a PascalCase noun, correcting the common consonant-sounding
    vowel-letter cases ("a User", "a Unit") so generated sentences read naturally."""
    lowered = (word or "").lower()
    if re.match(r"^(?:uni|use|eu|one)", lowered):
        return "a"
    return "an" if lowered[:1] in "aeiou" else "a"


def _fact_story_sections(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for fact in facts:
        actor = fact.get("actor")
        action = fact.get("action")
        object_name = fact.get("object")
        # A usable story needs an action plus at least one of actor / object; a
        # lone noun or a lone verb is not a requirement.
        if fact.get("nfr") is None and not (action and (actor or object_name)):
            continue
        index = len(sections) + 1
        actor_label = actor or "UnknownActor"
        action_label = action or "UnknownAction"
        object_label = object_name or "UnknownObject"
        condition = condition_to_text(fact.get("condition"))
        modal = {"obligation": "must", "negative": "cannot"}.get(str(fact.get("modality")), "can")
        object_article = _indefinite_article(object_label)
        sentence = f"The {actor_label} {modal} {action_label} {object_article} {object_label}."
        nfr = fact.get("nfr")
        if nfr:
            # An NFR's "action" is a metric name (responseTime), not a verb -
            # "The System must responseTime a Performance" is not a sentence.
            if nfr.get("measurable"):
                bound = " ".join(
                    str(part) for part in [nfr.get("operator") or "<=", nfr.get("targetValue"), nfr.get("unit")] if part
                )
                target = f" (target: {bound})"
            else:
                target = " (no measurable target yet)"
            sentence = (
                f"The system must meet the {str(nfr.get('category') or 'quality').lower()} requirement: "
                f"\"{str(fact.get('sourceText') or '').strip()}\"{target}."
            )
        elif condition:
            sentence = f"If {condition}, the {actor_label} {modal} {action_label} {object_article} {object_label}."
        sections.append(
            {
                "id": f"US-001-S{index}",
                "actor": actor_label,
                "action": action_label,
                "object": object_label,
                "condition": condition,
                "trigger": fact.get("trigger"),
                "quantity": fact.get("quantity"),
                "modality": fact.get("modality"),
                "negation": fact.get("negated"),
                "temporalConstraint": fact.get("temporalConstraint"),
                "sentenceIndex": fact.get("sentenceIndex"),
                "normalizedSentence": sentence,
                "sourceFactId": fact["id"],
                "sourceSentence": fact["sourceText"],
                "warnings": fact.get("warnings", [])
                + [f"{field} was not identified." for field in fact.get("missingFields", [])],
                "matchedRuleId": "FIN_ATOMIC_STORY_TEMPLATE_001",
            }
        )
    return sections


def generate_final_story(original_text: str, sentences: list[dict[str, Any]], facts: list[dict[str, Any]], answers: list[dict[str, Any]]) -> dict[str, Any]:
    # Per sentence: a curated business-narrative pattern (if it matches that
    # sentence) wins, because it is hand-tuned prose; every other sentence is
    # covered by the rule engine, which now understands stakeholder voice
    # directly (denarrate_clause). So a shop-story paragraph still reads well and
    # an arbitrary stakeholder document is no longer ignored.
    narrative_sections = _business_narrative_story_sections(sentences)
    covered = {section.get("sentenceIndex") for section in narrative_sections}
    fact_sections = [
        section for section in _fact_story_sections(facts) if section.get("sentenceIndex") not in covered
    ]

    merged = sorted(
        narrative_sections + fact_sections,
        key=lambda section: (section.get("sentenceIndex") or 0),
    )
    for index, section in enumerate(merged, start=1):
        section["id"] = f"US-001-S{index}"

    story_source = (
        "rule_facts"
        if not narrative_sections
        else "business_narrative" if not fact_sections else "mixed"
    )
    return {
        "originalText": original_text,
        "normalizedSentences": sentences,
        "atomicStorySections": merged,
        "appliedClarificationAnswers": answers,
        "unresolvedFields": sorted({field for fact in facts for field in fact.get("missingFields", [])}),
        "warnings": sorted({warning for section in merged for warning in section.get("warnings", [])}),
        "extractionMetadata": {
            "dictionaryVersionId": DICTIONARY_VERSION,
            "ruleVersionId": RULE_VERSION,
            "storySource": story_source,
        },
    }


def generate_requirements(final_story: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    fact_lookup = {fact["id"]: fact for fact in facts}
    fr_count = nfr_count = br_count = 0
    for section in final_story.get("atomicStorySections", []):
        fact = fact_lookup.get(section["sourceFactId"], {})
        if fact.get("nfr"):
            nfr_count += 1
            nfr = fact["nfr"]
            req_id = f"NFR-{nfr_count:03d}"
            target = f" within {nfr['targetValue']} {nfr['unit']}" if nfr.get("measurable") and isinstance(nfr.get("targetValue"), int) else ""
            requirements.append(
                {
                    "id": req_id,
                    "requirementId": req_id,
                    "requirementType": "non_functional",
                    "statement": f"The system shall satisfy {nfr['category'].lower()} expectations{target}.",
                    "sourceStorySectionId": section["id"],
                    "sourceSentence": section["sourceSentence"],
                    "matchedRuleId": nfr["matchedRuleId"],
                    "extractionMethod": "DICTIONARY_PATTERN",
                    "actor": fact.get("actor"),
                    "action": fact.get("action"),
                    "object": fact.get("object"),
                    "condition": section.get("condition"),
                    "nfrCategory": nfr["category"],
                    "metric": nfr.get("metric"),
                    "operator": nfr.get("operator"),
                    "targetValue": nfr.get("targetValue"),
                    "unit": nfr.get("unit"),
                    "measurable": nfr.get("measurable"),
                    "warnings": nfr.get("warnings", []),
                    "enabled": True,
                }
            )
            continue

        actor = section.get("actor") or "UnknownActor"
        action = section.get("action") or "UnknownAction"
        object_name = section.get("object") or "UnknownObject"
        fr_count += 1
        req_id = f"FR-{fr_count:03d}"
        condition = section.get("condition")
        if actor == "System":
            # "The system shall allow the System to generate the Invoice" is
            # nonsensical - the system doesn't need its own permission to act.
            core = f"the system shall {action} the {object_name}"
        else:
            actor_phrase = "an unspecified actor" if actor == "UnknownActor" else f"the {actor}"
            core = f"the system shall allow {actor_phrase} to {action} the {object_name}"
        statement = f"{core[0].upper()}{core[1:]}."
        if condition:
            statement = f"If {condition}, {core}."
        requirements.append(
            {
                "id": req_id,
                "requirementId": req_id,
                "requirementType": "functional",
                "statement": statement,
                "sourceStorySectionId": section["id"],
                "sourceSentence": section["sourceSentence"],
                "matchedRuleId": "FR_CONDITIONAL_ACTOR_ACTION_OBJECT_001" if condition else "FR_ACTOR_ACTION_OBJECT_001",
                "extractionMethod": fact.get("extractionType", "UNCLASSIFIED"),
                "actor": actor,
                "action": action,
                "rawAction": fact.get("rawAction"),
                "object": object_name,
                "condition": condition,
                "nfrCategory": None,
                "metric": None,
                "targetValue": None,
                "warnings": section.get("warnings", []),
                "enabled": True,
            }
        )
        source = " ".join([section.get("sourceSentence", ""), str(condition or "")]).lower()
        if any(keyword in source for keyword in ["only", "cannot", "must not", "at least", "at most", "exactly", "before", "after", "unless", "contain", "own"]):
            br_count += 1
            br_id = f"BR-{br_count:03d}"
            if "only" in source:
                br_statement = f"Only the {actor} may {action} the {object_name}."
                rule_id = "BR_ONLY_ACTOR_ACTION_OBJECT_001"
            elif "contain" in source or "own" in source:
                br_statement = f"The {actor} must maintain the required {object_name} relationship."
                rule_id = "BR_MANDATORY_CONTAINMENT_001"
            else:
                br_statement = f"The {actor} is constrained when attempting to {action} the {object_name}."
                rule_id = "BR_CONSTRAINT_KEYWORD_001"
            requirements.append(
                {
                    "id": br_id,
                    "requirementId": br_id,
                    "requirementType": "business_rule",
                    "statement": br_statement,
                    "sourceStorySectionId": section["id"],
                    "sourceSentence": section["sourceSentence"],
                    "matchedRuleId": rule_id,
                    "extractionMethod": "DICTIONARY_PATTERN",
                    "actor": actor,
                    "action": action,
                    "rawAction": fact.get("rawAction"),
                    "object": object_name,
                    "condition": condition,
                    "nfrCategory": None,
                    "metric": None,
                    "targetValue": fact.get("targetMultiplicity"),
                    "warnings": [],
                    "enabled": True,
                }
            )
    return {"requirements": requirements, "dictionaryVersionId": DICTIONARY_VERSION, "ruleVersionId": RULE_VERSION}


def verb_lemma(raw_verb: str | None) -> str | None:
    """Base form of the verb exactly as the author wrote it ("removes" ->
    "remove"). Unlike _canonical_action it does not map synonyms onto one
    canonical verb, so a class diagram keeps the author's vocabulary
    (removeBook, not deleteBook)."""
    if not raw_verb:
        return None
    lowered = re.sub(r"\s+", " ", raw_verb.strip().lower())
    if not lowered:
        return None
    irregular = {str(k).lower(): str(v).lower() for k, v in load_dictionaries().get("irregular_verbs", {}).items()}
    if lowered in irregular:
        return irregular[lowered]
    aliases = _action_aliases()
    if lowered in aliases and not re.search(r"(?:ing|ed|s)$", lowered):
        return lowered
    for candidate in _regular_verb_bases(lowered):
        if candidate in aliases:
            return candidate
    base = common_verb_base(lowered)
    if base:
        return base
    if " " not in lowered:
        if re.search(r"[^aeiou]ie[sd]$", lowered):
            return lowered[:-3] + "y"
        if re.search(r"(?:ch|sh|x|ss|z)es$", lowered):
            return lowered[:-2]
        if lowered.endswith("s") and not lowered.endswith(("ss", "us", "is")) and len(lowered) > 3:
            return lowered[:-1]
    return lowered


_DOMAIN_RE = re.compile(
    r"\b(?P<domain>[a-z][a-z]+(?:\s+[a-z][a-z]+)?)\s+(?:management\s+|information\s+|booking\s+|reservation\s+)?"
    r"(?:system|application|app|platform|portal|software|website)\b",
    flags=re.IGNORECASE,
)
_NOT_A_DOMAIN = {"the", "a", "an", "this", "our", "my", "your", "their", "whole", "entire", "new", "online", "web", "management"}


def domain_words(texts: list[str]) -> set[str]:
    """The domain the text names itself after: "a library management system"
    -> {"library"}. A class name that merely prefixes this word ("library
    member") names the same thing as its head ("member")."""
    found: set[str] = set()
    for text in texts:
        for match in _DOMAIN_RE.finditer(text or ""):
            words = [word for word in match.group("domain").lower().split() if word not in _NOT_A_DOMAIN]
            if words:
                found.add(words[-1])
                found.add(singularize(words[-1]).lower())
    return found


def _pascal_words(name: str) -> list[str]:
    return re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", name)


def class_alias_map(
    names: list[str],
    sentences: dict[str, set[str]],
    domains: set[str],
    first_seen: dict[str, int] | None = None,
    protected: set[str] | frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Merge compound class names that are just a longer spelling of another
    class ("LibraryMember" -> "Member"), the way a person reading the text
    treats "a library member ... the member" as one entity.

    A compound "<Modifier><Head>" merges into "<Head>" when
    - the modifier is the system's own domain word ("library" in a library
      management system), or
    - it is the only compound built on that head, the modifier is not itself a
      class, the two spellings never appear in the same sentence (writers
      switch from "library member" to "member"; they don't contrast them), the
      compound is introduced first (the short form refers back to it - a
      compound that appears only after the head, like "a librarian is a kind of
      staff member" after "a member can borrow", defines a new concept), and
      the compound is not being defined in a hierarchy (`protected`).
    Several compounds on one head ("staff member", "library member") are
    distinct kinds, so none of them merge except through the domain rule.
    """
    name_set = set(names)
    by_head: dict[str, list[tuple[str, str]]] = {}
    for name in names:
        words = _pascal_words(name)
        for split in range(1, len(words)):
            head = "".join(words[split:])
            if head in name_set:
                modifier = " ".join(words[:split]).lower()
                by_head.setdefault(head, []).append((name, modifier))
                break
    aliases: dict[str, str] = {}
    for head, compounds in by_head.items():
        for name, modifier in compounds:
            if modifier in domains:
                aliases[name] = head
                continue
            if len(compounds) != 1:
                continue
            if pascal_case(modifier) in name_set:
                continue
            if sentences.get(name, set()) & sentences.get(head, set()):
                continue
            if name in protected:
                continue
            if first_seen and first_seen.get(name, 0) > first_seen.get(head, 0):
                continue
            aliases[name] = head
    return aliases


def _requirement_source_ids(requirements: list[dict[str, Any]], actor: str, object_name: str) -> list[str]:
    return sorted(
        {
            req["requirementId"]
            for req in requirements
            if req.get("enabled", True) and (req.get("actor") == actor or req.get("object") == object_name)
        }
    )


def _attribute_lexicon() -> tuple[set[str], dict[str, dict[str, str]], dict[str, str]]:
    dictionaries = load_dictionaries()
    primitives = {item.lower() for item in dictionaries.get("primitive_attributes", [])}
    phrases = {
        str(key).lower(): value
        for key, value in dictionaries.get("attribute_phrases", {}).items()
        if isinstance(value, dict) and value.get("name")
    }
    hints = {key.lower(): str(value) for key, value in dictionaries.get("data_type_hints", {}).items()}
    return primitives, phrases, hints


def _attribute_name_forms() -> set[str]:
    """snake_case of every token / phrase that names a field, not a class."""
    primitives, phrases, _ = _attribute_lexicon()
    forms = {snake_case(word) for word in primitives}
    for key, spec in phrases.items():
        forms.add(snake_case(key))
        forms.add(snake_case(str(spec.get("name", ""))))
    forms.discard("")
    return forms


def _is_attribute_like(name: str | None) -> bool:
    """True when a candidate class name is really a primitive field / data phrase."""
    if not name:
        return False
    snake = snake_case(name)
    if snake in _attribute_name_forms():
        return True
    primitives, _, _ = _attribute_lexicon()
    tail = snake.split("_")[-1]
    return tail in primitives or singularize(tail) in primitives


_POSSESSION_RE = re.compile(
    r"\b(?:has|have|having|had|contains?|containing|includes?|including|holds?|"
    r"stores?|records?|tracks?|comprising|consisting of|with the following|with)\b",
    flags=re.IGNORECASE,
)
_ATTRIBUTE_CHUNK_NOISE = re.compile(
    r"^(?:an?|the|its|their|his|her|our|your|each|every|some|one|a valid|a unique|"
    r"a required|an optional|following|fields?|attributes?|details?|properties)\s+",
    flags=re.IGNORECASE,
)


def _attributes_for_sentences(sentences: list[str]) -> list[dict[str, Any]]:
    """Pull known attribute phrases (e.g. "phone number", "due date") out of prose."""
    blob = " ".join(sentences).lower()
    _, attribute_phrases, _ = _attribute_lexicon()
    found: dict[str, dict[str, Any]] = {}
    for phrase, spec in attribute_phrases.items():
        if re.search(rf"\b{re.escape(phrase)}\b", blob):
            found[spec["name"]] = {
                "id": f"attr_{snake_case(spec['name'])}",
                "name": spec["name"],
                "type": spec.get("type", "String"),
                "visibility": "private",
                "sourceRuleId": "ATTR_PHRASE_DICTIONARY_001",
            }
    return sorted(found.values(), key=lambda item: item["name"].lower())


def _attributes_for_class(name: str, sentences: list[str]) -> list[dict[str, Any]]:
    """Given an already-confirmed class name, mine ITS evidence sentences for fields.

    Two sources: (1) any known multi-word attribute phrase in an evidence
    sentence; (2) bare primitive nouns, but only inside a possession list that
    this class itself opens ("a member has a name, an email and a join date").
    """
    primitives, phrases, hints = _attribute_lexicon()
    found: dict[str, dict[str, Any]] = {}

    def _record(attr_name: str, attr_type: str, rule_id: str) -> None:
        if attr_name and attr_name not in found:
            found[attr_name] = {
                "id": f"attr_{snake_case(attr_name)}",
                "name": attr_name,
                "type": attr_type,
                "visibility": "private",
                "sourceRuleId": rule_id,
            }

    name_tokens = set(re.findall(r"[a-z]+", name.lower()))
    for sentence in sentences:
        lowered = sentence.lower()
        for phrase, spec in phrases.items():
            if re.search(rf"\b{re.escape(phrase)}\b", lowered):
                _record(spec["name"], spec.get("type", "String"), "ATTR_PHRASE_DICTIONARY_001")
        match = _POSSESSION_RE.search(lowered)
        if not match:
            continue
        head = set(re.findall(r"[a-z]+", lowered[: match.start()]))
        if name_tokens and not (name_tokens & head):
            continue
        tail = re.split(
            r"[.?!;:]|\bso that\b|\bbecause\b|\bin order to\b|\bwhen\b|\bwhere\b",
            lowered[match.end():],
        )[0]
        for raw_chunk in re.split(r"\s*,\s*|\s+and\s+|\s+or\s+", tail):
            chunk = _ATTRIBUTE_CHUNK_NOISE.sub("", raw_chunk.strip()).strip()
            words = re.findall(r"[a-z]+", chunk)
            if not words or len(words) > 3:
                continue
            phrase_key = " ".join(words)
            if phrase_key in phrases:
                spec = phrases[phrase_key]
                _record(spec["name"], spec.get("type", "String"), "ATTR_PHRASE_DICTIONARY_001")
                continue
            last = words[-1]
            head_word = last if last in primitives else singularize(last) if singularize(last) in primitives else None
            if head_word:
                attr_name = camel_case(phrase_key) if len(words) > 1 else head_word
                _record(attr_name, hints.get(head_word, "String"), "ATTR_PRIMITIVE_NOUN_001")
    return sorted(found.values(), key=lambda item: item["name"].lower())


def _attribute_record_for(name: str) -> dict[str, Any] | None:
    """Build one attribute record from a noun already known to be attribute-like.

    Rejects mangled multi-noun phrases (e.g. "TitleAnIsbn" from a botched list
    normalisation) — only a known phrase or a short "<modifier> <primitive>"
    form is accepted.
    """
    primitives, phrases, hints = _attribute_lexicon()
    parts = [part for part in snake_case(name).split("_") if part]
    if parts and parts[0] in {"a", "an", "the"}:
        parts = parts[1:]
    if not parts:
        return None
    spaced = " ".join(parts)
    if spaced in phrases:
        spec = phrases[spaced]
        return {
            "id": f"attr_{snake_case(spec['name'])}",
            "name": spec["name"],
            "type": spec.get("type", "String"),
            "visibility": "private",
            "sourceRuleId": "ATTR_PHRASE_DICTIONARY_001",
        }
    tail = parts[-1]
    head = singularize(tail)
    key = head if head in primitives else tail if tail in primitives else None
    if key is None or len(parts) > 2:
        return None
    attr_name = camel_case(spaced) if len(parts) > 1 else key
    return {
        "id": f"attr_{snake_case(attr_name)}",
        "name": attr_name,
        "type": hints.get(key, "String"),
        "visibility": "private",
        "sourceRuleId": "ATTR_PRIMITIVE_NOUN_001",
    }


def _merge_attribute(cls: dict[str, Any], name: str) -> None:
    record = _attribute_record_for(name)
    if record and all(existing["name"] != record["name"] for existing in cls["attributes"]):
        cls["attributes"] = sorted(
            cls["attributes"] + [record], key=lambda item: item["name"].lower()
        )


def _apply_class_aliases(
    requirements: list[dict[str, Any]], facts: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    names: list[str] = []
    mentions: dict[str, set[str]] = {}
    first_seen: dict[str, int] = {}
    texts: list[str] = []
    for item in [*facts, *requirements]:
        sentence = str(item.get("sourceSentenceText") or item.get("sourceSentence") or item.get("sourceText") or "")
        texts.append(sentence)
        for field in ("actor", "object"):
            value = item.get(field)
            if value and not str(value).startswith("Unknown"):
                if value not in names:
                    names.append(value)
                mentions.setdefault(value, set()).add(sentence)
                if item.get("sentenceIndex") is not None:
                    first_seen[value] = min(first_seen.get(value, 10**6), int(item["sentenceIndex"]))
    aliases = class_alias_map(names, mentions, domain_words(texts), first_seen=first_seen)
    if not aliases:
        return requirements, facts, {}

    def _remap(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        remapped = []
        for item in items:
            copy = dict(item)
            for field in ("actor", "object"):
                if copy.get(field) in aliases:
                    copy[field] = aliases[copy[field]]
            remapped.append(copy)
        return remapped

    return _remap(requirements), _remap(facts), aliases


def generate_class_model(requirements: list[dict[str, Any]], facts: list[dict[str, Any]], threshold: int = 4) -> dict[str, Any]:
    requirements, facts, class_aliases = _apply_class_aliases(requirements, facts)
    scores: Counter[str] = Counter()
    source_fact_ids: dict[str, set[str]] = {}
    source_requirement_ids: dict[str, set[str]] = {}
    entity_sentences: dict[str, set[str]] = {}

    def _remember_sentence(name: str, text: str | None) -> None:
        if name and text:
            entity_sentences.setdefault(name, set()).add(text)

    for fact in facts:
        for field, score in [("actor", 5), ("object", 4)]:
            value = fact.get(field)
            if value and not value.startswith("Unknown"):
                scores[value] += score
                source_fact_ids.setdefault(value, set()).add(fact["id"])
                _remember_sentence(value, fact.get("sourceSentenceText") or fact.get("sourceText"))
        if fact.get("relationshipType"):
            for field in ["actor", "object"]:
                value = fact.get(field)
                if value:
                    scores[value] += 4
    for requirement in requirements:
        if not requirement.get("enabled", True) or requirement.get("requirementType") == "non_functional":
            continue
        for field, score in [("actor", 5), ("object", 4)]:
            value = requirement.get(field)
            if value and not value.startswith("Unknown"):
                scores[value] += score
                source_requirement_ids.setdefault(value, set()).add(requirement["requirementId"])
                _remember_sentence(value, requirement.get("sourceSentence"))
    primitive = {item.lower() for item in load_dictionaries().get("primitive_attributes", [])}
    generic = {item.lower() for item in load_dictionaries().get("generic_nouns", [])}
    pronoun_words = {
        word.lower()
        for group in load_dictionaries().get("pronouns", {}).values()
        for word in group
    }
    state_words = {item.lower() for item in load_dictionaries().get("state_words", [])}
    for name in list(scores):
        lowered = name.lower()
        # A primitive field / data phrase is never a class, no matter how often
        # it is mentioned — it will be folded into its owner as an attribute.
        if _is_attribute_like(name):
            del scores[name]
            continue
        if lowered in primitive:
            scores[name] -= 5
        if lowered in generic:
            scores[name] -= 4
        if lowered in pronoun_words or lowered in state_words:
            scores[name] -= 6
    class_names = sorted(name for name, score in scores.items() if score >= threshold)

    classes: dict[str, dict[str, Any]] = {}
    for name in class_names:
        class_id = f"class_{snake_case(name)}"
        source_ids = sorted(source_requirement_ids.get(name, set()) | set(_requirement_source_ids(requirements, name, name)))
        classes[class_id] = {
            "id": class_id,
            "name": name,
            "stereotype": "entity" if name != "System" else "service",
            "attributes": _attributes_for_class(name, sorted(entity_sentences.get(name, set()))),
            "methods": [],
            "sourceFactIds": sorted(source_fact_ids.get(name, set())),
            "sourceRequirementIds": source_ids,
            "warnings": [],
            "enabled": True,
        }

    fact_by_clause = {fact.get("sourceText"): fact for fact in facts}
    method_signatures: set[tuple[str, str]] = set()
    relationships = []
    for requirement in requirements:
        if not requirement.get("enabled", True) or requirement.get("requirementType") == "non_functional":
            continue
        actor = requirement.get("actor")
        object_name = requirement.get("object")
        action = requirement.get("action")
        if not actor or not object_name or actor.startswith("Unknown") or object_name.startswith("Unknown"):
            continue
        source_id = f"class_{snake_case(actor)}"
        target_id = f"class_{snake_case(object_name)}"
        # "X has a due date" — the target is a field, so record it on X instead
        # of inventing a DueDate class + edge.
        if source_id in classes and target_id not in classes and _is_attribute_like(object_name):
            _merge_attribute(classes[source_id], object_name)
            continue
        if source_id not in classes or target_id not in classes:
            continue

        # Name the behaviour with the author's own verb ("remove", not the
        # canonical "delete") unless a clarification answer replaced the action.
        raw_verb = verb_lemma(requirement.get("rawAction"))
        verb = raw_verb if raw_verb and _canonical_action(raw_verb)[0] == action else action
        # Behaviour on the acting class, taking the acted-upon object:
        # "librarian.approveRequest(request: Request)".
        actor_method = camel_case(f"{verb} {object_name}")
        if (source_id, actor_method) not in method_signatures:
            method_signatures.add((source_id, actor_method))
            classes[source_id]["methods"].append(
                {
                    "id": f"method_{snake_case(actor)}_{snake_case(actor_method)}",
                    "name": actor_method,
                    "parameters": [{"name": camel_case(object_name), "type": object_name}]
                    if source_id != target_id
                    else [],
                    "returnType": "void",
                    "visibility": "public",
                    "static": False,
                    "sourceRequirementIds": [requirement["requirementId"]],
                }
            )
        # Lifecycle behaviour on the acted-upon class so entities are not empty shells.
        target_method = camel_case(verb or "handle")
        if (target_id, target_method) not in method_signatures:
            method_signatures.add((target_id, target_method))
            classes[target_id]["methods"].append(
                {
                    "id": f"method_{snake_case(object_name)}_{snake_case(target_method)}",
                    "name": target_method,
                    "parameters": [],
                    "returnType": "void",
                    "visibility": "public",
                    "static": False,
                    "sourceRequirementIds": [requirement["requirementId"]],
                }
            )

        fact = fact_by_clause.get(requirement.get("sourceSentence")) or {}
        rel_type = normalize_relationship_type(fact.get("relationshipType") or "association") or "association"
        if rel_type in CARDINALITY_RELATIONSHIP_TYPES:
            source_multiplicity = fact.get("sourceMultiplicity") or "1"
            target_multiplicity = fact.get("targetMultiplicity") or "0..*"
            warnings = [] if fact.get("targetMultiplicity") else ["Default multiplicity applied."]
        else:
            source_multiplicity = None
            target_multiplicity = None
            warnings = []
        relationships.append(
            {
                "id": f"edge_{snake_case(actor)}_{snake_case(verb or 'uses')}_{snake_case(object_name)}",
                "sourceClassId": source_id,
                "targetClassId": target_id,
                "type": rel_type,
                "label": verb or "uses",
                "sourceMultiplicity": source_multiplicity,
                "targetMultiplicity": target_multiplicity,
                "direction": "source-to-target",
                "sourceRequirementIds": [requirement["requirementId"]],
                "warnings": warnings,
                "enabled": True,
            }
        )

    # Rule: a noun only becomes a class if it has behaviour (at least one method)
    # or state (at least one attribute). A bare noun that is merely mentioned or
    # merely linked is inert — drop it and any dangling edges.
    kept_ids = {
        class_id
        for class_id, cls in classes.items()
        if cls["methods"] or cls["attributes"]
    }
    dropped = sorted(classes[class_id]["name"] for class_id in classes if class_id not in kept_ids)
    classes = {class_id: cls for class_id, cls in classes.items() if class_id in kept_ids}
    relationships = [
        rel
        for rel in relationships
        if rel["sourceClassId"] in kept_ids and rel["targetClassId"] in kept_ids
    ]

    model: dict[str, Any] = {
        "classes": sorted(classes.values(), key=lambda item: item["name"].lower()),
        "relationships": _dedupe_relationships(relationships),
        "enums": [],
        "constraints": [],
        "dictionaryVersionId": DICTIONARY_VERSION,
        "ruleVersionId": RULE_VERSION,
    }
    if dropped:
        model["eliminatedClasses"] = dropped
    if class_aliases:
        model["mergedClasses"] = dict(sorted(class_aliases.items()))
    return model


def _dedupe_relationships(relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for relationship in sorted(
        relationships,
        key=lambda item: (item["sourceClassId"], item["targetClassId"], item["type"], item["label"]),
    ):
        key = (relationship["sourceClassId"], relationship["targetClassId"], relationship["type"], relationship["label"])
        if key in grouped:
            grouped[key]["sourceRequirementIds"] = sorted(
                set(grouped[key]["sourceRequirementIds"]) | set(relationship["sourceRequirementIds"])
            )
        else:
            grouped[key] = relationship
    return list(grouped.values())


def validate_class_model(class_model: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    class_ids: set[str] = set()
    disabled_class_ids: set[str] = set()
    for item in class_model.get("classes", []):
        if not isinstance(item, dict):
            continue
        class_id = str(item.get("id") or "").strip()
        if not item.get("enabled", True):
            if class_id:
                disabled_class_ids.add(class_id)
            continue
        if not class_id:
            errors.append("Enabled class is missing an ID.")
        elif class_id in class_ids:
            errors.append(f"Duplicate class ID: {class_id}.")
        else:
            class_ids.add(class_id)

    relationship_ids: set[str] = set()
    inheritance_graph: dict[str, set[str]] = {}
    for relationship in class_model.get("relationships", []):
        if not isinstance(relationship, dict) or not relationship.get("enabled", True):
            continue

        # A relationship whose endpoint the user has excluded is inert, not an
        # error — skip it the same way a disabled relationship is skipped.
        source_id = relationship.get("sourceClassId")
        target_id = relationship.get("targetClassId")
        if source_id in disabled_class_ids or target_id in disabled_class_ids:
            continue

        relationship_id = str(relationship.get("id") or "").strip()
        if not relationship_id:
            errors.append("Enabled relationship is missing an ID.")
            relationship_id = "<missing>"
        elif relationship_id in relationship_ids or relationship_id in class_ids:
            errors.append(f"Duplicate diagram element ID: {relationship_id}.")
        else:
            relationship_ids.add(relationship_id)

        if source_id not in class_ids:
            errors.append(f"Relationship {relationship_id} source class is missing or disabled.")
        if target_id not in class_ids:
            errors.append(f"Relationship {relationship_id} target class is missing or disabled.")

        canonical_type = normalize_relationship_type(relationship.get("type"))
        if canonical_type is None:
            errors.append(
                f"Relationship {relationship_id} has unsupported type: {relationship.get('type')}."
            )
        direction = normalize_association_direction(relationship.get("direction"))
        if direction is None:
            errors.append(
                f"Relationship {relationship_id} has invalid direction: {relationship.get('direction')}."
            )

        if canonical_type in CARDINALITY_RELATIONSHIP_TYPES:
            for field in ("sourceMultiplicity", "targetMultiplicity"):
                multiplicity = relationship.get(field)
                if multiplicity is not None and not MULTIPLICITY_PATTERN.fullmatch(str(multiplicity).strip()):
                    errors.append(
                        f"Relationship {relationship_id} has invalid {field}: {multiplicity}."
                    )
        if canonical_type in {"inheritance", "realization"} and source_id == target_id:
            errors.append(f"Relationship {relationship_id} cannot target the same class it starts from.")
        if canonical_type == "inheritance" and source_id in class_ids and target_id in class_ids:
            inheritance_graph.setdefault(str(source_id), set()).add(str(target_id))

    visiting: set[str] = set()
    visited: set[str] = set()

    def has_inheritance_cycle(class_id: str) -> bool:
        if class_id in visiting:
            return True
        if class_id in visited:
            return False
        visiting.add(class_id)
        if any(has_inheritance_cycle(parent_id) for parent_id in inheritance_graph.get(class_id, set())):
            return True
        visiting.remove(class_id)
        visited.add(class_id)
        return False

    if any(has_inheritance_cycle(class_id) for class_id in sorted(inheritance_graph)):
        errors.append("Inheritance relationships contain a cycle.")
    return {"valid": not errors, "errors": errors, "matchedRuleId": "VAL_CLASS_MODEL_REFERENCES_001"}


def _drawio_graph_model() -> ET.Element:
    return ET.Element(
        "mxGraphModel",
        {
            "dx": "1422",
            "dy": "794",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "1169",
            "pageHeight": "827",
            "math": "0",
            "shadow": "0",
        },
    )


def _class_header(cls: dict[str, Any]) -> str:
    name = escape(str(cls.get("name", "")))
    stereotype = str(cls.get("stereotype") or "")
    if stereotype in {"enumeration", "interface", "abstract"}:
        return f"«{stereotype}» {name}"
    return name


def _attribute_row(attr: dict[str, Any], is_enum: bool = False) -> str:
    if is_enum:
        return escape(str(attr.get("name", "")))
    visibility = {"public": "+", "protected": "#", "package": "~"}.get(str(attr.get("visibility") or ""), "-")
    return f"{visibility} {escape(str(attr['name']))}: {escape(str(attr.get('type') or 'String'))}"


def _method_row(method: dict[str, Any]) -> str:
    parameters = []
    for parameter in method.get("parameters") or []:
        if isinstance(parameter, dict) and parameter.get("name"):
            kind = parameter.get("type")
            parameters.append(f"{parameter['name']}: {kind}" if kind else str(parameter["name"]))
        elif isinstance(parameter, str) and parameter.strip():
            parameters.append(parameter.strip())
    visibility = {"private": "-", "protected": "#", "package": "~"}.get(str(method.get("visibility") or ""), "+")
    return (
        f"{visibility} {escape(str(method['name']))}({escape(', '.join(parameters))}): "
        f"{escape(str(method.get('returnType') or 'void'))}"
    )


def generate_drawio_xml(class_model: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    validation = validate_class_model(class_model)
    if not validation["valid"]:
        return "", validation

    root = ET.Element("mxfile", {"host": "app.diagrams.net", "type": "device"})
    diagram = ET.SubElement(root, "diagram", {"id": "class-diagram", "name": "Class Diagram"})
    graph = _drawio_graph_model()
    diagram.append(graph)
    graph_root = ET.SubElement(graph, "root")
    ET.SubElement(graph_root, "mxCell", {"id": "0"})
    ET.SubElement(graph_root, "mxCell", {"id": "1", "parent": "0"})

    classes = sorted(
        [item for item in class_model.get("classes", []) if item.get("enabled", True)],
        key=lambda item: str(item.get("name", "")).lower(),
    )
    id_set = {"0", "1"}
    layout = {
        "columns": 3,
        "startX": 80,
        "startY": 80,
        "horizontalGap": 340,
        "verticalGap": 260,
        "classWidth": 240,
        "headerHeight": 32,
        "rowHeight": 22,
        "dividerHeight": 8,
        "minimumClassHeight": 100,
    }

    for index, cls in enumerate(classes):
        attributes = sorted(cls.get("attributes", []), key=lambda item: item.get("name", "").lower())
        methods = sorted(cls.get("methods", []), key=lambda item: (item.get("name", "").lower(), str(item.get("parameters", []))))
        is_enum = cls.get("stereotype") == "enumeration"
        attribute_rows = [_attribute_row(attr, is_enum) for attr in attributes]
        method_rows = [_method_row(method) for method in methods]
        attribute_section_height = max(len(attribute_rows), 1) * layout["rowHeight"]
        method_section_height = max(len(method_rows), 1) * layout["rowHeight"]
        height = max(
            layout["headerHeight"] + attribute_section_height + method_section_height + layout["dividerHeight"],
            layout["minimumClassHeight"],
        )
        class_id = cls["id"]
        id_set.add(class_id)
        cell = ET.SubElement(
            graph_root,
            "mxCell",
            {
                "id": class_id,
                "value": _class_header(cls),
                "style": "swimlane;fontStyle=1;align=center;verticalAlign=top;childLayout=stackLayout;horizontal=1;startSize=32;horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;collapsible=0;marginBottom=0;rounded=0;whiteSpace=wrap;html=1;",
                "vertex": "1",
                "parent": "1",
            },
        )
        column = index % layout["columns"]
        row = index // layout["columns"]
        ET.SubElement(
            cell,
            "mxGeometry",
            {
                "x": str(layout["startX"] + column * layout["horizontalGap"]),
                "y": str(layout["startY"] + row * layout["verticalGap"]),
                "width": str(layout["classWidth"]),
                "height": str(height),
                "as": "geometry",
            },
        )
        for section_name, y_offset, rows, section_height in [
            ("attributes", layout["headerHeight"], attribute_rows or [" "], attribute_section_height),
            (
                "methods",
                layout["headerHeight"] + attribute_section_height + layout["dividerHeight"],
                method_rows or [" "],
                method_section_height,
            ),
        ]:
            section_id = f"{class_id}_{section_name}"
            id_set.add(section_id)
            section = ET.SubElement(
                graph_root,
                "mxCell",
                {
                    "id": section_id,
                    "value": "<br>".join(rows),
                    "style": "text;strokeColor=none;fillColor=none;align=left;verticalAlign=top;spacingLeft=8;spacingRight=8;overflow=hidden;rotatable=0;whiteSpace=wrap;html=1;",
                    "vertex": "1",
                    "parent": class_id,
                },
            )
            ET.SubElement(
                section,
                "mxGeometry",
                {
                    "x": "0",
                    "y": str(y_offset),
                    "width": str(layout["classWidth"]),
                    "height": str(section_height),
                    "as": "geometry",
                },
            )

    rendered_class_ids = {str(cls["id"]) for cls in classes}
    relationships = sorted(
        [
            item
            for item in class_model.get("relationships", [])
            if item.get("enabled", True)
            and str(item.get("sourceClassId", "")) in rendered_class_ids
            and str(item.get("targetClassId", "")) in rendered_class_ids
        ],
        key=lambda item: (
            str(item.get("sourceClassId", "")),
            str(item.get("targetClassId", "")),
            str(item.get("type", "")),
            str(item.get("label", "")),
        ),
    )
    edge_counts: Counter[str] = Counter()
    for relationship in relationships:
        base_id = relationship["id"]
        edge_counts[base_id] += 1
        edge_id = base_id if edge_counts[base_id] == 1 else f"{base_id}_{edge_counts[base_id]:03d}"
        id_set.add(edge_id)
        relationship_type = normalize_relationship_type(relationship.get("type"))
        assert relationship_type is not None
        direction = normalize_association_direction(relationship.get("direction")) or "undirected"
        edge = ET.SubElement(
            graph_root,
            "mxCell",
            {
                "id": edge_id,
                "value": relationship.get("label", ""),
                "style": relationship_drawio_style(relationship_type, direction),
                "edge": "1",
                "parent": "1",
                "source": relationship["sourceClassId"],
                "target": relationship["targetClassId"],
            },
        )
        ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})
        if relationship_type in CARDINALITY_RELATIONSHIP_TYPES:
            for suffix, field, position in (
                ("source_multiplicity", "sourceMultiplicity", "-0.85"),
                ("target_multiplicity", "targetMultiplicity", "0.85"),
            ):
                value = relationship.get(field)
                if value is None:
                    continue
                label_id = f"{edge_id}_{suffix}"
                id_set.add(label_id)
                label = ET.SubElement(
                    graph_root,
                    "mxCell",
                    {
                        "id": label_id,
                        "value": str(value),
                        "style": "edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];",
                        "vertex": "1",
                        "connectable": "0",
                        "parent": edge_id,
                    },
                )
                geometry = ET.SubElement(
                    label,
                    "mxGeometry",
                    {"x": position, "relative": "1", "as": "geometry"},
                )
                ET.SubElement(geometry, "mxPoint", {"as": "offset"})

    xml_text = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    xml_validation = validate_drawio_xml(xml_text, class_model)
    return xml_text, xml_validation


def validate_drawio_xml(xml_text: str, class_model: dict[str, Any] | None = None) -> dict[str, Any]:
    errors = []
    try:
        parsed = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return {"valid": False, "errors": [str(exc)], "matchedRuleId": "VAL_XML_WELL_FORMED_001"}

    ids = []
    for cell in parsed.findall(".//mxCell"):
        cell_id = cell.attrib.get("id")
        if cell_id:
            ids.append(cell_id)
        if cell.attrib.get("vertex") == "1" and cell.find("mxGeometry") is None:
            errors.append(f"Class cell {cell_id} has no geometry.")
        if cell.attrib.get("edge") == "1":
            geometry = cell.find("mxGeometry")
            if geometry is None or geometry.attrib.get("relative") != "1":
                errors.append(f"Edge cell {cell_id} has no relative geometry.")
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"Duplicate XML IDs: {', '.join(duplicates)}")

    if class_model:
        model_validation = validate_class_model(class_model)
        errors.extend(model_validation["errors"])
        class_ids = {item["id"] for item in class_model.get("classes", []) if item.get("enabled", True)}
        for edge in parsed.findall(".//mxCell[@edge='1']"):
            if edge.attrib.get("source") not in class_ids:
                errors.append(f"Edge {edge.attrib.get('id')} source points to a missing or disabled class.")
            if edge.attrib.get("target") not in class_ids:
                errors.append(f"Edge {edge.attrib.get('id')} target points to a missing or disabled class.")
        for relationship in class_model.get("relationships", []):
            if not relationship.get("enabled", True):
                continue
            # Edges to an excluded class are intentionally left out of the XML.
            if (
                relationship.get("sourceClassId") not in class_ids
                or relationship.get("targetClassId") not in class_ids
            ):
                continue
            relationship_id = relationship.get("id")
            edge = parsed.find(f".//mxCell[@id='{relationship_id}'][@edge='1']")
            if edge is None:
                errors.append(f"Relationship {relationship_id} has no XML edge.")
                continue
            relationship_type = normalize_relationship_type(relationship.get("type"))
            direction = normalize_association_direction(relationship.get("direction"))
            if relationship_type is None or direction is None:
                continue
            expected_style = relationship_drawio_style(relationship_type, direction)
            if edge.attrib.get("style") != expected_style:
                errors.append(f"Relationship {relationship_id} has an incorrect UML edge style.")
            if relationship_type in CARDINALITY_RELATIONSHIP_TYPES:
                for suffix, field in (
                    ("source_multiplicity", "sourceMultiplicity"),
                    ("target_multiplicity", "targetMultiplicity"),
                ):
                    value = relationship.get(field)
                    if value is None:
                        continue
                    label = parsed.find(f".//mxCell[@id='{relationship_id}_{suffix}']")
                    if label is None or label.attrib.get("value") != str(value):
                        errors.append(
                            f"Relationship {relationship_id} is missing its {field} XML label."
                        )
    return {"valid": not errors, "errors": errors, "matchedRuleId": "VAL_XML_DRAWIO_001"}





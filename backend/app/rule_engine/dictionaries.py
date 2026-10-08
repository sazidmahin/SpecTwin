import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DICTIONARY_VERSION = "dict_v1"
DICTIONARY_DIR = Path(__file__).resolve().parents[1] / "dictionaries" / "v1"


@lru_cache
def load_dictionaries() -> dict[str, Any]:
    dictionaries: dict[str, Any] = {}
    for path in sorted(DICTIONARY_DIR.glob("*.json")):
        with path.open(encoding="utf-8-sig") as file:
            dictionaries[path.stem] = json.load(file)
    return dictionaries


def dictionary_names() -> list[str]:
    return sorted(load_dictionaries())


def get_dictionary(name: str) -> Any:
    dictionaries = load_dictionaries()
    if name not in dictionaries:
        raise KeyError(name)
    return dictionaries[name]


def reset_dictionary_cache() -> None:
    load_dictionaries.cache_clear()


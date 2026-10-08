"""Score the Class Modeler on the held-out cases: `python -m tests.unit.oop_eval [-v] [--blind | --precision]`."""

import sys

from app.rule_engine.oop_modeler import analyze_oop_text
from tests.unit.oop_eval_cases import CASES
from tests.unit.oop_eval_cases_blind import BLIND_CASES
from tests.unit.oop_eval_cases_precision import PRECISION_CASES


def precision_counts(case: dict, result: dict) -> tuple[int, int, list[str], list[str]]:
    """(correct classes, predicted classes, false classes, empty classes)."""
    expected = set(case["exact_classes"])
    predicted = {cls["name"] for cls in result["model"]["classes"]}
    empty = sorted(
        cls["name"]
        for cls in result["model"]["classes"]
        if not cls["attributes"] and not cls["methods"] and cls["stereotype"] != "interface"
    )
    return len(predicted & expected), len(predicted), sorted(predicted - expected), empty


def score_case(case: dict) -> tuple[int, int, list[str]]:
    result = analyze_oop_text(case["text"])
    classes = {cls["name"]: cls for cls in result["model"]["classes"]}
    rels = result["model"]["relationships"]
    enums = {item["name"]: item["literals"] for item in result["model"]["enums"]}
    checks: list[tuple[bool, str]] = []
    for name in case.get("classes", []):
        checks.append((name in classes, f"class {name}"))
    for name in case.get("not_classes", []):
        checks.append((name not in classes, f"not a class: {name}"))
    for owner, attrs in case.get("attributes", {}).items():
        have = {attr["name"] for attr in classes.get(owner, {}).get("attributes", [])}
        # an attribute inherited from a parent also counts
        for rel in rels:
            if rel["type"] == "inheritance" and rel["source"] == owner and rel["target"] in classes:
                have |= {attr["name"] for attr in classes[rel["target"]]["attributes"]}
        for attr in attrs:
            checks.append((attr in have, f"{owner}.{attr}"))
    for owner, methods in case.get("methods", {}).items():
        have = {method["name"] for method in classes.get(owner, {}).get("methods", [])}
        for method in methods:
            checks.append((method in have, f"{owner}.{method}()"))
    for name in case.get("exact_classes", []):
        checks.append((name in classes, f"class {name}"))
    for child, parent in case.get("inherits", []):
        ok = any(r["type"] == "inheritance" and r["source"] == child and r["target"] == parent for r in rels)
        checks.append((ok, f"{child} inherits {parent}"))
    for a, b in case.get("links", []):
        ok = any({r["source"], r["target"]} == {a, b} for r in rels)
        checks.append((ok, f"link {a}-{b}"))
    for source, target, mult in case.get("multiplicity", []):
        ok = any(r["source"] == source and r["target"] == target and r["targetMultiplicity"] == mult for r in rels)
        checks.append((ok, f"{source}->{target} [{mult}]"))
    for child, iface in case.get("realizes", []):
        ok = any(r["type"] == "realization" and r["source"] == child and r["target"] == iface for r in rels)
        checks.append((ok, f"{child} implements {iface}"))
    for name in case.get("interfaces", []):
        checks.append((classes.get(name, {}).get("stereotype") == "interface", f"«interface» {name}"))
    for name in case.get("abstract", []):
        checks.append((classes.get(name, {}).get("stereotype") == "abstract", f"«abstract» {name}"))
    for name, literals in case.get("enums", {}).items():
        checks.append((enums.get(name) == literals, f"enum {name}"))
    checks.append((result["validation"]["valid"], "valid draw.io"))
    failures = [label for ok, label in checks if not ok]
    return len(checks) - len(failures), len(checks), failures


def main() -> None:
    verbose = "-v" in sys.argv
    cases = BLIND_CASES if "--blind" in sys.argv else PRECISION_CASES if "--precision" in sys.argv else CASES
    total_ok = total = correct = predicted = 0
    for case in cases:
        ok, count, failures = score_case(case)
        total_ok += ok
        total += count
        line = f"{case['name']:<26} {ok:>3}/{count:<3} {100 * ok // count:>3}%"
        if "exact_classes" in case:
            hit, made, false_classes, empty = precision_counts(case, analyze_oop_text(case["text"]))
            correct += hit
            predicted += made
            line += f"   precision {hit}/{made}"
            if verbose and (false_classes or empty):
                failures = failures + [f"FALSE CLASS {name}" for name in false_classes] + [f"empty box {name}" for name in empty]
        print(line)
        if verbose:
            for failure in failures:
                print(f"      x {failure}")
    print(f"{'TOTAL':<26} {total_ok:>3}/{total:<3} {100 * total_ok // total:>3}%")
    if predicted:
        print(f"{'CLASS PRECISION':<26} {correct:>3}/{predicted:<3} {100 * correct // predicted:>3}%")


if __name__ == "__main__":
    main()

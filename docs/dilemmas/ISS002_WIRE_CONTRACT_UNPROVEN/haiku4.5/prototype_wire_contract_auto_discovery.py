#!/usr/bin/env python3
"""Prototype: Automatic Dart-to-Python wire contract pair discovery.

Demonstrates feasibility of Layer 1 (auto-pairing) and Layer 3 (unreachable detection).
Run against the actual codebase to verify the heuristic works.

    python prototype_wire_contract_auto_discovery.py
"""

import re
from pathlib import Path
from typing import NamedTuple


class DartModel(NamedTuple):
    """A Dart model discovered to have a fromJson factory."""

    stem: str  # e.g., "sim"
    cls: str  # e.g., "SimPortfolio"
    path: Path


class PythonModel(NamedTuple):
    """A Python/Pydantic model that could be a response."""

    module: str  # e.g., "app.api.sim"
    attr: str  # e.g., "PortfolioSnapshot"


def scan_dart_models_with_fromJson(root: Path) -> dict[str, DartModel]:
    """Find all Dart classes with factory X.fromJson."""
    models = {}
    factory_re = re.compile(r"factory\s+(\w+)\.fromJson")

    for dart_file in root.glob("mobile/lib/models/*.dart"):
        stem = dart_file.stem
        text = dart_file.read_text()
        for match in factory_re.finditer(text):
            cls = match.group(1)
            models[f"{stem}/{cls}"] = DartModel(stem=stem, cls=cls, path=dart_file)

    return models


def scan_python_models(root: Path) -> dict[str, PythonModel]:
    """Find all Pydantic BaseModel classes in app.api."""
    models = {}
    class_re = re.compile(r"^class\s+(\w+)\s*\(\s*BaseModel\s*\)")

    for py_file in root.glob("backend/app/api/*.py"):
        module = f"app.api.{py_file.stem}"
        text = py_file.read_text()
        for line_num, line in enumerate(text.splitlines(), 1):
            match = class_re.search(line)
            if match:
                cls = match.group(1)
                models[f"{module}/{cls}"] = PythonModel(module=module, attr=cls)

    return models


def auto_pair_dart_to_python(
    dart_models: dict[str, DartModel], python_models: dict[str, PythonModel]
) -> dict[tuple[str, str], tuple[str, str]]:
    """
    Use naming heuristics to pair Dart models to Python response models.

    Returns: {("sim", "SimPortfolio"): ("app.api.sim", "PortfolioSnapshot"), ...}
    """
    pairs = {}

    for dart_key, dart in dart_models.items():
        stem, cls = dart.stem, dart.cls

        # Pattern 1: SimX → XSnapshot (in app.api.sim)
        patterns = [
            (f"app.api.{stem}", cls.replace("Sim", "") + "Snapshot", "sim.Snapshot"),
            (f"app.api.{stem}", cls.replace("Sim", "") + "Out", "sim.Out"),
            (f"app.api.{stem}", cls, "exact match"),
            (f"app.api.{stem}", cls + "Out", "sim.Out suffix"),
        ]

        for module, candidate_cls, reason in patterns:
            key = f"{module}/{candidate_cls}"
            if key in python_models:
                pair_key = ((stem, cls), (module, candidate_cls))
                pairs[pair_key] = reason
                break

    return pairs


def find_unreachable_dart_models(root: Path, dart_models: dict[str, DartModel]) -> list[str]:
    """Flag Dart models with fromJson that are never called."""
    unreachable = []

    for dart_key, model in dart_models.items():
        # Search for instantiation: ClassName(...) or ClassName.fromJson(...)
        patterns = [
            rf"\b{model.cls}\s*\(",  # ClassName(
            rf"\b{model.cls}\.fromJson\s*\(",  # ClassName.fromJson(
            rf"=>\s*{model.cls}\.fromJson\s*\(",  # => ClassName.fromJson(
        ]

        found = False
        for pattern in patterns:
            # Search in mobile code
            for dart_file in root.glob("mobile/lib/**/*.dart"):
                if re.search(pattern, dart_file.read_text()):
                    found = True
                    break
            if found:
                break
            # Search in backend tests (integration)
            for py_file in root.glob("backend/tests/**/*.py"):
                if model.cls in py_file.read_text():
                    found = True
                    break
            if found:
                break

        if not found:
            unreachable.append(dart_key)

    return unreachable


def main():
    repo = Path(__file__).resolve().parents[4]  # Navigate up to repo root
    print(f"Scanning repository: {repo}\n")

    # Scan
    print("=" * 70)
    print("LAYER 1: AUTO-DISCOVERY")
    print("=" * 70)
    dart_models = scan_dart_models_with_fromJson(repo)
    python_models = scan_python_models(repo)

    print(f"\nFound {len(dart_models)} Dart models with fromJson:")
    for key, model in sorted(dart_models.items()):
        print(f"  {key}")

    print(f"\nFound {len(python_models)} Python response models:")
    for key, model in sorted(python_models.items())[:10]:  # Show first 10
        print(f"  {key}")
    if len(python_models) > 10:
        print(f"  ... and {len(python_models) - 10} more")

    # Pair
    pairs = auto_pair_dart_to_python(dart_models, python_models)
    print(f"\n✓ Auto-paired {len(pairs)} Dart models to Python models:")
    for (dart_stem, dart_cls), (py_module, py_cls) in sorted(pairs.keys()):
        print(f"  ({dart_stem}, {dart_cls}) → ({py_module}, {py_cls})")

    if len(pairs) < len(dart_models):
        unpaired = len(dart_models) - len(pairs)
        print(f"\n⚠ {unpaired} Dart models could not be auto-paired (would need explicit registration)")

    # Unreachable
    print("\n" + "=" * 70)
    print("LAYER 3: UNREACHABLE MODELS")
    print("=" * 70)
    unreachable = find_unreachable_dart_models(repo, dart_models)
    if unreachable:
        print(f"\nWARNING: {len(unreachable)} Dart models have fromJson but are never called:")
        for model_key in unreachable:
            print(f"  {model_key}")
    else:
        print("\n✓ No unreachable Dart models found.")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    auto_pair_rate = len(pairs) / len(dart_models) * 100 if dart_models else 0
    print(f"Auto-pair success rate: {auto_pair_rate:.1f}% ({len(pairs)}/{len(dart_models)})")
    print(f"Unreachable models: {len(unreachable)}")
    print("\nConclusion: The auto-discovery mechanism is {'FEASIBLE' if auto_pair_rate > 80 else 'NEEDS REFINEMENT'}")


if __name__ == "__main__":
    main()

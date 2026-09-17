"""C02 step 2 — extract each chatbot's code block, safety-check it, and gate it for look-ahead.

Reads every out/generated/pNN_<model>.json, extracts the single Python code block from
`follow_up_reply` verbatim into out/strategies/pNN_<model>.py, statically rejects anything that
imports outside numpy/pandas/stdlib math or that touches files/network/subprocess/eval/exec, then
gates each surviving strategy on real SPY daily bars: (a) it must run without error and return a
{-1,0,1}-valued Series aligned to bars.index (NaN->0 is allowed), and (b) a truncation test for
look-ahead at 5 cut dates spread through the sample. A first failure is sent back to the strategy's
own generator for one repair round (out/repairs/pNN_<model>_repair.json); a second failure excludes
the strategy. Results are written to out/gate_results.json.
"""

import ast
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.data import load_daily  # noqa: E402
from common.ask_chatbot import ask  # noqa: E402

C02 = Path(__file__).resolve().parents[1]
GENERATED = C02 / "out" / "generated"
STRATEGIES = C02 / "out" / "strategies"
REPAIRS = C02 / "out" / "repairs"
DEVIATIONS = C02 / "out" / "DEVIATIONS.md"

ALLOWED_IMPORTS = {"numpy", "pandas", "math"}
FORBIDDEN_NAMES = {"eval", "exec", "open", "__import__", "compile", "input"}
FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "requests", "urllib",
    "http", "ftplib", "telnetlib", "multiprocessing", "threading", "ctypes", "importlib",
}

TO_CODE = (
    "Now write exactly that strategy as a single Python function and nothing else: "
    "`def signal(bars: pandas.DataFrame) -> pandas.Series`. `bars` has a DatetimeIndex and float "
    "columns open, high, low, close, volume (daily bars). Return a Series aligned to bars.index "
    "holding the target position decided at the close of each bar: 1 = long, -1 = short, 0 = flat. "
    "The value for a bar may use only data up to and including that bar, never later rows. Handle "
    "any stop loss or profit target inside the function by tracking the entry price bar by bar. "
    "Use only numpy and pandas. Reply with one Python code block only."
)

CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code_block(reply: str) -> str | None:
    matches = CODE_BLOCK_RE.findall(reply)
    if not matches:
        return None
    return matches[0].strip() + "\n"


def static_safety_check(code: str) -> list[str]:
    problems = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in FORBIDDEN_MODULES or top not in ALLOWED_IMPORTS:
                    problems.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top in FORBIDDEN_MODULES or top not in ALLOWED_IMPORTS:
                problems.append(f"forbidden import: {node.module}")
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
            if name in FORBIDDEN_NAMES:
                problems.append(f"forbidden call: {name}")
    return problems


def load_strategy_fn(py_path: Path):
    namespace = {}
    code = py_path.read_text()
    exec(compile(code, str(py_path), "exec"), namespace)  # noqa: S102 -- sandboxed by static_safety_check above
    if "signal" not in namespace or not callable(namespace["signal"]):
        raise ValueError("no callable `signal` function defined")
    return namespace["signal"]


def validate_output(positions: pd.Series, bars: pd.DataFrame) -> tuple[bool, str, pd.Series]:
    if not isinstance(positions, pd.Series):
        return False, f"signal() returned {type(positions)}, not a Series", positions
    if len(positions) != len(bars) or not positions.index.equals(bars.index):
        try:
            positions = positions.reindex(bars.index)
        except Exception as exc:
            return False, f"could not align output to bars.index: {exc}", positions
    nan_count = int(positions.isna().sum())
    positions = positions.fillna(0.0)
    vals = positions.to_numpy(dtype=float)
    if not np.all(np.isin(vals, [-1.0, 0.0, 1.0])):
        bad = sorted(set(vals.tolist()) - {-1.0, 0.0, 1.0})
        return False, f"values outside {{-1,0,1}}: {bad[:5]}", positions
    note = f"{nan_count} NaN positions coerced to 0" if nan_count else ""
    return True, note, positions


def truncation_test(signal_fn, bars: pd.DataFrame, cut_dates: list) -> tuple[bool, str]:
    full = signal_fn(bars.copy())
    ok, _, full = validate_output(full, bars)
    if not ok:
        return False, "full-series run failed validation during truncation test"

    for cut in cut_dates:
        truncated_bars = bars.loc[:cut].copy()
        truncated = signal_fn(truncated_bars)
        ok, _, truncated = validate_output(truncated, truncated_bars)
        if not ok:
            return False, f"truncated run at {cut.date()} failed validation"

        full_slice = full.loc[:cut]
        if len(truncated) != len(full_slice):
            return False, f"length mismatch at cut {cut.date()}"
        mismatches = full_slice[full_slice.to_numpy() != truncated.to_numpy()]
        if len(mismatches) > 0:
            first_bad = mismatches.index[0]
            return False, f"look-ahead: positions differ from {first_bad.date()} onward (cut={cut.date()})"

    return True, "passed"


def run_gate(py_path: Path, bars: pd.DataFrame, cut_dates: list) -> dict:
    try:
        signal_fn = load_strategy_fn(py_path)
    except Exception as exc:
        return {"ran": False, "error": f"could not load signal(): {type(exc).__name__}: {exc}", "truncation_pass": False}

    try:
        positions = signal_fn(bars.copy())
    except Exception as exc:
        return {"ran": False, "error": f"{type(exc).__name__}: {exc}", "truncation_pass": False}

    ok, note, positions = validate_output(positions, bars)
    if not ok:
        return {"ran": True, "error": note, "truncation_pass": False}

    try:
        trunc_ok, trunc_msg = truncation_test(signal_fn, bars, cut_dates)
    except Exception as exc:
        return {"ran": True, "error": None, "nan_note": note,
                "truncation_pass": False, "truncation_msg": f"exception during truncation test: {type(exc).__name__}: {exc}"}

    return {
        "ran": True, "error": None, "nan_note": note,
        "truncation_pass": trunc_ok, "truncation_msg": trunc_msg,
    }


def attempt_repair(name: str, model: str, original_code: str, failure_msg: str, original_prompt: str) -> str | None:
    REPAIRS.mkdir(parents=True, exist_ok=True)
    repair_prompt = (
        f"Your earlier answer to this request:\n\n\"{original_prompt}\"\n\n"
        f"produced this Python function:\n\n```python\n{original_code}\n```\n\n"
        f"This function fails validation with: {failure_msg}\n\n"
        f"Please correct it. {TO_CODE}"
    )
    try:
        record = ask(model, repair_prompt, timeout=600)
    except Exception as exc:
        record = {"model_alias": model, "prompt": repair_prompt, "error": repr(exc)}
    record["name"] = name
    (REPAIRS / f"{name}_repair.json").write_text(json.dumps(record, indent=2))
    if "error" in record:
        return None
    return extract_code_block(record.get("reply", "") or "")


def main():
    STRATEGIES.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("loading SPY daily bars for gating...", flush=True)
    spy = load_daily(["SPY"], start="2005-01-01", end="2026-08-31")["SPY"]
    n = len(spy)
    cut_idx = [int(n * f) for f in (0.2, 0.4, 0.6, 0.8, 0.95)]
    cut_dates = [spy.index[i] for i in cut_idx]
    print(f"SPY bars: {n}, cut dates: {[d.date().isoformat() for d in cut_dates]}", flush=True)

    files = sorted(GENERATED.glob("p*_*.json"))
    deviations = []
    catalogue_gate = {}
    results = {"cut_dates": [d.date().isoformat() for d in cut_dates], "strategies": {}}

    counts = {"haiku": {"passed_first": 0, "repaired": 0, "excluded": 0},
              "sonnet": {"passed_first": 0, "repaired": 0, "excluded": 0},
              "opus": {"passed_first": 0, "repaired": 0, "excluded": 0}}

    for f in files:
        record = json.loads(f.read_text())
        name = record.get("name", f.stem)
        model = record.get("model_alias", "unknown")
        prompt = record.get("prompt", "")
        reply = record.get("follow_up_reply")

        entry = {"name": name, "model": model, "prompt": prompt}

        if "error" in record or not reply:
            entry["status"] = "excluded"
            entry["reason"] = "generation error or missing follow_up_reply"
            results["strategies"][name] = entry
            if model in counts:
                counts[model]["excluded"] += 1
            continue

        code = extract_code_block(reply)
        if code is None:
            entry["status"] = "excluded"
            entry["reason"] = "no python code block found in follow_up_reply"
            results["strategies"][name] = entry
            if model in counts:
                counts[model]["excluded"] += 1
            deviations.append(f"- `{name}`: no code block found in follow_up_reply; excluded.")
            continue

        py_path = STRATEGIES / f"{name}.py"
        py_path.write_text(code)

        problems = static_safety_check(code)
        if problems:
            entry["status"] = "excluded"
            entry["reason"] = f"failed static safety check: {problems}"
            results["strategies"][name] = entry
            if model in counts:
                counts[model]["excluded"] += 1
            deviations.append(f"- `{name}`: failed static safety check: {problems}; excluded, not executed.")
            continue

        gate1 = run_gate(py_path, spy, cut_dates)
        entry["gate_attempt_1"] = gate1

        passed1 = gate1.get("ran") and gate1.get("error") is None and gate1.get("truncation_pass")
        if passed1:
            entry["status"] = "passed_first"
            entry["strategy_path"] = str(py_path.relative_to(C02))
            if model in counts:
                counts[model]["passed_first"] += 1
            results["strategies"][name] = entry
            continue

        failure_msg = gate1.get("error") or gate1.get("truncation_msg") or "unknown failure"
        print(f"{name}: gate 1 failed ({failure_msg}); requesting repair...", flush=True)

        repaired_code = attempt_repair(name, model, code, failure_msg, prompt)
        if repaired_code is None:
            entry["status"] = "excluded"
            entry["reason"] = f"gate 1 failed ({failure_msg}); repair call errored or returned no code block"
            results["strategies"][name] = entry
            if model in counts:
                counts[model]["excluded"] += 1
            continue

        repaired_path = STRATEGIES / f"{name}.py"
        repaired_path.write_text(repaired_code)

        problems2 = static_safety_check(repaired_code)
        if problems2:
            entry["status"] = "excluded"
            entry["reason"] = f"repair failed static safety check: {problems2}"
            results["strategies"][name] = entry
            if model in counts:
                counts[model]["excluded"] += 1
            deviations.append(f"- `{name}`: repair attempt failed static safety check: {problems2}; excluded.")
            continue

        gate2 = run_gate(repaired_path, spy, cut_dates)
        entry["gate_attempt_2"] = gate2

        passed2 = gate2.get("ran") and gate2.get("error") is None and gate2.get("truncation_pass")
        if passed2:
            entry["status"] = "repaired"
            entry["strategy_path"] = str(repaired_path.relative_to(C02))
            if model in counts:
                counts[model]["repaired"] += 1
        else:
            entry["status"] = "excluded"
            entry["reason"] = (
                f"repair still failed: {gate2.get('error') or gate2.get('truncation_msg')}"
            )
            if model in counts:
                counts[model]["excluded"] += 1

        results["strategies"][name] = entry

    results["counts_by_model"] = counts
    results["wall_time_seconds"] = round(time.time() - t0, 1)
    (C02 / "out" / "gate_results.json").write_text(json.dumps(results, indent=2, default=str))

    if deviations:
        with open(DEVIATIONS, "a") as fh:
            fh.write("\n## 02_extract_and_gate.py\n\n")
            fh.write("\n".join(deviations) + "\n")

    total_passed = sum(c["passed_first"] + c["repaired"] for c in counts.values())
    total_excluded = sum(c["excluded"] for c in counts.values())
    print(f"\nDone in {results['wall_time_seconds']}s. Passed: {total_passed}, excluded: {total_excluded}")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()

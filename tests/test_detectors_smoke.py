#!/usr/bin/env python3
"""
Smoke tests for sample_detectors.

Usage:
    python tests/test_detectors_smoke.py /path/to/repo

This script:
- Calls each detector in src.detectors.sample_detectors
- Verifies the returned structure contains the expected keys and types
- Prints a concise summary for each detector
- Exits with non-zero status if any check fails
"""

import sys
import json
from typing import Any, Dict, List
from pathlib import Path

from src.detectors import sample_detectors
print("Starting detector smoke tests, PYTHONPATH:", __import__("sys").path[0])

REPO_PATH = sys.argv[1] if len(sys.argv) > 1 else "."

# Helper assertions
def assert_is_dict(obj: Any, name: str):
    if not isinstance(obj, dict):
        raise AssertionError(f"{name} did not return a dict (got {type(obj).__name__})")

def assert_list_of_str(lst: Any, name: str):
    if not isinstance(lst, list):
        raise AssertionError(f"{name} expected list, got {type(lst).__name__}")
    for i, v in enumerate(lst):
        if not isinstance(v, str):
            raise AssertionError(f"{name}[{i}] expected str, got {type(v).__name__}")

def safe_get(d: Dict, key: str, default=None):
    return d.get(key, default)

def check_git(repo_path: str):
    out = sample_detectors.detect_git_evidence(repo_path) or {}
    assert_is_dict(out, "detect_git_evidence")
    # expected keys
    commit_count = safe_get(out, "commit_count")
    commit_shas = safe_get(out, "commit_shas", [])
    recent_commits = safe_get(out, "recent_commits", [])

    if not isinstance(commit_count, int):
        raise AssertionError(f"detect_git_evidence.commit_count expected int, got {type(commit_count).__name__}")
    assert_list_of_str(commit_shas, "detect_git_evidence.commit_shas")
    assert_list_of_str(recent_commits, "detect_git_evidence.recent_commits")

    return {
        "commit_count": commit_count,
        "commit_shas": commit_shas[:5],
        "recent_commits": recent_commits[:5],
    }

def check_schema(repo_path: str):
    out = sample_detectors.detect_schema_files(repo_path) or {}
    assert_is_dict(out, "detect_schema_files")
    schema_files = safe_get(out, "schema_files", [])
    assert_list_of_str(schema_files, "detect_schema_files.schema_files")
    return {"schema_files": schema_files[:5]}

def check_diagrams(repo_path: str):
    out = sample_detectors.detect_diagrams(repo_path) or {}
    assert_is_dict(out, "detect_diagrams")
    diagram_count = safe_get(out, "diagram_count", 0)
    diagram_paths = safe_get(out, "diagram_paths", [])
    if not isinstance(diagram_count, int):
        raise AssertionError(f"detect_diagrams.diagram_count expected int, got {type(diagram_count).__name__}")
    assert_list_of_str(diagram_paths, "detect_diagrams.diagram_paths")
    return {"diagram_count": diagram_count, "diagram_paths": diagram_paths[:5]}

def check_orchestration(repo_path: str):
    out = sample_detectors.detect_orchestration(repo_path) or {}
    assert_is_dict(out, "detect_orchestration")
    orchestration = safe_get(out, "orchestration", {})
    if not isinstance(orchestration, dict):
        raise AssertionError(f"detect_orchestration.orchestration expected dict, got {type(orchestration).__name__}")
    uses_async = orchestration.get("uses_async")
    graph_files = orchestration.get("graph_files", [])
    if not isinstance(uses_async, bool):
        raise AssertionError(f"detect_orchestration.orchestration.uses_async expected bool, got {type(uses_async).__name__}")
    assert_list_of_str(graph_files, "detect_orchestration.orchestration.graph_files")
    return {"uses_async": uses_async, "graph_files": graph_files[:5]}

def check_docs(repo_path: str):
    out = sample_detectors.detect_docs_and_examples(repo_path) or {}
    assert_is_dict(out, "detect_docs_and_examples")
    docs = safe_get(out, "docs", [])
    assert_list_of_str(docs, "detect_docs_and_examples.docs")
    return {"docs": docs[:5]}

def check_hosts(repo_path: str):
    out = sample_detectors.detect_hosts(repo_path) or {}
    assert_is_dict(out, "detect_hosts")
    hosts = safe_get(out, "hosts", [])
    assert_list_of_str(hosts, "detect_hosts.hosts")
    return {"hosts": hosts[:5]}

def run_all(repo_path: str):
    repo = Path(repo_path)
    if not repo.exists():
        raise SystemExit(f"Repository path does not exist: {repo_path}")

    summary = {}
    failures: List[str] = []

    detectors = [
        ("git", check_git),
        ("schema", check_schema),
        ("diagrams", check_diagrams),
        ("orchestration", check_orchestration),
        ("docs", check_docs),
        ("hosts", check_hosts),
    ]

    for name, fn in detectors:
        try:
            result = fn(repo_path)
            summary[name] = result
            print(f"[OK] {name}: {json.dumps(result, ensure_ascii=False)}")
        except AssertionError as e:
            failures.append(f"{name}: {e}")
            print(f"[FAIL] {name}: {e}")
        except Exception as e:
            failures.append(f"{name}: unexpected error: {e}")
            print(f"[ERROR] {name}: unexpected error: {e}")

    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if failures:
        print("\nFailures:")
        for f in failures:
            print(" -", f)
        raise SystemExit(2)

    print("\nAll detectors returned expected shapes. If evidence lists are empty, run detectors manually to inspect repository contents.")

if __name__ == "__main__":
    try:
        run_all(REPO_PATH)
    except SystemExit as e:
        code = int(e.code) if isinstance(e.code, int) else 1
        sys.exit(code)
    except Exception as e:
        print("Unexpected error during smoke tests:", e)
        sys.exit(1)

"""
src/detectors/sample_detectors.py

Improved sample detectors that return consistent, well-typed dictionaries.
Detectors:
 - always return lists (never None)
 - ignore virtualenvs, caches, site-packages, and generated audit outputs
 - broaden detection for schemas, diagrams, and orchestration frameworks
 - avoid false positives by checking context before marking files as evidence
"""

import os
import subprocess
from typing import Dict, List, Any
from pathlib import Path


# Helper to detect ignored directories robustly
def _is_ignored_dir(root: str) -> bool:
    parts = Path(os.path.normpath(root)).parts
    ignore = {".venv", ".pytest_cache", "site-packages", "venv", "__pycache__", "dist", "build"}
    return any(p.lower() in ignore or p.lower().startswith(".venv") for p in parts)


def detect_git_evidence(repo_path: str) -> Dict[str, Any]:
    """
    Returns:
      {
        "commit_count": int,
        "commit_shas": [str],
        "recent_commits": [str]
      }
    """
    commit_shas: List[str] = []
    recent_commits: List[str] = []
    commit_count = 0

    try:
        git_dir = os.path.join(repo_path, ".git")
        if os.path.isdir(git_dir):
            p = subprocess.run(
                ["git", "-C", repo_path, "rev-list", "--all", "--count"],
                capture_output=True,
                text=True,
                check=False,
            )
            if p.returncode == 0 and p.stdout.strip().isdigit():
                commit_count = int(p.stdout.strip())

            p2 = subprocess.run(
                ["git", "-C", repo_path, "rev-list", "--all", "--max-count=50"],
                capture_output=True,
                text=True,
                check=False,
            )
            if p2.returncode == 0:
                commit_shas = [s.strip() for s in p2.stdout.splitlines() if s.strip()][:50]

            p3 = subprocess.run(
                ["git", "-C", repo_path, "log", "--pretty=%s", "-n", "5"],
                capture_output=True,
                text=True,
                check=False,
            )
            if p3.returncode == 0:
                recent_commits = [s.strip() for s in p3.stdout.splitlines() if s.strip()][:5]
    except Exception:
        # best-effort fallback: inspect .git/refs
        try:
            refs_dir = os.path.join(repo_path, ".git", "refs")
            if os.path.isdir(refs_dir):
                for root, _, files in os.walk(refs_dir):
                    for f in files:
                        path = os.path.join(root, f)
                        try:
                            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                                sha = fh.read().strip()
                                if sha:
                                    commit_shas.append(sha)
                        except Exception:
                            continue
                commit_shas = commit_shas[:50]
                commit_count = len(commit_shas)
        except Exception:
            commit_count = 0

    return {
        "commit_count": int(commit_count or 0),
        "commit_shas": [str(s) for s in commit_shas],
        "recent_commits": [str(s) for s in recent_commits],
    }


def detect_schema_files(repo_path: str) -> Dict[str, Any]:
    """
    Look for common schema file names and extensions and references in package files.
    Returns:
      { "schema_files": [path_str] }
    """
    schema_files: List[str] = []
    try:
        for root, _, files in os.walk(repo_path):
            if _is_ignored_dir(root):
                continue
            for f in files:
                lf = f.lower()
                if lf.endswith((".schema.json", ".schema", ".avsc", ".proto", ".jsonschema")) or lf == "schema.json":
                    schema_files.append(os.path.relpath(os.path.join(root, f), repo_path))
                elif lf.endswith(".json"):
                    # heuristic: JSON files in schemas/ or with "schema" in name
                    if "schema" in lf or "schemas" in root.lower():
                        schema_files.append(os.path.relpath(os.path.join(root, f), repo_path))

        # Inspect package.json and pyproject.toml for schema/openapi hints
        for candidate in ("package.json", "pyproject.toml"):
            p = os.path.join(repo_path, candidate)
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read(64 * 1024)
                        if "schema" in content.lower() or "openapi" in content.lower():
                            rel = os.path.relpath(p, repo_path)
                            if rel not in schema_files:
                                schema_files.append(rel)
                except Exception:
                    pass

        # also check for schemas/ directory
        schemas_dir = os.path.join(repo_path, "schemas")
        if os.path.isdir(schemas_dir):
            for root, _, files in os.walk(schemas_dir):
                for f in files:
                    schema_files.append(os.path.relpath(os.path.join(root, f), repo_path))

        schema_files = list(dict.fromkeys(schema_files))[:50]
    except Exception:
        schema_files = []
    return {"schema_files": [str(p) for p in schema_files]}


def detect_diagrams(repo_path: str) -> Dict[str, Any]:
    """
    Detect diagram files (drawio, PlantUML, .puml, .png/.svg in docs/diagrams, mermaid files).
    Returns:
      { "diagram_count": int, "diagram_paths": [path_str] }
    """
    diagram_paths: List[str] = []
    try:
        for root, _, files in os.walk(repo_path):
            # skip virtualenvs, caches, site-packages, and generated audit outputs
            rel_root = os.path.relpath(root, repo_path).replace("\\", "/")
            if rel_root.startswith("audit/") or rel_root.startswith("build/") or rel_root.startswith("dist/"):
                continue
            if _is_ignored_dir(root):
                continue

            for f in files:
                lf = f.lower()
                # direct diagram file types
                if lf.endswith((".drawio", ".drawio.svg", ".mmd", ".mermaid", ".puml", ".plantuml")):
                    diagram_paths.append(os.path.relpath(os.path.join(root, f), repo_path))
                    continue

                # images in docs/diagrams or docs folders
                if lf.endswith((".svg", ".png", ".jpg", ".jpeg")):
                    if "diagram" in root.lower() or "diagrams" in root.lower() or "docs" in root.lower():
                        diagram_paths.append(os.path.relpath(os.path.join(root, f), repo_path))
                    continue

                # markdown heuristics: include only if explicit image/diagram references exist
                if lf.endswith(".md"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                            txt = fh.read(16 * 1024).lower()
                            # require explicit image or diagram keywords
                            if any(k in txt for k in (".svg", ".png", ".drawio", "mermaid", "plantuml", "```mermaid")):
                                diagram_paths.append(os.path.relpath(path, repo_path))
                    except Exception:
                        pass

        diagram_paths = list(dict.fromkeys(diagram_paths))[:50]
    except Exception:
        diagram_paths = []
    return {"diagram_count": int(len(diagram_paths)), "diagram_paths": [str(p) for p in diagram_paths]}


def detect_orchestration(repo_path: str) -> Dict[str, Any]:
    """
    Detect orchestration artifacts: presence of graph files, async usage hints, and known frameworks.
    Returns:
      { "orchestration": {"uses_async": bool, "graph_files": [path_str]} }
    """
    graph_files: List[str] = []
    uses_async = False
    try:
        orchestration_indicators = ("dags", "airflow", "prefect", "dagster", "luigi", "pipeline", "pipelines", "flows")
        for root, _, files in os.walk(repo_path):
            if _is_ignored_dir(root):
                continue

            # detect framework folders (e.g., dags/)
            parts = Path(os.path.normpath(root)).parts
            if any(any(ind in p.lower() for ind in orchestration_indicators) for p in parts):
                graph_files.append(os.path.relpath(root, repo_path))

            for f in files:
                lf = f.lower()
                # explicit graph files
                if lf.endswith((".graph", ".dot", ".dag")) or "dag" in lf:
                    graph_files.append(os.path.relpath(os.path.join(root, f), repo_path))
                    continue

                # Python files: only mark as orchestration evidence if they import frameworks and are in likely folders
                if lf.endswith(".py"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                            content = fh.read(200 * 1024)
                            lower = content.lower()
                            framework_hit = any(k in lower for k in ("airflow", "prefect", "dagster", "luigi"))
                            in_orch_folder = any(part.lower() in ("dags", "orchestration", "pipelines", "flows") for part in Path(root).parts)
                            if framework_hit and (in_orch_folder or "dag" in f.lower()):
                                graph_files.append(os.path.relpath(path, repo_path))
                            if "async def" in content or "await " in content:
                                uses_async = True
                    except Exception:
                        continue

        graph_files = list(dict.fromkeys(graph_files))[:50]
    except Exception:
        graph_files = []
    return {"orchestration": {"uses_async": bool(uses_async), "graph_files": [str(p) for p in graph_files]}}


def detect_docs_and_examples(repo_path: str) -> Dict[str, Any]:
    """
    Detect README, docs/, examples/ folders and common docs files.
    Returns:
      { "docs": [path_str] }
    """
    docs: List[str] = []
    try:
        for root, _, files in os.walk(repo_path):
            if _is_ignored_dir(root):
                continue
            rel_root = os.path.relpath(root, repo_path).replace("\\", "/")
            if rel_root.startswith("audit/") or rel_root.startswith("build/") or rel_root.startswith("dist/"):
                continue
            for f in files:
                lf = f.lower()
                if lf in ("readme.md", "readme.rst", "readme.txt") or "docs" in root.lower() or "example" in root.lower():
                    docs.append(os.path.relpath(os.path.join(root, f), repo_path))
        for candidate in ("README.md", "README.rst", "README.txt"):
            p = os.path.join(repo_path, candidate)
            if os.path.isfile(p) and os.path.relpath(p, repo_path) not in docs:
                docs.insert(0, os.path.relpath(p, repo_path))
        docs = list(dict.fromkeys(docs))[:50]
    except Exception:
        docs = []
    return {"docs": [str(p) for p in docs]}


def detect_hosts(repo_path: str) -> Dict[str, Any]:
    """
    Detect host-related artifacts (hosts files, inventory, hosts.yaml, .env with HOST entries).
    Returns:
      { "hosts": [host_identifier] }
    """
    hosts: List[str] = []
    try:
        for root, _, files in os.walk(repo_path):
            if _is_ignored_dir(root):
                continue
            rel_root = os.path.relpath(root, repo_path).replace("\\", "/")
            if rel_root.startswith("audit/") or rel_root.startswith("build/") or rel_root.startswith("dist/"):
                continue
            for f in files:
                lf = f.lower()
                if lf in ("hosts", "hosts.txt", "hosts.yaml", "hosts.yml", "inventory", "inventory.ini"):
                    hosts.append(os.path.relpath(os.path.join(root, f), repo_path))
                elif lf.endswith(".env"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                            for line in fh:
                                if "HOST=" in line.upper() or "HOSTNAME=" in line.upper():
                                    hosts.append(f"{os.path.relpath(path, repo_path)}:{line.strip()}")
                                    break
                    except Exception:
                        continue
        hosts = list(dict.fromkeys(hosts))[:50]
    except Exception:
        hosts = []
    return {"hosts": [str(h) for h in hosts]}

def collect_all_evidence(repo_path: str) -> dict:
    """
    Convenience wrapper that runs all detectors and returns a single dict.
    Kept minimal and stable so callers (like src.graph) can rely on it.
    """
    try:
        git = detect_git_evidence(repo_path) or {}
    except Exception:
        git = {"commit_count": 0, "commit_shas": [], "recent_commits": []}

    try:
        schema = detect_schema_files(repo_path) or {}
    except Exception:
        schema = {"schema_files": []}

    try:
        diagrams = detect_diagrams(repo_path) or {}
    except Exception:
        diagrams = {"diagram_count": 0, "diagram_paths": []}

    try:
        orchestration = detect_orchestration(repo_path) or {}
    except Exception:
        orchestration = {"orchestration": {"uses_async": False, "graph_files": []}}

    try:
        docs = detect_docs_and_examples(repo_path) or {}
    except Exception:
        docs = {"docs": []}

    try:
        hosts = detect_hosts(repo_path) or {}
    except Exception:
        hosts = {"hosts": []}

    return {
        "git": git,
        "schema": schema,
        "diagrams": diagrams,
        "orchestration": orchestration,
        "docs": docs,
        "hosts": hosts,
    }

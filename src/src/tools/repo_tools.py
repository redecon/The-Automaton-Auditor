
import tempfile
import subprocess
import os
import ast

import subprocess
import tempfile
import os
from src.state import Evidence

def clone_repo(repo_url: str) -> str:
    """Clone a repo into a sandboxed temp directory and return path."""
    try:
        temp_dir = tempfile.TemporaryDirectory()
        repo_path = os.path.join(temp_dir.name, "repo")

        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, repo_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return repo_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git clone failed: {e.stderr.decode()}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error cloning repo: {e}")


def extract_git_history(repo_path: str) -> list:
    """Return commit history as list of (hash, message, timestamp)."""
    result = subprocess.run(
        ["git", "-C", repo_path, "log", "--oneline", "--reverse", "--pretty=format:%h|%s|%cd"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    commits = []
    for line in result.stdout.decode().splitlines():
        parts = line.split("|")
        if len(parts) == 3:
            commits.append({"hash": parts[0], "message": parts[1], "timestamp": parts[2]})
    return commits

def analyze_graph_structure(file_path: str) -> dict:
    """Parse Python file AST to check for StateGraph and parallel add_edge calls."""
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=file_path)

    graph_found = False
    parallel_edges = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_edge":
                parallel_edges = True
        if isinstance(node, ast.Name) and node.id == "StateGraph":
            graph_found = True

    return {"graph_found": graph_found, "parallel_edges": parallel_edges}

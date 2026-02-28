# src/nodes/detectives.py
import os
import re
from src.detectors.sample_detectors import detect_git_evidence
from src.state import AgentState, Evidence
from src.tools import repo_tools, doc_tools, vision_tools
import ast

# --- Git Forensic Analysis ---
def git_forensic_analysis(state: AgentState, dimension: dict) -> AgentState:
    """
    Run the git forensic detector and ensure the evidence payload is structured.
    """
    repo_path = getattr(state, "repo_path", ".")
    try:
        raw_result = detect_git_evidence(repo_path)
    except Exception as e:
        raw_result = str(e)

    # If detector returned a string (legacy behavior), convert to structured dict
    if isinstance(raw_result, str):
        content = {
            "commits": [],
            "signed_commits": 0,
            "commit_count": 0,
            "recent_activity_days": None,
            "error": raw_result,
        }
    # If detector returned None, convert to structured error
    elif raw_result is None:
        content = {
            "commits": [],
            "signed_commits": 0,
            "commit_count": 0,
            "recent_activity_days": None,
            "error": "detector returned None",
        }
    # If detector returned a dict, trust it but ensure required keys exist
    elif isinstance(raw_result, dict):
        content = dict(raw_result)  # shallow copy
        # ensure canonical keys exist
        content.setdefault("commits", [])
        content.setdefault("signed_commits", 0)
        content.setdefault("commit_count", len(content["commits"]) if isinstance(content["commits"], list) else 0)
        content.setdefault("recent_activity_days", None)
        content.setdefault("error", None)
    else:
        # fallback for unexpected types
        content = {
            "commits": [],
            "signed_commits": 0,
            "commit_count": 0,
            "recent_activity_days": None,
            "error": f"unexpected detector return type: {type(raw_result).__name__}",
        }

    evidence = Evidence(
        goal=dimension.get("name", "Git Forensic Analysis"),
        found=bool(content.get("commits")),
        content=content,
        location="git_forensic_analysis",
        rationale=dimension.get("success_pattern", "Collected commit metadata and provenance signals")
        if content.get("commits")
        else dimension.get("failure_pattern", "No commits found or error"),
        confidence=0.9 if content.get("commits") else 0.3,
    )

    state.evidences.setdefault("git_forensic_analysis", []).append(evidence)

    return state

# --- Document analysis (compatibility wrapper) ---
def doc_analyst(state: AgentState, dimension: dict) -> AgentState:
    """
    Minimal doc analysis: check for README, docs/, and examples.
    Returns structured Evidence so graph imports remain stable.
    """
    try:
        found_files = []
        for candidate in ("README.md", "README.rst", "docs", "examples"):
            if os.path.exists(candidate):
                found_files.append(candidate)
        found = len(found_files) > 0
        rationale = dimension.get("success_pattern") if found else dimension.get("failure_pattern")
        content = {"found_files": found_files, "summary": f"Found {len(found_files)} doc artifacts"}
        evidence = Evidence(
            goal=dimension.get("name", "Documentation Analysis"),
            found=found,
            content=content,
            location="doc_analyst",
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
    except Exception as e:
        evidence = Evidence(
            goal=dimension.get("name", "Documentation Analysis"),
            found=False,
            content={"error": str(e)},
            location="doc_analyst",
            rationale="Error scanning docs",
            confidence=0.3,
        )
    state.evidences.setdefault(dimension["id"], []).append(evidence)
    return state

# --- Diagram flow analysis (compatibility wrapper) ---
def diagram_flow(state: AgentState, dimension: dict) -> AgentState:
    """
    Minimal diagram flow check: look for common diagram files and simple flow markers.
    """
    try:
        diagram_files = []
        for root, _, files in os.walk("."):
            for f in files:
                if f.lower().endswith((".drawio", ".svg", ".png", ".jpg", ".jpeg", ".pdf")):
                    diagram_files.append(os.path.relpath(os.path.join(root, f), "."))
        found = len(diagram_files) > 0
        rationale = dimension.get("success_pattern") if found else dimension.get("failure_pattern")
        content = {"diagram_files": diagram_files, "summary": f"Found {len(diagram_files)} diagram files"}
        evidence = Evidence(
            goal=dimension.get("name", "Diagram Flow Analysis"),
            found=found,
            content=content,
            location="diagram_flow",
            rationale=rationale,
            confidence=0.9 if found else 0.3,
        )
    except Exception as e:
        evidence = Evidence(
            goal=dimension.get("name", "Diagram Flow Analysis"),
            found=False,
            content={"error": str(e)},
            location="diagram_flow",
            rationale="Error scanning for diagrams",
            confidence=0.3,
        )
    state.evidences.setdefault(dimension["id"], []).append(evidence)
    return state

# --- Host Analysis Accuracy ---
def host_analysis_accuracy(state: AgentState, dimension: dict) -> AgentState:
    try:
        chunks = doc_tools.ingest_pdf(getattr(state, "pdf_path", ""), chunk_size=500)
        text = " ".join(chunks)
        file_refs = re.findall(r"[A-Za-z0-9_/\\.-]+\.(py|md|pdf|json)", text)

        actual_files = []
        for root, _, files in os.walk("."):
            for f in files:
                actual_files.append(os.path.relpath(os.path.join(root, f), "."))

        missing = [ref for ref in file_refs if ref not in actual_files]
        found = len(missing) == 0
        rationale = dimension.get("success_pattern") if found else dimension.get("failure_pattern")

        evidence = Evidence(
            goal=dimension.get("name", "Host Analysis Accuracy"),
            found=found,
            content={"references": file_refs, "missing": missing},
            location="host_analysis_accuracy",
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
    except Exception as e:
        evidence = Evidence(
            goal=dimension.get("name", "Host Analysis Accuracy"),
            found=False,
            content={"error": str(e)},
            location="host_analysis_accuracy",
            rationale="Error parsing PDF or repo",
            confidence=0.3,
        )
    state.evidences.setdefault(dimension["id"], []).append(evidence)
    return state

# --- State Management Rigor ---
def state_management_rigor(state: AgentState, dimension: dict) -> AgentState:
    try:
        with open("src/state.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = "BaseModel" in content and "TypedDict" in content
        rationale = dimension.get("success_pattern") if found else dimension.get("failure_pattern")

        evidence = Evidence(
            goal=dimension.get("name", "State Management Rigor"),
            found=found,
            content="Checked for BaseModel and TypedDict usage",
            location="src/state.py",
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
    except Exception as e:
        evidence = Evidence(
            goal=dimension.get("name", "State Management Rigor"),
            found=False,
            content={"error": str(e)},
            location="src/state.py",
            rationale="Error reading state.py",
            confidence=0.3,
        )
    state.evidences.setdefault(dimension["id"], []).append(evidence)
    return state

# --- Graph Orchestration ---
def graph_orchestration(state: AgentState, dimension: dict) -> AgentState:
    try:
        with open("src/graph.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = "StateGraph" in content and "add_edge" in content
        rationale = dimension.get("success_pattern") if found else dimension.get("failure_pattern")

        evidence = Evidence(
            goal=dimension.get("name", "Graph Orchestration"),
            found=found,
            content="Checked for StateGraph orchestration",
            location="src/graph.py",
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
    except Exception as e:
        evidence = Evidence(
            goal=dimension.get("name", "Graph Orchestration"),
            found=False,
            content={"error": str(e)},
            location="src/graph.py",
            rationale="Error reading graph.py",
            confidence=0.3,
        )
    state.evidences.setdefault(dimension["id"], []).append(evidence)
    return state

# --- Safe Tool Engineering ---
def safe_tool_engineering(state: AgentState, dimension: dict) -> AgentState:
    try:
        with open("src/tools/repo_tools.py", "r", encoding="utf-8") as f:
            content = f.read()
        found = "subprocess.run" in content and "check=True" in content
        rationale = dimension.get("success_pattern") if found else dimension.get("failure_pattern")

        evidence = Evidence(
            goal=dimension.get("name", "Safe Tool Engineering"),
            found=found,
            content="Checked for safe subprocess usage",
            location="src/tools/repo_tools.py",
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
    except Exception as e:
        evidence = Evidence(
            goal=dimension.get("name", "Safe Tool Engineering"),
            found=False,
            content={"error": str(e)},
            location="src/tools/repo_tools.py",
            rationale="Error reading repo_tools.py",
            confidence=0.3,
        )
    state.evidences.setdefault(dimension["id"], []).append(evidence)
    return state

# --- Structured Output Enforcement ---
def structured_output(state: AgentState, dimension: dict) -> AgentState:
    files = ["src/state.py", "src/nodes/justice.py"]
    try:
        found = True
        for file in files:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
                if "BaseModel" not in content and "Evidence" not in content:
                    found = False
        rationale = dimension.get("success_pattern") if found else dimension.get("failure_pattern")

        evidence = Evidence(
            goal=dimension.get("name", "Structured Output Enforcement"),
            found=found,
            content="Checked for structured Evidence output",
            location="structured_output",
            rationale=rationale,
            confidence=0.9 if found else 0.5,
        )
    except Exception as e:
        evidence = Evidence(
            goal=dimension.get("name", "Structured Output Enforcement"),
            found=False,
            content={"error": str(e)},
            location="structured_output",
            rationale="Error reading files",
            confidence=0.3,
        )
    state.evidences.setdefault(dimension["id"], []).append(evidence)
    return state
